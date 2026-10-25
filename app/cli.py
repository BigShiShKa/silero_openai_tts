"""Server and console entry points; client dependencies are loaded on demand."""
import argparse
import os
import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Preserve legacy server flags, while exposing top-level help.
    if not argv or (argv[0].startswith("-") and argv[0] not in ("--help", "-h")):
        argv.insert(0, "server")
    parser = argparse.ArgumentParser(description="Silero TTS")
    commands = parser.add_subparsers(dest="command", required=True)
    server = commands.add_parser("server", help="Run the HTTP server")
    server.add_argument("--host", default="0.0.0.0")
    server.add_argument("--port", type=int, default=8000)
    server.add_argument("--force-play", action="store_true")
    server.add_argument("--show-text", action="store_true")
    for name in ("speak", "console"):
        command = commands.add_parser(name, help="Speak text" if name == "speak" else "Interactive console")
        command.add_argument("--config")
        command.add_argument("--url", help="Server base URL, without /v1")
        command.add_argument("--api-key")
        command.add_argument("--voice")
        command.add_argument("--speed", type=float)
        command.add_argument("--device", help="Output device name or 'default'")
        command.add_argument("--monitor", action=argparse.BooleanOptionalAction, default=None,
                             help="Also play on the system default output device")
        command.add_argument("--connect-timeout", type=float)
        command.add_argument("--read-timeout", type=float)
        command.add_argument("--startup-timeout", type=float)
        command.add_argument("--no-start", action="store_true", help="Use an existing server only")
        if name == "speak":
            command.add_argument("--output", help="Also save the WAV to this path")
            command.add_argument("text", nargs="+", help="Text to speak")
    args = parser.parse_args(argv)
    if args.command == "server":
        if args.force_play:
            os.environ["FORCE_PLAY"] = "true"
        if args.show_text:
            os.environ["SHOW_TEXT"] = "true"
        import uvicorn
        uvicorn.run("app.main:app", host=args.host, port=args.port, reload=False)
        return 0
    try:
        from app.client.session import run
        return run(args)
    except KeyboardInterrupt:
        print("\nПрервано пользователем.")
        return 130
    except ImportError:
        print('Для клиента установите зависимости: pip install -e ".[client]"', file=sys.stderr)
        return 1
    except (ValueError, OSError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
