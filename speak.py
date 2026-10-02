import sys
import io
import requests
import sounddevice as sd
import soundfile as sf

# silero-tts --host 127.0.0.1 --port 8000   

SERVER_URL = "http://127.0.0.1:8000/v1/audio/speech"
DEVICE_INDEX = 18
VOICES = ["baya", "aidar", "kseniya", "xenia", "eugene"]
DEFAULT_VOICE = "eugene"

def speak(text, voice):
    payload = {
        "model": "tts-1",
        "input": text,
        "voice": voice,
        "response_format": "wav"
    }
    try:
        response = requests.post(SERVER_URL, json=payload, stream=True)
        response.raise_for_status()
        audio_data, samplerate = sf.read(io.BytesIO(response.content))
        sd.play(audio_data, samplerate, device=DEVICE_INDEX)
        sd.wait()
        print("Воспроизведение завершено.")
    except requests.exceptions.ConnectionError:
        print("Ошибка: не удалось подключиться к серверу.")
    except Exception as e:
        print(f"Произошла ошибка: {e}")


if __name__ == "__main__":
    current_voice = DEFAULT_VOICE

    if len(sys.argv) > 1:
        speak(" ".join(sys.argv[1:]), current_voice)
        sys.exit(0)

    print(f"Текущий голос: {current_voice}")
    print("Команды: /voice <имя>, /voices, exit")
    print(f"Доступные голоса: {', '.join(VOICES)}")

    while True:
        try:
            line = input(f"[{current_voice}]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break

        if not line:
            continue

        parts = line.split()

        # --- Смена голоса ---
        if parts[0].lower() in ("/voice", "/v"):
            if len(parts) < 2:
                print(f"Текущий голос: {current_voice}")
                continue
            new_voice = parts[1].lower()
            if new_voice not in VOICES:
                print(f"Неизвестный голос. Доступны: {', '.join(VOICES)}")
                continue
            current_voice = new_voice
            print(f"Голос переключён на: {current_voice}")

            # Если после имени голоса есть ещё текст — сразу его озвучим
            rest = " ".join(parts[2:])
            if rest:
                speak(rest, current_voice)
            continue

        if parts[0].lower() in ("/voices", "/list"):
            print(", ".join(VOICES))
            continue

        if line.lower() == "exit":
            print("Выход.")
            break

        speak(line, current_voice)