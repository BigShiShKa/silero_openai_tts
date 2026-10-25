import json
import math
import os
import tempfile
from dataclasses import dataclass, fields
from pathlib import Path
from urllib.parse import urlsplit


def config_path():
    root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) if os.name == "nt" else Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "silero-tts" / "client.json"


@dataclass
class ClientConfig:
    url: str = "http://127.0.0.1:8000"
    api_key: str = ""
    voice: str = "eugene"
    speed: float = 1.0
    device: str | None = None
    monitor: bool = False
    connect_timeout: float = 3.0
    read_timeout: float = 120.0
    startup_timeout: float = 120.0

    def validate(self):
        if not isinstance(self.url, str):
            raise ValueError("URL должен быть строкой")
        parts = urlsplit(self.url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ("", "/"):
            raise ValueError("URL должен быть базовым адресом http(s)://host:port без /v1 и учётных данных")
        _ = parts.port
        self.url = self.url.rstrip("/")
        if self.voice not in ("baya", "aidar", "kseniya", "xenia", "eugene", "random", "alloy", "echo", "fable", "onyx", "nova", "shimmer"):
            raise ValueError("Неизвестный голос")
        if not isinstance(self.api_key, str) or (self.device is not None and not isinstance(self.device, str)):
            raise ValueError("api_key и device должны быть строками")
        if not isinstance(self.monitor, bool):
            raise ValueError("monitor должен быть true или false")
        for name in ("speed", "connect_timeout", "read_timeout", "startup_timeout"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"Некорректное значение {name}")
        if not 0.25 <= self.speed <= 4:
            raise ValueError("Скорость должна быть от 0.25 до 4")
        if self.device == "default":
            self.device = None
        return self


def load_config(path, overrides):
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise ValueError(f"Не удалось прочитать настройки {path}") from exc
        if not isinstance(data, dict):
            raise ValueError("Настройки должны быть JSON-объектом")
    names = {f.name for f in fields(ClientConfig)}
    unknown = set(data) - names
    if unknown:
        raise ValueError(f"Неизвестные настройки: {', '.join(sorted(unknown))}")
    for name in names:
        value = os.environ.get("SILERO_CLIENT_" + name.upper())
        if value is not None:
            try:
                if name == "monitor":
                    if value.lower() not in ("true", "false", "1", "0"):
                        raise ValueError("monitor")
                    data[name] = value.lower() in ("true", "1")
                else:
                    data[name] = float(value) if name in ("speed", "connect_timeout", "read_timeout", "startup_timeout") else value
            except ValueError as exc:
                raise ValueError(f"Некорректная переменная SILERO_CLIENT_{name.upper()}") from exc
        value = getattr(overrides, name, None)
        if value is not None:
            data[name] = value
    return ClientConfig(**data).validate()


def save_preferences(path, config):
    # Never persist API keys or CLI connection overrides implicitly.
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.update({name: getattr(config, name) for name in ("voice", "speed", "device", "monitor")})
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
