"""
Лаунчер: поднимает TTS-сервер, ждёт готовности, запускает speak.py, гасит сервер.

Использование:
    python run_tts.py                # интерактивный режим speak.py
    python run_tts.py "привет мир"   # разовая озвучка (аргументы уйдут в speak.py)
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from jobobject import create_kill_on_close_job, assign_pid_to_job

import requests

# ==== Настройки ====
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
DOCS_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/docs"

PROJECT_DIR = Path(__file__).resolve().parent
CLIENT_SCRIPT = PROJECT_DIR / "speak.py"
LOG_FILE = PROJECT_DIR / "tts_server.log"

SHOW_SERVER_WINDOW = False  # True — сервер стартует в видимом окне cmd


# =======================  Поиск исполняемого сервера  =======================

def _find_silero_exe() -> Path | None:
    candidates = []
    for scripts in (PROJECT_DIR / ".venv" / "Scripts",
                    PROJECT_DIR / ".venv" / "bin",
                    Path(sys.executable).parent):
        for name in ("silero-tts.exe", "silero-tts"):
            candidates.append(scripts / name)
    return next((p for p in candidates if p.exists()), None)


def _find_venv_python() -> Path:
    for p in (PROJECT_DIR / ".venv" / "Scripts" / "python.exe",
              PROJECT_DIR / ".venv" / "bin" / "python",
              Path(sys.executable)):
        if p.exists():
            return p
    return Path(sys.executable)


# =======================  Порт / готовность  =======================

def _port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((SERVER_HOST, SERVER_PORT)) == 0


def _wait_server(timeout: float = 120.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            requests.get(DOCS_URL, timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


# =======================  Сервер  =======================

def start_server() -> tuple[subprocess.Popen | None, bool]:
    """(process, owned). owned=True — сервер подняли мы и должны его погасить."""
    if _port_in_use():
        print(f"Сервер уже слушает {SERVER_HOST}:{SERVER_PORT} — использую его.")
        return None, False

    silero_exe = _find_silero_exe()
    if silero_exe is not None:
        cmd = [str(silero_exe), "--host", SERVER_HOST, "--port", str(SERVER_PORT)]
    else:
        py = _find_venv_python()
        cmd = [str(py), "-m", "uvicorn", "app.main:app",
               "--host", SERVER_HOST, "--port", str(SERVER_PORT)]

    creationflags = 0
    if os.name == "nt":
        creationflags = (subprocess.CREATE_NEW_CONSOLE if SHOW_SERVER_WINDOW
                         else subprocess.CREATE_NO_WINDOW)

    print(f"Запуск TTS-сервера: {' '.join(cmd)}")
    print(f"Логи сервера: {LOG_FILE}")

    log_fh = open(LOG_FILE, "w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_DIR),
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    return proc, True


def stop_server(proc: subprocess.Popen | None):
    if proc is None or proc.poll() is not None:
        return
    print(f"Останавливаю сервер (PID={proc.pid})...")
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


# =======================  Запуск клиента  =======================

def run_client(extra_args: list[str]) -> int:
    """
    Запускает speak.py отдельным процессом, чтобы его sys.exit / Ctrl+C
    не мешали нашему finally.
    """
    cmd = [str(_find_venv_python()), str(CLIENT_SCRIPT), *extra_args]
    return subprocess.call(cmd, cwd=str(PROJECT_DIR))


# =======================  Точка входа  =======================

def main() -> int:
    if not CLIENT_SCRIPT.exists():
        print(f"[ОШИБКА] Не найден клиент: {CLIENT_SCRIPT}")
        return 1

    # создаём job заранее, до старта сервера
    job = None
    try:
        job = create_kill_on_close_job()
    except Exception as e:
        print(f"[warn] не удалось создать Job Object: {e}")

    proc, owned = start_server()

     # если сервер наш и job есть — кладём в job
    if owned and proc is not None and job is not None:
        try:
            assign_pid_to_job(job, proc.pid)
        except Exception as e:
            print(f"[warn] не удалось поместить сервер в Job Object: {e}")

    try:
        print("Ожидание готовности сервера...")
        if not _wait_server():
            print(f"Сервер не поднялся. Смотри лог: {LOG_FILE}")
            return 1
        print("Сервер готов.\n")

        rc = run_client(sys.argv[1:])
        return rc
    finally:
        if owned:
            stop_server(proc)
        print("Готово.")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nПрервано пользователем.")
        sys.exit(130)   