# Registro de integración SOL

## Inspección y decisiones

Se encontraron únicamente dos Markdown originales; se leyeron y preservaron. No había aplicación ni repositorio. Se resolvió la contradicción de alimentación a favor de la corrección explícita: ECG Click 5V/AN A0; MyoWare VIN a 3.3V, RAW A1 y ENV A2; GND común; ADC DEFAULT nominal de 5V configurable. Nunca conectar VIN del Mega al sensor ni 3.3V a AREF.

Contratos y modelos guardados antes del trabajo paralelo en commit 51b37f8. Exactamente tres participantes: SOL coordinó; TERRA 1a12a6e; LUNA 725af0b. Cada agente trabajó en sus rutas. SOL realizó la integración posterior.

## Cambios de integración

- Entrada `python -m app.main`, bandera explícita --demo, JSON --config y --smoke-seconds con adquisición y comprobación real de curvas.
- Configuración central validada, requisitos, empaquetado y scripts Windows/POSIX. Python312 real localizado porque el alias python de Windows no funciona en este equipo.
- Interfaz reorganizada para mantener tres gráficas visibles; controles desplazables, bloqueo de fuente durante adquisición y estado coherente al terminar o desconectar.
- Cierre Qt sin callback de cierre duplicado; conservación de workers activos y entrega de últimos bloques en cola antes de cerrar CSV.
- Guardas para no reutilizar grabador con un hilo anterior activo; metadatos usan versión central, modo y frecuencia del bloque adquirido.
- Calibración mantiene reposo pendiente sin normalizar hasta contracción válida, invalida perfiles incompatibles y conserva separación real/demo.
- Notas generativas pendientes se conservan si todavía no se cumple el intervalo mínimo. Fallos de audio controlados, sin cerrar adquisición.
- Firmware conserva 230400 por defecto; macro ACQUISITION_BAUD_RATE permite alternativa seleccionable sin cambiar silenciosamente el protocolo.

## Verificaciones de software ejecutadas

| Comprobación | Resultado |
|---|---|
| Arduino CLI, core AVR 1.8.7, arduino:avr:mega | Compila; 3928 bytes flash, 210 bytes RAM |
| python -m compileall app | Aprobado |
| pytest -q --basetemp=.tmp/pytest-final | 37 aprobadas, código de salida 0 |
| Ruff check . | Sin errores |
| pip check | Sin dependencias incompatibles |
| Demo CLI --demo --smoke-seconds | Tres canales y curvas actualizadas, salida 0 |
| GUI nativa Windows | Inicio, adquisición demo y cierre correctos; captura docs/demo-preview.png |
| Mypy | No ejecutado: sin configuración Mypy ni herramienta requerida |
| Marcadores incompletos / filtros no causales | Sin TODO, pass, NotImplementedError ni filtfilt en código de aplicación |

Desglose: parser 5; procesamiento 5; grabador 4; calibración 5; audio 5; configuración 8; integración Qt 5 = 37. Pruebas integradas incluyen fragmentación serial, líneas dañadas, saltos, desconexión, cierre de grabación, arranque/parada/reinicio, tres curvas y calibración de dos fases con JSON. Audio usa dummy/mocks y prueba error de dispositivo y limitación de notas.

El entorno virtual local tiene NumPy 2.5.4, SciPy 1.18.1, pyserial 3.5, PySide6 6.12.0, pyqtgraph 0.14.0, pygame 2.6.1, pytest 9.2.0 y Ruff 0.17.3. No se fijaron versiones innecesarias en requisitos.

En el sandbox restringido las fuentes Qt no se renderizan correctamente y algunas ejecuciones de pytest terminaron de forma nativa al salir aunque sus aserciones pasaban. La suite completa se repitió con ejecución local autorizada y terminó con código 0. La aplicación nativa y el smoke también cerraron con código 0; no se ocultaron errores mediante salida forzada.

## Límites que requieren montaje real

230400 baudios no garantizan 1000 tramas/s en el peor caso: 26 bytes/trama × 1000 × 10 bits = 260000 bit/s. Ambos extremos deben configurarse juntos para probar 460800. El firmware salta períodos en retrasos en vez de acumular ráfagas, y el parser cuenta pérdidas. ADC multiplexado: canales secuenciales, no simultáneos. El filtro digital no elimina aliasing ya adquirido. El detector R es una heurística educativa, no una medición médica validada.

