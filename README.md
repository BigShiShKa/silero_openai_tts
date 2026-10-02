# Silero TTS, compatible with the OpenAI API and ElevenLabs API + Console client

**Local**, self-hosted speech synthesis (Text-to-Speech, TTS) server implementing both **OpenAI TTS API** (`POST /v1/audio/speech`)
and an **ElevenLabs-compatible API** (`POST /v1/text-to-speech/{voice_id}`, `GET /v1/voices`, `GET /v1/models`).

The main goal of the project is to provide a **“drop-in and works” TTS backend**, compatible with OpenAI- and ElevenLabs-style clients, for
[OpenClaw](https://github.com/openclaw/openclaw) — чтобы OpenClaw мог говорить, не полагаясь на внешние облачные сервисы.
At the same time, this server works with **any** project that expects an OpenAI-compatible and/or ElevenLabs-compatible TTS endpoint: simply configure the
client to use this server's base URL.

A key feature of this fork is the **built-in standalone console client**,
which starts and stops the server itself, waits for it to become ready, provides an interactive
REPL with voice switching, and can also speak text passed as a
command-line argument. The client works on Windows (for Linux/macOS
just replace the path to `python.exe` with `python`).

> **Console client** — see the [“Console client”](#console-client) section.

Under the hood, the project uses **Silero TTS** models via `torch.hub` (downloaded on first launch), plus a small
text normalization pipeline focused on **Russian and English**, including **number expansion**.

## What is this project for?

The key advantage of the project is **very fast CPU speech synthesis**. In practice, this allows scarce
GPU resources to remain available for a local LLM while TTS runs separately on the CPU with low latency.

The project also supports **automatic audio playback** directly on the server. This mode is especially useful because in the current version of **OpenClaw**, built-in client-side auto-playback (in the **webchat** browser) is unstable.

---

## Features

- **OpenAI API compatibility**: реализует `POST /v1/audio/speech` с привычными полями запроса:
  `model`, `input`, `voice`, `response_format`, `speed`.
- **Optional ElevenLabs-compatible mode**: может отдавать `POST /v1/text-to-speech/{voice_id}` и `GET /v1/voices` для клиентов с ElevenLabs-style контрактом.
- **Designed for OpenClaw**, но работает с любым OpenAI-совместимым клиентом.
- **Standalone console client** (Windows): сам запускает сервер в фоне,
  ждёт готовности, ведёт REPL со сменой голосов, корректно гасит сервер
  по `exit`, `Ctrl+C` и закрытию окна.
- **Russian and English support** (автоматическое распознавание).
- **Natural number reading**:
  - expands integers into words;
  - for Russian, matches noun forms to numbers (например: “21 рубль / 22 рубля / 25 рублей”);
  - expands common patterns such as `%` and `₽` (the ruble symbol).
- **Multiple voices**:
  - accepts OpenAI voice names (`alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`) and maps them to Silero speakers;
  - also accepts Silero speaker IDs directly (например: `baya`, `aidar`, `kseniya`, `xenia`, `eugene`, `random`).
- **Multiple output formats**: `wav`, `mp3`, `opus`, `aac`, `flac`.
- **Speed control** (`0.25`–`4.0`) с помощью аудиофильтров FFmpeg.
- **Disk cache**, чтобы не пересинтезировать одну и ту же фразу снова и снова.
- **Optional API key** (Bearer token) для приватных развёртываний.
- **Runs on CPU by default**, с опциональной поддержкой GPU (CUDA), если ваша сборка PyTorch её поддерживает.

---

## Quick start

### 0) Clone the repository

```bash
git clone https://github.com/ndrco/silero_openai_tts.git
cd silero_openai_tts
```

### 1) System dependencies

**FFmpeg** (for encoding and speed control) and **libsndfile** (for WAV input/output) are required.

**Debian / Ubuntu (including WSL2):**
```bash
sudo apt update
sudo apt install -y ffmpeg libsndfile1
```

**Windows (PowerShell):**

1. Install Python 3.10+ from the official website and make sure the `python` command is available in `PATH`.
2. Install FFmpeg (required for formats other than WAV and for speed changes), for example via winget:

```powershell
winget install Gyan.FFmpeg
```

3. Verify the installation:

```powershell
python --version
ffmpeg -version
```

### 2) Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .

# optional for console client
pip install -e ".[client]"
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip

# Server only:
python -m pip install -e .

# Server + console client (recommended):
python -m pip install -e ".[client]"

# Server + client + tests:
python -m pip install -e ".[client,test]"
```

If PowerShell blocks script execution, allow local scripts for the current user once:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 3) Configuration

Copy `.env.example` to `.env` and edit it if necessary:

```bash
cp .env.example .env
```

**Windows (PowerShell):**

```powershell
copy .env.example .env
```

### 4) Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Windows (PowerShell):**

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If the project was installed with `pip install -e .`, you can run it using the console command:

```bash
silero-tts
```

Or invoke it directly from the virtual environment without activation:

```bash
./.venv/bin/silero-tts
```

Windows equivalent:

```powershell
.\.venv\Scripts\silero-tts.exe
```

**CLI options:**

```bash
silero-tts --help
```

| Option | Description |
|--------|-------------|
| `--host` | Interface to bind to (default: `0.0.0.0`) |
| `--port` | Port to listen on (default: `8000`) |
| `--force-play` | Force-enable server-side audio playback (also enables text output) |
| `--show-text` | Print text to the console before synthesis |

**Examples:**

```bash
# Launch with force-play (audio playing + text output)
silero-tts --force-play

# Launch with text-only
silero-tts --show-text

# Launch with both options
silero-tts --port 8080 --force-play
```

On the first launch, the server downloads the selected Silero model (via `torch.hub`).

---

## Console client

In addition to the HTTP API, this fork includes an interactive console client that
handles all orchestration: starts the server, waits for it to become ready, speaks
the entered text, and stops the server on exit.

### Components

| File | Purpose |
|---|---|
| `speak.py` | Client: HTTP requests to the server + playback via `sounddevice`. Pure client, with no startup logic. |
| `run_tts.py` | Orchestrator: starts/stops the server, waits for `/docs`, and launches `speak.py`. |
| `run_tts.bat` | Thin wrapper for launching from File Explorer. |
| `jobobject.py` | Windows Job Object with `KILL_ON_JOB_CLOSE` — ensures the server dies with the launcher, even if the window is closed with the X button. |

### Requirements

- Windows (uses `taskkill`, `jobobject`, and `sounddevice` with WASAPI devices).
- Python 3.10+ from the project's virtual environment (`.venv`).
- FFmpeg — only if you plan to work with non-WAV formats.
- Installed `sounddevice` (see the `[client]` extra in `pyproject.toml`).

### Installation

```powershell
cd D:\Programms\silero_openai_tts
.\.venv\Scripts\Activate.ps1
pip install -e ".[client]"
```

### Settings

All client parameters are located at the beginning of `speak.py`:

```python
SERVER_URL   = "http://127.0.0.1:8000/v1/audio/speech"
DEVICE_INDEX = 18
VOICES       = ["baya", "aidar", "kseniya", "xenia", "eugene"]
DEFAULT_VOICE = "eugene"
```

Orchestrator parameters are located at the beginning of `run_tts.py`:

```python
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
SHOW_SERVER_WINDOW = False   # True — Server starting in visible cmd window
```

#### How to find the audio device index

`DEVICE_INDEX` is the output device number to which the client sends
the synthesized audio. To view the list of available devices:

```powershell
python -c "import sounddevice as sd; print(sd.query_devices())"
```

The output will look approximately like this:

```
   0 Microsoft Sound Mapper - Input, MME (2 in, 0 out)
   1 Microphone (Realtek Audio), MME (2 in, 0 out)
   ...
  18 Speakers (USB Audio), WASAPI (0 in, 2 out)
  19 Headphones (Realtek Audio), WASAPI (0 in, 2 out)
```

Find the line with the desired output device and put its **index** (the number
at the beginning of the line) into `DEVICE_INDEX` in `speak.py`. In the example above, it is `18`.

> **Important.** Device indices in Windows may change after reboot
> or enabling/disabling usb. If the sound suddenly disappears —
> restart `python -c "import sounddevice as sd; print(sd.query_devices())"`
> and check for `DEVICE_INDEX` still points to the required device.

#### Voices

The list of available voices is defined in `VOICES`. By default, it contains all speakers
модели `v5_1_ru`: `baya`, `aidar`, `kseniya`, `xenia`, `eugene`.
The default voice is `eugene` (`DEFAULT_VOICE`). The list can be changed
in `speak.py` as well as at runtime using the `/voices` and `/voice <name>` commands
in the REPL.

---

### Running

#### Interactive mode

```powershell
python run_tts.py
```

The `[eugene]>` prompt will appear, where you can enter text and commands:

| Command | Description |
|---|---|
| `<текст>` | Synthesizes and plays the text using the current voice. |
| `/voice <имя>` | Switches the voice. You can include text immediately: `/voice aidar привет`. |
| `/voices` | Shows the list of available voices. |
| `exit` | Exits the client and stops the server. |

Example session (currently RU lang only):

```
Текущий голос: eugene
Команды: /voice <имя>, /voices, exit
Доступные голоса: baya, aidar, kseniya, xenia, eugene
[eugene]> Привет, мир
Воспроизведение завершено.
[eugene]> /voice aidar
Голос переключён на: aidar
[aidar]> Как дела?
Воспроизведение завершено.
[aidar]> exit
Выход.
Останавливаю сервер (PID=15480)...
Готово.
```

#### One-shot synthesis

If you need to speak a single phrase and exit immediately:

```powershell
python run_tts.py "Hello world! It`s a test phrase."
```

The client will start the server, speak the text using the default voice (`eugene`),
stop the server, and exit. Voice switching and the REPL are unavailable in this mode.

---

### Desktop shortcut

A shortcut is created automatically on the first run of `run_tts.py`, provided that
`run_tts.bat` and `silero.ico` are located next to it. No manual actions are
required: run the client once, and
“Silero TTS” will appear on the desktop.

Configuration is at the beginning of `run_tts.py`:

```python
CREATE_DESKTOP_SHORTCUT = True   # False — do not create
SHORTCUT_NAME = "Silero TTS"     # file name (no .lnk)
```

Contents of `run_tts.bat` (used as the shortcut TargetPath):

```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" "%~dp0run_tts.py" %*
if errorlevel 1 pause
```

> **Downside of console shortcuts.** The Windows taskbar displays the
> `cmd.exe`, а не `silero.ico`. This is a Windows limitation for console
> applications — the icon of the shortcut itself and the file `.bat` will be yours, but the taskbar
> will still show cmd.

#### If you want your own taskbar icon

The only way is to launch Python **directly**, without an intermediate
`cmd.exe`. For this, a minimal C# launcher `SileroTTS.exe`
with an embedded icon is built. The C# compiler is included with .NET Framework.

Place `launcher.cs` and `silero.ico` next to each other:

```csharp
using System;
using System.Diagnostics;
using System.IO;

class Launcher
{
    static int Main(string[] args)
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        string py  = Path.Combine(dir, ".venv", "Scripts", "python.exe");
        string run = Path.Combine(dir, "run_tts.py");

        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = py;
        psi.WorkingDirectory = dir;
        psi.UseShellExecute = false;
        psi.Arguments = "\"" + run + "\"" +
            (args.Length > 0 ? " " + string.Join(" ", args) : "");

        Process p = Process.Start(psi);
        p.WaitForExit();
        return p.ExitCode;
    }
}
```

Build `SileroTTS.exe`:

```powershell
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe `
    /target:exe /win32icon:silero.ico `
    /out:SileroTTS.exe launcher.cs
```

Then create a shortcut to `SileroTTS.exe`:

```powershell
$ws  = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut("$env:USERPROFILE\Desktop\Silero TTS.lnk")
$lnk.TargetPath       = "$PWD\SileroTTS.exe"
$lnk.WorkingDirectory = "$PWD"
$lnk.IconLocation     = "$PWD\SileroTTS.exe,0"
$lnk.Save()
```

`SileroTTS.exe` launches Python directly: there is no extra `cmd.exe`, no
flashing console window at startup, and the taskbar icon is yours.

### Shutdown behavior

Client and server behavior depends on how they are terminated:

| Action | What happens |
|---|---|
| `exit` in REPL | `run_tts.py` handles the exit and stops the server via `taskkill` in `finally`. |
| `Ctrl+C` in REPL | `speak.py` catches `KeyboardInterrupt`, prints “Exit.”, and `finally` in `run_tts.py` stops the server. |
| `Ctrl+C` while waiting for the server | `requests.get` в `_wait_server` raises an exception, and `finally` stops the server. |
| The cross on the launcher window. | If `jobobject.py` is connected, Windows will kill the server via `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. Without it, the server survives the close and will be reused on the next launch. |
| The server has already been started manually | `run_tts.py` detects that the port is occupied, does not start a second server, and **does not stop** the existing server on exit (`owned=False`). |

#### Job Object (protection against an “orphaned” server)

To ensure the server always dies with the launcher, even if the window
is closed with the X button, `run_tts.py` uses a Windows Job Object.
The `jobobject.py` module creates a job with the `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` flag
and places the `silero-tts.exe` process in it. As soon as the parent process
dies for any reason, the OS kills all processes in the job.

The integration is already built into `run_tts.py`; no additional action is required.
On Linux/macOS, the module becomes a no-op — there, `finally` already works
reliably.

---

## API

### Endpoint

`POST /v1/audio/speech`

### Request body (JSON)

| Field | Type | Required | Notes |
|------|------|-------------|------------|
| `model` | string | yes | OpenAI-compatible field. **Ignored** by this server (kept for compatibility). |
| `input` | string | yes | Text to synthesize (typical limit: 1–4096 characters). |
| `voice` | string | yes | OpenAI voice name or Silero speaker ID. |
| `response_format` | string | no | `wav` (default), `mp3`, `opus`, `aac`, `flac` |
| `speed` | number | no | Playback speed (default `1.0`, range `0.25`–`4.0`) |
 
### Example (curl)

```bash
curl http://localhost:8000/v1/audio/speech   -H "Content-Type: application/json"   -d '{
    "model": "gpt-4o-mini-tts",
    "voice": "alloy",
    "input": "У меня 5 запросов и 21 рубль.",
    "response_format": "mp3",
    "speed": 1.1
  }'   --output out.mp3
```

### Authentication

If `REQUIRE_AUTH=true`, add:

```bash
-H "Authorization: Bearer YOUR_API_KEY"
```

### Skip playback

To skip the current playback (when `AUTO_PLAY=true`):

```bash
curl -X DELETE http://localhost:8000/v1/audio/speech/skip \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Response:
```json
{"skipped": true}
```

If nothing was playing, it returns `{"skipped": false}`.

---


## ElevenLabs-compatible adapter (optional)

An additional ElevenLabs-style API layer can be enabled on top of the same Silero backend:

- `GET /v1/voices`
- `GET /v1/models`
- `POST /v1/text-to-speech/{voice_id}`
- `POST /v1/text-to-speech/{voice_id}/stream` (в этой версии — alias для совместимости)

Enable it in `.env`:

```bash
ENABLE_ELEVENLABS_COMPAT=true
ELEVENLABS_REQUIRE_XI_API_KEY=true
```

If `REQUIRE_AUTH=true`, authentication works via:
- `Authorization: Bearer <API_KEY>`
- `xi-api-key: <API_KEY>` (preferred for ElevenLabs-compatible clients)

Example request:

```bash
curl http://localhost:8000/v1/text-to-speech/EXAVITQu4vr4xnSDxMaL \
  -H "xi-api-key: dummy-local-key" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Пример ElevenLabs-совместимого запроса",
    "model_id": "eleven_multilingual_v2",
    "output_format": "mp3_44100_128"
  }' \
  --output out.mp3
