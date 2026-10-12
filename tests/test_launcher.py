from pathlib import Path

import httpx

from launcher import (
    ServerController,
    _escape_applescript_string,
    _frozen_working_directory,
    build_parser,
)


def test_launcher_defaults_to_dynamic_loopback_port() -> None:
    args = build_parser().parse_args([])

    assert args.host == "127.0.0.1"
    assert args.port == 0
    assert args.headless is False
    assert args.no_browser is False


def test_applescript_values_are_escaped() -> None:
    assert _escape_applescript_string('a\\b"c\nd') == 'a\\\\b\\"c\\nd'


def test_regular_frozen_executable_uses_its_parent(monkeypatch) -> None:
    monkeypatch.setattr("launcher.sys.platform", "win32")

    assert _frozen_working_directory(Path("/tmp/FastAPI-Service.exe")) == Path("/tmp")


def test_macos_app_uses_directory_next_to_bundle(monkeypatch) -> None:
    monkeypatch.setattr("launcher.sys.platform", "darwin")
    executable = Path("/Applications/FastAPI-Service.app/Contents/MacOS/FastAPI-Service")

    assert _frozen_working_directory(executable) == Path("/Applications")


def test_server_controller_starts_and_stops_service() -> None:
    controller = ServerController()

    try:
        controller.start()
        response = httpx.get(f"{controller.url}/health", timeout=5)

        assert controller.is_running
        assert controller.port > 0
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    finally:
        controller.stop()

    assert not controller.is_running
