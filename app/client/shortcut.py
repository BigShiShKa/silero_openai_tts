"""Legacy desktop shortcut support for run_tts.py."""
import os
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
BAT_SCRIPT    = PROJECT_DIR / "run_tts.bat"
ICON_FILE     = PROJECT_DIR / "silero.ico"

# ==== Ярлык на рабочем столе ====
CREATE_DESKTOP_SHORTCUT = True       # создавать ярлык при запуске, если его нет
SHORTCUT_NAME = "Silero TTS"         # имя файла ярлыка (без .lnk)

# =======================  Ярлык на рабочем столе  =======================

def _desktop_dir() -> Path | None:
    """Рабочий стол текущего пользователя (учитывает OneDrive-редирект)."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        # CSIDL_DESKTOPDIRECTORY = 0x0010
        res = ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)
        if res == 0 and buf.value:
            return Path(buf.value)
    except Exception:
        pass
    d = Path.home() / "Desktop"
    return d if d.exists() else None


def _ps_quote(s: str) -> str:
    """Обернуть строку в одинарные кавычки для PowerShell."""
    return "'" + str(s).replace("'", "''") + "'"


def _ensure_desktop_shortcut() -> None:
    """Создать ярлык на рабочем столе на run_tts.bat, если его ещё нет."""
    if not CREATE_DESKTOP_SHORTCUT or os.name != "nt":
        return
    if not BAT_SCRIPT.exists():
        print(f"[warn] нет {BAT_SCRIPT.name} — ярлык не создаю.")
        return

    desktop = _desktop_dir()
    if desktop is None:
        return

    lnk = desktop / f"{SHORTCUT_NAME}.lnk"
    if lnk.exists():
        return  # уже есть — не трогаем

    icon = ICON_FILE if ICON_FILE.exists() else BAT_SCRIPT
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut({_ps_quote(str(lnk))}); "
        f"$s.TargetPath = {_ps_quote(str(BAT_SCRIPT))}; "
        f"$s.WorkingDirectory = {_ps_quote(str(PROJECT_DIR))}; "
        f"$s.IconLocation = {_ps_quote(f'{icon},0')}; "
        "$s.Save()"
    )
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            creationflags=creationflags, timeout=15,
        )
        if r.returncode == 0:
            print(f"Создан ярлык на рабочем столе: {lnk.name}")
        else:
            err = r.stderr.decode(errors="ignore").strip()
            print(f"[warn] не удалось создать ярлык: {err}")
    except Exception as e:
        print(f"[warn] не удалось создать ярлык: {e}")
