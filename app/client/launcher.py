"""Start only local servers and always release processes owned by this session."""
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

from app.client.jobobject import assign_pid_to_job, close_job, create_kill_on_close_job

log = logging.getLogger("silero.client")


class ClientError(Exception):
    pass


def probe(config):
    try:
        response = requests.get(config.url + "/health", timeout=(config.connect_timeout, config.connect_timeout), allow_redirects=False)
        with response:
            if response.status_code != 200:
                return None
            data = response.json()
        if isinstance(data, dict) and data.get("service") == "silero-openai-tts" and data.get("status") == "ready" and isinstance(data.get("server_playback"), bool):
            return data
    except (requests.RequestException, ValueError):
        pass
    return None


def port_open(host, port):
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


class ServerSession:
    def __init__(self, config, log_dir, auto_start=True):
        self.config = config
        self.log_dir = Path(log_dir)
        self.auto_start = auto_start
        self.proc = None
        self.job = None

    @staticmethod
    def check_playback(status):
        if status["server_playback"]:
            raise ClientError("На сервере включён AUTO_PLAY/FORCE_PLAY. Отключите его перед клиентским воспроизведением.")

    def __enter__(self):
        try:
            self.ensure_ready()
            return self
        except BaseException:
            self.close()
            raise

    def ensure_ready(self):
        status = probe(self.config)
        if status:
            self.check_playback(status)
            return
        parts = urlsplit(self.config.url)
        host = parts.hostname
        port = parts.port or (443 if parts.scheme == "https" else 80)
        if host not in ("localhost", "127.0.0.1", "::1") or parts.scheme != "http" or not self.auto_start:
            raise ClientError("TTS-сервер недоступен или не поддерживает /health. Проверьте адрес и запуск сервера.")
        if port_open(host, port):
            raise ClientError(f"Порт {port} занят приложением без совместимого /health. Остановите его или укажите другой URL.")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.job = create_kill_on_close_job()
        except OSError as exc:
            raise ClientError("Не удалось создать Windows Job Object; безопасный запуск сервера отменён.") from exc
        env = os.environ.copy()
        # Client and server playback are mutually exclusive. Never log spoken text.
        env.update(AUTO_PLAY="false", FORCE_PLAY="false", SHOW_TEXT="false", PYTHONUNBUFFERED="1")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "app.client.server", "--host", host, "--port", str(port), "--log-dir", str(self.log_dir)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=env, creationflags=flags,
        )
        if self.job is not None:
            assign_pid_to_job(self.job, self.proc.pid)
        print(f"Ожидание готовности сервера (до {self.config.startup_timeout:g} с)...")
        print(f"Лог сервера: {self.log_dir / 'server.log'}")
        deadline = time.monotonic() + self.config.startup_timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise ClientError(f"Сервер завершился при запуске. Лог: {self.log_dir / 'server.log'}")
            status = probe(self.config)
            if status:
                # A second launcher may have won the bind race.
                if self.proc.poll() is not None:
                    raise ClientError("Запущенный сервер завершился до готовности.")
                self.check_playback(status)
                return
            time.sleep(0.2)
        raise ClientError(f"Истекло время запуска сервера. Лог: {self.log_dir / 'server.log'}")

    def close(self):
        try:
            if self.proc is not None:
                try:
                    if self.proc.poll() is None:
                        try:
                            self.proc.stdin.write(b"shutdown\n")
                            self.proc.stdin.flush()
                        except (BrokenPipeError, OSError):
                            pass
                        try:
                            self.proc.wait(timeout=8)
                        except subprocess.TimeoutExpired:
                            log.warning("Graceful shutdown timed out; terminating owned server")
                            if os.name == "nt":
                                subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                            else:
                                self.proc.kill()
                            self.proc.wait(timeout=5)
                finally:
                    if self.proc.stdin:
                        self.proc.stdin.close()
        finally:
            close_job(self.job)
            self.job = None

    def __exit__(self, *_):
        self.close()
