import re
import time
from dataclasses import replace

import numpy as np
import serial
from serial.tools import list_ports
from PySide6.QtCore import QThread, Signal

from .models import AcquisitionStats, SampleBlock
from .signal_processing import SignalProcessor


class SerialParser:
    """Parse ASCII frames; expose a normalized uint64 sample index for each frame."""
    _header = re.compile(r'^#fs=([0-9]+(?:\.[0-9]+)?),columns=n,ecg,emg_raw,emg_env$')
    _integer = re.compile(r'^[0-9]+$')

    def __init__(self, config):
        self.sample_rate = float(config.sample_rate)
        self.stats = AcquisitionStats(nominal_fs=self.sample_rate)
        self.metadata_seen = False
        self.normalized_index = None
        self._last_wire = None
        self._start = None

    def feed_line(self, line):
        try:
            text = line.decode('ascii') if isinstance(line, bytes) else str(line)
            text = text.strip('\r\n')
            if text.startswith('#'):
                match = self._header.fullmatch(text)
                if not match or not 0 < float(match.group(1)) <= 1e6 or self.stats.received:
                    raise ValueError('metadata invalida')
                self.sample_rate = float(match.group(1))
                self.stats.nominal_fs = self.sample_rate
                self.metadata_seen = True
                return None
            parts = text.split(',')
            if len(parts) != 4 or any(not self._integer.fullmatch(p) for p in parts):
                raise ValueError('trama invalida')
            idx, ecg, raw, env = (int(p) for p in parts)
            if idx > 0xffffffff or any(x > 1023 for x in (ecg, raw, env)):
                raise ValueError('fuera de rango')
            if self._last_wire is None:
                normalized = 0
            elif idx > self._last_wire:
                delta = idx - self._last_wire
                normalized = self.normalized_index + delta
                self.stats.lost += delta - 1
            elif self._last_wire >= 0xf0000000 and idx <= 0x0fffffff:
                delta = (idx - self._last_wire) & 0xffffffff
                normalized = self.normalized_index + delta
                self.stats.lost += delta - 1
            elif idx < self._last_wire:
                self.stats.resets += 1
                normalized = self.normalized_index + 1
            else:
                raise ValueError('indice duplicado')
            self._last_wire = idx
            self.normalized_index = normalized
            now = time.monotonic()
            if self._start is None:
                self._start = now
            self.stats.received += 1
            elapsed = now - self._start
            if elapsed > 0 and self.stats.received > 1:
                self.stats.effective_fs = (self.stats.received - 1) / elapsed
            return idx, ecg, raw, env
        except (UnicodeError, ValueError, OverflowError):
            self.stats.invalid += 1
            return None


class SerialWorker(QThread):
    block_ready = Signal(object)
    stats_ready = Signal(object)
    status_changed = Signal(str)
    error = Signal(str)

    def __init__(self, config, port):
        super().__init__()
        self.config = config
        self.port = port
        self._stopping = False

    @staticmethod
    def list_ports():
        return [p.device for p in list_ports.comports()]

    def stop(self):
        self._stopping = True
        self.requestInterruption()
        if self.isRunning() and QThread.currentThread() != self:
            self.wait(max(1000, int((self.config.serial_timeout_s + 1) * 1000)))

    def run(self):
        parser = SerialParser(self.config)
        indices, rows = [], []
        pending = bytearray()
        last_frame = time.monotonic()
        last_emit = last_frame
        def emit_block():
            if rows:
                index = np.asarray(indices, dtype=np.uint64)
                block = SampleBlock(index, index.astype(float) / parser.sample_rate, np.asarray(rows, dtype=np.int32), parser.sample_rate, False)
                self.block_ready.emit(processor.process(block))
                self.stats_ready.emit(replace(parser.stats))
                indices.clear()
                rows.clear()
        try:
            processor = SignalProcessor(self.config)
            self.status_changed.emit('Conectando')
            with serial.Serial(self.port, self.config.baudrate, timeout=self.config.serial_timeout_s) as connection:
                connection.reset_input_buffer()
                self.status_changed.emit('Adquiriendo')
                while not self._stopping and not self.isInterruptionRequested():
                    chunk = connection.read(min(4096, max(1, connection.in_waiting)))
                    if chunk:
                        pending.extend(chunk)
                        while b'\n' in pending:
                            line, _, remaining = pending.partition(b'\n')
                            pending = bytearray(remaining)
                            result = parser.feed_line(bytes(line))
                            if result is not None:
                                last_frame = time.monotonic()
                                indices.append(parser.normalized_index)
                                rows.append(result[1:])
                                if len(rows) >= self.config.block_size:
                                    emit_block()
                                    last_emit = time.monotonic()
                        if len(pending) > 512:
                            pending.clear()
                            parser.stats.invalid += 1
                    now = time.monotonic()
                    if rows and now - last_emit >= 0.1:
                        emit_block()
                        last_emit = now
                    if now - last_frame > self.config.silence_timeout_s:
                        raise TimeoutError('Sin datos seriales: compruebe conexion y firmware')
                emit_block()
        except Exception as exc:
            if rows:
                try:
                    emit_block()
                except Exception as block_exc:
                    self.error.emit(f'Error al procesar bloque pendiente: {block_exc}')
            if not self._stopping:
                self.error.emit(f'Error de adquisicion serial: {exc}')
        finally:
            self.stats_ready.emit(replace(parser.stats))
            self.status_changed.emit('Desconectado')