```

Current `output_format` mapping:
- `mp3_*` -> response MP3
- `pcm_*` -> response WAV

You can override `voice_id` mapping via `ELEVENLABS_VOICE_MAP_JSON` (a JSON object in env).

## OpenClaw integration

OpenClaw expects an OpenAI-compatible TTS endpoint. Run this server locally and configure OpenClaw to use:

- **Base URL**: `http://127.0.0.1:8000` (or the address where you host the server)
- **Endpoint**: `/v1/audio/speech`
- **API key**: optional (only if you enabled `REQUIRE_AUTH`)

### Recommended OpenClaw configuration
Add the following to the OpenClaw configuration (for example, ~/.openclaw/openclaw.json):

**Required** (so OpenClaw sends TTS requests to this local server and does not require a real key):

```json
"env": {
  "OPENAI_TTS_BASE_URL": "http://127.0.0.1:8000/v1",
  "OPENAI_API_KEY": "dummy-local-key"
}
```

- `OPENAI_TTS_BASE_URL` — the base URL of the OpenAI‑compatible API (important: with the `/v1` suffix).
- `OPENAI_API_KEY` — “placeholder”: many clients require some key in the configuration even for a local endpoint; if you enable `REQUIRE_AUTH`, use the same token here as the server's `API_KEY`.

