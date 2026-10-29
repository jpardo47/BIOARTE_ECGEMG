"""Best-effort audio output; failures are isolated from signal acquisition."""

from __future__ import annotations

import math
import time

import numpy as np

from .config import AppConfig


class AudioEngine:
    def __init__(self, config: AppConfig):
        self.config = config
        self.error: str | None = None
        self.enabled = False
        self.mode: str | None = None
        self._pygame = None
        self._note_channel = None
        self._beat_channel = None
        self._notes: dict[int, object] = {}
        self._beat_sound = None
        self._last_note_at = 0.0
        self._last_level: int | None = None
        self._pending_sync_level: int | None = None
        self._volume = 0.0
        self._music_path: str | None = None

    def volume_for_level(self, level: float) -> float:
        level = float(np.clip(level if math.isfinite(float(level)) else 0.0, 0.0, 1.0))
        lo, hi = sorted((float(self.config.volume_min), float(self.config.volume_max)))
        return float(np.clip(lo + level * (hi - lo), 0.0, 1.0))

    def level_to_note(self, level: float) -> int:
        scale = self.config.pentatonic
        value = float(np.clip(level if math.isfinite(float(level)) else 0.0, 0.0, 1.0))
        return int(scale[min(len(scale) - 1, int(value * len(scale)))])

    def start(self, mode: str, music_path: str | None = None, sync_r: bool = False) -> bool:
        self.stop()
        self.error = None
        self._sync_r = bool(sync_r)
        self._last_note_at = -float("inf")
        self._volume = 0.0
        if mode not in ("music", "generative"):
            self.error = "Modo de audio desconocido"
            return False
        if mode == "music" and (not music_path or not __import__("pathlib").Path(music_path).is_file()):
            self.error = "Selecciona un archivo de música existente"
            return False
        try:
            import pygame

            self._pygame = pygame
            pygame.mixer.init(frequency=self.config.audio_rate, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(4)
            self._note_channel = pygame.mixer.Channel(1)
            self._beat_channel = pygame.mixer.Channel(2)
            self._notes = {
                midi: self._make_tone(pygame, midi, self.config.note_duration_s) for midi in self.config.pentatonic
            }
            self._beat_sound = self._make_click(pygame)
            if mode == "music":
                pygame.mixer.music.load(music_path)
                pygame.mixer.music.set_volume(self.config.volume_min)
                pygame.mixer.music.play(-1)
                self._music_path = music_path
            self.mode = mode
            self.enabled = True
            return True
        except Exception as exc:
            self.error = f"Audio no disponible: {exc}"
            self.enabled = False
            self._shutdown_mixer()
            return False

    def update(self, level: float, r_peak: bool = False) -> None:
        if not self.enabled:
            return
        try:
            value = float(np.clip(float(level), 0.0, 1.0))
            target_volume = self.volume_for_level(value)
            alpha = float(np.clip(self.config.audio_smoothing, 0.0, 1.0))
            self._volume += alpha * (target_volume - self._volume)
            if self.mode == "music":
                self._pygame.mixer.music.set_volume(self._volume)
                if r_peak and self._beat_sound:
                    self._beat_channel.play(self._beat_sound)
            elif self.mode == "generative":
                note = self.level_to_note(value)
                changed = note != self._last_level
                if changed:
                    self._last_level = note
                    self._pending_sync_level = note
                if self._pending_sync_level is not None and (not self._sync_r or r_peak):
                    if self._trigger_note(self._pending_sync_level, self._volume):
                        self._pending_sync_level = None
        except Exception as exc:
            self.error = f"Error de reproducción: {exc}"
            self.enabled = False
            self._shutdown_mixer()

    def _trigger_note(self, midi: int, volume: float) -> bool:
        now = time.monotonic()
        if now - self._last_note_at < self.config.note_interval_s:
            return False
        tone = self._notes.get(midi)
        if tone is not None:
            tone.set_volume(float(np.clip(volume, 0.0, 1.0)))
            self._note_channel.play(tone)
            self._last_note_at = now
            return True
        return False

    def stop(self) -> None:
        self.enabled = False
        if self._pygame is not None:
            try:
                self._pygame.mixer.music.stop()
                for channel in (self._note_channel, self._beat_channel):
                    if channel is not None:
                        channel.stop()
            except Exception as exc:
                self.error = self.error or f"No se pudo detener el audio: {exc}"
            self._shutdown_mixer()
        self.mode = None
        self._notes = {}
        self._last_level = None
        self._pending_sync_level = None

    def _shutdown_mixer(self) -> None:
        if self._pygame is not None:
            try:
                self._pygame.mixer.quit()
            except Exception as exc:
                self.error = self.error or f"No se pudo cerrar el mezclador: {exc}"
        self._pygame = None
        self._note_channel = None
        self._beat_channel = None
        self._beat_sound = None

    def _make_tone(self, pygame, midi_note: int, duration_s: float):
        rate = int(self.config.audio_rate)
        count = max(1, int(rate * max(0.04, duration_s)))
        t = np.arange(count, dtype=np.float64) / rate
        frequency = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
        envelope = np.minimum(1.0, t * 40.0) * np.minimum(1.0, np.maximum(0.0, (duration_s - t) * 16.0))
        wave = (np.sin(2 * np.pi * frequency * t) * envelope * 0.45 * 32767).astype(np.int16)
        stereo = np.column_stack((wave, wave))
        return pygame.sndarray.make_sound(stereo)

    def _make_click(self, pygame):
        rate = int(self.config.audio_rate)
        t = np.arange(max(1, int(rate * 0.055))) / rate
        wave = (np.sin(2 * np.pi * 1100 * t) * np.exp(-t * 75) * 0.45 * 32767).astype(np.int16)
        return pygame.sndarray.make_sound(np.column_stack((wave, wave)))
