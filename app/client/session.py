import io
from contextlib import ExitStack
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import sounddevice as sd
import soundfile as sf

from app.client.config import config_path, load_config, save_preferences
from app.client.launcher import ClientError, ServerSession, probe

log = logging.getLogger("silero.client")
VOICES = ("baya", "aidar", "kseniya", "xenia", "eugene", "random", "alloy", "echo", "fable", "onyx", "nova", "shimmer")


def output_devices():
    apis = sd.query_hostapis()
    return [(index, f"{device['name']} [{apis[device['hostapi']]['name']}]")
            for index, device in enumerate(sd.query_devices()) if device["max_output_channels"] > 0]


def choose_device(config, path, interactive):
    devices = output_devices()
    if not devices:
        raise ClientError("Аудиоустройства вывода не найдены.")
    if config.device is None:
        try:
            sd.query_devices(kind="output")
            return None
        except sd.PortAudioError:
            pass
    else:
        matches = [index for index, name in devices if name == config.device]
        if len(matches) == 1:
            return matches[0]
    print("Выбранное аудиоустройство недоступно. Доступные устройства:")
    for index, name in devices:
        print(f"  {index}: {name}")
    if not interactive:
        raise ClientError("Выберите устройство через --device или запустите console и /device.")
    while True:
        try:
            answer = input("Номер устройства (или exit): ").strip()
        except EOFError as exc:
            raise ClientError("Выбор устройства отменён: ввод завершён.") from exc
        if answer.lower() == "exit":
            raise ClientError("Выбор устройства отменён.")
        for index, name in devices:
            if answer == str(index):
                config.device = name
                save_preferences(path, config)
                return index
        print("Укажите номер из списка.")


def http_session(config):
    session = requests.Session()
    # Only connection failures before transmitting a request are retried.
    retry = Retry(total=1, connect=1, read=0, status=0, redirect=0, other=0, backoff_factor=0.2)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    if config.api_key:
        session.headers["Authorization"] = "Bearer " + config.api_key
    return session


def play_audio(audio, sample_rate, device, monitor):
    """Mirror to the default device using independent PortAudio streams."""
    if not monitor or device is None or device == sd.default.device[1]:
        sd.play(audio, sample_rate, device=device)
        sd.wait()
        return

    samples = audio[:, None] if audio.ndim == 1 else audio

    def callback_for_device():
        position = 0

        def callback(outdata, frames, _time, status):
            nonlocal position
            if status:
                log.warning("Audio stream status: %s", status)
            count = min(frames, len(samples) - position)
            outdata.fill(0)
            outdata[:count] = samples[position:position + count]
            position += count
            if position >= len(samples):
                raise sd.CallbackStop

        return callback

    with ExitStack() as stack:
        # Open both devices before starting either, so an unavailable monitor
        # does not leave the primary playing after reporting an error.
        streams = []
        for output_device in (device, None):
            stream = sd.OutputStream(device=output_device, samplerate=sample_rate,
                                     channels=samples.shape[1], dtype="float32",
                                     callback=callback_for_device())
            stack.callback(stream.close)
            streams.append(stream)
        try:
            for stream in streams:
                stream.start()
            while any(stream.active for stream in streams):
                sd.sleep(20)
        finally:
            for stream in streams:
                stream.abort()


def speak(session, config, path, text, *, output=None, interactive=False):
    if not text.strip() or len(text) > 4096:
        raise ClientError("Текст должен содержать от 1 до 4096 символов.")
    device = choose_device(config, path, interactive)
    try:
        with session.post(
            config.url + "/v1/audio/speech",
            json={"model": "tts-1", "input": text, "voice": config.voice, "speed": config.speed, "response_format": "wav"},
            timeout=(config.connect_timeout, config.read_timeout), allow_redirects=False,
        ) as response:
            if response.status_code != 200:
                log.warning("Synthesis failed: HTTP %s", response.status_code)
                detail = " Проверьте API key." if response.status_code in (401, 403) else ""
                raise ClientError(f"Ошибка синтеза: HTTP {response.status_code}.{detail}")
            wav = response.content
    except requests.Timeout as exc:
        raise ClientError("Истекло время ожидания сервера; запрос не повторён.") from exc
    except requests.RequestException as exc:
        raise ClientError("Ошибка соединения с сервером. Проверьте подключение и состояние сервера.") from exc
    try:
        audio, sample_rate = sf.read(io.BytesIO(wav), dtype="float32")
    except (ValueError, RuntimeError) as exc:
        raise ClientError("Сервер вернул некорректное аудио.") from exc
    if output:
        destination = Path(output)
        # Avoid silently replacing an existing recording.
        with destination.open("xb") as stream:
            stream.write(wav)
    try:
        play_audio(audio, sample_rate, device, config.monitor)
    except sd.PortAudioError as exc:
        raise ClientError("Не удалось воспроизвести аудио. Проверьте устройство и выберите его через /device или --device.") from exc
    finally:
        sd.stop()
    log.info("Playback completed: bytes=%d sample_rate=%d", len(wav), sample_rate)
    print("Воспроизведение завершено.")


