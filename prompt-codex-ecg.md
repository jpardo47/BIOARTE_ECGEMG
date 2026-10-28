# Prompt para Codex: sistema ECG–EMG con Arduino Mega y Python

Copia desde **“INICIO DEL PROMPT”** hasta **“FIN DEL PROMPT”** y pégalo en Codex dentro de una carpeta vacía de proyecto.

---

## INICIO DEL PROMPT

Actúa como ingeniero de software y de instrumentación biomédica. Crea un proyecto local completo para adquirir, visualizar, filtrar, almacenar y sonificar señales ECG y EMG usando un Arduino Mega 2560, un ECG Click MIKROE-2455 y un MyoWare 2.0.

No entregues solamente una explicación: crea todos los archivos funcionales del proyecto, escribe el código completo, instala o documenta las dependencias, comprueba la sintaxis y deja instrucciones reproducibles. No uses pseudocódigo ni dejes funciones con `pass`, `TODO` o contenido incompleto.

## Hardware y conexiones obligatorias

Usa esta asignación exacta:

| Dispositivo | Terminal | Arduino Mega |
|---|---|---|
| ECG Click | `5V` | Pin `5V` |
| ECG Click | `GND` | `GND` común |
| ECG Click | `AN` | `A0` |
| MyoWare 2.0 | `VIN` | Pin `3.3V` |
| MyoWare 2.0 | `GND` | `GND` común |
| MyoWare 2.0 | `RAW` | `A1` |
| MyoWare 2.0 | `ENV` | `A2` |

Consideraciones eléctricas:

- El ECG Click se alimenta a 5 V.
- El MyoWare se alimenta a 3.3 V y sus salidas RAW y ENV estarán limitadas aproximadamente al rango 0–3.3 V.
- El ADC del Arduino Mega continúa usando su referencia predeterminada de 5 V y resolución de 10 bits. No activar `analogReference(INTERNAL)` ni conectar 3.3 V al pin AREF.
- RAW estará centrada aproximadamente en 1.65 V porque el MyoWare se alimenta a 3.3 V.
- Todas las masas deben estar unidas.
- No usar el pin `VIN` del Arduino para alimentar el MyoWare.
- A2 es un tercer canal analógico independiente para ENV; conservar también RAW en A1.

## Arquitectura requerida

Implementa este flujo:

```text
ECG Click AN ───── A0 ┐
MyoWare RAW ────── A1 ├─ Arduino Mega ─ USB serial ─ Python
MyoWare ENV ────── A2 ┘                       │
                                              ├─ filtros causales
                                              ├─ gráficas en tiempo real
                                              ├─ registro CSV
                                              └─ sonificación/música
```

El Arduino debe transmitir las cuentas ADC originales sin filtrarlas. Todo el procesamiento digital se realiza en Python.

## Estructura del proyecto

Crea como mínimo:

```text
bioarte_ecg_emg/
├── arduino/
│   └── acquisition_mega/
│       └── acquisition_mega.ino
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── serial_worker.py
│   ├── signal_processing.py
│   ├── audio_engine.py
│   ├── data_recorder.py
│   └── config.py
├── audio/
│   └── README.md
├── recordings/
│   └── .gitkeep
├── tests/
│   ├── test_parser.py
│   └── test_filters.py
├── requirements.txt
├── README.md
├── .gitignore
└── run.bat
```

Añade también `run.sh` si el entorno lo permite.

## Firmware Arduino

Crea un firmware para Arduino Mega con estas condiciones:

- Frecuencia nominal: 1.000 tramas por segundo.
- Entradas: ECG `A0`, EMG RAW `A1`, EMG ENV `A2`.
- Velocidad serial: 230400 baudios.
- Formato ASCII por trama: `indice,ecg,emg_raw,emg_env\n`.
- Primera línea de metadatos: `#fs=1000,columns=n,ecg,emg_raw,emg_env`.
- Emplear `micros()` con comparación segura ante desbordamiento.
- No usar `delay()` en el ciclo de adquisición.
- No filtrar ni promediar las muestras en Arduino.
- Detectar retrasos graves y evitar transmitir ráfagas ilimitadas para recuperar muestras atrasadas.
- Las lecturas deben permanecer entre 0 y 1023.

