# Bioarte ECG–EMG

Aplicación local educativa para adquirir tres canales con Arduino Mega 2560, visualizar señales crudas y filtradas, guardar CSV con metadatos y producir música reactiva o una melodía pentatónica. Esta carpeta es la raíz del proyecto; los dos documentos Markdown originales se conservan como antecedentes. La especificación actual prevalece donde existe una contradicción.

> Prototipo educativo y artístico. No es un dispositivo médico y no debe utilizarse para diagnóstico. Cuando haya electrodos conectados a una persona, utilizar alimentación por batería, portátil desconectado del cargador y de otros equipos conectados a la red, y preferiblemente aislamiento USB.

## Hardware y conexiones

Arduino Mega 2560, ECG Click MIKROE-2455, MyoWare 2.0, electrodos y cables correspondientes, cable USB y preferiblemente aislador USB compatible. Para RAW puede ser necesario soldar un cable al pad RAW: verificar la serigrafía con el sistema apagado.

| Dispositivo | Terminal | Arduino Mega |
|---|---|---|
| ECG Click | 5V | 5V |
| ECG Click | GND | GND común |
| ECG Click | AN | A0 |
| MyoWare 2.0 | VIN | **3.3V** |
| MyoWare 2.0 | GND | GND común |
| MyoWare 2.0 | RAW | A1 |
| MyoWare 2.0 | ENV | A2 |

```text
ECG Click AN ── A0 ┐
MyoWare RAW ─── A1 ├─ Mega ADC → USB serial → filtros causales → GUI / CSV / audio
MyoWare ENV ─── A2 ┘
Mega 5V ────── ECG Click 5V
Mega 3.3V ──── MyoWare VIN
Mega GND ───── ambos GND
```

**Está prohibido usar VIN del Mega para alimentar el MyoWare.** VIN del sensor y VIN del Mega son terminales diferentes. No conectar 3.3V a AREF y no activar `analogReference(INTERNAL)`. Mantener la referencia DEFAULT del ADC, nominalmente 5V. Todas las masas deben estar unidas.

