import os
import sys
import time
import subprocess
from pathlib import Path
from urllib.request import urlopen


def _wait_for_api(url: str, timeout_s: float = 20.0) -> bool:
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            with urlopen(url, timeout=2) as resp:
                return 200 <= getattr(resp, "status", 200) < 500
        except Exception:
            time.sleep(0.4)
    return False


def main() -> int:
    project_dir = Path(__file__).resolve().parent
    api_host = os.getenv("API_HOST", "127.0.0.1")
    api_port = os.getenv("API_PORT", "8000")
    api_base = os.getenv("API_BASE_URL", f"http://{api_host}:{api_port}")

    session_file = project_dir / "current_session.json"

    env = os.environ.copy()
    env["API_BASE_URL"] = api_base
    env["SESSION_FILE"] = str(session_file)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["SERVER_TTS"] = "1"

    new_consoles = os.getenv("INTEGRATED_NEW_CONSOLES", "").strip().lower() in ("1", "true", "yes", "on")
    creationflags = subprocess.CREATE_NEW_CONSOLE if (os.name == "nt" and new_consoles) else 0
    bg_stdin = subprocess.DEVNULL
    api_log = (project_dir / "api_server.log").open("a", encoding="utf-8")
    vision_log = (project_dir / "vision_process.log").open("a", encoding="utf-8")

    # Start API server (FastAPI) in background
    api_cmd = [sys.executable, "-m", "uvicorn", "api:app", "--host", api_host, "--port", str(api_port)]
    api_proc = subprocess.Popen(
        api_cmd,
        cwd=str(project_dir),
        env=env,
        creationflags=creationflags,
        stdin=bg_stdin,
        stdout=api_log,
        stderr=api_log,
    )

    if not _wait_for_api(f"{api_base}/docs", timeout_s=25.0):
        print("API server did not start in time. Is uvicorn installed?")
        api_proc.terminate()
        return 2

    # Start computer vision monitor (comp-vision) in background
    vision_dir = project_dir / "comp-vision"
    env2 = env.copy()
    env2["VISION_LOG_PATH"] = str(project_dir / "vision_log.jsonl")
    vision_proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(vision_dir),
        env=env2,
        creationflags=creationflags,
        stdin=bg_stdin,
        stdout=vision_log,
        stderr=vision_log,
    )

    # Run question_delivery.py directly in THIS console (full UI + TTS + timer)
    print("\n  API server ready. Starting interview...\n")
    try:
        interview_proc = subprocess.Popen(
            [sys.executable, "question_delivery.py"],
            cwd=str(project_dir),
            env=env,
        )
        interview_code = interview_proc.wait()
        return interview_code or 0
    except KeyboardInterrupt:
        return 0
    finally:
        for p in (vision_proc, api_proc):
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass
        try:
            api_log.close()
        except Exception:
            pass
        try:
            vision_log.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())