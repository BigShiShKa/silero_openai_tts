"""Compatibility wrapper for the interactive client and one-shot speech."""
import sys
from app.cli import main

if __name__ == "__main__":
    from app.client.shortcut import _ensure_desktop_shortcut
    _ensure_desktop_shortcut()
    command = "speak" if len(sys.argv) > 1 else "console"
    sys.exit(main([command, *sys.argv[1:]]))
