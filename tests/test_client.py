import argparse
import io
import json
import os
from unittest.mock import Mock

import numpy as np
import pytest
import requests
import soundfile as sf

from app import cli
from app.client import session, launcher
from app.client.config import ClientConfig, load_config, save_preferences


@pytest.fixture
def config():
    return ClientConfig()


def test_configuration_precedence_and_private_preferences(tmp_path, monkeypatch):
    path = tmp_path / "client.json"
    path.write_text(json.dumps({"voice": "baya", "speed": 1.5, "api_key": "stored"}))
    monkeypatch.setenv("SILERO_CLIENT_VOICE", "aidar")
    monkeypatch.setenv("SILERO_CLIENT_SPEED", "2")
    config = load_config(path, argparse.Namespace(voice="eugene", api_key="temporary"))
    assert (config.voice, config.speed, config.api_key) == ("eugene", 2, "temporary")
    save_preferences(path, config)
    assert json.loads(path.read_text())["api_key"] == "stored"


@pytest.mark.parametrize("settings", [{"speed": 0}, {"speed": float("nan")}, {"read_timeout": -1}, {"url": "http://localhost/v1"}, {"url": "http://user:key@localhost"}, {"device": 18}])
def test_invalid_settings_rejected(settings):
    with pytest.raises(ValueError):
        ClientConfig(**settings).validate()


def test_corrupt_config_is_not_overwritten(tmp_path):
    path = tmp_path / "client.json"
    path.write_text("broken")
    with pytest.raises(ValueError):
        load_config(path, argparse.Namespace())
    assert path.read_text() == "broken"


def test_cli_preserves_server_flags(monkeypatch):
    uvicorn = Mock()
    monkeypatch.setitem(__import__("sys").modules, "uvicorn", uvicorn)
    assert cli.main(["--host", "127.0.0.1", "--port", "8123"]) == 0
    assert uvicorn.run.call_args.kwargs["port"] == 8123


def test_cli_client_failure_and_interrupt_exit_codes(monkeypatch):
    monkeypatch.setattr(session, "run", Mock(side_effect=ValueError("bad config")))
    assert cli.main(["speak", "hello"]) == 1
    monkeypatch.setattr(session, "run", Mock(side_effect=KeyboardInterrupt))
    assert cli.main(["console"]) == 130


def response(data=None, status=200, content=b""):
    result = Mock(status_code=status, content=content)
    result.json.return_value = data
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    return result


@pytest.mark.parametrize("data,status", [({"service": "other"}, 200), ({"service": "silero-openai-tts", "status": "ready", "server_playback": False}, 500), ([], 200)])
def test_health_rejects_unrelated_service(config, monkeypatch, data, status):
    monkeypatch.setattr(launcher.requests, "get", Mock(return_value=response(data, status)))
    assert launcher.probe(config) is None


def test_busy_port_never_starts_process(config, tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "probe", lambda _: None)
    monkeypatch.setattr(launcher, "port_open", lambda *_: True)
    popen = Mock()
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    with pytest.raises(launcher.ClientError, match="занят"):
        with launcher.ServerSession(config, tmp_path):
            pass
    popen.assert_not_called()


def test_existing_server_is_not_stopped(config, tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "probe", lambda _: {"server_playback": False})
    popen = Mock()
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    with launcher.ServerSession(config, tmp_path):
        pass
    popen.assert_not_called()


def test_server_playback_refused(config, tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "probe", lambda _: {"server_playback": True})
    with pytest.raises(launcher.ClientError, match="AUTO_PLAY"):
        with launcher.ServerSession(config, tmp_path):
            pass


def test_remote_server_is_never_started(config, tmp_path, monkeypatch):
    config.url = "http://example.invalid:8000"
    monkeypatch.setattr(launcher, "probe", lambda _: None)
    popen = Mock()
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    with pytest.raises(launcher.ClientError):
        with launcher.ServerSession(config, tmp_path):
            pass
    popen.assert_not_called()


