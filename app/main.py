"""Entrada local: python -m app.main [--demo] [--config config.json]."""

import argparse
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.config import AppConfig


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bioarte ECG/EMG educativo")
    parser.add_argument("--demo", action="store_true", help="Habilita exclusivamente datos simulados")
    parser.add_argument("--config", help="Archivo JSON de configuracion")
    parser.add_argument("--smoke-seconds", type=float, help="Prueba demo automatica con cierre acotado")
    args = parser.parse_args(argv)
    if args.smoke_seconds is not None and (not args.demo or args.smoke_seconds <= 0):
        parser.error("--smoke-seconds requiere --demo y duracion positiva")
    try:
        config = AppConfig.load(args.config) if args.config else AppConfig()
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    from app.ui import MainWindow

    application = QApplication.instance() or QApplication(sys.argv[:1])
    application.setApplicationName("Bioarte ECG-EMG")
    window = MainWindow(config, demo=args.demo)
    window.show()
    smoke_ok = [False]
    if args.smoke_seconds:
        QTimer.singleShot(0, window.start_button.click)

        def finish_smoke():
            block = window.last_block
            smoke_ok[0] = bool(
                block is not None
                and len(block)
                and block.raw.simulated
                and len(window.plots) == 3
                and all(len(curves[0].getData()[0]) for curves in window.curves)
            )
            print("Demo smoke:", "OK (3 canales y curvas actualizadas)" if smoke_ok[0] else "ERROR sin datos/curvas")
            window.close()

        QTimer.singleShot(int(args.smoke_seconds * 1000), finish_smoke)
    result = application.exec()
    return (0 if smoke_ok[0] else 1) if args.smoke_seconds else result


if __name__ == "__main__":
    raise SystemExit(main())
