"""Compatibility wrapper: use an already running server."""
import sys
from app.cli import main

if __name__ == "__main__":
    command = "speak" if len(sys.argv) > 1 else "console"
    sys.exit(main([command, "--no-start", *sys.argv[1:]]))