El encabezado inicial puede descartarse al vaciar el búfer; si no llega se usa la frecuencia nominal configurada. Guardar cuentas originales permite reprocesar. El índice CSV es normalizado de sesión y conserva huecos; no es timestamp físico por muestra.

La presencia del puerto no demuestra continuidad de cables, tensiones medidas, contacto de electrodos ni aislamiento. Durante uso corporal: batería, portátil sin cargador ni equipos de red y preferiblemente aislamiento USB, según README y fabricantes. No se cargó firmware ni se abrió adquisición real mientras la alimentación permaneció sin confirmar.


## Prueba con Arduino real — 29 de octubre de 2026

Usuario confirmó MyoWare a 3.3V, ECG Click a 5V y alimentación USB desde portátil solo con batería, sin cargador ni otros equipos conectados a red. No confirmó aislador USB. Enumeración identificó Mega 2560 en COM10 (VID:PID 2341:0042). Una primera lectura a 230400 no recibió datos. Tras autorización explícita se cargó el firmware compilado mediante Arduino CLI, con salida 0.

Se abrió la GUI real y se capturaron 12997 muestras durante una prueba acotada: fs efectiva 999.6923Hz, fs nominal 1000Hz, perdidas 0, inválidas 0, sin errores seriales ni de grabación. Las tres gráficas se actualizaron y la aplicación cerró correctamente. Archivo CSV y metadatos en recordings/bioarte_20261029_103307_509073.csv y .json; resumen recordings/hardware-validation.json y captura recordings/live-preview.png. Los datos personales no se incluyen en Git.

Rangos ADC observados [mínimo, máximo]: ECG A0 [132,339]; RAW A1 [0,1]; ENV A2 [0,83]. RAW estuvo por debajo del umbral bajo en todas las muestras. ENV estuvo bajo en 12991/12997 muestras; ENV baja puede corresponder a reposo, pero no demuestra funcionamiento del sensor. RAW cerca de cero no coincide con el centro nominal de 1.65V (~338 cuentas) esperado con MyoWare a 3.3V.

El usuario confirmó RAW→A1 y ENV→A2. La causa eléctrica queda pendiente de medición: con electrodos retirados del cuerpo, medir VIN–GND (~3.3V) y RAW–GND (~1.65V en reposo), verificar GND común, continuidad del cable y soldadura/pad RAW con el montaje apagado. Si el pad tiene voltaje correcto pero A1 lee cero, revisar cable y entrada ADC; si el pad está a cero, revisar alimentación y sensor. No se alteraron cables ni se aplicaron señales de prueba a las entradas desde firmware. No se declara validada la señal EMG ni se infiere un estado fisiológico.

Adquisición detenida y COM10 liberado al terminar. Pendientes: resolver RAW, calibrar EMG con reposo/contracción y validar sonido físico y estabilidad de sesión larga. La prueba de 14s no sustituye una prueba de al menos un minuto ni el cálculo del peor caso de transporte.

Comprobación final del archivo real: **13124 filas de datos, 15 columnas**, índices consecutivos de 5 a 13128. El contador del observador previo a la detención era 12997; el CSV incluye además los bloques finales drenados durante el cierre. La grabación comienza después del primer bloque recibido; en esta ejecución su primer índice es 5. Los bloques pueden emitirse parcialmente por tiempo de espera.


## Timbres clásicos y nueva prueba de contacto

Se añadieron piano y violín sintetizados (armónicos con decaimiento o arco/vibrato), selector GUI, nota de prueba independiente y WAV de ejemplo generados localmente. El formato PCM está acotado a 45% de escala completa, con ataque/salida en cero; no se trata de grabaciones acústicas reales. El banco se precalcula al iniciar audio.

39 pruebas aprobadas, compileall y Ruff limpios. La reproducción por dispositivo real a 44100Hz/16bit/estéreo se inició y terminó sin error para ambos timbres; el usuario confirmó escuchar piano y violín. Resultado local en recordings/audio-output-check.json.