**Recommended** (auto-speech + default voice, with Edge TTS disabled):

```json
"messages": {
  "ackReactionScope": "group-mentions",
  "tts": {
    "provider": "openai",
    "auto": "always",
    "mode": "final",
    "openai": { "voice": "alloy" },
    "edge": { "enabled": false }
  }
}
```

Result: OpenClaw gets local speech synthesis with lower latency and no external calls.

---

## Configuration

Configuration is defined through environment variables (loaded from `.env`).

### Network

- `HOST` (default: `0.0.0.0`) — interface to listen on. Use `127.0.0.1` to restrict access to the local machine only.
- `PORT` (default: `8000`) — port to listen on.

### Silero model

- `SILERO_LANGUAGE` (default: `ru`) — language code (for ex.: `ru`, `en`).
- `SILERO_MODEL_ID` (default: `v5_1_ru`) — Silero model ID for the selected language (for ex.: `v5_ru`, `v4_ru`).
- `SILERO_SAMPLE_RATE` (default: `48000`) — output sample rate in Hz (default values: `8000`, `24000`, `48000`).
- `SILERO_DEVICE` (default: `cpu`) — `cpu` or `cuda`.
- `SILERO_NUM_THREADS` (default: `0`) — inference threads (`0` = авто).
- `SILERO_DEFAULT_SPEAKER` (default: `kseniya`) — speaker used when `voice` is unknown/unmapped.
- `SILERO_MODELS_DIR` (default: `models`) — directory for downloaded models (if your implementation preserves them).

