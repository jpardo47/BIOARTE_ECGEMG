"""Spanish PySide6 interface for live ECG/EMG acquisition and sonification."""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from . import __version__, theme
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
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _build_ui(self):
        self.setWindowTitle("Bioarte ECG–EMG")
        self.setWindowIcon(theme.icon("activity", theme.TRACE_ECG, 32))
        self.resize(1440, 900)
        self.setMinimumSize(1100, 680)
        self.setFont(theme.ui_font())
        self.setStyleSheet(theme.stylesheet())
        root = QtWidgets.QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QtWidgets.QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Sidebar: every control grouped by task, in the order a session is run.
        sidebar = QtWidgets.QScrollArea()
        sidebar.setObjectName("sidebar")
        sidebar.setWidgetResizable(True)
        sidebar.setFixedWidth(372)
        sidebar.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        contents = QtWidgets.QWidget()
        contents.setObjectName("sidebarContents")
        sidebar.setWidget(contents)
        panel = QtWidgets.QVBoxLayout(contents)
        panel.setContentsMargins(16, 18, 16, 16)
        panel.setSpacing(12)
        outer.addWidget(sidebar)

        brand = QtWidgets.QHBoxLayout()
        brand.setSpacing(10)
        logo = QtWidgets.QLabel()
        logo.setPixmap(theme.pixmap("activity", theme.TRACE_ECG, 28))
        brand.addWidget(logo)
        brand_text = QtWidgets.QVBoxLayout()
        brand_text.setSpacing(0)
        title = QtWidgets.QLabel("Bioarte")
        title.setObjectName("brandTitle")
        subtitle = QtWidgets.QLabel("ECG · EMG · Sonificación")
        subtitle.setObjectName("brandSubtitle")
        brand_text.addWidget(title)
        brand_text.addWidget(subtitle)
        brand.addLayout(brand_text)
        brand.addStretch(1)
        panel.addLayout(brand)

        # Source and connection
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["Real (Arduino)", "Demo (simulado)"])
        self.mode_combo.setCurrentIndex(1 if self.demo_allowed else 0)
        self.mode_combo.setEnabled(self.demo_allowed)
        self.mode_combo.setToolTip("La fuente demo solo está disponible al iniciar con --demo")
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setToolTip("Puerto serial del Arduino Mega")
        self.refresh_button = _button("", "refresh", variant="icon", tip="Actualizar puertos")
        self.connect_button = _button("Conectar", "plug")
        self.disconnect_button = _button("Desconectar", "unplug")
        self.disconnect_button.setEnabled(False)
        card, body = _card("FUENTE Y CONEXIÓN")
        body.addWidget(_field("Fuente", self.mode_combo))
        port_row = QtWidgets.QHBoxLayout()
        port_row.setSpacing(8)
        port_row.addWidget(self.port_combo, 1)
        port_row.addWidget(self.refresh_button)
        body.addWidget(_field("Puerto", port_row))
        body.addLayout(_row(self.connect_button, self.disconnect_button))
        panel.addWidget(card)

        # Acquisition and recording
        self.start_button = _button("Iniciar adquisición", "play", variant="primary", color="#FFFFFF")
        self.stop_button = _button("Detener", "stop", variant="danger", color=theme.DANGER)
        self.stop_button.setToolTip("Detener adquisición")
        self.stop_button.setEnabled(False)
        self.record_start = _button("Grabar CSV", "record", color=theme.DANGER)
        self.record_start.setToolTip("Iniciar grabación CSV + JSON en recordings/")
        self.record_stop = _button("Detener grabación", "stop")
        self.record_stop.setEnabled(False)
        card, body = _card("ADQUISICIÓN")
        body.addLayout(_row(self.start_button, self.stop_button, stretch=(3, 2)))
        body.addLayout(_row(self.record_start, self.record_stop))
        panel.addWidget(card)

        # EMG calibration
        self.source_combo = QtWidgets.QComboBox()
        self.source_combo.addItem("ENV A2", "env")
        self.source_combo.addItem("RMS RAW A1", "rms")
        self.source_combo.addItem("Envolvente RAW A1", "envelope")
        idx = self.source_combo.findData(self.config.normalization_source)
        self.source_combo.setCurrentIndex(max(0, idx))
        self.rest_button = _button("1 · Reposo 5 s", "target")
        self.rest_button.setToolTip("Calibrar reposo (5 s): mantén el músculo relajado")
        self.active_button = _button("2 · Contracción 5 s", "target")
        self.active_button.setToolTip("Calibrar contracción (5 s): mantén una contracción cómoda")
        self.load_cal_button = _button("Cargar calibración", "folder")
        self.calibration_progress = QtWidgets.QProgressBar()
        self.calibration_progress.setRange(0, 100)
        self.calibration_progress.setValue(0)
        self.calibration_progress.setFormat("Calibración: %p%")
        self.calibration_state = QtWidgets.QLabel()
        self.calibration_state.setObjectName("badge")
        self.calibration_state.setWordWrap(True)
        card, body = _card("CALIBRACIÓN EMG")
        body.addWidget(_field("Señal de control", self.source_combo))
        body.addLayout(_row(self.rest_button, self.active_button))
        body.addWidget(self.calibration_progress)
        body.addWidget(self.calibration_state)
        body.addWidget(self.load_cal_button)
        panel.addWidget(card)

        # Sonification: only the controls of the selected mode are shown.
        self.audio_mode = QtWidgets.QComboBox()
        self.audio_mode.addItem("Música reactiva", "music")
        self.audio_mode.addItem("Melodía generativa", "generative")
        self.instrument_combo = QtWidgets.QComboBox()
        self.instrument_combo.addItem("Piano sintetizado", "piano")
        self.instrument_combo.addItem("Violín sintetizado", "violin")
        self.instrument_combo.addItem("Seno simple", "sine")
        self.instrument_combo.setCurrentIndex(max(0, self.instrument_combo.findData(self.config.instrument)))
        self.instrument_combo.setToolTip("Timbres sintetizados; cambiar instrumento y reiniciar audio para aplicarlo")
        self.audio_test = _button("Probar", "music")
        self.audio_test.setToolTip("Reproduce una nota de prueba independiente del ECG/EMG")
        self.music_path = QtWidgets.QLineEdit()
        self.music_path.setPlaceholderText("Archivo WAV, OGG o MP3")
        self.music_browse = _button("", "folder", variant="icon", tip="Elegir archivo de audio")
        self.volume_min_spin = _spin(0, 1, 0.05, self.config.volume_min)
        self.volume_spin = _spin(0, 1, 0.05, self.config.volume_max)
        self.duration_spin = _spin(0.05, 2, 0.05, self.config.note_duration_s)
        self.interval_spin = _spin(0.05, 5, 0.05, self.config.note_interval_s)
        self.sync_r = QtWidgets.QCheckBox("Sincronizar con siguiente pico R")
        self.audio_start = _button("Iniciar audio", "volume", variant="primary", color="#FFFFFF")
        self.audio_stop = _button("Detener audio", "stop")
        card, body = _card("SONIFICACIÓN")
        body.addWidget(_field("Modo", self.audio_mode))
        music_row = QtWidgets.QHBoxLayout()
        music_row.setSpacing(8)
        music_row.addWidget(self.music_path, 1)
        music_row.addWidget(self.music_browse)
        self.music_field = _field("Archivo", music_row)
        body.addWidget(self.music_field)
        instrument_row = QtWidgets.QHBoxLayout()
        instrument_row.setSpacing(8)
        instrument_row.addWidget(self.instrument_combo, 1)
        instrument_row.addWidget(self.audio_test)
        self.instrument_field = _field("Instrumento", instrument_row)
        body.addWidget(self.instrument_field)
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.addWidget(_field("Vol. mín.", self.volume_min_spin), 0, 0)
        grid.addWidget(_field("Vol. máx.", self.volume_spin), 0, 1)
        self.duration_field = _field("Duración nota (s)", self.duration_spin)
        self.interval_field = _field("Intervalo (s)", self.interval_spin)
        grid.addWidget(self.duration_field, 1, 0)
        grid.addWidget(self.interval_field, 1, 1)
        body.addLayout(grid)
        body.addWidget(self.sync_r)
        body.addLayout(_row(self.audio_start, self.audio_stop))
        panel.addWidget(card)
        self.audio_test.clicked.connect(self._test_instrument)

        # Visualization
        self.window_spin = _spin(2, 15, 1, self.config.window_s)
        self.window_spin.setSuffix(" s")
        self.ecg_raw_checkbox = QtWidgets.QCheckBox("Mostrar ECG crudo")
        self.ecg_raw_checkbox.setChecked(True)
        self.ecg_center_checkbox = QtWidgets.QCheckBox("Centrar crudo: solo visualización")
        self.ecg_center_checkbox.setChecked(True)
        self.ecg_center_checkbox.setToolTip(
            "Resta la mediana de la ventana al crudo para compararlo con el filtrado; CSV y filtros conservan sus valores originales"
        )
        card, body = _card("VISUALIZACIÓN")
        body.addWidget(_field("Ventana visible", self.window_spin))
        body.addWidget(self.ecg_raw_checkbox)
        body.addWidget(self.ecg_center_checkbox)
        panel.addWidget(card)

        panel.addStretch(1)
        footer = QtWidgets.QLabel(
            f"Prototipo educativo y artístico · v{__version__}\nNo es un dispositivo médico ni sirve para diagnóstico."
        )
        footer.setObjectName("footer")
        footer.setWordWrap(True)
        panel.addWidget(footer)

        # Main area: header, live indicators and the three signal plots.
        main = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(main)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)
        outer.addWidget(main, 1)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(10)
        heading = QtWidgets.QVBoxLayout()
        heading.setSpacing(2)
        page_title = QtWidgets.QLabel("Monitor en vivo")
        page_title.setObjectName("pageTitle")
        self.status_label = QtWidgets.QLabel("Desconectado")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        heading.addWidget(page_title)
        heading.addWidget(self.status_label)
        header.addLayout(heading, 1)
        self.rec_badge = _badge("GRABANDO", "danger")
        self.rec_badge.hide()
        self.audio_badge = _badge("AUDIO ACTIVO", "info")
        self.audio_badge.hide()
        self.demo_label = _badge("")
        self._set_source_badge(self.demo_allowed)
        self.pause_button = _button("Pausar vista", "pause")
        self.pause_button.setCheckable(True)
        self.pause_button.setToolTip("Congela las gráficas; la adquisición y la grabación continúan")
        self.pause_button.toggled.connect(self._pause_toggled)
        for widget in (self.rec_badge, self.audio_badge, self.demo_label, self.pause_button):
            header.addWidget(widget, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        main_layout.addLayout(header)

        self.error_label = ErrorBanner()
        main_layout.addWidget(self.error_label)

        kpis = QtWidgets.QHBoxLayout()
        kpis.setSpacing(12)
        self.kpi_bpm = KpiTile("FRECUENCIA CARDÍACA", "BPM")
        self.kpi_emg = KpiTile("NIVEL EMG", "0–1", meter=True)
        self.kpi_fs = KpiTile("MUESTREO EFECTIVO", "Hz")
        self.kpi_samples = KpiTile("MUESTRAS RECIBIDAS")
        self.kpi_saturation = KpiTile("SATURACIÓN ADC", "en bloque")
        for tile in (self.kpi_bpm, self.kpi_emg, self.kpi_fs, self.kpi_samples, self.kpi_saturation):
            kpis.addWidget(tile, 1)
        main_layout.addLayout(kpis)
        self._reset_indicators()

        self.plots: list[pg.PlotWidget] = []
        self.curves: list[list[pg.PlotDataItem]] = []
        specs = [
            ("ECG · A0", "Amplitud (V)", [("Crudo", theme.TRACE_RAW, 1.2), ("Filtrado", theme.TRACE_ECG, 1.6)]),
            (
                "EMG RAW · A1",
                "Amplitud / RMS (V)",
                [
                    ("RAW crudo", theme.TRACE_RAW, 1.0),
                    ("Filtrado", theme.TRACE_EMG, 1.3),
                    ("RMS", theme.TRACE_RMS, 1.8),
                    ("Envolvente", theme.TRACE_ENVELOPE, 1.8),
                ],
            ),
            ("EMG ENV · A2", "Amplitud (V)", [("Crudo", theme.TRACE_ENV_RAW, 1.2), ("Suavizado", theme.TRACE_ENV_SMOOTH, 1.8)]),
        ]
        tick_font = theme.mono_font(11)
        for title, label, traces in specs:
            frame = QtWidgets.QFrame()
            frame.setObjectName("plotCard")
            frame_layout = QtWidgets.QVBoxLayout(frame)
            frame_layout.setContentsMargins(6, 6, 6, 6)
            plot = pg.PlotWidget()
            plot.setBackground(theme.PLOT_BG)
            _set_plot_title(plot, title)
            plot.setMinimumHeight(120)
            plot.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Ignored)
            for name in ("left", "bottom"):
                axis = plot.getAxis(name)
                axis.setPen(pg.mkPen(theme.BORDER_STRONG))
                axis.setTextPen(pg.mkPen(theme.TEXT_MUTED))
                axis.setStyle(tickFont=tick_font)
            plot.setLabel("left", label, color=theme.TEXT_MUTED)
            plot.setLabel("bottom", "Tiempo", units="s", color=theme.TEXT_MUTED)
            plot.showGrid(x=True, y=True, alpha=0.18)
            plot.addLegend(
                offset=(8, 4),
                colCount=len(traces),
                labelTextSize="8pt",
                labelTextColor=theme.TEXT,
                brush=pg.mkBrush(15, 23, 42, 210),
                pen=pg.mkPen(theme.BORDER_STRONG),
            )
            plot.setDownsampling(auto=True, mode="peak")
            curves = [
                plot.plot([], [], name=name, pen=pg.mkPen(color, width=width)) for name, color, width in traces
            ]
            frame_layout.addWidget(plot)
            main_layout.addWidget(frame, stretch=1)
            self.plots.append(plot)
            self.curves.append(curves)
        self._ecg_title = "ECG · A0"

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

    def _set_source_badge(self, simulated):
        self.demo_label.setText("● DATOS SIMULADOS" if simulated else "● DATOS REALES")
        _set_tone(self.demo_label, "warn" if simulated else "ok")

    def _pause_toggled(self, paused):
        self.pause_button.setText("Reanudar vista" if paused else "Pausar vista")
        self.pause_button.setIcon(theme.icon("play" if paused else "pause", theme.FOCUS if paused else theme.TEXT))

    def _reset_indicators(self):
        self.kpi_bpm.set("—", "esperando picos R")
        self.kpi_emg.set("0.00", "sin datos")
        self.kpi_fs.set("—", "nominal —")
        self.kpi_samples.set("0", "perdidas 0 · inválidas 0")
        self.kpi_saturation.set("0", "ECG 0 · RAW 0 · ENV 0")

    def _tick(self):
        self._refresh_indicators()
        if not self.pause_button.isChecked():
            self._refresh_plots()

    def _refresh_indicators(self):
        recording = bool(self.recorder.is_recording)
        if self.rec_badge.isHidden() == recording:
            self.rec_badge.setVisible(recording)
        audio_on = bool(self.audio.enabled)
        if self.audio_badge.isHidden() == audio_on:
            self.audio_badge.setVisible(audio_on)
        cal = self.calibration
        if cal is None:
            text, tone = "Sin calibración: el nivel EMG se mantiene en 0", "warn"
        else:
            text, tone = f"Calibrado · reposo {cal.rest_level:.3f} · contracción {cal.active_level:.3f}", "ok"
        if self.calibration_state.text() != text:
            self.calibration_state.setText(text)
            _set_tone(self.calibration_state, tone)

    def _mode_changed(self):
        simulated = self.demo_allowed and self.mode_combo.currentIndex() == 1
        self._set_source_badge(simulated)
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
            self._set_source_badge(simulated)
            self._reset_indicators()
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
        nominal = float(stats.nominal_fs)
        drift = nominal > 0 and abs(stats.effective_fs - nominal) / nominal > 0.02
        self.kpi_fs.set(f"{stats.effective_fs:.1f}", f"nominal {nominal:.0f} Hz", "warn" if drift else None)
        problems = stats.lost or stats.invalid
        self.kpi_samples.set(
            f"{stats.received:,}".replace(",", " "),
            f"perdidas {stats.lost} · inválidas {stats.invalid}",
            "warn" if problems else None,
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
            calibrated = True
        else:
            target = 0.0
            calibrated = False
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
        self.kpi_bpm.set(bpm, "último intervalo R–R" if len(finite) else "esperando picos R")
        self.kpi_emg.set(
            f"{self._level_smoothed:.2f}",
            f"fuente {self.source_combo.currentText()}" if calibrated else "sin calibración",
            None if calibrated else "warn",
            level=self._level_smoothed,
        )
        self.kpi_saturation.set(
            str(sum(sat)), f"ECG {sat[0]} · RAW {sat[1]} · ENV {sat[2]}", "danger" if any(sat) else "ok"
        )

    def _refresh_plots(self):
        if not self._plot_time:
            return
        t = np.asarray(self._plot_time)
        visible = self.window_spin.value()
        mask = t >= (t[-1] - visible)
        x = t[mask] - t[-1]
        series = [np.asarray(self._plot_data[i])[mask] for i in range(8)]
        raw_ecg = series[0]
        centered = self.ecg_center_checkbox.isChecked()
        if centered:
            raw_ecg = raw_ecg - np.median(raw_ecg)
        self.curves[0][0].setData(x, raw_ecg)
        self.curves[0][0].setVisible(self.ecg_raw_checkbox.isChecked())
        self.curves[0][1].setData(x, series[1])
        if self.ecg_raw_checkbox.isChecked():
            detail = "crudo centrado (solo vista) + filtrado" if centered else "crudo absoluto + filtrado"
        else:
            detail = "filtrado"
        title = "ECG · A0 · " + detail
        if title != self._ecg_title:
            self._ecg_title = title
            _set_plot_title(self.plots[0], title)
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
        # Progressive disclosure: show only the controls that affect the selected mode.
        self.music_field.setVisible(music)
        for field in (self.instrument_field, self.duration_field, self.interval_field):
            field.setVisible(not music)

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


class ErrorBanner(QtWidgets.QLabel):
    """Error label that only occupies space while it has a message."""

    def __init__(self):
        super().__init__()
        self.setObjectName("errorBanner")
        self.setWordWrap(True)
        self.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setAccessibleName("Mensaje de error")
        self.hide()

    def setText(self, text):
        super().setText(text)
        self.setVisible(bool(text))

    def clear(self):
        super().clear()
        self.hide()


class KpiTile(QtWidgets.QFrame):
    """Large tabular value with caption and secondary detail line."""

    def __init__(self, caption, unit="", meter=False):
        super().__init__()
        self.setObjectName("kpi")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        caption_label = QtWidgets.QLabel(caption)
        caption_label.setObjectName("kpiCaption")
        layout.addWidget(caption_label)
        value_row = QtWidgets.QHBoxLayout()
        value_row.setSpacing(6)
        self.value = QtWidgets.QLabel("—")
        self.value.setObjectName("kpiValue")
        self.value.setFont(theme.mono_font(24, QtGui.QFont.Weight.DemiBold))
        value_row.addWidget(self.value, 0, QtCore.Qt.AlignmentFlag.AlignBaseline)
        if unit:
            unit_label = QtWidgets.QLabel(unit)
            unit_label.setObjectName("kpiUnit")
            value_row.addWidget(unit_label, 0, QtCore.Qt.AlignmentFlag.AlignBaseline)
        value_row.addStretch(1)
        layout.addLayout(value_row)
        self.meter = None
        if meter:
            self.meter = QtWidgets.QProgressBar()
            self.meter.setObjectName("meter")
            self.meter.setRange(0, 100)
            self.meter.setTextVisible(False)
            layout.addWidget(self.meter)
        self.detail = QtWidgets.QLabel("")
        self.detail.setObjectName("kpiDetail")
        layout.addWidget(self.detail)
        self.setAccessibleName(caption.capitalize())

    def set(self, value, detail=None, tone=None, level=None):
        if self.value.text() != value:
            self.value.setText(value)
        if detail is not None and self.detail.text() != detail:
            self.detail.setText(detail)
        if self.value.property("tone") != tone:
            _set_tone(self.value, tone)
            _set_tone(self.detail, tone)
        if self.meter is not None and level is not None:
            self.meter.setValue(int(round(float(np.clip(level, 0, 1)) * 100)))


def _set_tone(widget, tone):
    widget.setProperty("tone", tone)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _badge(text, tone=None):
    label = QtWidgets.QLabel(text)
    label.setObjectName("badge")
    if tone:
        label.setProperty("tone", tone)
    return label


def _button(text, icon_name=None, variant=None, color=theme.TEXT, tip=None):
    button = QtWidgets.QPushButton(text)
    if icon_name:
        button.setIcon(theme.icon(icon_name, color))
    if variant:
        button.setProperty("variant", variant)
    if tip:
        button.setToolTip(tip)
        button.setAccessibleName(tip)
    button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
    return button


def _spin(minimum, maximum, step, value):
    spin = QtWidgets.QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setSingleStep(step)
    spin.setValue(value)
    return spin


def _card(title):
    card = QtWidgets.QFrame()
    card.setObjectName("card")
    body = QtWidgets.QVBoxLayout(card)
    body.setContentsMargins(14, 12, 14, 14)
    body.setSpacing(10)
    heading = QtWidgets.QLabel(title)
    heading.setObjectName("cardTitle")
    body.addWidget(heading)
    return card, body


def _field(label, content):
    """Visible label stacked above its control (layout or widget)."""
    wrapper = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    caption = QtWidgets.QLabel(label)
    caption.setObjectName("fieldLabel")
    layout.addWidget(caption)
    if isinstance(content, QtWidgets.QLayout):
        layout.addLayout(content)
        buddy = content.itemAt(0).widget() if content.count() else None
    else:
        layout.addWidget(content)
        buddy = content
    if buddy is not None:
        caption.setBuddy(buddy)
        buddy.setAccessibleName(label)
    return wrapper


def _row(*widgets, stretch=None):
    row = QtWidgets.QHBoxLayout()
    row.setSpacing(8)
    for i, widget in enumerate(widgets):
        row.addWidget(widget, stretch[i] if stretch else 1)
    return row


def _set_plot_title(plot, text):
    plot.setTitle(text, color=theme.TEXT, size="10pt")
