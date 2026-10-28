# Adquisición y sonificación ECG–EMG con Arduino Mega y Python
## Respuesta técnica
Sí es viable captar simultáneamente el **ECG Click MIKROE-2455** y el **MyoWare 2.0** con un Arduino Mega, enviar las muestras sin filtrar digitalmente por USB y procesarlas en una interfaz local de Python. La arquitectura recomendada es: **sensores analógicos → ADC del Mega → enlace serial → adquisición y filtros causales en Python → PyQtGraph → motor de sonificación**.

La tasa inicial recomendada es **1.000 tramas por segundo**, donde cada trama contiene una lectura ECG y una EMG. Esto supera el mínimo de 256 Hz indicado para el ECG Click y permite trabajar con la salida RAW del MyoWare, cuyo acondicionamiento analógico cubre aproximadamente 20–500 Hz; debido a que el límite superior queda justo en Nyquist, en la práctica conviene filtrar digitalmente hasta 400–450 Hz o, posteriormente, aumentar la tasa con un ADC externo.[^1][^2]

> **Advertencia esencial:** este montaje conecta electrodos al cuerpo. Debe emplearse exclusivamente como prototipo educativo o artístico, no como instrumento diagnóstico. Mientras una persona tenga electrodos conectados, el sistema debe quedar aislado de la red eléctrica: Arduino y sensores alimentados desde batería, portátil funcionando sin cargador ni periféricos conectados a red, y preferiblemente un aislador USB entre Arduino y computador. El fabricante del ECG recomienda alimentación por batería y SparkFun recomienda aislamiento USB al depurar el MyoWare conectado a un PC.[^3][^2]
## Hardware identificado
Las dos primeras fotografías corresponden al **MyoWare 2.0 Muscle Sensor**, con sus tres broches de electrodo y el conector de tres pines rotulado VIN–ENV–GND.

La placa verde de las fotografías tercera y cuarta es el **ECG Click MIKROE-2455**, basado en dos amplificadores MCP609 y una referencia MAX6106. Su salida hacia el microcontrolador es analógica, no I2C ni SPI.[^4]

El Arduino Mega dispone de 16 entradas analógicas de 10 bits, rango predeterminado de 0–5 V, y un puerto serie USB presentado al computador como puerto virtual. Por tanto, no se necesita una biblioteca Arduino específica para leer ninguno de los sensores: `analogRead()` es suficiente; la biblioteca oficial MyoWare es opcional si se desean conversiones a milivoltios, pero no es necesaria para transmitir las cuentas ADC originales.[^5][^6]
## Diferencia crítica del MyoWare
El MyoWare no entrega una única “señal EMG”, sino tres posibles representaciones:

| Salida | Qué contiene | Uso recomendado |
|---|---|---|
| **RAW** | EMG amplificada y filtrada, centrada aproximadamente en VIN/2; ganancia fija 200 | Procesamiento digital, espectro, RMS y sonificación rica |
| **RECT** | RAW rectificada en onda completa; ganancia fija 200 | Magnitud instantánea sin signo |
| **ENV** | Envolvente suavizada de RECT, entre 0 y VIN; ganancia ajustable | Control sencillo de volumen, luces o umbrales |

La placa ya incorpora un pasaaltas cercano a 20,8 Hz, un pasabajas cercano a 498,4 Hz y un detector de envolvente de aproximadamente 3,6 Hz. **Si se conecta solamente ENV, Python no puede reconstruir después la forma de onda RAW:** la rectificación y el suavizado ya eliminaron información.[^1][^7]

En las fotografías, el cabezal soldado de tres pines da acceso directo a **VIN, ENV y GND**. Para obtener RAW hay que soldar cuidadosamente un cable al pad rotulado **RAW** —visible entre los pads auxiliares de la placa— o añadir el MyoWare Link Shield y seleccionar RAW con su interruptor; el fabricante advierte que ese selector solo debe cambiarse con el sistema apagado.[^8][^9][^3]
## Conexiones eléctricas
### Configuración recomendada
| Dispositivo | Terminal del sensor | Arduino Mega | Observación |
|---|---|---|---|
| ECG Click | `5V`, pin mikroBUS 10 | `5V` | La placa ECG funciona a 5 V.[^2] |
| ECG Click | `GND`, pin 8 o 9 | `GND` | Masa analógica común |
| ECG Click | `AN`, pin 1 | `A0` | Es la salida ECG acondicionada.[^4] |
| MyoWare | `VIN` | `5V` | Admite típicamente 3,3 o 5 V; máximo especificado 5,47 V.[^10] |
| MyoWare | `GND` | `GND` | Masa común con Mega y ECG Click |
| MyoWare | pad `RAW` | `A1` | Recomendado para análisis y filtrado en Python |
| MyoWare | `ENV` | `A2` opcional | Útil como tercer canal para comparar o controlar volumen |

