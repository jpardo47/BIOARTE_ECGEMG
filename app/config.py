from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import math

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

    def __post_init__(self):
        positive = (
            self.sample_rate,
            self.adc_reference_voltage,
            self.block_size,
            self.serial_timeout_s,
            self.silence_timeout_s,
            self.plot_fps,
            self.calibration_duration_s,
            self.note_interval_s,
            self.note_duration_s,
            self.audio_rate,
            self.baudrate,
        )
        if not all(math.isfinite(v) and v > 0 for v in positive):
            raise ValueError("Frecuencias, tiempos, referencia y bloque deben ser positivos y finitos")
        if any(int(v) != v for v in (self.block_size, self.baudrate, self.plot_fps, self.audio_rate)):
            raise ValueError("Bloque, baudrate, FPS y tasa de audio deben ser enteros")
        if not 2 <= self.window_s <= 15 or self.max_window_s < self.window_s or self.max_window_s > 15:
            raise ValueError("Ventana permitida: 2 a 15 segundos")
        if not 0 <= self.volume_min <= self.volume_max <= 1:
            raise ValueError("Volumen minimo/maximo fuera de rango")
        if not all(0 < v <= 1 for v in (self.audio_smoothing, self.normalization_smoothing)):
            raise ValueError("Suavizado permitido: mayor que 0 y hasta 1")
        if not self.pentatonic or any(not 0 <= note <= 127 for note in self.pentatonic):
            raise ValueError("Escala MIDI invalida")
        if self.normalization_source not in ("env", "rms", "envelope"):
            raise ValueError("Fuente EMG invalida")
        if not 0 <= self.saturation_low < self.saturation_high <= 1023:
            raise ValueError("Umbrales ADC invalidos")
        self.recordings_dir = Path(self.recordings_dir)
        self.calibration_dir = Path(self.calibration_dir)

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
        return obj
