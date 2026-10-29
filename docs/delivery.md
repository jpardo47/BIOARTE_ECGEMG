# Entrega del proyecto Bioarte ECG–EMG

## Estado

Software terminado y verificado; firmware compilado y cargado al Mega de COM10 con autorización. Adquisición real, GUI y grabación funcionan. Validación EMG parcialmente pendiente: RAW A1 queda en 0–1 cuentas, pese a cableado RAW→A1 confirmado por el usuario. No se declara validado el funcionamiento eléctrico del MyoWare.

Los dos Markdown originales de la raíz permanecen intactos. Esta carpeta es la raíz del proyecto solicitado; no hace falta entrar a una subcarpeta adicional.

## Trabajo por agente

- SOL: contratos/modelos/configuración, entorno virtual, entrada CLI, empaquetado, scripts, README, integración, pruebas de Qt/hardware y documentación. Commit inicial 51b37f8; commit final identificable mediante git log -1.
- TERRA: firmware Mega, parser tolerante, pérdidas/índice/tiempo, fuente demo, filtros causales y detector básico R. Commit 1a12a6e; 10 pruebas propias.
- LUNA: GUI, grabador asíncrono, calibración JSON y ambos modos de audio. Commit 725af0b; 12 pruebas propias.

SOL integró controles de cierre/reconexión y entrega del último bloque, metadatos con versión/frecuencia correctas, protección del hilo CSV anterior, nota pendiente respetando intervalo mínimo, validación de configuración y disposición de tres plots. No hay solicitudes de contrato pendientes ni dependencias circulares detectadas.

## Instalación y ejecución exactas en este equipo

PowerShell, desde C:\Users\sebas\OneDrive\Escritorio\BIOARTE_MUSICA:

```powershell
# El entorno .venv ya está creado e instalado.
.\.venv\Scripts\python.exe -m app.main --demo
.\.venv\Scripts\python.exe -m app.main
# Alternativa
.\run.bat
```

Para reinstalar:

```powershell
& 'C:\Users\sebas\AppData\Local\Programs\Python\Python312\python.exe' -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

En modo real seleccionar COM10 → Conectar → Iniciar adquisición. No se inicia demo automáticamente ante errores. La aplicación quedó cerrada y el puerto liberado después de las pruebas.

## Firmware

Ya cargado en COM10. Comandos reproducibles usando Arduino CLI instalado:

```powershell
& 'C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe' compile --fqbn arduino:avr:mega arduino/acquisition_mega
& 'C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe' upload --fqbn arduino:avr:mega --port COM10 arduino/acquisition_mega
```

Compilación: 3928 bytes flash, 210 bytes RAM. Protocolo por defecto 230400/1000Hz con cuatro campos. README documenta cálculo de margen insuficiente en el peor caso y alternativa 460800 sincronizada.

## Resultados de pruebas

| Módulo | Aprobadas |
|---|---:|
| Parser serial | 5 |
| Procesamiento y estados | 5 |
| Grabación CSV/JSON | 4 |
| Calibración | 5 |
| Audio dummy/mocks | 5 |
| Configuración | 8 |
| Integración Qt/serial/calibración | 5 |
| Total | **37** |

compileall, Ruff, pip check, análisis de ciclos y conservación de documentos originales: aprobados. Suite completa terminó con código 0. Demo nativa recibió tres canales, actualizó curvas y cerró con código 0; captura docs/demo-preview.png. Registro detallado y restricciones del runner Qt en docs/integration-log.md.

## Resultado del montaje real y próximo paso físico

Prueba acotada con GUI: 12997 muestras, 999.6923Hz efectivos, cero pérdidas y cero líneas inválidas, CSV/JSON correctos. ECG A0 varió entre 132 y 339 cuentas; RAW A1 entre 0 y 1; ENV A2 entre 0 y 83. Estos rangos no validan calidad fisiológica ni tienen uso diagnóstico.

**Próximo paso:** retirar electrodos del cuerpo; comprobar con multímetro VIN–GND del MyoWare (~3.3V) y RAW–GND (~1.65V); con montaje apagado revisar masa común, soldadura RAW y continuidad hasta A1. Solo después repetir adquisición y calibrar reposo/contracción. Pendientes además escucha real, estabilidad larga y calidad de señal/aislamiento. No reubicar cables con electrodos puestos.

Grabación personal: recordings/bioarte_20261029_103307_509073.csv y JSON asociado; resumen hardware-validation.json y captura live-preview.png en recordings/. Excluidos de Git. No se sustituyen señales reales por simulación.

## Árbol e inventario de fuentes entregadas

Se excluyen .git/, .venv/, .tmp/, cachés y grabaciones personales. La lista recoge archivos versionados y nuevos; los dos documentos originales de la raíz se preservan adicionalmente con sus nombres originales.

```text
BIOARTE_MUSICA/
  .gitattributes
  .gitignore
  README.md
  app/__init__.py
  app/audio_engine.py
  app/config.py
  app/data_recorder.py
  app/demo_source.py
  app/main.py
  app/models.py
  app/serial_worker.py
  app/signal_processing.py
  app/ui.py
  arduino/acquisition_mega/acquisition_mega.ino
  audio/README.md
  calibration/.gitkeep
  calibration/README.md
  config.example.json
  docs/architecture.md
  docs/delivery.md
  docs/demo-preview.png
  docs/handoffs/luna-requests.md
  docs/handoffs/terra-requests.md
  docs/integration-log.md
  docs/interfaces.md
  docs/task-board.md
  prompt-codex-ecg.md
  pyproject.toml
  recordings/.gitkeep
  requirements.txt
  run.bat
  run.sh
  tests/conftest.py
  tests/test_audio_engine.py
  tests/test_calibration.py
  tests/test_config.py
  tests/test_data_recorder.py
  tests/test_integration.py
  tests/test_parser.py
  tests/test_signal_processing.py
```

Comprobación final del archivo real: **13124 filas de datos, 15 columnas**, índices consecutivos de 32 a 13155. El contador del observador previo a la detención era 12997; el CSV incluye además los bloques finales drenados durante el cierre. La grabación comienza después del primer bloque, por eso su primer índice es 32.