Debe seguirse la **serigrafía** del ECG Click, no únicamente la posición física del conector: en mikroBUS, AN es el pin 1, 5 V el pin 10 y GND los pines 8/9. No se debe conectar el pin `3.3V` del ECG Click porque figura como no conectado; tampoco se necesitan RST, CS, SCK, MISO, MOSI, PWM, INT, UART o I2C.[^4]

El jumper JP1 del ECG Click selecciona un rango de salida de **0–2,048 V** o **0–4,096 V**. Con el Arduino Mega usando referencia ADC de 5 V, la posición de 4,096 V aprovecha mejor la resolución, siempre que el potenciómetro de ganancia se ajuste para impedir saturación; en esa posición la línea base queda cerca de 2,048 V. En 2,048 V, la línea base queda cerca de 1,024 V.[^2][^4]
### Electrodos ECG
La guía del ECG Click especifica tres electrodos: brazo izquierdo, brazo derecho y lado izquierdo del abdomen o pierna izquierda. Su código de color documentado es **LL rojo, LA negro y RA blanco**; conviene comprobar continuidad del cable si los colores del cable adquirido difieren.[^2]

Para reducir artefactos:

- Limpiar la piel y dejarla seca antes de colocar electrodos.
- Usar electrodos nuevos.
- Evitar movimiento durante la primera validación.
- Mantener cables cortos, separados de cables USB, fuentes conmutadas y parlantes.
- Ajustar primero la ganancia baja y aumentarla gradualmente sin permitir lecturas cercanas a 0 o 1023.
### Electrodos EMG
En el MyoWare, **MID** va sobre el centro del músculo, **END** en la dirección longitudinal de sus fibras y **REF** sobre una zona ósea o un músculo no adyacente; el contacto estable de REF es especialmente importante. Para una primera prueba puede usarse el bíceps o flexor del antebrazo, limpiando la piel y alineando MID–END con las fibras.[^1]

No es aconsejable colocar ECG y EMG sobre zonas demasiado próximas durante la puesta a punto. Primero debe validarse cada sensor por separado y luego ambos a la vez, porque una contracción muscular puede contaminar el ECG y el latido puede aparecer débilmente en el canal EMG.
## Arquitectura de software
```text
ECG Click (AN) ── A0 ┐
                      ├─ Arduino Mega, 1 kframe/s ─ USB serial ─ Python
MyoWare (RAW) ─── A1 ┘                                      │
                                                             ├─ filtros causales
                                                             ├─ extracción de rasgos
                                                             ├─ PyQtGraph
                                                             └─ música / notas / percusión
```

Se recomienda separar la aplicación de Python en cuatro tareas:

1. **Hilo serial:** recibe líneas, valida columnas y deposita las muestras en una cola.
2. **Procesamiento:** convierte cuentas ADC a voltios, filtra por bloques y calcula R-peaks, RMS o envolvente.
3. **Interfaz:** actualiza las curvas cada 25–40 ms; no debe intentar redibujar una vez por cada muestra.
4. **Audio:** reproduce música o notas en un hilo interno, sin bloquear la adquisición.

PySerial ofrece lectura de líneas terminadas en salto de línea; su documentación recomienda abrir el puerto con `timeout` para evitar un bloqueo indefinido. PyQtGraph está orientado a gráficos científicos interactivos y actualización en tiempo real, utiliza NumPy y Qt, y permite organizar varias gráficas mediante `GraphicsLayoutWidget`.[^11][^12][^13]
## Bibliotecas
### Arduino
Para el prototipo inicial no hace falta instalar bibliotecas adicionales:

