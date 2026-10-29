"""Spanish PySide6 interface for live ECG/EMG acquisition and sonification."""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets

from . import __version__
from .audio_engine import AudioEngine
from .config import AppConfig
from .data_recorder import DataRecorder, load_calibration, save_calibration
from .models import Calibration, ProcessedBlock


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, config: AppConfig, demo: bool = False):
        super().__init__()
        self.config = config
        self.demo_allowed = bool(demo)
        self.last_block: ProcessedBlock | None = None
        self.worker = None
        self.connected_port: str | None = None
        self.recorder = DataRecorder(config)
        self.audio = AudioEngine(config)
        self.calibration: Calibration | None = None
        self._calibration_phase: str | None = None
        self._calibration_source = config.normalization_source
        self._calibration_start: float | None = None
        self._calibration_values: list[float] = []
        self._calibration_simulated = False
        self._pending_rest: tuple[float, bool] | None = None
        self._stopping_worker = False
        self._close_pending = False
        self._level_smoothed = 0.0
        self._normalization_source = config.normalization_source
        self._acquisition_started_at: float | None = None
        self._latest_effective_fs = 0.0
        self._plot_capacity = max(1, int(config.sample_rate * config.max_window_s))
        self._plot_data = [deque(maxlen=self._plot_capacity) for _ in range(10)]
        self._plot_time = deque(maxlen=self._plot_capacity)
        self._build_ui()
        self._load_saved_calibration()
        self._refresh_ports()
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(max(1, int(1000 / max(1, config.plot_fps))))
        self.timer.timeout.connect(self._refresh_plots)
        self.timer.start()

    def _build_ui(self):
        self.setWindowTitle("Bioarte ECG–EMG")
        self.resize(1280, 960)
        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        outer = QtWidgets.QVBoxLayout(root)
        control_scroll = QtWidgets.QScrollArea()
        control_scroll.setWidgetResizable(True)
        control_scroll.setMaximumHeight(310)
        control_scroll.setMinimumHeight(200)
        contents = QtWidgets.QWidget()
        control_scroll.setWidget(contents)
        panel = QtWidgets.QVBoxLayout(contents)
        outer.addWidget(control_scroll)
        controls = QtWidgets.QGridLayout()
        panel.addLayout(controls)
        self.demo_label = QtWidgets.QLabel("● DATOS SIMULADOS" if self.demo_allowed else "● DATOS REALES")
        self.demo_label.setStyleSheet(
            "font-weight:bold;color:#d97706" if self.demo_allowed else "font-weight:bold;color:#15803d"
        )
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["Real (Arduino)", "Demo (simulado)"])
        self.mode_combo.setCurrentIndex(1 if self.demo_allowed else 0)
        self.mode_combo.setEnabled(self.demo_allowed)
        self.port_combo = QtWidgets.QComboBox()
        self.refresh_button = QtWidgets.QPushButton("Actualizar puertos")
        self.connect_button = QtWidgets.QPushButton("Conectar")
        self.disconnect_button = QtWidgets.QPushButton("Desconectar")
        self.start_button = QtWidgets.QPushButton("Iniciar adquisición")
        self.stop_button = QtWidgets.QPushButton("Detener adquisición")
        self.disconnect_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        controls.addWidget(QtWidgets.QLabel("Fuente"), 0, 0)
        controls.addWidget(self.mode_combo, 0, 1)
        controls.addWidget(self.demo_label, 0, 2)
        controls.addWidget(QtWidgets.QLabel("Puerto"), 1, 0)
        controls.addWidget(self.port_combo, 1, 1)
        controls.addWidget(self.refresh_button, 1, 2)
        controls.addWidget(self.connect_button, 1, 3)
        controls.addWidget(self.disconnect_button, 1, 4)
        controls.addWidget(self.start_button, 0, 3)
        controls.addWidget(self.stop_button, 0, 4)

        self.status_label = QtWidgets.QLabel("Desconectado")
        self.stats_label = QtWidgets.QLabel(
            "fs nominal: — | fs efectiva: — | recibidas: 0 | perdidas: 0 | inválidas: 0"
        )
        self.vitals_label = QtWidgets.QLabel("BPM: — | EMG normalizado: 0.00 | Saturación ECG: 0 | RAW: 0 | ENV: 0")
        self.error_label = QtWidgets.QLabel("")
        self.error_label.setStyleSheet("color:#b91c1c")
        for label in (self.status_label, self.stats_label, self.vitals_label, self.error_label):
            label.setWordWrap(True)
        panel.addWidget(self.status_label)
        panel.addWidget(self.stats_label)
        panel.addWidget(self.vitals_label)
        panel.addWidget(self.error_label)
        settings = QtWidgets.QGridLayout()
        panel.addLayout(settings)
        settings.addWidget(QtWidgets.QLabel("Ventana (s)"), 0, 0)
        self.window_spin = QtWidgets.QDoubleSpinBox()
        self.window_spin.setRange(2, 15)
        self.window_spin.setSingleStep(1)
        self.window_spin.setValue(self.config.window_s)
        settings.addWidget(self.window_spin, 0, 1)
        self.record_start = QtWidgets.QPushButton("Iniciar grabación")
        self.record_stop = QtWidgets.QPushButton("Detener grabación")
        self.record_stop.setEnabled(False)
        settings.addWidget(self.record_start, 0, 2)
        settings.addWidget(self.record_stop, 0, 3)
        settings.addWidget(QtWidgets.QLabel("Normalización EMG"), 0, 4)
        self.source_combo = QtWidgets.QComboBox()
        self.source_combo.addItem("ENV A2", "env")
        self.source_combo.addItem("RMS RAW A1", "rms")
        self.source_combo.addItem("Envolvente RAW A1", "envelope")
        idx = self.source_combo.findData(self.config.normalization_source)
        self.source_combo.setCurrentIndex(max(0, idx))
        settings.addWidget(self.source_combo, 0, 5)
        self.rest_button = QtWidgets.QPushButton("Calibrar reposo (5 s)")
        self.active_button = QtWidgets.QPushButton("Calibrar contracción (5 s)")
        self.load_cal_button = QtWidgets.QPushButton("Cargar calibración")
        settings.addWidget(self.rest_button, 1, 0)
        settings.addWidget(self.active_button, 1, 1)
        settings.addWidget(self.load_cal_button, 1, 2)
        self.calibration_progress = QtWidgets.QProgressBar()
        self.calibration_progress.setRange(0, 100)
        self.calibration_progress.setValue(0)
        self.calibration_progress.setFormat("Calibración: %p%")
        self.calibration_progress.setMaximumWidth(220)
        settings.addWidget(self.calibration_progress, 1, 3, 1, 3)

        audio_box = QtWidgets.QGroupBox("Sonificación")
        audio_layout = QtWidgets.QGridLayout(audio_box)
        panel.addWidget(audio_box)
        self.audio_mode = QtWidgets.QComboBox()
        self.audio_mode.addItem("Música reactiva", "music")
        self.audio_mode.addItem("Melodía generativa", "generative")
        self.instrument_combo = QtWidgets.QComboBox()
        self.instrument_combo.addItem("Piano sintetizado", "piano")
        self.instrument_combo.addItem("Violín sintetizado", "violin")
        self.instrument_combo.addItem("Seno simple", "sine")
        self.instrument_combo.setCurrentIndex(max(0, self.instrument_combo.findData(self.config.instrument)))
        self.instrument_combo.setToolTip("Timbres sintetizados; cambiar instrumento y reiniciar audio para aplicarlo")
        self.audio_test = QtWidgets.QPushButton("Probar instrumento")
        self.audio_test.setToolTip("Reproduce una nota de prueba independiente del ECG/EMG")
        self.music_path = QtWidgets.QLineEdit()
        self.music_path.setPlaceholderText("Archivo WAV, OGG o MP3")
        self.music_browse = QtWidgets.QPushButton("Elegir archivo")
        self.volume_min_spin = QtWidgets.QDoubleSpinBox()
        self.volume_min_spin.setRange(0, 1)
        self.volume_min_spin.setSingleStep(0.05)
        self.volume_min_spin.setValue(self.config.volume_min)
        self.volume_spin = QtWidgets.QDoubleSpinBox()
        self.volume_spin.setRange(0, 1)
        self.volume_spin.setSingleStep(0.05)
        self.volume_spin.setValue(self.config.volume_max)
        self.duration_spin = QtWidgets.QDoubleSpinBox()
        self.duration_spin.setRange(0.05, 2)
        self.duration_spin.setSingleStep(0.05)
        self.duration_spin.setValue(self.config.note_duration_s)
        self.interval_spin = QtWidgets.QDoubleSpinBox()
        self.interval_spin.setRange(0.05, 5)
        self.interval_spin.setSingleStep(0.05)
        self.interval_spin.setValue(self.config.note_interval_s)
        self.sync_r = QtWidgets.QCheckBox("Sincronizar con siguiente pico R")
        self.audio_start = QtWidgets.QPushButton("Iniciar audio")
        self.audio_stop = QtWidgets.QPushButton("Detener audio")
        audio_layout.addWidget(self.audio_mode, 0, 0)
        audio_layout.addWidget(self.music_path, 0, 1, 1, 2)
        audio_layout.addWidget(self.music_browse, 0, 3)
        audio_layout.addWidget(QtWidgets.QLabel("Vol. mín."), 0, 4)
        audio_layout.addWidget(self.volume_min_spin, 0, 5)
        audio_layout.addWidget(QtWidgets.QLabel("Vol. máx."), 0, 6)
        audio_layout.addWidget(self.volume_spin, 0, 7)
        audio_layout.addWidget(QtWidgets.QLabel("Duración s"), 1, 0)
        audio_layout.addWidget(self.duration_spin, 1, 1)
        audio_layout.addWidget(QtWidgets.QLabel("Intervalo s"), 1, 2)
        audio_layout.addWidget(self.interval_spin, 1, 3)
        audio_layout.addWidget(self.sync_r, 1, 4, 1, 2)
        audio_layout.addWidget(self.audio_start, 1, 6)
        audio_layout.addWidget(self.audio_stop, 1, 7)

        audio_layout.addWidget(QtWidgets.QLabel("Instrumento"), 2, 0)
        audio_layout.addWidget(self.instrument_combo, 2, 1, 1, 2)
        audio_layout.addWidget(self.audio_test, 2, 3)
        self.audio_test.clicked.connect(self._test_instrument)

        self.plots: list[pg.PlotWidget] = []
        self.curves: list[list[pg.PlotDataItem]] = []
        specs = [
            ("ECG · A0", "Amplitud (V)", [("Crudo", "#60a5fa"), ("Filtrado", "#f43f5e")]),
            (
                "EMG RAW · A1",
                "Amplitud / RMS (V)",
                [("RAW crudo", "#38bdf8"), ("Filtrado", "#f97316"), ("RMS", "#a3e635"), ("Envolvente", "#e879f9")],
            ),
            ("EMG ENV · A2", "Amplitud (V)", [("Crudo", "#fbbf24"), ("Suavizado", "#34d399")]),
        ]
        for title, label, traces in specs:
            plot = pg.PlotWidget(title=title)
            plot.setMinimumHeight(110)
            plot.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Ignored)
            plot.setLabel("left", label)
            plot.setLabel("bottom", "Tiempo", units="s")
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.addLegend()
            plot.setDownsampling(auto=True, mode="peak")
            curves = [plot.plot([], [], name=name, pen=pg.mkPen(color, width=1.5)) for name, color in traces]
            outer.addWidget(plot, stretch=1)
            self.plots.append(plot)
            self.curves.append(curves)

        self.refresh_button.clicked.connect(self._refresh_ports)
        self.connect_button.clicked.connect(self._connect)
        self.disconnect_button.clicked.connect(self._disconnect)
        self.start_button.clicked.connect(self._start_acquisition)
        self.stop_button.clicked.connect(self._stop_acquisition)
        self.record_start.clicked.connect(self._start_recording)
        self.record_stop.clicked.connect(self._stop_recording)
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        self.rest_button.clicked.connect(lambda: self._begin_calibration("rest"))
        self.active_button.clicked.connect(lambda: self._begin_calibration("active"))
        self.load_cal_button.clicked.connect(self._choose_calibration)
        self.music_browse.clicked.connect(self._choose_music)
        self.audio_start.clicked.connect(self._start_audio)
        self.audio_stop.clicked.connect(self.audio.stop)
        self.audio_mode.currentIndexChanged.connect(self._audio_mode_changed)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self._audio_mode_changed()

    def _mode_changed(self):
        simulated = self.demo_allowed and self.mode_combo.currentIndex() == 1
        self.demo_label.setText("● DATOS SIMULADOS" if simulated else "● DATOS REALES")
        self.demo_label.setStyleSheet(
            "font-weight:bold;color:#d97706" if simulated else "font-weight:bold;color:#15803d"
        )
        self.calibration = None
        self._pending_rest = None
        self._calibration_phase = None
        self._level_smoothed = 0.0
        self._load_saved_calibration()

    def _refresh_ports(self):
        current = self.port_combo.currentText()
        try:
            from .serial_worker import SerialWorker

            ports = SerialWorker.list_ports()
        except Exception:
            try:
                import serial.tools.list_ports

                ports = [p.device for p in serial.tools.list_ports.comports()]
            except Exception:
                ports = []
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        if current:
            idx = self.port_combo.findText(current)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)

    def _connect(self):
        if self.demo_allowed and self.mode_combo.currentIndex() == 1:
            self.connected_port = "DEMO"
            self.status_label.setText("Conectado a fuente simulada")
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.mode_combo.setEnabled(False)
            return
        port = self.port_combo.currentText()
        if not port:
            self._show_error("No hay un puerto serial seleccionado")
            return
        try:
            import serial

            probe = serial.Serial(port, self.config.baudrate, timeout=self.config.serial_timeout_s)
            probe.close()
            self.connected_port = port
            self.status_label.setText(f"Puerto disponible: {port}")
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.mode_combo.setEnabled(False)
            self.error_label.clear()
        except Exception as exc:
            self._show_error(f"No se pudo abrir {port}: {exc}")

    def _start_acquisition(self):
        if self.worker is not None and self.worker.isRunning():
            return
        simulated = self.demo_allowed and self.mode_combo.currentIndex() == 1
        if not simulated and not self.connected_port:
            self._show_error("Conecta primero con el Arduino")
            return
        try:
            if simulated:
                from .demo_source import DemoSource

                self.worker = DemoSource(self.config)
            else:
                from .serial_worker import SerialWorker

                self.worker = SerialWorker(self.config, self.connected_port)
            self.worker.block_ready.connect(self._worker_block)
            self.worker.stats_ready.connect(self._worker_stats)
            self.worker.status_changed.connect(self._worker_status)
            self.worker.error.connect(self._worker_error_signal)
            self.worker.finished.connect(self._worker_finished_signal)
            self._clear_buffers()
            self._acquisition_started_at = time.monotonic()
            self.demo_label.setText("● DATOS SIMULADOS" if simulated else "● DATOS REALES")
            self.demo_label.setStyleSheet(
                "font-weight:bold;color:#d97706" if simulated else "font-weight:bold;color:#15803d"
            )
            self.mode_combo.setEnabled(False)
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.port_combo.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.worker.start()
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.error_label.clear()
        except Exception as exc:
            self._show_error(f"No se pudo iniciar adquisición: {exc}")

    def _stop_acquisition(self):
        self._calibration_phase = None
        self.calibration_progress.setValue(0)
        worker = self.worker
        if worker is not None:
            try:
                self._stopping_worker = True
                worker.stop()
                if worker.isRunning():
                    worker.wait(1500)
            except Exception as exc:
                self._show_error(f"Error deteniendo adquisición: {exc}")
            if not worker.isRunning():
                # Deliver final queued blocks before closing the recording and releasing its source.
                QtCore.QCoreApplication.sendPostedEvents(self, QtCore.QEvent.Type.MetaCall)
                self._worker_finished(worker)
        self._stop_recording()
        self.status_label.setText("Adquisición detenida")

    def _disconnect(self):
        self._stop_acquisition()
        self.connected_port = None
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.mode_combo.setEnabled(self.demo_allowed)
        self.status_label.setText("Desconectado")

    def _worker_error(self, worker, message):
        if self.worker is not worker:
            return
        self._show_error(message)
        self._stop_recording()

    @QtCore.Slot(object)
    def _worker_block(self, block):
        if self.sender() is self.worker:
            self._on_block(block)

    @QtCore.Slot(object)
    def _worker_stats(self, stats):
        if self.sender() is self.worker:
            self._on_stats(stats)

    @QtCore.Slot(str)
    def _worker_status(self, status):
        if self.sender() is self.worker:
            self.status_label.setText(status)

    @QtCore.Slot(str)
    def _worker_error_signal(self, message):
        self._worker_error(self.sender(), message)

    @QtCore.Slot()
    def _worker_finished_signal(self):
        self._worker_finished(self.sender())

    def _worker_finished(self, worker):
        if self.worker is not worker:
            return
        if self.recorder.is_recording:
            self._stop_recording()
        self.worker = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        if self.connected_port == "DEMO":
            self.connected_port = None
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
        self.mode_combo.setEnabled(self.demo_allowed and not self.connected_port)
        self.port_combo.setEnabled(True)
        self.refresh_button.setEnabled(True)
        was_stopping = self._stopping_worker
        if not was_stopping:
            self.connected_port = None
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            self.status_label.setText("Fuente detenida; puedes volver a conectar")
            self.mode_combo.setEnabled(self.demo_allowed)
        self._stopping_worker = False
        if self._close_pending:
            QtCore.QTimer.singleShot(0, self.close)

    @QtCore.Slot(object)
    def _on_block(self, block: ProcessedBlock):
        self.last_block = block
        raw = block.raw
        if len(block) == 0:
            return
        # Plots use volts; ADC saturation is derived independently from raw counts.
        mapping = [
            block.volts[:, 0],
            block.ecg_filtered,
            block.volts[:, 1],
            block.emg_filtered,
            block.emg_rms,
            block.emg_envelope,
            block.volts[:, 2],
            block.emg_env_smoothed,
            raw.adc[:, 0],
            raw.adc[:, 1],
        ]
        for i, value in enumerate(mapping):
            self._plot_data[i].extend(np.asarray(value, dtype=float).tolist())
        self._plot_time.extend(np.asarray(raw.time_s, dtype=float).tolist())
        self._update_vitals(block)
        self.recorder.write(block)
        if self.recorder.error:
            self._show_error(self.recorder.error)
            self.record_stop.setEnabled(False)
            self.record_start.setEnabled(True)
        self._collect_calibration(block)
        self._update_audio(block)

    @QtCore.Slot(object)
    def _on_stats(self, stats):
        self._latest_effective_fs = float(stats.effective_fs)
        self.stats_label.setText(
            f"fs nominal: {stats.nominal_fs:.1f} Hz | fs efectiva: {stats.effective_fs:.1f} Hz | recibidas: {stats.received} | perdidas: {stats.lost} | inválidas: {stats.invalid}"
        )

    def _update_vitals(self, block):
        finite = block.bpm[np.isfinite(block.bpm) & (block.bpm > 0)]
        bpm = f"{finite[-1]:.0f}" if len(finite) else "—"
        source = self.source_combo.currentData()
        control = block.control(source)
        if (
            self.calibration is not None
            and self.calibration.simulated == block.raw.simulated
            and self.calibration.source == source
        ):
            normalized = self.calibration.normalize(control)
            target = float(normalized[-1]) if len(normalized) else 0.0
        else:
            target = 0.0
        alpha = float(np.clip(self.config.normalization_smoothing, 0, 1))
        self._level_smoothed += alpha * (target - self._level_smoothed)
        counts = block.raw.adc
        sat = [
            int(
                np.count_nonzero(
                    (counts[:, c] <= self.config.saturation_low) | (counts[:, c] >= self.config.saturation_high)
                )
            )
            for c in range(3)
        ]
        self.vitals_label.setText(
            f"BPM: {bpm} | EMG normalizado: {self._level_smoothed:.2f} | Saturación ECG: {sat[0]} RAW: {sat[1]} ENV: {sat[2]}"
        )

    def _refresh_plots(self):
        if not self._plot_time:
            return
        t = np.asarray(self._plot_time)
        visible = self.window_spin.value()
        mask = t >= (t[-1] - visible)
        x = t[mask] - t[-1]
        series = [np.asarray(self._plot_data[i])[mask] for i in range(8)]
        for curve, y in zip(self.curves[0], series[:2]):
            curve.setData(x, y)
        for curve, y in zip(self.curves[1], series[2:6]):
            curve.setData(x, y)
        for curve, y in zip(self.curves[2], series[6:8]):
            curve.setData(x, y)
        for plot in self.plots:
            plot.setXRange(-visible, 0, padding=0)

    def _clear_buffers(self):
        for values in self._plot_data:
            values.clear()
        self._plot_time.clear()
        self.last_block = None
        self._latest_effective_fs = 0.0
        self._level_smoothed = 0.0
        self._pending_rest = None
        self._calibration_phase = None

    def _start_recording(self):
        if self.worker is None or not self.worker.isRunning() or self.last_block is None:
            self._show_error("Inicia adquisición y espera el primer bloque antes de grabar")
            return
        simulated = (
            bool(self.last_block.raw.simulated)
            if self.last_block
            else (self.demo_allowed and self.mode_combo.currentIndex() == 1)
        )
        metadata = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "port": "DEMO" if simulated else (self.connected_port or ""),
            "baudrate": self.config.baudrate,
            "nominal_fs": self.last_block.raw.sample_rate,
            "effective_fs_initial": self._latest_effective_fs,
            "adc_reference_voltage": self.config.adc_reference_voltage,
            "filters": self.config.filters.__dict__.copy(),
            "normalization_source": self.source_combo.currentData(),
            "calibration": self._calibration_dict() if self.calibration else None,
            "mode": "demo" if simulated else "real",
            "app_version": __version__,
        }
        try:
            path = self.recorder.start(metadata)
            self.status_label.setText(f"Grabando: {path.name}")
            self.record_start.setEnabled(False)
            self.record_stop.setEnabled(True)
            self.error_label.clear()
        except Exception as exc:
            self._show_error(f"No se pudo iniciar la grabación: {exc}")

    def _stop_recording(self):
        self.recorder.stop()
        self.record_start.setEnabled(True)
        self.record_stop.setEnabled(False)
        if self.recorder.error:
            self._show_error(self.recorder.error)

    def _source_changed(self):
        source = self.source_combo.currentData()
        if source != self._normalization_source:
            self.calibration = None
            self._normalization_source = source
            self._level_smoothed = 0.0
            self._pending_rest = None
            self._calibration_phase = None
        self._calibration_source = source
        self._load_saved_calibration()

    def _begin_calibration(self, phase):
        if self.worker is None or not self.worker.isRunning():
            self._show_error("Inicia la adquisición para calibrar")
            return
        if phase == "active" and (
            self._pending_rest is None or self._calibration_source != self.source_combo.currentData()
        ):
            self._show_error("Calibra primero el nivel de reposo")
            return
        self._calibration_phase = phase
        self._calibration_start = None
        self._calibration_values = []
        self._calibration_simulated = bool(self.last_block.raw.simulated) if self.last_block else False
        self.calibration_progress.setValue(0)
        self.status_label.setText(
            "Calibrando reposo: mantén el músculo relajado"
            if phase == "rest"
            else "Calibrando contracción: mantén una contracción cómoda"
        )

    def _collect_calibration(self, block):
        if self._calibration_phase is None or len(block) == 0:
            return
        if self._calibration_simulated != block.raw.simulated:
            self._calibration_phase = None
            self._show_error("La fuente cambió durante la calibración")
            return
        times = block.raw.time_s
        if self._calibration_start is None:
            self._calibration_start = float(times[0])
        elapsed = float(times[-1] - self._calibration_start)
        values = np.asarray(block.control(self._calibration_source), dtype=float)
        valid = values[np.isfinite(values)]
        self._calibration_values.extend(valid.tolist())
        self.calibration_progress.setValue(int(np.clip(elapsed / self.config.calibration_duration_s * 100, 0, 100)))
        if elapsed >= self.config.calibration_duration_s:
            level = float(np.median(self._calibration_values)) if self._calibration_values else float("nan")
            phase = self._calibration_phase
            self._calibration_phase = None
            self.calibration_progress.setValue(100)
            if phase == "rest":
                self._pending_rest = (level, block.raw.simulated)
                self.status_label.setText("Reposo medido; ahora realiza una contracción cómoda")
            else:
                try:
                    if self._pending_rest is None:
                        raise ValueError("Calibra primero el reposo")
                    rest, rest_simulated = self._pending_rest
                    if rest_simulated != block.raw.simulated:
                        raise ValueError("La fuente cambió desde la medición de reposo")
                    candidate = Calibration(
                        self._calibration_source,
                        rest,
                        level,
                        block.raw.simulated,
                        datetime.now(timezone.utc).isoformat(),
                    )
                    candidate.validate()
                    self.calibration = candidate
                    path = self._calibration_path()
                    save_calibration(candidate, path)
                    self.status_label.setText(f"Calibración guardada: {path.name}")
                    self.error_label.clear()
                except Exception as exc:
                    self._show_error(f"Calibración inválida: {exc}")

    def _calibration_path(self):
        mode = "demo" if self.demo_allowed and self.mode_combo.currentIndex() == 1 else "real"
        return self.config.calibration_dir / f"calibration_{mode}_{self.source_combo.currentData()}.json"

    def _load_saved_calibration(self):
        path = self._calibration_path()
        if path.exists():
            try:
                candidate = load_calibration(path)
                expected_sim = self.demo_allowed and self.mode_combo.currentIndex() == 1
                if candidate.simulated == expected_sim and candidate.source == self.source_combo.currentData():
                    self.calibration = candidate
            except Exception as exc:
                self._show_error(f"No se pudo cargar calibración: {exc}")

    def _choose_calibration(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Cargar calibración", str(self.config.calibration_dir), "JSON (*.json)"
        )
        if not path:
            return
        try:
            candidate = load_calibration(Path(path))
            expected_sim = self.demo_allowed and self.mode_combo.currentIndex() == 1
            if candidate.simulated != expected_sim:
                raise ValueError("La calibración pertenece a otra fuente (real/demo)")
            if candidate.source != self.source_combo.currentData():
                raise ValueError("La fuente de normalización no coincide")
            self.calibration = candidate
            self.status_label.setText("Calibración cargada")
        except Exception as exc:
            self._show_error(f"No se pudo cargar calibración: {exc}")

    def _calibration_dict(self):
        if self.calibration is None:
            return None
        return {
            "source": self.calibration.source,
            "rest_level": self.calibration.rest_level,
            "active_level": self.calibration.active_level,
            "simulated": self.calibration.simulated,
            "created_at": self.calibration.created_at,
        }

    def _choose_music(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Seleccionar música", "", "Audio (*.wav *.ogg *.mp3)")
        if path:
            self.music_path.setText(path)

    def _audio_mode_changed(self):
        music = self.audio_mode.currentData() == "music"
        self.music_path.setEnabled(music)
        self.music_browse.setEnabled(music)
        self.instrument_combo.setEnabled(not music)

    def _test_instrument(self):
        self.audio_mode.setCurrentIndex(self.audio_mode.findData("generative"))
        self._start_audio()
        if self.audio.enabled:
            # A single explicit audition, never represented as physiological data.
            self.audio.audition()
            self.status_label.setText("Nota de prueba del instrumento (independiente de sensores)")

    def _start_audio(self):
        self.config.instrument = self.instrument_combo.currentData()
        self.config.volume_min = self.volume_min_spin.value()
        self.config.volume_max = self.volume_spin.value()
        self.config.note_duration_s = self.duration_spin.value()
        self.config.note_interval_s = self.interval_spin.value()
        success = self.audio.start(
            self.audio_mode.currentData(), self.music_path.text() or None, self.sync_r.isChecked()
        )
        if success:
            self.status_label.setText("Audio activo")
        else:
            self._show_error(self.audio.error or "No se pudo iniciar el audio")

    def _update_audio(self, block):
        if self.audio.enabled:
            source = self.source_combo.currentData()
            if (
                self.calibration is not None
                and self.calibration.source == source
                and self.calibration.simulated == block.raw.simulated
            ):
                levels = self.calibration.normalize(block.control(source))
            else:
                levels = np.zeros(len(block), dtype=float)
            for level, peak in zip(levels, block.r_peak):
                self.audio.update(float(level), bool(peak))
            if self.audio.error:
                self._show_error(self.audio.error)

    def _show_error(self, message):
        self.error_label.setText(str(message))

    def closeEvent(self, event):
        self.timer.stop()
        self._calibration_phase = None
        self.audio.stop()
        self._stop_acquisition()
        self.recorder.stop()
        if self.worker is not None and self.worker.isRunning():
            self._close_pending = True
            event.ignore()
            return
        self._close_pending = False
        event.accept()
