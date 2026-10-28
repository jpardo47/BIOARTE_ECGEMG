import numpy as np
import pytest
from app.config import AppConfig
from app.models import SampleBlock
from app.signal_processing import SignalProcessor


def block(adc, fs=1000, start=0):
    n = len(adc)
    indices = np.arange(start, start + n, dtype=np.uint64)
    return SampleBlock(indices, indices.astype(float) / fs, np.asarray(adc).reshape(n, 3), fs)


def test_empty_small_finite_and_conversion():
    p = SignalProcessor(AppConfig())
    for n in (0, 1, 2, 10):
        out = p.process(block(np.full((n, 3), 512)))
        assert out.volts.shape == (n, 3)
        assert np.isfinite(out.volts).all()
        for x in (out.ecg_filtered, out.emg_filtered, out.emg_rms, out.emg_envelope, out.emg_env_smoothed, out.bpm):
            assert len(x) == n and np.isfinite(x).all()
        if n:
            assert out.volts[0, 0] == pytest.approx(512 * 5 / 1023)


def test_state_across_blocks_and_reset():
    rng = np.random.default_rng(4)
    adc = rng.integers(200, 800, (1000, 3))
    full = SignalProcessor(AppConfig()).process(block(adc))
    p = SignalProcessor(AppConfig())
    first = p.process(block(adc[:367]))
    second = p.process(block(adc[367:], start=367))
    for name in ('ecg_filtered', 'emg_filtered', 'emg_rms', 'emg_envelope', 'emg_env_smoothed', 'bpm', 'r_peak'):
        np.testing.assert_allclose(np.r_[getattr(first, name), getattr(second, name)], getattr(full, name), atol=1e-12)
    p.reset()
    reset = p.process(block(adc[:367]))
    np.testing.assert_allclose(reset.ecg_filtered, first.ecg_filtered)


def test_out_of_band_attenuation_and_frequency_validation():
    fs = 1000
    t = np.arange(6000) / fs
    def response(freq, channel):
        adc = np.full((len(t), 3), 512.0)
        adc[:, channel] += 100 * np.sin(2 * np.pi * freq * t)
        out = SignalProcessor(AppConfig()).process(block(adc))
        baseline = SignalProcessor(AppConfig()).process(block(np.full_like(adc, 512.0)))
        name = 'ecg_filtered' if channel == 0 else 'emg_filtered'
        return np.std((getattr(out, name) - getattr(baseline, name))[2000:])
    assert response(100, 0) < response(10, 0) * 0.1
    assert response(5, 1) < response(100, 1) * 0.1
    with pytest.raises(ValueError, match='Nyquist'):
        SignalProcessor(AppConfig()).process(block(np.full((1, 3), 512), fs=500))


def test_stale_bpm_and_large_gap_reset():
    p = SignalProcessor(AppConfig())
    p.last_peak = 0
    p.current_bpm = 60.0
    out = p.process(block(np.full((10, 3), 512), start=2100))
    assert out.bpm[-1] == 0
    first = np.full((10, 3), 512)
    p.process(block(first, start=2110))
    after_gap = p.process(block(first, start=5000))
    fresh = SignalProcessor(AppConfig()).process(block(first, start=5000))
    np.testing.assert_allclose(after_gap.ecg_filtered, fresh.ecg_filtered)


def test_gap_inside_block_matches_independent_segments():
    adc = np.full((20, 3), 512)
    indices = np.r_[np.arange(10), np.arange(3000, 3010)].astype(np.uint64)
    joined = SampleBlock(indices, indices.astype(float) / 1000, adc, 1000)
    actual = SignalProcessor(AppConfig()).process(joined)
    fresh = SignalProcessor(AppConfig()).process(block(adc[10:], start=3000))
    np.testing.assert_allclose(actual.ecg_filtered[10:], fresh.ecg_filtered)
