"""Visual tokens, Qt stylesheet and vector icons for the Bioarte interface."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtSvg

ASSETS = Path(__file__).resolve().parent / "assets"

# Semantic colour tokens: dark scientific theme, text pairs meet WCAG AA on SURFACE.
BG = "#070B14"
SURFACE = "#0F172A"
SURFACE_ALT = "#0B1222"
RAISED = "#16213A"
BORDER = "#1E293B"
BORDER_STRONG = "#334155"
TEXT = "#E2E8F0"
TEXT_MUTED = "#94A3B8"
TEXT_DISABLED = "#526075"
PRIMARY = "#2563EB"
PRIMARY_HOVER = "#3B82F6"
FOCUS = "#60A5FA"
SUCCESS = "#4ADE80"
WARNING = "#FBBF24"
DANGER = "#F87171"
PLOT_BG = "#0A1120"

# Raw traces stay muted so processed signals carry the visual weight.
TRACE_RAW = "#64748B"
TRACE_ECG = "#F43F5E"
TRACE_EMG = "#38BDF8"
TRACE_RMS = "#A3E635"
TRACE_ENVELOPE = "#F59E0B"
TRACE_ENV_RAW = "#94A3B8"
TRACE_ENV_SMOOTH = "#34D399"

UI_FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Inter", "Noto Sans", "DejaVu Sans"]
MONO_FAMILIES = ["Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono"]

# Lucide-style strokes (24×24 viewBox); currentColor is replaced at render time.
_ICONS = {
    "activity": '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18'
    'a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "stop": '<rect width="14" height="14" x="5" y="5" rx="2"/>',
    "pause": '<rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/>',
    "record": '<circle cx="12" cy="12" r="6" fill="currentColor"/>',
    "refresh": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>'
    '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    "plug": '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/>'
    '<path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
    "unplug": '<path d="m19 5 3-3"/><path d="m2 22 3-3"/>'
    '<path d="M6.3 20.3a2.4 2.4 0 0 0 3.4 0L12 18l-6-6-2.3 2.3a2.4 2.4 0 0 0 0 3.4Z"/>'
    '<path d="M7.5 13.5 10 11"/><path d="M10.5 16.5 13 14"/>'
    '<path d="m12 6 6 6 2.3-2.3a2.4 2.4 0 0 0 0-3.4l-2.6-2.6a2.4 2.4 0 0 0-3.4 0Z"/>',
    "folder": '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4'
    'a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
    "volume": '<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6'
    'a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/>'
    '<path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.364 18.364a9 9 0 0 0 0-12.728"/>',
    "music": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
}


def _render(name: str, color: str, size: int) -> QtGui.QPixmap:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + _ICONS[name] + "</svg>"
    ).replace("currentColor", color)
    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg.encode("utf-8")))
    scale = 2
    pixmap = QtGui.QPixmap(size * scale, size * scale)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def icon(name: str, color: str = TEXT, size: int = 16) -> QtGui.QIcon:
    result = QtGui.QIcon()
    result.addPixmap(_render(name, color, size), QtGui.QIcon.Mode.Normal)
    result.addPixmap(_render(name, TEXT_DISABLED, size), QtGui.QIcon.Mode.Disabled)
    return result


def pixmap(name: str, color: str = TEXT, size: int = 16) -> QtGui.QPixmap:
    return _render(name, color, size)


def ui_font(pixel_size: int = 13, weight=QtGui.QFont.Weight.Normal) -> QtGui.QFont:
    font = QtGui.QFont()
    font.setFamilies(UI_FAMILIES)
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


def mono_font(pixel_size: int = 13, weight=QtGui.QFont.Weight.Normal) -> QtGui.QFont:
    font = QtGui.QFont()
    font.setFamilies(MONO_FAMILIES)
    font.setStyleHint(QtGui.QFont.StyleHint.Monospace)
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


def stylesheet() -> str:
    chevron_down = (ASSETS / "chevron-down.svg").as_posix()
    chevron_up = (ASSETS / "chevron-up.svg").as_posix()
    check = (ASSETS / "check.svg").as_posix()
    return f"""
QMainWindow, QWidget#root {{ background: {BG}; }}
QWidget {{ color: {TEXT}; }}
QToolTip {{ background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER_STRONG}; padding: 6px 8px; }}

QScrollArea#sidebar {{ background: {SURFACE}; border: none; border-right: 1px solid {BORDER}; }}
QWidget#sidebarContents {{ background: {SURFACE}; }}
QLabel#brandTitle {{ font-size: 18px; font-weight: 700; }}
QLabel#brandSubtitle, QLabel#muted, QLabel#footer {{ color: {TEXT_MUTED}; }}
QLabel#footer {{ font-size: 11px; }}

QFrame#card {{ background: {SURFACE_ALT}; border: 1px solid {BORDER}; border-radius: 10px; }}
QLabel#cardTitle {{ color: {TEXT_MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
QLabel#fieldLabel {{ color: {TEXT_MUTED}; font-size: 12px; }}

QLabel#pageTitle {{ font-size: 20px; font-weight: 600; }}
QLabel#status {{ color: {TEXT_MUTED}; }}

QLabel#badge {{ border-radius: 11px; padding: 3px 10px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;
    background: {RAISED}; color: {TEXT_MUTED}; border: 1px solid {BORDER_STRONG}; }}
