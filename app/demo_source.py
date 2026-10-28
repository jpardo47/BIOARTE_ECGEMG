import time
from dataclasses import replace
import numpy as np
from PySide6.QtCore import QThread, Signal
from .models import AcquisitionStats, SampleBlock
from .signal_processing import SignalProcessor


class DemoSource(QThread):
    """Synthetic periodic test signals, not physiological measurements."""
    block_ready = Signal(object)
    stats_ready = Signal(object)
    status_changed = Signal(str)
    error = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._stopping = False

    def stop(self):
        self._stopping = True
        self.requestInterruption()
        if self.isRunning() and QThread.currentThread() != self:
            self.wait(2000)

    def run(self):
        stats = AcquisitionStats(nominal_fs=self.config.sample_rate)
        try:
            processor = SignalProcessor(self.config)
            fs = float(self.config.sample_rate)
            size = self.config.block_size
            start = time.monotonic()
            index = 0
            self.status_changed.emit('Demo: datos simulados')
            while not self._stopping and not self.isInterruptionRequested():
                target = start + (index + size) / fs
                remaining = target - time.monotonic()
                if remaining > 0:
                    self.msleep(max(1, min(20, int(remaining * 1000))))
                    continue
                indices = np.arange(index, index + size, dtype=np.uint64)
                t = indices.astype(float) / fs
                phase = np.mod(t, 0.85)
                ecg = 512 + 150 * np.exp(-((phase - 0.1) / 0.012) ** 2) + 15 * np.sin(2 * np.pi * 1.2 * t)
                activity = (np.sin(2 * np.pi * 0.12 * t) + 1) / 2
                raw = 338 + 55 * activity * np.sin(2 * np.pi * 95 * t)
                env = 80 + 260 * activity
                adc = np.clip(np.column_stack((ecg, raw, env)), 0, 1023).astype(np.int32)
                block = SampleBlock(indices, t, adc, fs, True)
                self.block_ready.emit(processor.process(block))
                index += size
                stats.received = index
                elapsed = time.monotonic() - start
                stats.effective_fs = index / elapsed if elapsed > 0 else 0.0
                self.stats_ready.emit(replace(stats))
        except Exception as exc:
            if not self._stopping:
                self.error.emit(f'Error de demo: {exc}')
        finally:
            self.status_changed.emit('Detenido')