def test_early_server_exit_releases_job(config, tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "probe", lambda _: None)
    monkeypatch.setattr(launcher, "port_open", lambda *_: False)
    job = object()
    monkeypatch.setattr(launcher, "create_kill_on_close_job", lambda: job)
    monkeypatch.setattr(launcher, "assign_pid_to_job", Mock())
    closed = Mock()
    monkeypatch.setattr(launcher, "close_job", closed)
    proc = Mock()
    proc.poll.return_value = 1
    monkeypatch.setattr(launcher.subprocess, "Popen", Mock(return_value=proc))
    with pytest.raises(launcher.ClientError, match="завершился"):
        with launcher.ServerSession(config, tmp_path):
            pass
    closed.assert_called_once_with(job)
    proc.stdin.close.assert_called_once()


def test_graceful_shutdown_on_interrupt(config, tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "probe", lambda _: {"server_playback": False})
    monkeypatch.setattr(launcher, "close_job", Mock())
    proc = Mock()
    proc.poll.return_value = None
    with pytest.raises(KeyboardInterrupt):
        with launcher.ServerSession(config, tmp_path) as owner:
            owner.proc = proc
            raise KeyboardInterrupt
    proc.stdin.write.assert_called_once_with(b"shutdown\n")
    proc.wait.assert_called_once_with(timeout=8)


def test_connection_only_retry_policy(config):
    config.api_key = "secret"
    with session.http_session(config) as client:
        retry = client.get_adapter(config.url).max_retries
        assert retry.connect == 1
        assert retry.read == retry.status == retry.other == 0
        assert client.headers["Authorization"] == "Bearer secret"


def test_missing_device_prompts_and_persists(config, tmp_path, monkeypatch):
    config.device = "disconnected"
    monkeypatch.setattr(session, "output_devices", lambda: [(3, "Speakers [WASAPI]")])
    monkeypatch.setattr("builtins.input", lambda _: "3")
    path = tmp_path / "client.json"
    assert session.choose_device(config, path, True) == 3
    assert json.loads(path.read_text())["device"] == "Speakers [WASAPI]"


def test_missing_device_noninteractive_fails(config, tmp_path, monkeypatch):
    config.device = "disconnected"
    monkeypatch.setattr(session, "output_devices", lambda: [(3, "Speakers [WASAPI]")])
    with pytest.raises(launcher.ClientError):
        session.choose_device(config, tmp_path / "client.json", False)


def test_device_prompt_eof_is_a_clean_failure(config, tmp_path, monkeypatch):
    config.device = "disconnected"
    monkeypatch.setattr(session, "output_devices", lambda: [(3, "Speakers [WASAPI]")])
    monkeypatch.setattr("builtins.input", Mock(side_effect=EOFError))
    with pytest.raises(launcher.ClientError, match="ввод завершён"):
        session.choose_device(config, tmp_path / "client.json", True)


def wav_bytes():
    buf = io.BytesIO()
    sf.write(buf, np.zeros(48, dtype="float32"), 48000, format="WAV")
    return buf.getvalue()


def test_audio_optional_save_and_no_text_in_logs(config, tmp_path, monkeypatch, caplog):
    wav = wav_bytes()
    client = Mock()
    client.post.return_value = response(content=wav)
    monkeypatch.setattr(session, "choose_device", lambda *_: None)
    monkeypatch.setattr(session.sd, "play", Mock())
    monkeypatch.setattr(session.sd, "wait", Mock())
    monkeypatch.setattr(session.sd, "stop", Mock())
    with caplog.at_level("INFO", logger="silero.client"):
        session.speak(client, config, tmp_path / "client.json", "private sentence")
    assert list(tmp_path.iterdir()) == []
    assert "private sentence" not in caplog.text
    output = tmp_path / "recording.wav"
    session.speak(client, config, tmp_path / "client.json", "private sentence", output=output)
    assert output.read_bytes() == wav
    with pytest.raises(FileExistsError):
        session.speak(client, config, tmp_path / "client.json", "test", output=output)