- `Arduino.h`: `analogRead()`, `micros()` y `Serial`.
- `MyoWare.h`: opcional, solo para conversiones propias de la biblioteca; el ejemplo oficial admite Uno y Mega y asigna ENV, RAW, REF y RECT a entradas analógicas.[^5]
### Python
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install pyserial numpy scipy pyside6 pyqtgraph pygame
```

| Biblioteca | Función en el proyecto |
|---|---|
| `pyserial` | Comunicación con el puerto COM/tty |
| `numpy` | Búferes, escalamiento, RMS y operaciones vectorizadas |
| `scipy.signal` | Butterworth, notch de 60 Hz y filtrado causal por secciones SOS |
| `PySide6` | Ventana, controles, temporizadores e hilos Qt |
| `pyqtgraph` | Gráficas ECG y EMG rápidas |
| `pygame` | Música de fondo, muestras de percusión y notas precalculadas |
| `mido` + `python-rtmidi` | Opcional: salida MIDI hacia Ableton, Reaper, FL Studio o un sintetizador virtual |

SciPy recomienda la representación en secciones de segundo orden (`output='sos'`) para filtrado general, porque es numéricamente más estable que polinomios `b, a`, especialmente en órdenes altos. Para tiempo real se usa `sosfilt()` conservando el estado entre bloques; `sosfiltfilt()` procesa hacia delante y hacia atrás y resulta apropiado para archivos ya grabados, no para una visualización causal instantánea porque necesita muestras futuras.[^14][^15][^16]
## Firmware Arduino
Este firmware transmite **datos ADC crudos**, sin aplicar filtros digitales. Lee ECG en A0 y MyoWare RAW en A1 a 1.000 tramas/s y utiliza 230.400 baudios.

```cpp
#include <Arduino.h>

constexpr uint32_t FS_HZ = 1000;
constexpr uint32_t PERIOD_US = 1000000UL / FS_HZ;
constexpr uint8_t ECG_PIN = A0;
constexpr uint8_t EMG_PIN = A1;

uint32_t nextSampleUs;
uint32_t sampleIndex = 0;

void setup() {
  Serial.begin(230400);
  pinMode(ECG_PIN, INPUT);
  pinMode(EMG_PIN, INPUT);
  delay(1000);

  // Lecturas de descarte para estabilizar el multiplexor ADC.
  analogRead(ECG_PIN);
  analogRead(EMG_PIN);

  Serial.println("#fs=1000,columns=n,ecg,emg");
  nextSampleUs = micros();
}

void loop() {
  const uint32_t now = micros();
  if ((int32_t)(now - nextSampleUs) >= 0) {
    nextSampleUs += PERIOD_US;

    const uint16_t ecg = analogRead(ECG_PIN);
    const uint16_t emg = analogRead(EMG_PIN);

    Serial.print(sampleIndex++);
    Serial.write(',');
    Serial.print(ecg);
    Serial.write(',');
    Serial.println(emg);
  }
}
```

El ADC del Mega es de 10 bits: entrega 0–1023 para aproximadamente 0–5 V. Dos llamadas a `analogRead()` por milisegundo son viables para este prototipo; no son simultáneas, pero la separación temporal entre ECG y EMG es pequeña respecto del período de 1 ms. Si se observan saltos de índice o variación temporal, el siguiente nivel de mejora es usar un temporizador hardware, un paquete binario con marcador y CRC, o un ADC externo multicanal.[^6][^17]

La conversión nominal en Python es:

```python
volts = adc_counts * 5.0 / 1023.0
```

Para medición cuantitativa debe medirse la tensión real del riel de 5 V con multímetro y reemplazar `5.0` por ese valor. Para arte biointeractivo y visualización relativa, las cuentas ADC originales suelen ser suficientes.
## Filtros en Python
### ECG
El ECG Click ya incluye acondicionamiento analógico, dos etapas pasaaltas, un pasabajas de tercer orden limitado aproximadamente a 60 Hz y un circuito DRL para reducir interferencia en modo común. Como filtro digital de visualización se recomienda:[^2]

- Pasa banda Butterworth de 4.º orden: **0,5–40 Hz**.
- Notch: **60 Hz**, porque Colombia utiliza red de 60 Hz; puede omitirse si el pasabajas a 40 Hz ya brinda suficiente rechazo.
- Detección de picos R sobre la señal filtrada, con período refractario de aproximadamente 250 ms y umbral adaptativo.
### EMG RAW
- Eliminar la línea base centrada en VIN/2 mediante pasaaltas.
- Pasa banda Butterworth de 4.º orden: **20–400 Hz** a 1.000 Hz de muestreo.
- Notch de **60 Hz** y, si es necesario, armónicos de 120 y 180 Hz.
- Calcular amplitud de control como RMS en ventana de 100–200 ms o como envolvente obtenida mediante valor absoluto más pasabajas de 3–10 Hz.
### Implementación base
```python
import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi, iirnotch, tf2sos