MyoWare se alimenta a 3.3V siguiendo la corrección explícita del proyecto; su fabricante admite 3.3V como tensión típica. RAW queda cerca de 1.65V en reposo y RAW/ENV no deberían superar la alimentación del sensor. El pin 3.3V del Mega tiene un límite de 50mA: no agregar cargas de alto consumo en ese riel. [MyoWare: especificaciones](https://myoware.com/products/technical-specifications/), [Mega: pinout oficial](https://docs.arduino.cc/resources/pinouts/A000067-full-pinout.pdf).

Los tres canales usan el mismo ADC de 10 bits con referencia de 5V, incluso los del sensor a 3.3V:

```python
voltage = adc_counts * adc_reference_voltage / 1023.0
```

El valor inicial `adc_reference_voltage=5.0` es configurable. Medir la referencia real con multímetro para ajustar la escala. El rango nominal del MyoWare ocupa aproximadamente 0–675 cuentas, no 0–1023. Las unidades de los filtros son voltios de salida del sensor, no milivoltios de potencial corporal. [Referencia ADC del Mega](https://store.arduino.cc/products/arduino-mega-2560-rev3).

## Instalación en Windows

Instalar Python 3.11 o superior de [python.org](https://www.python.org/downloads/) con soporte de entornos virtuales y pip. Abrir PowerShell en esta carpeta. Si `python` abre la tienda de Windows, usar la ruta real de Python instalado; en este equipo se encontró `C:\Users\sebas\AppData\Local\Programs\Python\Python312\python.exe`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.main --demo
```

Si el alias `python` no funciona en este equipo:

```powershell
& 'C:\Users\sebas\AppData\Local\Programs\Python\Python312\python.exe' -m venv .venv
```

No es necesario activar el entorno; alternativamente usar `.\.venv\Scripts\Activate.ps1` y después `python -m app.main`. Las dependencias no tienen versiones fijadas arbitrariamente. Python 3.11 es el mínimo de empaquetado del proyecto.

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
sh run.sh --demo
```

## Firmware

En Arduino IDE abrir `arduino/acquisition_mega/acquisition_mega.ino`, elegir **Arduino Mega or Mega 2560**, procesador ATmega2560 y el puerto correspondiente. Cerrar monitor/plotter serial y la adquisición Python antes de cargar. No requiere bibliotecas adicionales.

Con Arduino CLI (sustituir COM3 por el puerto real):

```powershell
arduino-cli core install arduino:avr
arduino-cli compile --fqbn arduino:avr:mega arduino/acquisition_mega
arduino-cli board list
arduino-cli upload --fqbn arduino:avr:mega --port COM3 arduino/acquisition_mega
```

La instalación Arduino IDE de este equipo incluye CLI en `C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe`; se puede invocar con `& 'ruta completa'` en PowerShell.

## Uso

```powershell
# Real: nunca genera datos sintéticos
.\.venv\Scripts\python.exe -m app.main
# Simulación explícita, marcada en pantalla y metadatos
.\.venv\Scripts\python.exe -m app.main --demo
# Configuración externa opcional
.\.venv\Scripts\python.exe -m app.main --config config.example.json
# Alternativa Windows
.\run.bat --demo
```

En modo real: Actualizar puertos → seleccionar COM → Conectar → Iniciar adquisición. Detener adquisición y Desconectar liberan la fuente y cierran la grabación. En demo elegir la fuente simulada e Iniciar adquisición. La bandera `--demo` habilita el selector demo; no existe simulación automática cuando falla el hardware. Cada nueva adquisición reinicia filtros y búferes.

Tres gráficas muestran A0 ECG, A1 RAW con RMS/envolvente y A2 ENV. Se actualizan alrededor de 30FPS, independientemente del muestreo. La ventana visible permite 2–15s y los búferes están acotados. La interfaz muestra tasas nominal/efectiva, recibidas/perdidas/inválidas, saturación por canal, BPM y nivel EMG. Saturación inicial: ADC ≤5 o ≥1018. ENV puede llegar normalmente cerca de cero en reposo; ese indicador no demuestra por sí solo una falla del sensor. En MyoWare a 3.3V también puede existir recorte del sensor alrededor de 675 cuentas sin llegar al umbral ADC alto.

## Calibración y audio

Elegir ENV A2, RMS de RAW A1 o envolvente digital de RAW. Iniciar adquisición, mantener reposo y pulsar Calibrar reposo (5s); después mantener una contracción cómoda y pulsar Calibrar contracción (5s). La barra muestra progreso. La contracción debe superar el reposo; la calibración completa se guarda en `calibration/`. Cargar calibración permite reutilizar un JSON con la misma fuente y modo. Demo y real mantienen calibraciones separadas.

Normalización: `clip((value-rest)/(active-rest+1e-9), 0, 1)`, con suavizado posterior. Para audio conviene esperar a que los transitorios de filtros hayan pasado y calibrar de nuevo si cambian sensor, ganancia o montaje.

Música reactiva: elegir WAV, OGG o MP3 y activar audio. Reproduce en bucle; el EMG controla volumen suavizado y los picos R disparan un sonido corto en un canal separado. El soporte de decodificación depende de la instalación de pygame/SDL.

Melodía generativa: seleccionar el modo y activar audio, sin archivos externos. El nivel normalizado elige notas pentatónicas. Se puede configurar volumen, duración, intervalo mínimo y esperar al siguiente pico R. Detener audio no detiene adquisición. Los errores de dispositivo/archivo aparecen en la ventana; la captura sigue funcionando.

## Grabación

Durante adquisición pulsar Iniciar grabación; Detener grabación cierra el archivo y drena los bloques pendientes. Se crean `recordings/bioarte_FECHA_HORA.csv` y un JSON del mismo nombre. La escritura utiliza un hilo y una cola acotada; si el disco no mantiene el ritmo se informa el fallo en lugar de perder bloques silenciosamente.

Columnas CSV en orden:

```text
sample_index,time_s,ecg_adc,emg_raw_adc,emg_env_adc,ecg_v,emg_raw_v,emg_env_v,ecg_filtered,emg_filtered,emg_rms,emg_envelope,emg_env_smoothed,r_peak,bpm
```

Las cuentas ADC se conservan sin filtrar. `sample_index` es el índice normalizado de sesión: empieza en 0, conserva saltos y mantiene continuidad ante reinicio/desbordamiento del contador de firmware; `time_s=sample_index/fs`. No es un timestamp físico por muestra. BPM=0 significa que todavía no hay un intervalo válido. JSON registra fecha ISO, puerto, baudrate, tasas nominal/efectiva inicial, referencia ADC, filtros, fuente EMG, calibración, modo y versión. Grabaciones y calibraciones personales se excluyen de Git.

## Procesamiento y límites de transporte

Filtros causales Butterworth SOS con estado entre bloques: ECG 0.5–40Hz, RAW 20–400Hz, notch 60Hz Q30 opcional, RMS 150ms, envolvente y ENV suavizada a 5Hz. Se procesan únicamente muestras nuevas en el trabajador. La configuración de ejemplo permite desactivar notch o ajustar parámetros; una frecuencia incompatible con Nyquist produce un error controlado. El detector R es básico/adaptativo, con refractario 250ms: no es una validación clínica ni garantiza detectar todos los latidos.

El protocolo predeterminado es ASCII 230400 baudios, 1000 tramas/s, 8N1:

```text
#fs=1000,columns=n,ecg,emg_raw,emg_env
0,512,338,120
```

Con LF una trama máxima tiene 26 bytes (índice de 10 dígitos, tres ADC de 4, tres comas y LF). 1000×26×10=260000 bit/s supera 230400; no puede garantizarse el ritmo indefinidamente con el formato ASCII solicitado. En condiciones típicas tres ADC de tres dígitos e índice de siete dígitos requieren 200000bit/s. La cuantización del UART del AVR también afecta la velocidad efectiva. El firmware conserva el valor solicitado, evita ráfagas ilimitadas y deja saltos de índice al omitir períodos. Revisar pérdidas y tasa efectiva durante una sesión larga con el hardware real.

Alternativa seleccionable: compilar con baudrate 460800 y cambiar también `baudrate` en una copia de `config.example.json`; consultar el comentario del firmware para la constante/flag exacta. Ambos extremos deben coincidir. La estabilidad depende del UART/puente USB y debe medirse. Un protocolo binario con CRC es una mejora futura y no se activa silenciosamente.

A 1kHz, RAW analógica cercana a 500Hz está cerca de Nyquist. Un filtro digital a 400Hz no elimina aliasing que ya haya ocurrido; para medición de mayor calidad hace falta antialiasing analógico adecuado o mayor muestreo/ADC externo. A0/A1/A2 se leen secuencialmente, no simultáneamente.

## Problemas frecuentes

| Síntoma | Acción |
|---|---|
| Ruido de 60Hz | Revisar aislamiento, contacto de electrodos y cables; notch configurable. No conectar cargador durante prueba corporal. |
| Saturación ADC | Bajar ganancia ECG, revisar cableado y referencia; verificar también recorte propio del MyoWare a 3.3V. |
| Pérdida de muestras / tasa baja | Revisar margen serial, cable/puente USB y carga; comparar tasas y saltos; probar alternativa de baudrate sincronizada. |
| Puerto ocupado | Cerrar monitor serial, otra aplicación o instancia; desconectar desde GUI y volver a conectar. |
| Puerto ausente | Actualizar puertos; revisar cable USB de datos y controlador de la placa. |
| Sin audio | Comprobar salida del sistema y archivo; detener/reiniciar audio. La adquisición sigue disponible. |
| Arduino desconectado | Se informa el error, termina captura/grabación; volver a seleccionar puerto y conectar. |
| RAW plana | Revisar que A1 esté en RAW y A2 en ENV; ENV no permite reconstruir RAW. |
| Calibración rechazada | Contracción debe superar reposo; comprobar fuente, esperar transitorios y repetir. |

## Verificación reproducible

```powershell
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m app.main --demo --smoke-seconds 4
```

Ruff es opcional: instalar con `.\.venv\Scripts\python.exe -m pip install ruff`. Las pruebas de audio usan controlador dummy/mocks, sin requerir altavoz físico. El smoke de CLI abre y cierra la ventana en tiempo acotado; las pruebas de integración comprueban además recepción de bloques y curvas actualizadas. No hay configuración Mypy obligatoria.

Los resultados reales y las comprobaciones pendientes se registran en `docs/integration-log.md`; no debe confundirse la validación demo con validación eléctrica o fisiológica del montaje.

## Organización

`app/` aplicación; `arduino/` firmware; `audio/` instrucciones de recursos opcionales; `recordings/` CSV+JSON; `calibration/` perfiles; `tests/` verificaciones; `docs/` contratos, arquitectura, tablero y handoffs de TERRA/LUNA. SOL integra después del trabajo paralelo. No se han modificado los Markdown originales.


## Estado de entrega

Software integrado: **37 pruebas aprobadas**, firmware Mega compilado, compileall y Ruff limpios, demo gráfica nativa verificada. Consulte [registro de integración](docs/integration-log.md) y [entrega con árbol e inventario](docs/delivery.md). La validación eléctrica y una sesión larga con hardware siguen siendo necesarias.

Para la alternativa de baudrate, compilar con:

```powershell
arduino-cli compile --fqbn arduino:avr:mega --build-property "compiler.cpp.extra_flags=-DACQUISITION_BAUD_RATE=460800UL" arduino/acquisition_mega
```

Después cargar ese firmware y usar `baudrate: 460800` en el JSON de Python. Mantener 230400 en ambos extremos para el firmware predeterminado.

Prueba real del montaje en COM10: firmware cargado con autorización; enlace de tres canales y grabación verificados (~999.7Hz, sin pérdidas en la prueba breve). RAW A1 permaneció cerca de cero: la validación eléctrica del MyoWare queda pendiente; detalles y siguiente medición en docs/integration-log.md.


## Piano y violín

En Sonificación, elegir **Melodía generativa**, seleccionar **Piano sintetizado** o **Violín sintetizado**, y pulsar **Iniciar audio**. El selector aplica el timbre al reiniciar audio. **Probar instrumento** reproduce una nota explícita independiente de ECG/EMG. Los timbres se generan con armónicos y envolventes; son aproximaciones sintetizadas, no grabaciones de instrumentos acústicos. Piano usa ataque corto y decaimiento; violín usa ataque progresivo, sostenimiento y vibrato suave. Las notas siguen una escala pentatónica, no reproducen una obra clásica específica.

También se incluyen `audio/preview-piano.wav` y `audio/preview-violin.wav`, frases de ejemplo generadas localmente. Se pueden seleccionar como archivo en **Música reactiva** para reproducirlas en bucle y controlar volumen con el nivel EMG calibrado.

Antes de comprobar respuesta al músculo, seleccionar ENV A2 y calibrar 5 segundos de reposo y 5 segundos de contracción cómoda. Un audio de prueba audible no demuestra que la calibración fisiológica ya sea válida. Si ECG recorta en 0/1023, no usar sincronización por R hasta estabilizar contacto/ganancia. Los datos personales de calibración se guardan en `calibration/` y se excluyen de Git.


## Inspección de ondas ECG

La aplicación dibuja todas las muestras, no solo picos R. **Centrar crudo: solo visualización** elimina el desplazamiento de continua únicamente en la gráfica para compararlo con el filtrado. Desmarcarlo recupera el voltaje absoluto. **Mostrar ECG crudo** permite ocultarlo y ampliar el filtrado. Para ver detalles usar una ventana de 2s; las ondas pequeñas necesitan señal estable y sin recorte. CSV y filtros conservan sus valores originales. Ningún ajuste visual reconstruye una señal saturada; el modo demo es una forma sintética simplificada.

Si el LED **VIN** del MyoWare no enciende, comprobar con multímetro 3.3V entre VIN–GND en el propio sensor; no confundirlo con **ENV**, que puede estar apagado en reposo. No agregar otra fuente en paralelo. El uso de Uno como fuente separada y sus restricciones están documentados en docs/integration-log.md.
