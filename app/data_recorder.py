"""Non-blocking block recorder and EMG calibration persistence."""

from __future__ import annotations

import csv
import json
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


from . import __version__
from .config import AppConfig
from .models import Calibration, ProcessedBlock

CSV_COLUMNS = (
    "sample_index",
    "time_s",
    "ecg_adc",
    "emg_raw_adc",
    "emg_env_adc",
    "ecg_v",
    "emg_raw_v",
    "emg_env_v",
    "ecg_filtered",
    "emg_filtered",
    "emg_rms",
    "emg_envelope",
    "emg_env_smoothed",
    "r_peak",
    "bpm",
)


def save_calibration(calibration: Calibration, path: Path) -> None:
    calibration.validate()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    data = {
        "source": calibration.source,
        "rest_level": float(calibration.rest_level),
        "active_level": float(calibration.active_level),
        "simulated": bool(calibration.simulated),
        "created_at": calibration.created_at or datetime.now(timezone.utc).isoformat(),
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_calibration(path: Path) -> Calibration:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    result = Calibration(**data)
    result.validate()
    return result


class DataRecorder:
    """CSV writer whose bounded queue keeps disk I/O off the GUI thread."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.error: str | None = None
        self._queue: queue.Queue[ProcessedBlock | None] = queue.Queue(maxsize=64)
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._recording = False
        self.path: Path | None = None
        self.metadata_path: Path | None = None

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    def start(self, metadata: dict[str, Any]) -> Path:
        with self._lock:
            if self._recording or (self._thread is not None and self._thread.is_alive()):
                raise RuntimeError("Ya hay una grabación activa")
            self.error = None
            self.config.recordings_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
            self.path = self.config.recordings_dir / f"bioarte_{timestamp}.csv"
            self.metadata_path = self.path.with_suffix(".json")
            document = dict(metadata)
            document.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
            document.setdefault("app_version", __version__)
            self.metadata_path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
            )
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
            self._recording = True
            self._thread = threading.Thread(target=self._write_loop, name="BioarteCSV", daemon=True)
            self._thread.start()
            return self.path

    def write(self, block: ProcessedBlock) -> None:
        if not len(block):
            return
        with self._lock:
            active = self._recording
        if not active:
            return
        try:
            self._queue.put_nowait(block)
        except queue.Full:
            self._set_error("La cola de grabación se llenó; se detuvo para no perder bloques silenciosamente")

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            active = self._recording
            self._recording = False
        if thread is None:
            return
        if active:
            # A full queue is drained by the writer; retry briefly without blocking GUI for long.
            try:
                self._queue.put(None, timeout=0.5)
            except queue.Full:
                self._set_error(self.error or "No se pudo finalizar la grabación a tiempo")
        thread.join(timeout=5.0)
        if thread.is_alive():
            self._set_error(self.error or "El hilo de grabación no cerró a tiempo")
        else:
            self._thread = None

    def _set_error(self, message: str) -> None:
        self.error = message
        with self._lock:
            self._recording = False

    def _write_loop(self) -> None:
        try:
            assert self.path is not None
            with self.path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(CSV_COLUMNS)
                while True:
                    try:
                        item = self._queue.get(timeout=0.1)
                    except queue.Empty:
                        with self._lock:
                            if not self._recording:
                                break
                        continue
                    if item is None:
                        break
                    self._write_block(writer, item)
                stream.flush()
        except Exception as exc:  # surfaced to GUI via .error
            self._set_error(f"Error escribiendo CSV: {exc}")
        finally:
            with self._lock:
                self._recording = False

    @staticmethod
    def _write_block(writer: csv.writer, block: ProcessedBlock) -> None:
        n = len(block)
        if n == 0:
            return
        raw = block.raw
        arrays = [
            raw.sample_index,
            raw.time_s,
            raw.adc[:, 0],
            raw.adc[:, 1],
            raw.adc[:, 2],
            block.volts[:, 0],
            block.volts[:, 1],
            block.volts[:, 2],
            block.ecg_filtered,
            block.emg_filtered,
            block.emg_rms,
            block.emg_envelope,
            block.emg_env_smoothed,
            block.r_peak,
            block.bpm,
        ]
        if any(len(a) != n for a in arrays):
            raise ValueError("Las columnas del bloque procesado tienen longitudes distintas")
        for row in zip(*arrays):
            writer.writerow(
                [
                    int(row[0]),
                    float(row[1]),
                    int(row[2]),
                    int(row[3]),
                    int(row[4]),
                    *[float(v) for v in row[5:13]],
                    int(row[13]),
                    float(row[14]),
                ]
            )