FS = 1000.0

class OnlineSOS:
    def __init__(self, sos):
        self.sos = np.asarray(sos)
        self.zi = sosfilt_zi(self.sos) * 0.0

    def process(self, x):
        y, self.zi = sosfilt(self.sos, np.asarray(x), zi=self.zi)
        return y

sos_ecg_bp = butter(4, [0.5, 40], btype="bandpass", fs=FS, output="sos")
sos_emg_bp = butter(4, [20, 400], btype="bandpass", fs=FS, output="sos")

b60, a60 = iirnotch(60.0, Q=30.0, fs=FS)
sos_notch60 = tf2sos(b60, a60)

ecg_bp = OnlineSOS(sos_ecg_bp)
ecg_notch = OnlineSOS(sos_notch60)
emg_bp = OnlineSOS(sos_emg_bp)
emg_notch = OnlineSOS(sos_notch60)

def filter_block(ecg_raw, emg_raw):
    ecg = ecg_notch.process(ecg_bp.process(ecg_raw))
    emg = emg_notch.process(emg_bp.process(emg_raw))
    return ecg, emg
```

Debe evitarse volver a filtrar desde cero toda la ventana visible en cada actualización, ya que produce transitorios en los bordes y desperdicia CPU. La clase anterior conserva los estados y procesa únicamente las muestras nuevas.
## Interfaz gráfica
Una interfaz práctica puede contener:

- Selector de puerto COM y botones **Conectar**, **Iniciar**, **Detener** y **Guardar CSV**.
- Curva 1: ECG crudo y ECG filtrado.
- Curva 2: EMG crudo, EMG filtrado y envolvente/RMS.
- Indicadores: frecuencia de muestreo efectiva, muestras perdidas, BPM estimado, nivel EMG normalizado y saturación ADC.
- Controles de audio: modo, escala musical, volumen máximo, umbral EMG y archivo de música.
- Registro simultáneo de `n`, tiempo, ECG crudo, EMG crudo, ECG filtrado y EMG filtrado.

Esqueleto de actualización gráfica:

```python
from PySide6 import QtCore, QtWidgets
import pyqtgraph as pg
import numpy as np

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECG–EMG Bioarte")
        self.graph = pg.GraphicsLayoutWidget()
        self.setCentralWidget(self.graph)

        self.p_ecg = self.graph.addPlot(row=0, col=0, title="ECG filtrado")
        self.p_emg = self.graph.addPlot(row=1, col=0, title="EMG filtrado")
        self.c_ecg = self.p_ecg.plot(pen=pg.mkPen("#00d8ff", width=2))
        self.c_emg = self.p_emg.plot(pen=pg.mkPen("#ff4fa3", width=2))

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(33)  # cerca de 30 FPS visuales

    def refresh(self):
        # Obtener únicamente las muestras nuevas desde una cola thread-safe,
        # filtrarlas, agregarlas al búfer circular y actualizar las curvas.
        self.c_ecg.setData(np.asarray(ecg_display_buffer))
        self.c_emg.setData(np.asarray(emg_display_buffer))