Toma como base funcional este comportamiento, pero mejora la organización si es necesario:

```cpp
#include <Arduino.h>

constexpr uint32_t FS_HZ = 1000;
constexpr uint32_t PERIOD_US = 1000000UL / FS_HZ;
constexpr uint8_t ECG_PIN = A0;
constexpr uint8_t EMG_RAW_PIN = A1;
constexpr uint8_t EMG_ENV_PIN = A2;

uint32_t nextSampleUs;
uint32_t sampleIndex = 0;

void setup() {
  Serial.begin(230400);
  pinMode(ECG_PIN, INPUT);
  pinMode(EMG_RAW_PIN, INPUT);
  pinMode(EMG_ENV_PIN, INPUT);
  delay(1000);

  analogRead(ECG_PIN);
  analogRead(EMG_RAW_PIN);
  analogRead(EMG_ENV_PIN);

  Serial.println("#fs=1000,columns=n,ecg,emg_raw,emg_env");
  nextSampleUs = micros();
}

void loop() {
  const uint32_t now = micros();

  if ((int32_t)(now - nextSampleUs) >= 0) {
    if ((uint32_t)(now - nextSampleUs) > 5UL * PERIOD_US) {
      nextSampleUs = now;
    }
    nextSampleUs += PERIOD_US;

    const uint16_t ecg = analogRead(ECG_PIN);
    const uint16_t emgRaw = analogRead(EMG_RAW_PIN);
    const uint16_t emgEnv = analogRead(EMG_ENV_PIN);

    Serial.print(sampleIndex++);
    Serial.write(',');
    Serial.print(ecg);
    Serial.write(',');
    Serial.print(emgRaw);
    Serial.write(',');
    Serial.println(emgEnv);
  }
}
```

## Aplicación Python

Utiliza:

- Python 3.11 o superior.
- `PySide6` para la interfaz.
- `pyqtgraph` para las gráficas.
- `pyserial` para comunicación.
- `numpy` para búferes y cálculos.
- `scipy.signal` para filtros.
- `pygame` para música y sonidos.

La aplicación debe ejecutarse con:

```bash
python -m app.main
```

## Comunicación serial

Implementa un trabajador serial en un `QThread` o hilo equivalente. La lectura serial jamás debe bloquear el hilo principal de Qt.

El trabajador debe:

- Enumerar puertos disponibles.
- Abrir el puerto seleccionado a 230400 baudios con `timeout`.
- Ignorar líneas que comiencen con `#`, pero leer el valor `fs` de los metadatos.
- Validar exactamente cuatro campos numéricos.
- Rechazar líneas dañadas sin cerrar la aplicación.
- Detectar muestras perdidas usando el índice.
- Enviar bloques a la GUI mediante señales Qt o una cola segura.
- Poder conectarse y desconectarse sin reiniciar la aplicación.
- Vaciar el búfer serial al conectar.

## Conversión de unidades

Conserva siempre las cuentas ADC crudas. Para mostrar voltaje usa:

```python
voltage = counts * 5.0 / 1023.0
```

El ECG y las salidas del MyoWare se digitalizan con el ADC de 5 V del Mega. Aunque el MyoWare se alimente a 3.3 V, no convertir sus cuentas usando 3.3 V, porque la referencia ADC continúa siendo 5 V.

Permite configurar `adc_reference_voltage` en `config.py`, con valor inicial de 5.0 V, para reemplazarlo después por el voltaje real medido con multímetro.

## Procesamiento en tiempo real

Los filtros deben ser causales y conservar su estado entre bloques. Emplea filtros SOS (`output="sos"`) y `scipy.signal.sosfilt`. No uses `filtfilt` ni `sosfiltfilt` durante adquisición en vivo.

Implementa:

### ECG