def console(session, config, path):
    print("Команды: /voice, /voices, /speed, /device, /devices, /monitor, /status, /help, exit. Ctrl+C — выход.")
    while True:
        try:
            line = input(f"[{config.voice}, {config.speed:g}x]> ").strip()
        except EOFError:
            return 0
        if not line:
            continue
        if line.lower() == "exit":
            return 0
        parts = line.split()
        command = parts[0].lower()
        try:
            if command in ("/voice", "/v"):
                if len(parts) == 1:
                    print(config.voice)
                    continue
                voice = parts[1].lower()
                if voice not in VOICES:
                    raise ClientError("Неизвестный голос. Список: /voices")
                config.voice = voice
                save_preferences(path, config)
                if len(parts) > 2:
                    speak(session, config, path, " ".join(parts[2:]), interactive=True)
            elif command in ("/voices", "/list"):
                print(", ".join(VOICES))
            elif command == "/speed":
                if len(parts) > 1:
                    speed = float(parts[1])
                    if not 0.25 <= speed <= 4:
                        raise ClientError("Скорость должна быть от 0.25 до 4.")
                    config.speed = speed
                    save_preferences(path, config)
                print(f"Скорость: {config.speed:g}")
            elif command in ("/device", "/devices"):
                devices = output_devices()
                for index, name in devices:
                    print(f"  {index}: {name}")
                print(f"Выбрано: {config.device or 'системное устройство'}")
                if command == "/device" and len(parts) > 1:
                    selection = " ".join(parts[1:])
                    matches = [name for index, name in devices if selection in (str(index), name)]
                    if selection == "default":
                        config.device = None
                    elif len(matches) == 1:
                        config.device = matches[0]
                    else:
                        raise ClientError("Укажите номер из списка или default.")
                    save_preferences(path, config)
            elif command == "/monitor":
                if len(parts) == 1:
                    config.monitor = not config.monitor
                elif len(parts) == 2 and parts[1].lower() in ("on", "off"):
                    config.monitor = parts[1].lower() == "on"
                else:
                    raise ClientError("Использование: /monitor [on|off]")
                save_preferences(path, config)
                print(f"Дублирование в системное устройство: {'включено' if config.monitor else 'выключено'}")
            elif command == "/status":
                status = probe(config)
                print(f"Сервер: {config.url}; {'готов' if status else 'недоступен'}")
                print(f"Голос: {config.voice}; скорость: {config.speed:g}; устройство: {config.device or 'системное'}")
                print(f"Дублирование в системное устройство: {'включено' if config.monitor else 'выключено'}")
            elif command == "/help":
                print("/voice <имя> [текст], /voices, /speed <0.25–4>, /device <номер|default>, /devices, /monitor [on|off], /status, exit")
            elif command.startswith("/"):
                print("Неизвестная команда. Справка: /help")
            else:
                speak(session, config, path, line, interactive=True)
        except (ClientError, ValueError, OSError, sd.PortAudioError) as exc:
            print(f"Ошибка: {exc}")
            log.warning("Console operation failed: %s", type(exc).__name__)


def run(args):
    path = Path(args.config).expanduser().resolve() if args.config else config_path().resolve()
    config = load_config(path, args)
    log_dir = path.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / "client.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    try:
        save_preferences(path, config)
        with ServerSession(config, log_dir, auto_start=not args.no_start), http_session(config) as session:
            if args.command == "console":
                return console(session, config, path)
            speak(session, config, path, " ".join(args.text), output=args.output, interactive=sys.stdin.isatty())
            return 0
    except ClientError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        log.warning("Client operation failed: %s", type(exc).__name__)
        return 1
    except KeyboardInterrupt:
        sd.stop()
        raise
    finally:
        log.removeHandler(handler)
        handler.close()
