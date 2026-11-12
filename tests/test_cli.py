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
