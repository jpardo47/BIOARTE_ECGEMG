from collections import deque
import numpy as np
from scipy import signal

from .models import ProcessedBlock, SampleBlock


class SignalProcessor:
    """Causal filters and simple adaptive ECG event detection, in volts."""
    def __init__(self, config):
        self.config = config
        self.reset(config.sample_rate)

    def reset(self, sample_rate=None):
        self.fs = float(self.config.sample_rate if sample_rate is None else sample_rate)
        f = self.config.filters
        nyquist = self.fs / 2
        values = (*f.ecg_band, *f.emg_band, f.envelope_hz, f.env_smoothing_hz)
        if self.fs <= 0 or any(v <= 0 or v >= nyquist for v in values) or f.ecg_band[0] >= f.ecg_band[1] or f.emg_band[0] >= f.emg_band[1]:
            raise ValueError('Frecuencia de muestreo incompatible con los filtros (Nyquist)')
        if f.notch_enabled and (not 0 < f.notch_hz < nyquist or f.notch_q <= 0):
            raise ValueError('Notch incompatible con frecuencia de muestreo')
        if f.order < 1 or f.rms_window_s <= 0 or f.refractory_s <= 0:
            raise ValueError('Configuracion de filtros invalida')
        self.ecg_sos = signal.butter(f.order, f.ecg_band, btype='bandpass', fs=self.fs, output='sos')
        self.emg_sos = signal.butter(f.order, f.emg_band, btype='bandpass', fs=self.fs, output='sos')
        if f.notch_enabled:
            b, a = signal.iirnotch(f.notch_hz, f.notch_q, self.fs)
            notch = signal.tf2sos(b, a)
            self.ecg_sos = np.vstack((self.ecg_sos, notch))
            self.emg_sos = np.vstack((self.emg_sos, notch))
        self.envelope_sos = signal.butter(f.order, f.envelope_hz, fs=self.fs, output='sos')
        self.env_sos = signal.butter(f.order, f.env_smoothing_hz, fs=self.fs, output='sos')
        self.zi = {k: np.zeros((len(sos), 2)) for k, sos in [('ecg', self.ecg_sos), ('emg', self.emg_sos), ('envelope', self.envelope_sos), ('env', self.env_sos)]}
        self.rms_n = max(1, round(f.rms_window_s * self.fs))
        self.squares = deque()
        self.sum_squares = 0.0
        self.level = 0.0
        self.previous = 0.0
        self.armed = True
        self.last_peak = None
        self.current_bpm = 0.0
        self.last_sample_index = None

    def _filter(self, name, sos, data):
        y, self.zi[name] = signal.sosfilt(sos, data, zi=self.zi[name])
        return y

    def process(self, block):
        if float(block.sample_rate) != self.fs:
            self.reset(block.sample_rate)
        n = len(block)
        adc = np.asarray(block.adc)
        if adc.shape != (n, 3):
            raise ValueError('El bloque ADC debe tener forma (N, 3)')
        if n:
            indices = np.asarray(block.sample_index, dtype=np.uint64)
            if self.last_sample_index is not None and int(indices[0]) - self.last_sample_index > 2 * self.fs:
                self.reset(block.sample_rate)
            breaks = np.flatnonzero(np.diff(indices.astype(np.float64)) > 2 * self.fs) + 1
            if len(breaks):
                pieces = []
                for start, end in zip(np.r_[0, breaks], np.r_[breaks, n]):
                    sub = SampleBlock(indices[start:end], block.time_s[start:end], adc[start:end], block.sample_rate, block.simulated)
                    pieces.append(self.process(sub))
                names = ('volts', 'ecg_filtered', 'emg_filtered', 'emg_rms', 'emg_envelope', 'emg_env_smoothed', 'r_peak', 'bpm')
                return ProcessedBlock(block, *(np.concatenate([getattr(part, name) for part in pieces]) for name in names))
            self.last_sample_index = int(indices[-1])
        volts = adc.astype(float) * (self.config.adc_reference_voltage / 1023.0)
        if n == 0:
            z = np.empty(0, dtype=float)
            return ProcessedBlock(block, volts, z.copy(), z.copy(), z.copy(), z.copy(), z.copy(), np.empty(0, dtype=bool), z.copy())
        ecg = self._filter('ecg', self.ecg_sos, volts[:, 0])
        emg = self._filter('emg', self.emg_sos, volts[:, 1])
        envelope = self._filter('envelope', self.envelope_sos, np.abs(emg))
        env = self._filter('env', self.env_sos, volts[:, 2])
        rms = np.empty(n)
        peaks = np.zeros(n, dtype=bool)
        bpm = np.empty(n)
        alpha = 1.0 - np.exp(-1.0 / self.fs)
        for i, (e, m, index) in enumerate(zip(ecg, emg, block.sample_index)):
            square = float(m * m)
            self.squares.append(square)
            self.sum_squares += square
            if len(self.squares) > self.rms_n:
                self.sum_squares -= self.squares.popleft()
            rms[i] = np.sqrt(max(0.0, self.sum_squares) / len(self.squares))
            magnitude = abs(float(e))
            self.level += alpha * (magnitude - self.level)
            threshold = max(0.005, 3.0 * self.level)
            if magnitude < threshold * 0.5:
                self.armed = True
            idx = int(index)
            if self.last_peak is not None and idx - self.last_peak > 2.0 * self.fs:
                self.current_bpm = 0.0
            if self.armed and magnitude >= threshold and self.previous < threshold and (self.last_peak is None or idx - self.last_peak >= self.config.filters.refractory_s * self.fs):
                peaks[i] = True
                if self.last_peak is not None:
                    rr = (idx - self.last_peak) / self.fs
                    self.current_bpm = 60.0 / rr if 0.3 <= rr <= 2.0 else 0.0
                self.last_peak = idx
                self.armed = False
            self.previous = magnitude
            bpm[i] = self.current_bpm
        return ProcessedBlock(block, volts, ecg, emg, rms, envelope, env, peaks, bpm)