### Authentication

- `REQUIRE_AUTH` (default: `false`) — if `true`, requests must include `Authorization: Bearer ...`.
- `API_KEY` (default: `dummy-local-key`) — expected Bearer token.

### Cache

- `CACHE_DIR` (default: `.cache_tts`) — directory where generated audio is cached.
- `CACHE_MAX_FILES` (default: `2000`) — maximum number of files in the cache (oldest files are removed when exceeded).

### Audio encoding

- `FFMPEG_BIN` (default: `ffmpeg`) — path to the FFmpeg binary.
- `FFPLAY_BIN` (default: `ffplay`) — path to the FFplay binary (used for automatic playback).
- `AUTO_PLAY` (default: `false`) — если `true`, generated audio is automatically played through the server's audio output device. `ffplay` is required (included with ffmpeg).

## Additional options  
- `AUTO_PLAY_SHOW_SKIP_WINDOW` (default: `true`) — if `true`, a local Tkinter window with a **“Skip”** button is shown during server-side playback; the button is hidden after playback ends.
- `FORCE_PLAY` (default: `false`) — force-enable server-side audio playback (CLI override). When enabled, text is also printed to the console before synthesis.
- `SHOW_TEXT` (default: `false`) — print text to the console before synthesis (CLI override).

---

## Voice mapping

