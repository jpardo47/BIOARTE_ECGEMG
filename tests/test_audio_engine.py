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


def test_device_initialization_error_is_controlled(monkeypatch):
    import pygame

    def fail(**kwargs):
        raise pygame.error("device unavailable")

    monkeypatch.setattr(pygame.mixer, "init", fail)
    engine = AudioEngine(AppConfig())
    assert not engine.start("generative")
    assert not engine.enabled and "device unavailable" in engine.error
    engine.stop()


def test_pending_note_waits_for_minimum_interval(monkeypatch):
    from unittest.mock import Mock

    clock = [10.0]
    monkeypatch.setattr("app.audio_engine.time.monotonic", lambda: clock[0])
    engine = AudioEngine(AppConfig(note_interval_s=0.2))
    engine.enabled = True
    engine.mode = "generative"
    engine._sync_r = False
    engine._notes = {note: Mock() for note in engine.config.pentatonic}
    engine._note_channel = Mock()
    engine.update(0.1)
    assert engine._note_channel.play.call_count == 1
    clock[0] += 0.05
    engine.update(0.9)
    assert engine._note_channel.play.call_count == 1
    clock[0] += 0.2
    engine.update(0.9)
    assert engine._note_channel.play.call_count == 2


def test_piano_violin_pcm_are_distinct_finite_and_bounded():
    piano = AudioEngine(AppConfig(instrument="piano")).synthesize_note(60, 0.6)
    violin = AudioEngine(AppConfig(instrument="violin")).synthesize_note(60, 0.6)
    for pcm in (piano, violin):
        assert pcm.shape == (26460, 2)
        assert pcm.dtype == np.int16 and pcm.flags.c_contiguous
        assert np.max(np.abs(pcm.astype(float))) <= 14746
        assert not pcm[0].any() and not pcm[-1].any()
        assert np.std(pcm) > 100
    assert not np.array_equal(piano, violin)
    # Piano decays; bowed violin sustains its energy after the attack.
    assert np.std(piano[-8000:].astype(float)) < np.std(piano[3000:11000].astype(float))


def test_instrument_audition_uses_dummy_device(monkeypatch):
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    for instrument in ("piano", "violin"):
        engine = AudioEngine(AppConfig(instrument=instrument))
        assert engine.start("generative"), engine.error
        assert engine.audition()
        engine.stop()
