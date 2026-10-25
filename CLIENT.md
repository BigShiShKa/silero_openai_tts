# Console client

Windows is the primary platform. Install the client extras and use the unified CLI:

```powershell
python -m pip install -e ".[client]"
silero-tts console
silero-tts speak --voice aidar --speed 1.2 "Hello"
silero-tts speak --output greeting.wav "Hello"
silero-tts server --host 127.0.0.1 --port 8000
```

`silero-tts` without a subcommand still starts the server; legacy server flags work too. Use `silero-tts --help` or subcommand `--help` for options.

## Connection and ownership

The default base URL is `http://127.0.0.1:8000`, without `/v1`. Override it with `--url`. Only a local HTTP server is automatically started; remote and HTTPS servers must already be running. Use `--no-start` to disable automatic startup.

Readiness requires HTTP 200 from `/health`, service `silero-openai-tts`, status `ready`, and a server playback flag. Update older servers without this endpoint. An occupied port with an unrelated service is an error; the client does not choose another port.

On exit, Ctrl+C, or failure, the client shuts down only its own server, first gracefully over a private stdin channel, then forcibly after eight seconds. A Windows Job Object also terminates the owned server tree when the launcher closes. Existing servers are never stopped.

Client and server playback are mutually exclusive. Disable `AUTO_PLAY` and `FORCE_PLAY` on an existing server before connecting. Automatically started servers have these options and `SHOW_TEXT` disabled in their process environment.

## Preferences and authentication

Default configuration: `%APPDATA%\silero-tts\client.json` on Windows; `${XDG_CONFIG_HOME:-~/.config}/silero-tts/client.json` elsewhere. Override with `--config`.

Precedence: CLI > `SILERO_CLIENT_*` environment variables > JSON > defaults. JSON fields:

```json
{
  "url": "http://127.0.0.1:8000",
  "voice": "eugene",
  "speed": 1.0,
  "device": null,
  "connect_timeout": 3,
  "read_timeout": 120,
  "startup_timeout": 120
}
```

Voice, speed and device preferences are saved automatically. Connection overrides and API keys are not implicitly persisted. Supply a Bearer token through `SILERO_CLIENT_API_KEY`, `--api-key`, or an explicit JSON `api_key` field. Other environment variables follow the same pattern, e.g. `SILERO_CLIENT_READ_TIMEOUT`.

Timeouts are in seconds and configurable with `--connect-timeout`, `--read-timeout`, and `--startup-timeout`. Only connection failures before transmitting a request receive one retry. Read timeouts, broken responses, and HTTP failures do not trigger a repeat synthesis.

## Audio and console commands

Defaults: voice `eugene`, speed `1.0`, system default output device. Playback uses WAV. Speeds from 0.25 to 4.0 are supported; changing speed requires FFmpeg on the server.

Commands: `/voice <name> [text]` (`/v`), `/voices` (`/list`), `/speed <number>`, `/devices`, `/device <index>`, `/device default`, `/status`, `/help`, `exit`. Ctrl+C always exits.

Use `/monitor on|off` to mirror audio to the system default output while keeping playback on the selected device. `/monitor` toggles it. The preference persists between runs (JSON `monitor`, environment `SILERO_CLIENT_MONITOR=true|false`, CLI `--monitor` / `--no-monitor`) and defaults to off. Selecting the default output already plays once; monitoring does not duplicate it. Both streams run in the client and stop on Ctrl+C, so server `FORCE_PLAY` remains disabled. If the default output is unavailable, playback reports an error.

Device preferences store the full name and host API instead of an unstable index. `--device` accepts the full name shown by `/devices`, or `default`. If a saved device is unavailable, the user is prompted to choose another; without an interactive terminal, the operation fails. Duplicate device names may require selection again.

Input remains line-based, limited to 4096 characters per request. File/stdin input and multiline editing are not implemented. Playback is sequential in this first stage; concurrent input and a phrase queue are planned next.

No recording is saved by default. `speak --output path.wav` saves and plays WAV; existing files are never overwritten. Server caching is independent. Save-only mode and automatic recording of all phrases are not implemented.

## Compatibility and diagnostics

`python run_tts.py` and `run_tts.bat` start the console, or speak command-line text once. `python speak.py` connects to an existing server only. The legacy desktop shortcut behavior remains available through `run_tts.py`.

Exit codes: 0 success/normal exit, 1 operation failure, 2 invalid arguments, 130 Ctrl+C. Interactive phrase errors are reported while keeping the console open.

Rotating logs live in `logs/` beside the configuration: `client.log` (1 MB) and `server.log` (2 MB, automatically started server only), each with three backups. The client does not log spoken text or keys; text logging is disabled for its child server. Existing servers manage their own logs.

Implementation: `app/client/`; tests: `python -m pytest tests/test_client.py -q`. See [the Russian guide](CLIENT_RU.md) for details.
