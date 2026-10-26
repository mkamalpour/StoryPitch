"""Launch StoryPitch from any working directory."""

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent


def free_port(start):
    for port in range(start, min(start + 20, 65536)):
        with socket.socket() as connection:
            try:
                connection.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port near {start}")


def wait_ready(process, url, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Server exited during startup; inspect the error above")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Server did not become ready at {url}")


def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main(argv=None):
    parser = argparse.ArgumentParser(description="StoryPitch interactive stories")
    parser.add_argument(
        "mode",
        nargs="?",
        default="html",
        choices=["html", "both", "api", "gradio", "telegram", "seed"],
    )
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    try:
        from config import API_PORT, TELEGRAM_TOKEN
    except (ImportError, ModuleNotFoundError) as exc:
        print(
            "\nStoryPitch could not start because a required dependency is missing.\n"
            "\nUse the assigned environment and install the project dependencies first:\n"
            "  conda activate base\n"
            "  python -m pip install -r requirements.txt\n"
            "\nIf you are using the managed workspace, open the project workspace for the assigned interpreter.\n"
            f"Original error: {type(exc).__name__}: {exc}\n"
        )
        raise SystemExit(2)

    env = os.environ.copy()
    if args.mode == "seed":
        return subprocess.call(
            [sys.executable, "-m", "db.seed_data"], cwd=ROOT, env=env
        )
    if args.mode == "telegram" and not TELEGRAM_TOKEN:
        parser.error("Set TELEGRAM_TOKEN in .env before starting the bot")
    port = free_port(API_PORT)
    base = f"http://127.0.0.1:{port}"
    env.update(API_HOST="127.0.0.1", API_PORT=str(port), API_BASE=base)
    api = frontend = None
    try:
        api = subprocess.Popen([sys.executable, "-m", "api.main"], cwd=ROOT, env=env)
        wait_ready(api, base + "/api/health")
        url = base
        if args.mode == "gradio":
            gradio_port = free_port(int(env.get("GRADIO_SERVER_PORT", "7860")))
            env["GRADIO_SERVER_PORT"] = str(gradio_port)
            frontend = subprocess.Popen(
                [sys.executable, "-m", "ui.gradio_ui"], cwd=ROOT, env=env
            )
            url = f"http://127.0.0.1:{gradio_port}"
            wait_ready(frontend, url, seconds=60)
        elif args.mode == "telegram":
            frontend = subprocess.Popen(
                [sys.executable, "-m", "ui.telegram_bot"], cwd=ROOT, env=env
            )
        print(f"StoryPitch: {url}  |  API reference: {base}/docs")
        if not args.no_browser and args.mode in {"html", "both", "gradio"}:
            webbrowser.open(url)
        if frontend:
            while frontend.poll() is None:
                if api.poll() is not None:
                    raise RuntimeError("API stopped unexpectedly")
                time.sleep(0.3)
            return frontend.returncode
        return api.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        stop(frontend)
        stop(api)


if __name__ == "__main__":
    raise SystemExit(main())
