import json
import sys
from unittest.mock import Mock

import pytest

import main as cli
from report import write_report


@pytest.mark.parametrize("arguments", [
    ["--url", "ftp://example.com", "--test", "Check"],
    ["--url", "https://example.com", "--test", " "],
    ["--url", "https://example.com"],
    ["--url", "https://example.com", "--test", "Check", "--test-file", "x.txt"],
    ["--url", "https://example.com:invalid", "--test", "Check"],
    ["--url", "https://user:password@example.com", "--test", "Check"],
])
def test_invalid_cli_stops_before_client(arguments, monkeypatch):
    client = Mock()
    monkeypatch.setattr(cli.genai, "Client", client)
    monkeypatch.setattr(sys, "argv", ["main.py", *arguments])
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 2
    client.assert_not_called()


@pytest.mark.parametrize("suffix,content", [
    (".txt", "Verify Welcome"),
    (".json", '{"test":"Verify Welcome"}'),
])
def test_test_file_loads_without_network(tmp_path, monkeypatch, suffix, content):
    path = tmp_path / ("case" + suffix)
    path.write_text(content)
    destination = tmp_path / "report.json"
    client = Mock(side_effect=RuntimeError("PRIVATE_MARKER"))
    monkeypatch.setattr(cli.genai, "Client", client)
    monkeypatch.setattr(cli, "load_dotenv", Mock())
    monkeypatch.setattr(sys, "argv", [
        "main.py", "--url", "https://example.com",
        "--test-file", str(path), "--report", str(destination),
    ])

    assert cli.main() == 1
    client.assert_called_once()
    report = json.loads(destination.read_text())
    assert report["verdict"] == "fail"
    assert "PRIVATE_MARKER" not in destination.read_text()


@pytest.mark.parametrize("suffix,content", [
    (".json", "{"),
    (".json", '["Verify Welcome"]'),
    (".json", '{"test":42}'),
    (".json", '{"test":"Check","extra":true}'),
    (".txt", " "),
    (".csv", "Verify Welcome"),
])
def test_invalid_test_files(tmp_path, monkeypatch, suffix, content):
    path = tmp_path / ("case" + suffix)
    path.write_text(content)
    client = Mock()
    monkeypatch.setattr(cli.genai, "Client", client)
    monkeypatch.setattr(sys, "argv", [
        "main.py", "--url", "https://example.com", "--test-file", str(path),
    ])
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 2
    client.assert_not_called()


def test_report_round_trip(tmp_path, capsys):
    result = {
        "verdict": "pass",
        "reason": "Verified fixture",
        "steps": 1,
        "elapsed_seconds": 0.1,
        "history": [],
    }
    destination = tmp_path / "nested" / "result.json"
    write_report(result, str(destination))
    assert json.loads(destination.read_text()) == result
    assert "VERDICT: PASS" in capsys.readouterr().out


@pytest.mark.parametrize("mode", ["file", "environment"])
def test_credential_cli_passes_bound_store_and_redacted_test(
    tmp_path, monkeypatch, mode
):
    from unittest.mock import MagicMock

    secret = "SYNTHETIC_CLI_PASSWORD_123"
    destination = tmp_path / "result.json"
    monkeypatch.setattr(cli, "load_dotenv", Mock())
    monkeypatch.delenv("CLOUDQA_CUSTOMER_USERNAME", raising=False)
    monkeypatch.delenv("CLOUDQA_CUSTOMER_PASSWORD", raising=False)

    if mode == "file":
        path = tmp_path / "synthetic.json"
        path.write_text(json.dumps({"customer.password": secret}))
        flags = ["--credentials", str(path)]
    else:
        monkeypatch.setenv("CLOUDQA_CUSTOMER_PASSWORD", secret)
        flags = ["--credential-env"]

    client = MagicMock()
    playwright = MagicMock()
    monkeypatch.setattr(cli.genai, "Client", client)
    monkeypatch.setattr(cli, "sync_playwright", playwright)

    def fake_run(page, api_client, test, *, model, credentials):
        assert secret not in test
        assert "[REDACTED]" in test
        assert credentials.resolve_fill(
            "{{customer.password}}", url="https://example.com/login"
        ) == secret
        with pytest.raises(ValueError):
            credentials.resolve_fill(
                "{{customer.password}}", url="https://other.example/login"
            )
        return {
            "verdict": "pass", "reason": "Synthetic CLI wiring verified",
            "steps": 1, "elapsed_seconds": 0.0, "history": [],
        }

    runner = Mock(side_effect=fake_run)
    monkeypatch.setattr(cli, "run", runner)
    monkeypatch.setattr(sys, "argv", [
        "main.py", "--url", "https://example.com/start",
        "--test", "Synthetic instruction " + secret,
        "--report", str(destination), *flags,
    ])
    assert cli.main() == 0
    runner.assert_called_once()
    assert secret not in destination.read_text()


def test_missing_credential_file_stops_before_client(tmp_path, monkeypatch, capsys):
    destination = tmp_path / "result.json"
    client = Mock()
    monkeypatch.setattr(cli.genai, "Client", client)
    monkeypatch.setattr(cli, "load_dotenv", Mock())
    monkeypatch.setattr(sys, "argv", [
        "main.py", "--url", "https://example.com", "--test", "Check",
        "--credentials", str(tmp_path / "missing.json"),
        "--report", str(destination),
    ])
    assert cli.main() == 1
    client.assert_not_called()
    assert json.loads(destination.read_text())["verdict"] == "fail"
    assert "missing.json" not in capsys.readouterr().out
