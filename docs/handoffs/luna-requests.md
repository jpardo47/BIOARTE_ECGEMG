# Informe LUNA y resolución SOL

LUNA entregó ui.py, audio_engine.py, data_recorder.py, documentación audio/calibration y tres módulos de pruebas. Commit 725af0b. Interfaces públicas: MainWindow, AudioEngine start/update/stop/mapeos y DataRecorder start/write/stop; save_calibration/load_calibration.

12 pruebas propias aprobadas, compileall y Ruff limpios; smoke Qt recibió bloque y confirmó tres plots con cierre exit 0.

SOL revisó y resolvió: limpieza en finished/error y desconexión; separación demo/real; reposo pendiente hasta contracción válida; eventos R sin calibración; versión central en metadatos; selección de volumen mínimo; controles adaptados al tamaño de pantalla; último bloque antes del cierre; evitar reiniciar grabador mientras su hilo anterior sigue activo; conservar nota pendiente hasta cumplir intervalo mínimo. Se mantiene la referencia a un QThread que aún esté terminando y se difiere el cierre de ventana si hace falta.

Limitaciones: validar sonido por salida física, calidad muscular y estabilidad serial con el montaje real. Sin solicitudes de contrato pendientes.