```

La lectura serial no debe ejecutarse dentro de `refresh()`: `readline()` puede esperar datos y congelar la ventana. Debe residir en `QThread`, `threading.Thread` o utilizar `QSerialPort`.
## Sonificación bioartística
Los proyectos de plantas no reproducen literalmente una “voz” de la planta: miden cambios de conductancia y un algoritmo los transforma en mensajes MIDI, notas o controles de sintetizador. MIDI Sprout, por ejemplo, detecta cambios de conductividad, asigna el tamaño del cambio a notas y envía MIDI hacia un sintetizador o estación de audio.[^18][^19]

Para ECG–EMG se recomiendan tres capas complementarias:

| Capa | Rasgo biológico | Parámetro musical |
|---|---|---|
| Pulso | Pico R del ECG | Golpe de percusión, nota grave o destello |
| Activación | RMS/envolvente EMG | Volumen, filtro, densidad o intensidad |
| Variación | Cambio de RMS EMG o intervalo RR | Selección de nota dentro de una escala |
### Modo A: música continua reactiva
- Al pulsar **Iniciar**, comienza una canción local en bucle.
- La envolvente EMG controla suavemente el volumen entre un mínimo y un máximo.
- Cada pico R dispara un sonido corto de percusión.
- El BPM fisiológico puede modular lentamente el tempo visual o la intensidad de un efecto, sin reiniciar la canción en cada latido.

`pygame.mixer.music` reproduce un flujo musical y permite controlar volumen entre 0 y 1; los objetos `Sound` pueden sonar simultáneamente en canales de mezcla independientes.[^20][^21]

```python
import pygame

pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.mixer.init()
pygame.mixer.music.load("musica.ogg")
pygame.mixer.music.play(-1, fade_ms=1500)
heartbeat = pygame.mixer.Sound("latido.wav")

def audio_update(emg_norm, r_peak):
    target = 0.15 + 0.75 * float(np.clip(emg_norm, 0, 1))
    pygame.mixer.music.set_volume(target)
    if r_peak:
        heartbeat.play()
