import csv
import json
import threading
import numpy as np

from app.config import AppConfig
from app.data_recorder import CSV_COLUMNS, DataRecorder, load_calibration, save_calibration
from app.models import Calibration, ProcessedBlock, SampleBlock


def block(n=4):
    raw = SampleBlock(
        np.arange(n, dtype=np.uint64), np.arange(n, dtype=float) / 1000, np.zeros((n, 3), dtype=np.int16), 1000.0
    )
    return ProcessedBlock(raw, np.zeros((n, 3)), *(np.zeros(n) for _ in range(5)), np.zeros(n, dtype=bool), np.zeros(n))


def test_csv_and_metadata_written_and_closed(tmp_path):
    config = AppConfig(recordings_dir=tmp_path)
    recorder = DataRecorder(config)
    path = recorder.start({"port": "COM4", "baudrate": 230400, "mode": "real"})
    recorder.write(block())
    recorder.stop()
    assert recorder.error is None
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.reader(stream))
    assert rows[0] == list(CSV_COLUMNS)
    assert len(rows) == 5
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["port"] == "COM4" and meta["mode"] == "real"
    assert meta["timestamp"] and meta["app_version"]


def test_empty_block_is_ignored(tmp_path):
    recorder = DataRecorder(AppConfig(recordings_dir=tmp_path))
    path = recorder.start({})
    recorder.write(block(0))
    recorder.stop()
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.reader(stream))
    assert rows == [list(CSV_COLUMNS)]


def test_full_queue_stops_with_visible_error_and_drains(tmp_path, monkeypatch):
    recorder = DataRecorder(AppConfig(recordings_dir=tmp_path))
    entered = threading.Event()
    release = threading.Event()
    original = recorder._write_block

    def slow_write(writer, data):
        entered.set()
        release.wait(2)
        original(writer, data)

    monkeypatch.setattr(recorder, "_write_block", slow_write)
    recorder._queue = __import__("queue").Queue(maxsize=1)
    recorder.start({})
    recorder.write(block())
    assert entered.wait(1)
    recorder.write(block())
    recorder.write(block())
    assert recorder.error is not None
    release.set()
    recorder.stop()
    assert not recorder.is_recording
    assert "cola" in recorder.error.lower()


def test_calibration_json_roundtrip_and_validation(tmp_path):
    cal = Calibration("rms", 0.02, 0.4, True, "2026-01-01T00:00:00+00:00")
    path = tmp_path / "calibration.json"
    save_calibration(cal, path)
    loaded = load_calibration(path)
    assert loaded == cal
    np.testing.assert_allclose(loaded.normalize([0.02, 0.21, 0.9]), [0, 0.5, 1], atol=1e-6)
    rejected = False
    try:
        save_calibration(Calibration("env", 0.4, 0.3), tmp_path / "bad.json")
    except ValueError:
        rejected = True
    assert rejected, "Calibration inversion must be rejected"
