from dataclasses import dataclass, field
import numpy as np

CHANNELS = ("ecg", "emg_raw", "emg_env")

@dataclass
class AcquisitionStats:
    received: int = 0
    lost: int = 0
    invalid: int = 0
    effective_fs: float = 0.0
    nominal_fs: float = 1000.0
    resets: int = 0

@dataclass
class SampleBlock:
    sample_index: np.ndarray
    time_s: np.ndarray
    adc: np.ndarray
    sample_rate: float
    simulated: bool = False

    def __len__(self):
        return len(self.sample_index)

@dataclass
class ProcessedBlock:
    raw: SampleBlock
    volts: np.ndarray
    ecg_filtered: np.ndarray
    emg_filtered: np.ndarray
    emg_rms: np.ndarray
    emg_envelope: np.ndarray
    emg_env_smoothed: np.ndarray
    r_peak: np.ndarray
    bpm: np.ndarray

    def __len__(self):
        return len(self.raw)

    def control(self, source):
        return {"env": self.emg_env_smoothed, "rms": self.emg_rms,
                "envelope": self.emg_envelope}[source]

@dataclass
class Calibration:
    source: str = "env"
    rest_level: float = 0.0
    active_level: float = 1.0
    simulated: bool = False
    created_at: str = ""

    def validate(self):
        if self.source not in ("env", "rms", "envelope"):
            raise ValueError("Fuente de calibracion desconocida")
        if not np.isfinite([self.rest_level, self.active_level]).all() or self.active_level <= self.rest_level:
            raise ValueError("La contraccion debe superar el reposo")

    def normalize(self, value):
        self.validate()
        return np.clip((np.asarray(value) - self.rest_level) / (self.active_level - self.rest_level + 1e-9), 0.0, 1.0)
