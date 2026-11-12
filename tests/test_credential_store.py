import pytest

from credential_store import CredentialStore


@pytest.fixture
def store():
    return CredentialStore({
        "customer.username": "SYNTHETIC_USER_123",
        "customer.password": "SYNTHETIC_PASSWORD_456",
    })


def test_resolves_exact_placeholder_only(store):
    assert store.resolve_fill("{{customer.password}}") == "SYNTHETIC_PASSWORD_456"
    assert store.resolve_fill("ordinary text") == "ordinary text"
    assert store.resolve_fill("") == ""


@pytest.mark.parametrize("value", [
    "{{missing.password}}",
    "prefix {{customer.password}}",
    "{{customer.token}}",
    "{{broken",
])
def test_rejects_unknown_or_embedded_placeholders(store, value):
    with pytest.raises(ValueError):
        store.resolve_fill(value)


def test_redacts_nested_values_without_mutating_source(store):
    source = {
        "text": "User SYNTHETIC_USER_123",
        "history": [{"value": "SYNTHETIC_PASSWORD_456"}],
        "steps": 2,
    }
    redacted = store.redact(source)
    assert redacted["text"] == "User [REDACTED]"
    assert redacted["history"][0]["value"] == "[REDACTED]"
    assert redacted["steps"] == 2
    assert source["history"][0]["value"] == "SYNTHETIC_PASSWORD_456"
    assert "SYNTHETIC" not in repr(store)


@pytest.mark.parametrize("values", [
    [],
    {"customer.password": ""},
    {"customer.password": " "},
    {"customer.password": 42},
    {"customer.token": "synthetic"},
    {"customer.password": "{{other.password}}"},
])
def test_rejects_invalid_entries_without_echoing_values(values):
    with pytest.raises(ValueError) as caught:
        CredentialStore(values)
    assert "synthetic" not in str(caught.value)


def test_overlapping_values_redact_longest_first():
    store = CredentialStore({
        "customer.username": "SYNTH",
        "customer.password": "SYNTH_LONG",
    })
    assert store.redact("SYNTH_LONG SYNTH") == "[REDACTED] [REDACTED]"


def test_loads_synthetic_json_with_environment_override(tmp_path):
    from credential_store import load_credentials

    path = tmp_path / "synthetic.json"
    path.write_text('{"customer.username":"FILE_USER","customer.password":"FILE_PASS"}')
    store = load_credentials(path, environ={
        "CLOUDQA_CUSTOMER_PASSWORD": "ENV_PASS",
    })
    assert store.resolve_fill("{{customer.username}}") == "FILE_USER"
    assert store.resolve_fill("{{customer.password}}") == "ENV_PASS"
    assert store.redact("FILE_USER ENV_PASS") == "[REDACTED] [REDACTED]"


def test_environment_only_and_empty_configuration():
    from credential_store import load_credentials

    store = load_credentials(environ={"CLOUDQA_CUSTOMER_USERNAME": "ENV_USER"})
    assert store.resolve_fill("{{customer.username}}") == "ENV_USER"
    assert load_credentials(environ={}).resolve_fill("plain") == "plain"


@pytest.mark.parametrize("content", [
    "{",
    "[]",
    '{"customer.password":42}',
    '{"customer.password":""}',
])
def test_invalid_credential_file_is_sanitized(tmp_path, content):
    from credential_store import load_credentials

    path = tmp_path / "synthetic.json"
    path.write_text(content)
    with pytest.raises(ValueError):
        load_credentials(path, environ={})


def test_missing_explicit_credential_file_fails_safely(tmp_path):
    from credential_store import load_credentials

    with pytest.raises(ValueError, match="Cannot read or parse"):
        load_credentials(tmp_path / "missing.json", environ={})


@pytest.mark.parametrize("url", [
    "http://example.com/login",
    "https://other.example/login",
    "https://example.com:444/login",
    "https://example.com.evil.test/login",
    "https://user:pass@example.com/login",
    None,
])
def test_bound_credentials_reject_other_origins(url):
    store = CredentialStore(
        {"customer.password": "SYNTHETIC_BOUND"},
        allowed_origin="https://example.com/start",
    )
    with pytest.raises(ValueError):
        store.resolve_fill("{{customer.password}}", url=url)


def test_bound_credentials_accept_same_origin_and_default_port():
    store = CredentialStore(
        {"customer.password": "SYNTHETIC_BOUND"},
        allowed_origin="https://example.com/start",
    )
    assert store.resolve_fill(
        "{{customer.password}}", url="https://EXAMPLE.com:443/login",
    ) == "SYNTHETIC_BOUND"


@pytest.mark.parametrize("fields", [
    {"action": "goto", "value": "https://example.com/{{customer.password}}"},
    {"action": "select", "element": 1, "value": "{{customer.password}}"},
    {"action": "press", "element": 1, "value": "{{customer.password}}"},
])
def test_action_rejects_placeholders_outside_fill(fields):
    from actions import Action

    with pytest.raises(ValueError):
        Action(reason="Synthetic policy check", **fields)