Tras acomodar el contacto: prueba real de 6945 muestras observadas a 998.7056Hz, sin pérdidas ni líneas inválidas. Rangos observados ECG [6,1023], RAW [0,345], ENV [100,224]. Hubo 641 muestras ECG en umbral de saturación y 2232 RAW bajo el umbral: persiste recorte/contacto inestable. ENV no saturó en esta prueba y se seleccionó para calibración guiada. No se declara validado ECG/RR con recorte. Grabación local: recordings/bioarte_20261029_104307_218006.csv; resumen hardware-recheck.json. El usuario autorizó seguir indicaciones en pantalla para reposo y contracción cómoda.


### Estado actual: instrumentos y calibración

Piano y violín sintetizados implementados, reproducidos por salida física y escuchados por el usuario. Hay botón Probar instrumento y dos frases WAV de ejemplo en audio/. Configuración instrument=piano|violin|sine y duración predeterminada 0.6s. Suite actual: **39 pruebas aprobadas** (audio pasó de 5 a 7), compileall y Ruff limpios.

La calibración guiada real de ENV A2 se intentó con 5s de reposo y 5s de contracción cómoda. El nivel de contracción no superó al reposo; el programa rechazó el resultado y no guardó un perfil inválido. No se declara verificado el control de notas por EMG. La prueba de instrumento audible fue independiente de sensores. Resultado local: recordings/classical-calibration-check.json. Contacto mejorado respecto a la prueba inicial, pero RAW aún presenta tramos cerca de cero y ECG recorte; estabilizar contacto/ganancia antes de calibrar o sincronizar por R. Adquisición y reproducción de prueba detenidas al terminar.


## Vista ECG y alimentación separada

Se confirmó que el trazado usa todas las muestras de ECG crudo/filtrado, no únicamente los eventos R. La superposición de crudo con nivel DC y filtrado centrado comprimía la escala. Se añadió centrado visual por mediana de ventana (predeterminado), selección de crudo visible y leyenda horizontal. El título distingue crudo centrado, crudo absoluto y filtrado. No cambia ADC, voltajes guardados ni procesamiento. Para inspección detallada usar ventana de 2s y ocultar crudo si es necesario. El centrado no reconstruye señal recortada ni garantiza distinguir P/QRS/T.

La grabación inicial tuvo ADC ECG [132,339] sin saturación ADC; la posterior [6,1023] con 641/7019 filas en el umbral alto. El filtro continuo no puede recuperar amplitud perdida por recorte de adquisición. El modo demo usa una forma simplificada con pulsos; no debe interpretarse como un ECG fisiológico completo.

El usuario informa VIN o ambos LED del MyoWare apagados. La guía del fabricante indica VIN encendido mientras hay alimentación; ENV puede apagarse en reposo. Verificar tensión en los pads VIN–GND del propio sensor y continuidad con multímetro; un ADC variable no confirma alimentación correcta.

Es posible usar un Uno como fuente separada regulada de 3.3V: retirar el cable de alimentación del sensor desde el Mega; Uno 3.3V→MyoWare VIN; Uno GND→MyoWare GND y Mega GND; RAW→Mega A1 y ENV→Mega A2. No conectar entre sí las salidas positivas 3.3V/5V de ambas placas, no usar VIN de Arduino como salida y no modificar AREF. La salida 3.3V del Uno también tiene límite 50mA; añadir placa no demuestra que se resuelva el problema. Ambas placas deben funcionar con batería/sin conexiones a red durante contacto corporal. Cambiar cableado únicamente apagado y con electrodos retirados del cuerpo. No se cambió físicamente alimentación ni se abrió adquisición para este ajuste.

Fuentes: guía MyoWare https://cdn.sparkfun.com/assets/learn_tutorials/1/9/5/6/MyoWare_v2_QuickStartGuide.pdf ; especificaciones https://myoware.com/products/technical-specifications/ ; Uno pinout https://docs.arduino.cc/resources/pinouts/A000066-full-pinout.pdf ; ECG Click https://www.mikroe.com/ecg-click .

Verificación de vista ECG: 40 pruebas aprobadas con salida 0; compileall y Ruff limpios. No se realizaron lecturas del puerto real ni cambios de alimentación.
