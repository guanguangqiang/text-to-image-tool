"""Desktop launcher used as the PyInstaller entrypoint.

The launcher runs Uvicorn on an available loopback port, opens the API in the
default browser, and provides a tiny window that owns the server lifecycle.
"""

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from contextlib import suppress
from pathlib import Path
from typing import IO, Optional

_LOG_STREAM: Optional[IO[str]] = None


def _frozen_working_directory(executable: Path) -> Path:
    """Return the directory where a frozen app should look for its .env file."""
    if sys.platform == "darwin" and executable.parent.name == "MacOS":
        app_bundle = executable.parent.parent.parent
        return app_bundle.parent
    return executable.parent


def _frozen_log_directory(executable_dir: Path) -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "FastAPI-Service"
    local_app_data = Path(os.environ.get("LOCALAPPDATA", executable_dir))
    return local_app_data / "FastAPI-Service" / "logs"


def _prepare_frozen_runtime() -> None:
    """Use paths next to the executable and retain logs for windowed builds."""
    global _LOG_STREAM

    if not getattr(sys, "frozen", False):
        return

    executable = Path(sys.executable).resolve()
    executable_dir = executable.parent
    os.chdir(_frozen_working_directory(executable))

    if sys.stdout is not None and sys.stderr is not None:
        return

    log_dir = _frozen_log_directory(executable_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    _LOG_STREAM = (log_dir / "app.log").open("a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = _LOG_STREAM
    if sys.stderr is None:
        sys.stderr = _LOG_STREAM


class ServerController:
    """Own a Uvicorn server running in a background thread."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.host = host
        self.requested_port = port
        self.port = port
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._server = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self._server.started)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self, timeout: float = 15.0) -> None:
        if self._thread and self._thread.is_alive():
            return

        import uvicorn

        from app.main import app

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.requested_port))
        self._socket.listen(2048)
        self.port = int(self._socket.getsockname()[1])

        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            loop="asyncio",
            log_config=None,
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(
            target=self._server.run,
            kwargs={"sockets": [self._socket]},
            name="fastapi-server",
            daemon=True,
        )
        self._thread.start()

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._server.started:
                return
            if not self._thread.is_alive():
                break
            time.sleep(0.05)

        self.stop()
        raise RuntimeError("FastAPI service failed to start")

    def stop(self, timeout: float = 10.0) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        if self._socket is not None:
            with suppress(OSError):
                self._socket.close()
        self._socket = None


def _show_error(message: str) -> None:
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, "FastAPI Service", 0x10)
    elif sys.platform == "darwin":
        escaped_message = _escape_applescript_string(message)
        script = (
            'display alert "FastAPI Service" message "'
            f'{escaped_message}" as critical buttons {{"确定"}} default button "确定"'
        )
        subprocess.run(["osascript", "-e", script], check=False)
    else:
        print(message, file=sys.stderr)


def _escape_applescript_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _run_macos_window(controller: ServerController, docs_url: str) -> None:
    escaped_url = _escape_applescript_string(docs_url)
    script = f'''
repeat
    set selectedButton to button returned of (display dialog "服务已启动\\n{escaped_url}" ¬
        with title "FastAPI Service" ¬
        buttons {{"退出", "打开浏览器"}} default button "打开浏览器")
    if selectedButton is "退出" then exit repeat
    open location "{escaped_url}"
end repeat
'''
    try:
        subprocess.run(["osascript", "-e", script], check=False)
    finally:
        controller.stop()


def _run_window(controller: ServerController, docs_url: str) -> None:
    if sys.platform == "darwin":
        _run_macos_window(controller, docs_url)
        return

    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("FastAPI Service")
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=24)
    frame.grid()
    ttk.Label(frame, text="服务已启动", font=("Segoe UI", 14, "bold")).grid(
        row=0,
        column=0,
        columnspan=2,
        pady=(0, 10),
    )
    ttk.Label(frame, text=docs_url).grid(row=1, column=0, columnspan=2, pady=(0, 16))

    ttk.Button(frame, text="打开浏览器", command=lambda: webbrowser.open(docs_url)).grid(
        row=2,
        column=0,
        padx=(0, 8),
    )

    def close() -> None:
        root.withdraw()
        controller.stop()
        root.destroy()

    ttk.Button(frame, text="退出", command=close).grid(row=2, column=1, padx=(8, 0))
    root.protocol("WM_DELETE_WINDOW", close)
    root.mainloop()


def _run_headless(controller: ServerController) -> None:
    try:
        while controller.is_running:
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the local FastAPI service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="0 selects an available port")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--headless", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    _prepare_frozen_runtime()
    args = build_parser().parse_args(argv)
    controller = ServerController(args.host, args.port)

    try:
        controller.start()
        docs_url = f"{controller.url}/docs"
        if not args.no_browser:
            webbrowser.open(docs_url)
        if args.headless:
            _run_headless(controller)
        else:
            _run_window(controller, docs_url)
    except KeyboardInterrupt:
        with suppress(KeyboardInterrupt):
            controller.stop(timeout=1)
        return 0
    except Exception as exc:
        controller.stop()
        _show_error(f"启动失败：{exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