def test_read_timeout_does_not_repeat_synthesis(config, tmp_path, monkeypatch):
    client = Mock()
    client.post.side_effect = requests.ReadTimeout()
    monkeypatch.setattr(session, "choose_device", lambda *_: None)
    with pytest.raises(launcher.ClientError, match="не повторён"):
        session.speak(client, config, tmp_path / "client.json", "hello")
    assert client.post.call_count == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows handle lifecycle")
def test_windows_job_uses_pointer_sized_handles():
    import ctypes
    from app.client import jobobject
    assert ctypes.sizeof(jobobject._kernel32.CreateJobObjectW.restype) == ctypes.sizeof(ctypes.c_void_p)
    job = jobobject.create_kill_on_close_job()
    jobobject.close_job(job)


@pytest.mark.skipif(os.name != "nt", reason="Windows process ownership")
def test_windows_job_closing_terminates_owned_child():
    import subprocess
    import sys
    from app.client import jobobject
    job = jobobject.create_kill_on_close_job()
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        jobobject.assign_pid_to_job(job, child.pid)
        jobobject.close_job(job)
        job = None
        child.wait(timeout=5)
        assert child.returncode is not None
    finally:
        if job is not None:
            jobobject.close_job(job)
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_health_contract_without_loading_models(app):
    from fastapi.testclient import TestClient
    from app.api.health import router
    app.state.settings.auto_play = False
    app.state.settings.force_play = False
    app.include_router(router)
    with TestClient(app) as client:
        result = client.get("/health")
        assert result.status_code == 200
        assert result.json() == {"service": "silero-openai-tts", "status": "ready", "server_playback": False}
        app.state.settings.force_play = True
        assert client.get("/health").json()["server_playback"] is True


def test_unauthorized_speech_is_a_failure(config, tmp_path, monkeypatch):
    client = Mock()
    client.post.return_value = response(status=401)
    monkeypatch.setattr(session, "choose_device", lambda *_: None)
    with pytest.raises(launcher.ClientError, match="API key"):
        session.speak(client, config, tmp_path / "client.json", "test")


def test_shutdown_timeout_forces_only_owned_pid(config, tmp_path, monkeypatch):
    import subprocess
    owner = launcher.ServerSession(config, tmp_path)
    proc = Mock(pid=12345)
    proc.poll.return_value = None
    proc.wait.side_effect = [subprocess.TimeoutExpired("server", 8), 0]
    owner.proc = proc
    kill = Mock()
    monkeypatch.setattr(launcher.subprocess, "run", kill)
    monkeypatch.setattr(launcher, "close_job", Mock())
    owner.close()
    if os.name == "nt":
        assert kill.call_args.args[0] == ["taskkill", "/PID", "12345", "/T", "/F"]
    else:
        proc.kill.assert_called_once()


