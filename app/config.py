from dataclasses import dataclass, field, asdict
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

@dataclass
class FilterConfig:
    ecg_band: tuple[float, float] = (0.5, 40.0)
    emg_band: tuple[float, float] = (20.0, 400.0)
    order: int = 4
    notch_enabled: bool = True
    notch_hz: float = 60.0
    notch_q: float = 30.0
    rms_window_s: float = 0.15
    envelope_hz: float = 5.0
    env_smoothing_hz: float = 5.0
    refractory_s: float = 0.25

@dataclass
class AppConfig:
    sample_rate: float = 1000.0
    baudrate: int = 230400
    adc_reference_voltage: float = 5.0
    block_size: int = 32
    serial_timeout_s: float = 0.1
    silence_timeout_s: float = 3.0
    plot_fps: int = 30
    window_s: float = 5.0
    max_window_s: float = 15.0
    saturation_low: int = 5
    saturation_high: int = 1018
    calibration_duration_s: float = 5.0
    normalization_source: str = "env"
    volume_min: float = 0.05
    volume_max: float = 0.8
    audio_smoothing: float = 0.15
    normalization_smoothing: float = 0.15
    note_interval_s: float = 0.2
    note_duration_s: float = 0.25
    audio_rate: int = 44100
    pentatonic: tuple[int, ...] = (48, 50, 52, 55, 57, 60)
    recordings_dir: Path = ROOT / "recordings"
    calibration_dir: Path = ROOT / "calibration"
    filters: FilterConfig = field(default_factory=FilterConfig)

    def to_dict(self):
        data = asdict(self)
        data["recordings_dir"] = str(self.recordings_dir)
        data["calibration_dir"] = str(self.calibration_dir)
        return data

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        filters = FilterConfig(**data.pop("filters", {}))
        for key in ("recordings_dir", "calibration_dir"):
            if key in data:
                data[key] = Path(data[key])
        obj = cls(filters=filters, **data)
        if obj.sample_rate <= 0 or obj.adc_reference_voltage <= 0 or obj.block_size < 1:
            raise ValueError("Frecuencia, referencia ADC y bloque deben ser positivos")
        if not 2 <= obj.window_s <= 15:
            raise ValueError("Ventana permitida: 2 a 15 segundos")
        return obj