```
### Modo B: melodía generativa
- Normalizar la envolvente EMG con una calibración de reposo y contracción máxima cómoda.
- Cuantizar el valor a una escala pentatónica, por ejemplo MIDI 48, 50, 52, 55, 57, 60.
- Generar nota solo cuando el cambio supere un umbral y haya transcurrido un tiempo mínimo de 100–250 ms.
- Usar el ECG para la duración o para disparar la nota en el siguiente pico R.

Este método conserva la relación con la señal y evita una cascada de notas causada por ruido. Para controlar un DAW puede usarse `mido` con `python-rtmidi`; para una aplicación autocontenida pueden precalcularse ondas seno o cargar muestras musicales con `pygame.mixer.Sound`.
### Normalización robusta
Durante 5 segundos de reposo se obtiene `RMS_REST`; durante varias contracciones cómodas se obtiene `RMS_ACTIVE`. Después:

```python
emg_norm = np.clip(
    (emg_rms - RMS_REST) / (RMS_ACTIVE - RMS_REST + 1e-9),
    0.0,
    1.0
)
```

Conviene suavizar `emg_norm` mediante un promedio exponencial antes de controlar el volumen para evitar saltos audibles.
## Validación por etapas
1. **ECG Click sin persona:** unir temporalmente las entradas/electrodos según la prueba del fabricante y confirmar una línea base cercana a 1,024 V o 2,048 V, según JP1.[^4]
2. **ECG conectado y aislado:** verificar que el ADC no toque 0 ni 1023; ajustar el trimmer lentamente.
3. **MyoWare ENV:** validar primero que la lectura suba con la contracción y que el LED ENV responda.[^22]
4. **MyoWare RAW:** soldar el pad RAW, comprobar línea base cercana a VIN/2 y observar oscilaciones con la contracción.[^1]
5. **Adquisición dual:** revisar continuidad de índices y medir la frecuencia efectiva durante al menos un minuto.
6. **Filtros:** guardar señal cruda; nunca almacenar únicamente la filtrada, pues se perdería la posibilidad de reprocesar.
7. **Audio:** comenzar con volumen EMG y golpe por R-peak; añadir melodía generativa solo después de estabilizar detección y normalización.
8. **Ensayo completo:** usar el portátil desconectado de cargador y pantallas, aislador USB y alimentación por batería.
## Problemas previsibles
| Síntoma | Causa probable | Acción |
|---|---|---|
| ECG pegado en 0 o 1023 | Ganancia excesiva, cable incorrecto o mala referencia | Bajar trimmer, revisar JP1, continuidad y electrodos |
| ECG con seno grande de 60 Hz | Acoplamiento de red o REF/DRL deficiente | Aislar USB, quitar cargador, mejorar contacto, separar cables |
| EMG RAW casi plana | Se conectó ENV por error, pad RAW mal soldado o músculo mal alineado | Verificar serigrafía, continuidad y posición MID/END |
| EMG RAW saturada | Movimiento, mala referencia o alimentación ruidosa | Reubicar REF, reducir movimiento, usar batería |
| Ventana se congela | Lectura serial en el hilo de GUI | Mover adquisición a hilo y usar cola |
| Audio entrecortado | Sonido generado en el mismo ciclo serial | Usar mixer/stream en segundo plano y mensajes de control |
| Se pierden muestras | CSV demasiado pesado o GUI bloqueante | Subir baudrate, reducir impresiones, usar paquetes binarios |
| BPM doble | Picos T detectados como R | Período refractario, umbral adaptativo y banda ECG adecuada |
## Mejoras posteriores
El Mega es apropiado para probar la idea, pero su ADC de 10 bits limita resolución y comparte un único convertidor entre canales. Para una segunda versión pueden considerarse:[^6]

- ADC externo simultáneo o de mayor resolución.
- Aislamiento digital de USB/UART y fuente DC–DC médica o batería dedicada.
- Enlace inalámbrico para eliminar la conexión galvánica con el PC.
- Paquetes binarios con contador, sincronización y CRC.
- Grabación BIDS/EDF si el proyecto evoluciona hacia investigación formal.
- Salida OSC o MIDI para conectar la interfaz con Pure Data, Max/MSP, Ableton o visuales en TouchDesigner; el uso de OSC para instrumentos controlados por ECG/EMG tiene antecedentes en entornos de síntesis musical biológica en tiempo real.[^23]
## Configuración mínima recomendada
- Arduino Mega 2560.
- ECG Click MIKROE-2455 con cable y tres electrodos.
- MyoWare 2.0 con tres electrodos y cable soldado al pad RAW; ENV puede conectarse adicionalmente.
- Aislador USB compatible con el Mega.
- Alimentación por batería y portátil sin cargador durante toda prueba corporal.
- Python con PySerial, NumPy, SciPy, PySide6, PyQtGraph y Pygame.
- Muestreo inicial: 1.000 tramas/s, 230.400 baudios.
- Filtros iniciales: ECG 0,5–40 Hz; EMG RAW 20–400 Hz; notch 60 Hz según necesidad.
- Sonificación inicial: música continua con volumen por RMS-EMG y percusión por picos R.

Esta combinación mantiene la señal original disponible, permite una interfaz fluida y produce una relación musical comprensible: el corazón marca eventos temporales y la contracción muscular controla intensidad y selección de notas.

---

## References

1. [learn.sparkfun.com › tutorials › getting-started-with-the-myoware-20-muscle-sensorGetting Started with the MyoWare® 2.0 Muscle Sensor Ecosystem](https://learn.sparkfun.com/tutorials/getting-started-with-the-myoware-20-muscle-sensor-ecosystem/all?print=1) - - **ENV** - Envelope signal ranging between 0-VIN.
...
|ENV/RECT/RAW [OUTPUT]|Tip|

2. [ECG Click Datasheet by MikroElektronika](https://www.digikey.de/htmldatasheets/production/2010179/0/0/1/ecg-click.html) - IC/Module MCP609 – OpAmp [1] MAX6106 – Voltage Reference [2]
Interface AN
Power supply 5V

3. [Getting Started with the MyoWare® 2.0 Muscle Sensor ...](https://learn.sparkfun.com/tutorials/getting-started-with-the-myoware-20-muscle-sensor-ecosystem/arduino-example-1-analog-read---single-sensor) - To view the Rectified or Raw signals, flip the power switch to the OFF position on the Link Shield, ...

4. [ECG Click Board (Electrocardiography Measurement)](https://www.mikroe.com/ecg-click) - An onboard 3.5mm phone jack is used to connect cables/electrodes to the Click board™.

5. [MyoWare-Arduino-Library/examples/ReadMyoWareVoltage ... - GitHub](https://github.com/AdvancerTechnologies/MyoWare-Arduino-Library/blob/main/examples/ReadMyoWareVoltage/ReadMyoWareVoltage.ino) - The ENV, RAW, and REF pins will need to connect to the A0, A1, and A2 pins

6. [Arduino Mega 2560 Rev3 – 54 Digital I/O, 16 Analog Inputs ...](https://store-usa.arduino.cc/products/arduino-mega-2560-rev3) - The Mega 2560 has 16 analog inputs, each of which provide 10 bits of resolution (i.e. 1024 different...

7. [Getting Started with the MyoWare® 2.0 Muscle Sensor Ecosystem](https://learn.sparkfun.com/tutorials/getting-started-with-the-myoware-20-muscle-sensor-ecosystem/myoware-20-muscle-sensor) - - **Raw (RAW):** G = 200
- **Rectified (RECT):** G = 200

8. [MYO004_AdvancedGuide_v12](https://www.mouser.com/datasheet/2/813/MyoWare_v2_AdvancedGuide_Updated-3225139.pdf) - To output the ENV signal, simply connect the ENV pin to one of your measuring device’s analog input.

9. [Link & Arduino Shields - myoware 2.0](https://myoware.com/products/link-and-arduino-shields/) - **3-Position Output Switch:** Choose between the EMG envelope, raw EMG, or rectified EMG output mode...

10. [Technical Specifications - MYOWARE by Advancer Technologies](https://myoware.com/products/technical-specifications/) - Envelope (ENV): G = 200 * R / 1 kOhm

11. [Short introduction — pySerial 3.4 documentation](https://pyserial.readthedocs.io/en/stable/shortintro.html) - Do specify a timeout when opening the
serial port otherwise it could block forever if no newline cha...

12. [GitHub - pyqtgraph/pyqtgraph: Fast data visualization and GUI tools ...](https://github.com/pyqtgraph/pyqtgraph) - The official documentation lives at pyqtgraph.readthedocs.io
...
`python -m pyqtgraph.examples` to l...

13. [pyqtgraph.readthedocs.io · getting_started · plottingPlotting in pyqtgraph — pyqtgraph 0.15.0.dev0 documentation](https://pyqtgraph.readthedocs.io/en/latest/getting_started/plotting.html) - |`pyqtgraph.plot()`|Create a new plot window showing your data|

14. [scipy.signal.sosfiltfilt — SciPy v1.12.0 Manual](https://docs.scipy.org/doc/scipy-1.12.0/reference/generated/scipy.signal.sosfiltfilt.html) - **scipy.signal.sosfiltfilt(*sos*, *x*, *axis=-1*, *padtype='odd'*, *padlen=None*)[source]#**
A forwa...

15. [Signal processing (scipy.signal)#](https://docs.scipy.org/doc//scipy-1.15.2/reference/signal.html) - |`butter`(N, Wn[, btype, analog, output, fs])|Butterworth digital and analog filter design.|

16. [butter — SciPy v1.16.2 Manual](https://docs.scipy.org/doc/scipy-1.16.2/reference/generated/scipy.signal.butter.html) - - ****output**{‘ba’, ‘zpk’, ‘sos’}, optional** Type of output: numerator/denominator (‘ba’), pole-ze...

17. [analogRead() - Arduino Documentation](https://docs.arduino.cc/language-reference/en/functions/analog-io/analogRead/) - resolution on Arduino boards is set to 10 bits, for compatibility.

18. [MTO 30.1: Miller, Music from Plant Biosignals](https://mtosmt.org/issues/mto.24.30.1/mto.24.30.1.millercox.html) - ^(14)^ Sound or music is produced by connecting the MIDISprout into a DAW (Digital Audio Workstation...

19. [Electricity for Progress](https://electricityforprogress.com/) - By measuring microcurrent fluctuations occurring across the surface of a plant’s leaf, this Biodata ...

20. [Mixer](https://www.pygame.org/docs/ref/mixer.html) - All sound playback is mixed in background threads.
When you begin to play a Sound object, it will re...

21. [pygame.mixer.music — pygame v2.6.0 documentation](https://www.pygame.org/docs/ref/music.html) - Use the music module to control the playback of music in the sound mixer. The difference between the...

22. [Learn](https://myoware.com/wp-content/uploads/2022/03/MyoWare_v2_QuickStartGuide.pdf) - Solder wiring of your choice (or connectors such as header pins) to the Vin, GND, and ENV pins on th...

23. [A real time music synthesis environment driven with biological signals](https://www.biopac.com/wp-content/uploads/ICASSP06.pdf) - This study proposes to use the analysis of physiological signals (elec- troencephalogram (EEG), elec...

