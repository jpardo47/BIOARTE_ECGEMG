import numpy as np

from app.audio_engine import AudioEngine
from app.config import AppConfig


def test_note_mapping_and_volume_limits():
    config = AppConfig(volume_min=0.12, volume_max=0.72, pentatonic=(48, 50, 52, 55, 57))
    engine = AudioEngine(config)
    assert engine.level_to_note(0) == 48
    assert engine.level_to_note(0.99) == 57
    assert engine.level_to_note(float("nan")) == 48
    assert engine.volume_for_level(0) == 0.12
    assert np.isclose(engine.volume_for_level(1), 0.72)
    assert 0.12 <= engine.volume_for_level(0.5) <= 0.72


def test_missing_device_or_file_is_nonfatal(monkeypatch):
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    engine = AudioEngine(AppConfig())
    assert engine.start("music", "missing-file.mp3") is False
    assert "archivo" in engine.error.lower()
    assert engine.enabled is False
    assert engine.start("unknown") is False
    assert engine.enabled is False


def test_dummy_audio_generates_notes_and_stops():
    import pytest

    pytest.importorskip("pygame")
    # SDL dummy provides a device-free mixer for CI and headless desktops.
    import os

    os.environ["SDL_AUDIODRIVER"] = "dummy"
    engine = AudioEngine(AppConfig(note_duration_s=0.06, note_interval_s=0.05))
    if not engine.start("generative"):
        pytest.skip(engine.error or "Pygame mixer unavailable")
    engine.update(0.1)
    engine.update(0.8)
    engine.update(0.8, r_peak=True)
    engine.stop()
    assert engine.enabled is False