- Pasa banda Butterworth de cuarto orden, 0.5–40 Hz.
- Notch configurable a 60 Hz, Q = 30. Debe poder desactivarse, ya que el pasa banda a 40 Hz puede hacerlo innecesario.
- Detección básica de picos R con umbral adaptativo y período refractario de 250 ms.
- Cálculo de BPM solo después de tener intervalos RR válidos.

### EMG RAW

- Pasa banda Butterworth de cuarto orden, 20–400 Hz.
- Notch configurable a 60 Hz, Q = 30.
- RMS móvil configurable, valor inicial 150 ms.
- Envolvente digital: valor absoluto seguido de pasabajas de 5 Hz.

### ENV analógica

- Mostrar tanto la señal cruda como una versión suavizada.
- Pasabajas configurable, valor inicial 5 Hz.
- Permitir seleccionar si la sonificación usa la envolvente analógica A2, el RMS de RAW A1 o la envolvente digital derivada de RAW.

Evita recalcular toda la ventana visible en cada actualización. Procesa solamente muestras nuevas y conserva estados de filtros.

## Interfaz

Crea una ventana con:

- Selector de puerto.
- Botones Actualizar puertos, Conectar, Desconectar, Iniciar adquisición y Detener.
- Botones Iniciar grabación CSV y Detener grabación.
- Indicador de conexión.
- Frecuencia de muestreo efectiva.
- Contador de muestras perdidas y líneas inválidas.
- Indicadores de saturación para cada canal cuando una lectura sea menor o igual a 5 o mayor o igual a 1018.
- BPM estimado.
- Nivel EMG normalizado.
- Tres gráficas principales: ECG, EMG RAW y ENV.
- Opción para superponer señal cruda y filtrada.
- Ventana temporal configurable entre 2 y 15 segundos.
- Leyendas, unidades y cuadrícula.
- Actualización visual cercana a 30 FPS, independiente de los 1.000 Hz de adquisición.

Usa búferes circulares con memoria limitada. La aplicación debe seguir respondiendo si el Arduino se desconecta.

## Registro CSV

Guarda en `recordings/` un archivo con fecha y hora. Columnas mínimas:

```text
sample_index,time_s,ecg_adc,emg_raw_adc,emg_env_adc,ecg_v,emg_raw_v,emg_env_v,ecg_filtered,emg_filtered,emg_rms,emg_envelope
```

La escritura debe hacerse por bloques o en un hilo para no congelar la GUI. Registra también un archivo JSON de metadatos con frecuencia nominal, puerto, referencia ADC, configuración de filtros y hora de inicio.

## Sonificación

Implementa dos modos seleccionables:

### Música reactiva

- Permitir elegir un archivo WAV, OGG o MP3.
- Reproducirlo en bucle.
- Controlar su volumen con el nivel EMG normalizado.
- Aplicar suavizado al volumen para evitar saltos.
- En cada pico R válido, reproducir un sonido corto de latido en otro canal.

### Melodía generativa

- Crear o precalcular notas de una escala pentatónica sin requerir archivos externos.
- Mapear el nivel EMG normalizado a notas de la escala.
- Disparar una nota solo si cambia el nivel cuantizado y se cumple un intervalo mínimo configurable.
- Ofrecer una opción para sincronizar el disparo de la nota con el siguiente pico R.

No generar audio directamente en el hilo serial ni bloquear la interfaz. Si falta el archivo de música o el dispositivo de audio no está disponible, mostrar el error sin cerrar la adquisición.

## Calibración EMG

Añade botones para:

1. Calibrar reposo durante 5 segundos.
2. Calibrar contracción cómoda durante 5 segundos.
3. Guardar los valores en un archivo JSON.

Normalizar con:

```python
normalized = np.clip(
    (value - rest_level) / (active_level - rest_level + 1e-9),
    0.0,
    1.0,
)
```

Permite elegir como `value` ENV A2, RMS RAW o envolvente digital.

## Dependencias

Incluye en `requirements.txt`, sin fijar versiones incompatibles:

```text
numpy
scipy
pyserial
PySide6
pyqtgraph
pygame
pytest
```

## README

Documenta:

- Diagrama de conexiones exacto.
- Cómo crear y activar un entorno virtual.
- Cómo instalar dependencias.
- Cómo cargar el firmware desde Arduino IDE.
- Cómo ejecutar la aplicación.
- Cómo seleccionar el puerto.
- Cómo calibrar EMG.
- Cómo activar música y melodía generativa.
- Cómo encontrar los CSV.
- Solución a errores comunes.

Incluye de forma visible esta advertencia:

> Prototipo educativo y artístico, no es un dispositivo médico ni debe emplearse para diagnóstico. Cuando haya electrodos conectados a una persona, usar Arduino y sensores alimentados por batería, portátil desconectado del cargador y de otros equipos conectados a red, y preferiblemente aislamiento USB. No conectar al cuerpo mientras se depura hardware alimentado directamente desde la red.

## Pruebas y validación

Crea pruebas automatizadas para:

- Analizar líneas seriales válidas e inválidas.
- Detectar saltos de índice.
- Verificar que los filtros produzcan salida finita y mantengan longitud.
- Verificar que el filtro EMG atenúe una componente fuera de banda.
- Verificar normalización y límites entre 0 y 1.

Ejecuta, si el entorno lo permite:

```bash
python -m compileall app
pytest
```

Corrige todos los errores encontrados. Si no es posible acceder a un Arduino o puerto serial real, implementa también un `--demo` que reproduzca un CSV existente o genere únicamente dentro de ese modo datos de prueba claramente marcados como simulados. El modo normal jamás debe mezclar datos simulados con adquisición real.

Al terminar:

1. Muestra el árbol final del proyecto.
2. Indica los comandos exactos para instalar y ejecutar.
3. Resume qué pruebas se ejecutaron.
4. No elimines archivos funcionales para abreviar la respuesta.

## FIN DEL PROMPT

---

## Conexión corregida

El MyoWare 2.0 puede alimentarse desde el pin **3.3V** del Mega: su rango especificado es 2.27–5.47 V y sus tensiones típicas son 3.3 o 5 V.[cite:105][cite:9] El pin 3.3V del Mega admite hasta 50 mA; no deben alimentarse otros módulos de consumo alto desde ese mismo riel.[cite:67][cite:111]

**No uses VIN del Mega para el MyoWare.** En el Mega, VIN es la entrada del regulador para aproximadamente 7–12 V cuando se alimenta externamente; no es una salida regulada de 5 V y podría dañar el MyoWare, cuyo máximo es 5.47 V.[cite:72][cite:111][cite:105]

El pin **5V sí existe** en el bloque POWER del Mega. Si ya lo ocupa el ECG Click, se puede distribuir con una protoboard: `5V del Mega → riel positivo → ECG Click`. No hace falta usar ese riel para el MyoWare si este queda a 3.3 V.

### Cableado final

```text
ARDUINO MEGA                ECG CLICK
------------                ---------
5V -----------------------> 5V
GND ----------------------> GND
A0  <---------------------- AN

ARDUINO MEGA                MYOWARE 2.0
------------                -----------
3.3V ---------------------> VIN
GND ----------------------> GND
A1  <---------------------- RAW
A2  <---------------------- ENV
```

Con MyoWare a 3.3 V, RAW queda centrada aproximadamente en 1.65 V y ENV puede variar entre 0 y 3.3 V.[cite:9][cite:107] El ADC del Mega sigue midiendo respecto a 5 V, por lo que las cuentas del MyoWare ocuparán aproximadamente de 0 a 675 en lugar de todo el rango 0–1023. Esto reduce algo la resolución disponible, pero es seguro y funcional.

No conectes 3.3 V al pin AREF mientras el firmware use la referencia predeterminada. Tampoco selecciones la referencia interna del ATmega2560: una señal del MyoWare de hasta 3.3 V podría excederla.

### Advertencia de seguridad

Este es un prototipo educativo/artístico, no un dispositivo médico. Durante mediciones sobre una persona, usar alimentación por batería, portátil sin cargador ni periféricos conectados a red y, preferiblemente, aislamiento USB.