QLabel#badge[tone="ok"] {{ background: rgba(74, 222, 128, 0.12); color: {SUCCESS}; border-color: rgba(74, 222, 128, 0.45); }}
QLabel#badge[tone="warn"] {{ background: rgba(251, 191, 36, 0.12); color: {WARNING}; border-color: rgba(251, 191, 36, 0.45); }}
QLabel#badge[tone="danger"] {{ background: rgba(248, 113, 113, 0.14); color: {DANGER}; border-color: rgba(248, 113, 113, 0.5); }}
QLabel#badge[tone="info"] {{ background: rgba(96, 165, 250, 0.14); color: {FOCUS}; border-color: rgba(96, 165, 250, 0.5); }}

QLabel#errorBanner {{ background: #2A1215; color: #FECACA; border: 1px solid #7F1D1D; border-left: 4px solid {DANGER};
    border-radius: 8px; padding: 8px 12px; }}

QFrame#kpi {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
QLabel#kpiCaption {{ color: {TEXT_MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
QLabel#kpiUnit, QLabel#kpiDetail {{ color: {TEXT_MUTED}; font-size: 12px; }}
QLabel#kpiValue {{ color: {TEXT}; }}
QLabel#kpiValue[tone="warn"] {{ color: {WARNING}; }}
QLabel#kpiValue[tone="danger"] {{ color: {DANGER}; }}
QLabel#kpiValue[tone="ok"] {{ color: {SUCCESS}; }}
QLabel#kpiDetail[tone="warn"] {{ color: {WARNING}; }}
QLabel#kpiDetail[tone="ok"] {{ color: {SUCCESS}; }}

QFrame#plotCard {{ background: {PLOT_BG}; border: 1px solid {BORDER}; border-radius: 10px; }}

QPushButton {{ background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER_STRONG}; border-radius: 8px;
    padding: 7px 12px; min-height: 20px; font-weight: 500; }}
QPushButton:hover {{ background: #1C2A47; border-color: #475569; }}
QPushButton:pressed {{ background: {SURFACE_ALT}; }}
QPushButton:focus {{ border-color: {FOCUS}; }}
QPushButton:checked {{ background: rgba(96, 165, 250, 0.16); border-color: {FOCUS}; color: {FOCUS}; }}
QPushButton:disabled {{ background: {SURFACE_ALT}; color: {TEXT_DISABLED}; border-color: {BORDER}; }}
QPushButton[variant="primary"] {{ background: {PRIMARY}; border-color: {PRIMARY}; color: #FFFFFF; font-weight: 600; }}
QPushButton[variant="primary"]:hover {{ background: {PRIMARY_HOVER}; border-color: {PRIMARY_HOVER}; }}
QPushButton[variant="primary"]:focus {{ border-color: #BFDBFE; }}
QPushButton[variant="primary"]:disabled {{ background: #1E2B4A; border-color: #1E2B4A; color: {TEXT_DISABLED}; }}
QPushButton[variant="danger"] {{ background: transparent; border-color: #7F1D1D; color: #FCA5A5; }}
QPushButton[variant="danger"]:hover {{ background: #2A1215; border-color: {DANGER}; }}
QPushButton[variant="danger"]:disabled {{ background: transparent; border-color: {BORDER}; color: {TEXT_DISABLED}; }}
QPushButton[variant="icon"] {{ padding: 7px; }}

QComboBox, QLineEdit, QDoubleSpinBox {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER_STRONG};
    border-radius: 6px; padding: 5px 8px; min-height: 20px; selection-background-color: {PRIMARY}; }}
QComboBox:hover, QLineEdit:hover, QDoubleSpinBox:hover {{ border-color: #475569; }}
QComboBox:focus, QLineEdit:focus, QDoubleSpinBox:focus {{ border-color: {FOCUS}; }}
QComboBox:disabled, QLineEdit:disabled, QDoubleSpinBox:disabled {{ color: {TEXT_DISABLED}; border-color: {BORDER}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url("{chevron_down}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER_STRONG};
    selection-background-color: {PRIMARY}; outline: none; padding: 4px; }}
QDoubleSpinBox {{ padding-right: 22px; }}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ border: none; width: 20px; background: transparent; }}
QDoubleSpinBox::up-button {{ subcontrol-position: top right; }}
QDoubleSpinBox::down-button {{ subcontrol-position: bottom right; }}
QDoubleSpinBox::up-arrow {{ image: url("{chevron_up}"); width: 10px; height: 10px; }}
QDoubleSpinBox::down-arrow {{ image: url("{chevron_down}"); width: 10px; height: 10px; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid #475569; background: {SURFACE}; }}
QCheckBox::indicator:hover {{ border-color: {FOCUS}; }}
QCheckBox::indicator:checked {{ background: {PRIMARY}; border-color: {PRIMARY}; image: url("{check}"); }}
QCheckBox:focus {{ color: #FFFFFF; }}

QProgressBar {{ background: {SURFACE}; border: 1px solid {BORDER_STRONG}; border-radius: 6px; min-height: 18px;
    text-align: center; color: {TEXT}; font-size: 11px; }}
QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 5px; }}
QProgressBar#meter {{ min-height: 6px; max-height: 6px; border: none; border-radius: 3px; background: {BORDER}; }}
QProgressBar#meter::chunk {{ border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {TRACE_ENV_SMOOTH}, stop:1 {TRACE_ENVELOPE}); }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER_STRONG}; border-radius: 3px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: #475569; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}
"""
