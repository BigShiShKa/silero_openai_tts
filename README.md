# Silero TTS, compatible with the OpenAI API and ElevenLabs API + Console client

**Local**, self-hosted speech synthesis (Text-to-Speech, TTS) server implementing both **OpenAI TTS API** (`POST /v1/audio/speech`)
and an **ElevenLabs-compatible API** (`POST /v1/text-to-speech/{voice_id}`, `GET /v1/voices`, `GET /v1/models`).

The main goal of the project is to provide a **“drop-in and works” TTS backend**, compatible with OpenAI- and ElevenLabs-style clients, for
[OpenClaw](https://github.com/openclaw/openclaw) — so OpenClaw can speak without relying on external cloud services.
At the same time, this server works with **any** project that expects an OpenAI-compatible and/or ElevenLabs-compatible TTS endpoint: simply configure the
client to use this server's base URL.

A key feature of this fork is the **built-in standalone console client**,
which starts and stops the server itself, waits for it to become ready, provides an interactive
REPL with voice, speed and output device selection, and can also speak text passed as a
command-line argument. Windows is the primary client platform; portable paths are
provided for other platforms, but their complete startup workflow has not been verified.

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
- **Optional ElevenLabs-compatible mode**: can send `POST /v1/text-to-speech/{voice_id}` и `GET /v1/voices` for clients with ElevenLabs-style contract.
- **Designed for OpenClaw**, but it works with any OpenAI‑compatible client.
- **Standalone console client** (Windows): It launches the server in the background,
  waits for readiness, runs REPL with voice changes, correctly shuts down the server
  by `exit`, `Ctrl+C` and window closing.
- **Russian and English support** (auto recognition).
- **Natural number reading**:
  - expands integers into words;
  - for Russian, matches noun forms to numbers (for ex.: “21 рубль / 22 рубля / 25 рублей”);
  - expands common patterns such as `%` and `₽` (the ruble symbol).
- **Multiple voices**:
  - accepts OpenAI voice names (`alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`) and maps them to Silero speakers;
  - also accepts Silero speaker IDs directly (for ex.: `baya`, `aidar`, `kseniya`, `xenia`, `eugene`, `random`).
- **Multiple output formats**: `wav`, `mp3`, `opus`, `aac`, `flac`.
- **Speed control** (`0.25`–`4.0`) using FFmpeg audio filters.
- **Disk cache**, so as not to re‑synthesize the same phrase over and over again.
- **Optional API key** (Bearer token) for private deployments.
- **Runs on CPU by default**, with optional GPU (CUDA) support, if your PyTorch build supports it.

---

## Quick start

### 0) Clone the repository

```bash
git clone https://github.com/BigShiShKa/silero_openai_tts/
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

[Console client guide](CLIENT.md)

Install the client extras: `python -m pip install -e ".[client]"`.

```powershell
silero-tts console
silero-tts speak --voice eugene "Hello"
silero-tts server --host 127.0.0.1 --port 8000
```

The client starts a local server when needed and stops only its own server on exit.
`silero-tts` without a subcommand still starts the server. `run_tts.bat` and
`python run_tts.py` open the interactive console.

Commands: `/voice <name>`, `/speed <0.25–4>`, `/devices`, `/device <index>`,
`/device default`, `/monitor on|off`, `/status`, `/help`, `exit`.

`/monitor on` mirrors audio to the system default speakers/headphones while keeping
output on the selected device, such as a virtual microphone. Monitoring defaults to off
and its setting persists. Server `FORCE_PLAY` is not required.

Voice, speed, device and monitoring preferences are saved in `%APPDATA%\silero-tts\client.json`.
Supply the server URL and key through `--url` and `SILERO_CLIENT_API_KEY`.
WAV recordings are not saved by default; add `speak --output <file.wav>` to save one.
Ctrl+C exits the client and its owned server. Readiness is checked through `/health`.

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
