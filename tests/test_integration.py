"""Integration checks exercise Qt delivery, plotting, disk and disconnect handling."""

import csv
import json
import time
from pathlib import Path

import numpy as np
import pytest
import serial
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.config import AppConfig
from app.serial_worker import SerialWorker
from app.ui import MainWindow


_qt_app = None


@pytest.fixture(scope="module")
def qt():
    global _qt_app
    _qt_app = QApplication.instance() or QApplication([])
    return _qt_app


def dispose(window):
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QTest.qWait(30)


def pump_until(predicate, seconds=4):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not predicate():
        QTest.qWait(20)
    assert predicate(), "La operacion Qt no termino dentro del limite"


def test_demo_graphs_record_and_restart(qt, tmp_path):
    config = AppConfig(recordings_dir=tmp_path / "records", calibration_dir=tmp_path / "cal")
    window = MainWindow(config, demo=True)
    window.show()
    try:
        window.start_button.click()
        pump_until(lambda: window.last_block is not None)
        assert window.last_block.raw.simulated
        assert window.last_block.raw.adc.shape[1] == 3
        assert len(window.plots) == 3
        pump_until(lambda: all(len(curves[0].getData()[0]) > 0 for curves in window.curves))
        window.record_start.click()
        pump_until(lambda: window.recorder.is_recording)
        QTest.qWait(250)
        window.record_stop.click()
        path = next(config.recordings_dir.glob("*.csv"))
        with path.open(encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        assert rows and "emg_env_smoothed" in rows[0]
        assert all(np.isfinite(float(row["ecg_filtered"])) for row in rows)
        metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        assert metadata["mode"] == "demo"
        assert metadata["adc_reference_voltage"] == 5.0
        assert metadata["app_version"] == "1.0.0"
        screenshot = Path(__file__).resolve().parents[1] / ".tmp" / "gui-demo.png"
        screenshot.parent.mkdir(exist_ok=True)
        assert window.grab().save(str(screenshot))
        window.stop_button.click()
        assert not window.recorder.is_recording
        window.start_button.click()
        pump_until(lambda: window.last_block is not None)
        assert window.last_block.raw.simulated
    finally:
        dispose(window)


def test_real_mode_does_not_fallback_to_demo(qt, tmp_path):
    window = MainWindow(AppConfig(calibration_dir=tmp_path), demo=False)
    try:
        assert not window.mode_combo.isEnabled()
        window.start_button.click()
        assert window.last_block is None
        assert window.worker is None
        assert window.error_label.text()
    finally:
        dispose(window)


def test_serial_fragmentation_bad_frame_gap_and_disconnect(qt, monkeypatch):
    class FakePort:
        def __init__(self, *args, **kwargs):
            self.fragments = iter(
                [
                    b"#fs=1000,columns=n,ecg,emg_raw,emg_env\n0,512,338,80\n1,51",
                    b"3,339,81\nbroken\n3,514,340,82\n",
                ]
            )

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def reset_input_buffer(self):
            self.reset_called = True

        @property
        def in_waiting(self):
            return 4096

        def read(self, size):
            try:
                return next(self.fragments)
            except StopIteration:
                raise serial.SerialException("physical disconnect simulated")

    monkeypatch.setattr("app.serial_worker.serial.Serial", FakePort)
    worker = SerialWorker(AppConfig(block_size=3), "TEST")
    blocks, stats, errors = [], [], []
    worker.block_ready.connect(blocks.append)
    worker.stats_ready.connect(stats.append)
    worker.error.connect(errors.append)
    worker.start()
    pump_until(lambda: not worker.isRunning())
    QTest.qWait(100)
    assert blocks and sum(len(block) for block in blocks) == 3
    assert not blocks[0].raw.simulated
    np.testing.assert_allclose(np.concatenate([block.raw.time_s for block in blocks]), [0, 0.001, 0.003])
    assert stats[-1].lost == 1 and stats[-1].invalid == 1
    assert errors and "disconnect" in errors[-1]
    worker.stop()


def test_gui_disconnect_closes_recording_and_restores_controls(qt, monkeypatch, tmp_path):
    import threading

    disconnect = threading.Event()

    class FakePort:
        def __init__(self, *args, **kwargs):
            self.first = True

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def reset_input_buffer(self):
            return None

        @property
        def in_waiting(self):
            return 4096

        def read(self, size):
            if self.first:
                self.first = False
                return b"0,512,338,80\n1,513,339,81\n2,514,340,82\n"
            if disconnect.wait(0.01):
                raise serial.SerialException("cable desconectado en prueba")
            return b""

    monkeypatch.setattr("app.serial_worker.serial.Serial", FakePort)
    window = MainWindow(AppConfig(block_size=3, recordings_dir=tmp_path, calibration_dir=tmp_path), demo=False)
    try:
        window.connected_port = "TEST"
        window.start_button.click()
        pump_until(lambda: window.last_block is not None)
        window.record_start.click()
        assert window.recorder.is_recording
        disconnect.set()
        pump_until(lambda: window.worker is None)
        assert not window.recorder.is_recording
        assert window.start_button.isEnabled() and window.connect_button.isEnabled()
        assert "desconectado" in window.error_label.text()
        assert window.connected_port is None
    finally:
        disconnect.set()
        dispose(window)


def test_calibration_phases_save_and_source_change_cancel(qt, tmp_path):
    from app.models import Calibration, SampleBlock
    from app.signal_processing import SignalProcessor

    window = MainWindow(AppConfig(calibration_dir=tmp_path), demo=True)
    try:
        times = np.arange(5001) / 1000
        adc = np.full((5001, 3), 100)
        raw = SampleBlock(np.arange(5001, dtype=np.uint64), times, adc, 1000, True)
        block = SignalProcessor(window.config).process(raw)
        block.emg_env_smoothed[:] = 0.1
        window._calibration_phase = "rest"
        window._calibration_simulated = True
        window._collect_calibration(block)
        assert window.calibration is None
        assert window._pending_rest[0] == pytest.approx(0.1)
        block.emg_env_smoothed[:] = 0.8
        window._calibration_start = None
        window._calibration_values = []
        window._calibration_phase = "active"
        window._collect_calibration(block)
        assert isinstance(window.calibration, Calibration)
        assert window.calibration.active_level == pytest.approx(0.8)
        assert (tmp_path / "calibration_demo_env.json").exists()
        window.source_combo.setCurrentIndex(1)
        assert window.calibration is None
        assert window._pending_rest is None
    finally:
        dispose(window)


def test_ecg_display_centering_preserves_acquired_data(qt, tmp_path):
    from app.models import SampleBlock
    from app.signal_processing import SignalProcessor

    window = MainWindow(AppConfig(calibration_dir=tmp_path), demo=False)
    try:
        adc = np.column_stack((np.array([200, 210, 205, 225, 210]), np.full(5, 338), np.full(5, 100)))
        indices = np.arange(5, dtype=np.uint64)
        block = SignalProcessor(window.config).process(SampleBlock(indices, indices / 1000, adc, 1000))
        original_volts = block.volts.copy()
        original_adc = adc.copy()
        window._on_block(block)
        window._refresh_plots()
        displayed = window.curves[0][0].getData()[1]
        assert np.median(displayed) == pytest.approx(0)
        np.testing.assert_array_equal(block.volts, original_volts)
        np.testing.assert_array_equal(block.raw.adc, original_adc)
        np.testing.assert_allclose(window.curves[0][1].getData()[1], block.ecg_filtered)
        window.ecg_center_checkbox.setChecked(False)
        window._refresh_plots()
        np.testing.assert_allclose(window.curves[0][0].getData()[1], original_volts[:, 0])
        window.ecg_raw_checkbox.setChecked(False)
        window._refresh_plots()
        assert not window.curves[0][0].isVisible()
    finally:
        dispose(window)
