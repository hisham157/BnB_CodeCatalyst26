import run


def test_existing_backend_is_reused(monkeypatch, capsys):
    monkeypatch.setattr(run, "backend_is_running", lambda: True)
    monkeypatch.setattr(run.subprocess, "call", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Duplicate process")))
    assert run.main() == 0
    assert "already running" in capsys.readouterr().out


def test_unrelated_or_reserved_port_is_not_taken_over(monkeypatch, capsys):
    monkeypatch.setattr(run, "backend_is_running", lambda: False)
    monkeypatch.setattr(run, "port_available", lambda: False)
    assert run.main() == 1
    assert "No process was stopped" in capsys.readouterr().out


def test_free_port_starts_backend_with_same_interpreter(monkeypatch):
    calls = []
    monkeypatch.setattr(run, "backend_is_running", lambda: False)
    monkeypatch.setattr(run, "port_available", lambda: True)
    monkeypatch.setattr(run.subprocess, "call", lambda command, **kwargs: calls.append((command, kwargs)) or 0)
    assert run.main(reload=True) == 0
    assert calls[0][0][0] == run.sys.executable
    assert calls[0][0][-1] == "--reload"
    assert calls[0][1]["cwd"] == run.BACKEND


def test_simultaneous_launch_reuses_winning_server(monkeypatch):
    states = iter([False, True])
    monkeypatch.setattr(run, "backend_is_running", lambda: next(states))
    monkeypatch.setattr(run, "port_available", lambda: True)
    monkeypatch.setattr(run.subprocess, "call", lambda *a, **k: 1)
    assert run.main() == 0