def test_console_changes_are_saved(config, tmp_path, monkeypatch):
    lines = iter(["/voice aidar", "/speed 1.5", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(lines))
    path = tmp_path / "client.json"
    assert session.console(Mock(), config, path) == 0
    assert json.loads(path.read_text()) == {"voice": "aidar", "speed": 1.5, "device": None, "monitor": False}


def test_monitor_preference_cli_environment_and_persistence(tmp_path, monkeypatch):
    path = tmp_path / "client.json"
    monkeypatch.setenv("SILERO_CLIENT_MONITOR", "true")
    config = load_config(path, argparse.Namespace())
    assert config.monitor is True
    save_preferences(path, config)
    assert json.loads(path.read_text())["monitor"] is True
    assert load_config(path, argparse.Namespace(monitor=False)).monitor is False
    monkeypatch.setenv("SILERO_CLIENT_MONITOR", "invalid")
    with pytest.raises(ValueError):
        load_config(path, argparse.Namespace())


def test_monitor_console_switches_and_remembers(config, tmp_path, monkeypatch):
    lines = iter(["/monitor on", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(lines))
    path = tmp_path / "client.json"
    session.console(Mock(), config, path)
    assert config.monitor is True
    assert json.loads(path.read_text())["monitor"] is True
    lines = iter(["/monitor", "exit"])
    session.console(Mock(), config, path)
    assert config.monitor is False


@pytest.mark.parametrize("device", [None, 7])
def test_monitor_does_not_duplicate_default_output(device, monkeypatch):
    monkeypatch.setattr(session.sd, "default", Mock(device=[-1, 7]))
    play = Mock()
    monkeypatch.setattr(session.sd, "play", play)
    monkeypatch.setattr(session.sd, "wait", Mock())
    output_stream = Mock()
    monkeypatch.setattr(session.sd, "OutputStream", output_stream)
    audio = np.zeros(5, dtype="float32")
    session.play_audio(audio, 48000, device, True)
    assert play.call_count == 1
    output_stream.assert_not_called()


def test_monitor_streams_each_receive_complete_audio(monkeypatch):
    monkeypatch.setattr(session.sd, "default", Mock(device=[-1, 7]))
    streams = []

    class Stream:
        def __init__(self, **kwargs):
            self.device = kwargs["device"]
            self.callback = kwargs["callback"]
            self.active = False
            self.chunks = []
            self.closed = self.aborted = False
            streams.append(self)

        def start(self):
            while True:
                block = np.empty((3, 1), dtype="float32")
                try:
                    self.callback(block, 3, None, None)
                except session.sd.CallbackStop:
                    self.chunks.append(block.copy())
                    break
                self.chunks.append(block.copy())

        def abort(self):
            self.aborted = True

        def close(self):
            self.closed = True

    monkeypatch.setattr(session.sd, "OutputStream", Stream)
    audio = np.arange(5, dtype="float32")
    session.play_audio(audio, 48000, 3, True)
    assert [stream.device for stream in streams] == [3, None]
    for stream in streams:
        played = np.concatenate(stream.chunks)[:, 0]
        np.testing.assert_array_equal(played[:5], audio)
        assert played[5] == 0
        assert stream.closed and stream.aborted


def test_monitor_interrupt_stops_both_streams(monkeypatch):
    monkeypatch.setattr(session.sd, "default", Mock(device=[-1, 7]))
    streams = [Mock(active=True), Mock(active=True)]
    monkeypatch.setattr(session.sd, "OutputStream", Mock(side_effect=streams))
    monkeypatch.setattr(session.sd, "sleep", Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        session.play_audio(np.zeros(5, dtype="float32"), 48000, 3, True)
    for stream in streams:
        stream.abort.assert_called_once()
        stream.close.assert_called_once()


def test_missing_monitor_closes_primary_before_playback(monkeypatch):
    monkeypatch.setattr(session.sd, "default", Mock(device=[-1, 7]))
    primary = Mock()
    monkeypatch.setattr(session.sd, "OutputStream", Mock(side_effect=[primary, session.sd.PortAudioError("missing")]))
    with pytest.raises(session.sd.PortAudioError):
        session.play_audio(np.zeros(5, dtype="float32"), 48000, 3, True)
    primary.start.assert_not_called()
    primary.close.assert_called_once()


@pytest.mark.parametrize("shutdown", [b"shutdown\n", None])
def test_shutdown_watcher_allows_native_imports_and_detects_parent(tmp_path, shutdown):
    """Keep stdin open during NumPy/Torch import, then test data and EOF shutdown."""
    import subprocess
    import sys
    import time

    ready = tmp_path / "ready"
    script = """
import sys, threading, time
from pathlib import Path
from types import SimpleNamespace
from app.client.server import watch_parent
server = SimpleNamespace(should_exit=False)
thread = threading.Thread(target=watch_parent, args=(server,), daemon=True)
thread.start()
import numpy
import torch
Path(sys.argv[1]).write_text('ready')
thread.join(timeout=10)
sys.exit(0 if server.should_exit else 1)
"""
    child = subprocess.Popen([sys.executable, "-c", script, str(ready)],
                             stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        deadline = time.monotonic() + 20
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        assert ready.exists(), "Native imports hung while the parent shutdown pipe was open"
        if shutdown is not None:
            child.stdin.write(shutdown)
            child.stdin.flush()
        else:
            child.stdin.close()
        child.wait(timeout=5)
        assert child.returncode == 0, child.stderr.read().decode(errors="replace")
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        if not child.stdin.closed:
            child.stdin.close()
        child.stderr.close()