The server accepts **OpenAI voice names** and maps them to Silero speakers. Example mapping:

| OpenAI voice | Silero speaker (example) |
|---|---|
| `alloy` | `baya` |
| `echo` | `aidar` |
| `fable` | `kseniya` |
| `onyx` | `eugene` |
| `nova` | `xenia` |
| `shimmer` | `baya` |

You can also pass a Silero speaker directly (ex.: `aidar`, `baya`, `kseniya`, `xenia`, `eugene`, `random`).

---

## Text normalization (numbers, currencies, etc.)

Before synthesis, the input text passes through a small normalizer that:

- expands integers (например: `5` → `five` / `пять`);
- expands patterns such as `10%` and `21 ₽`;
- in Russian, inflects neighboring nouns according to the number (more natural grammar).

---

## Troubleshooting

- **Cannot output MP3/OPUS/AAC/FLAC**: make sure `ffmpeg`, и `FFMPEG_BIN` points on it.
- **CUDA unused**: make sure your PyTorch build supports CUDA and `SILERO_DEVICE=cuda`.
- **First launch is slow**: the model is downloaded the first time. Subsequent starts are faster.
- **No sound / audio is corrupted**: first try `response_format: "wav"`, to isolate encoding problems.
- **`HTTP Error 403: rate limit exceeded` on the first launch**: `torch.hub` accesses the GitHub API to check the repository and hits the limit of anonymous requests (60 per hour per IP). Options:
  - set the environment variable `GITHUB_TOKEN` with a [personal access token](https://github.com/settings/tokens) (The limit will rise to 5,000 per hour.);
  - or create `.venv\Lib\site-packages\sitecustomize.py` with the following workaround:
    ```python
    import torch
    torch.hub._validate_not_a_forked_repo = lambda a, b, c: True

---

## License

The project is distributed under the **MIT License** (a permissive, “free” license).
The Silero models themselves have their own licensing terms — please check the upstream Silero repository for details.

---

## Acknowledgements

- [Silero Models](https://github.com/snakers4/silero-models) — the TTS models underlying the project.
- [OpenClaw](https://github.com/openclaw/openclaw) — the chatbot project this server was created to support.
