"""Owned server: private stdin shutdown channel, no unauthenticated stop endpoint."""
import argparse
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading
import time

import uvicorn


def watch_parent(server):
    """Wait for data/EOF without blocking a Windows pipe read during DLL imports."""
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        peek = kernel32.PeekNamedPipe
        peek.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                         ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        peek.restype = wintypes.BOOL
        handle = msvcrt.get_osfhandle(0)
        available = wintypes.DWORD()
        # A blocking read on the inherited pipe can deadlock native DLL loading.
        # We only need to detect a shutdown message or a closed parent pipe.
        while peek(handle, None, 0, None, ctypes.byref(available), None):
            if available.value:
                break
            time.sleep(0.1)
        else:
            error = ctypes.get_last_error()
            if error not in (109, 232, 233):  # broken/disconnected pipe
                logging.getLogger("silero.launcher").warning("Shutdown pipe failed: WinError %s", error)
    else:
        os.read(0, 1024)
    server.should_exit = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--log-dir", type=Path, required=True)
    args = parser.parse_args()
    handler = RotatingFileHandler(args.log_dir / "server.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    server = uvicorn.Server(uvicorn.Config("app.main:app", host=args.host, port=args.port, log_config=None))

    threading.Thread(target=watch_parent, args=(server,), daemon=True).start()
    try:
        server.run()
    except BaseException:
        logging.getLogger("silero.launcher").exception("Owned server stopped with an error")
        raise


if __name__ == "__main__":
    main()
