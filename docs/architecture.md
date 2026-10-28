# Arquitectura acordada por SOL
La raiz actual es la raiz del proyecto bioarte_ecg_emg; se conservan ambos documentos originales.
Fuente (SerialWorker o DemoSource QThread) -> SignalProcessor en el mismo hilo de adquisicion -> bloques ProcessedBlock por senales Qt -> GUI. GUI refresca 30 FPS con memoria acotada. Grabador usa cola acotada y thread dedicado. Audio pygame usa mezclador y banco de notas precalculado fuera del hilo serial.
MyoWare VIN se conecta a 3.3V del Mega, nunca a VIN del Mega. ECG Click 5V, AN A0; RAW A1; ENV A2; GND comun. ADC DEFAULT 5V configurable en Python. Prevalece la correccion del prompt sobre la investigacion antigua.
No se puede corregir aliasing analogico con un filtro digital; RAW llega cerca de Nyquist a 1kHz. Tres analogRead son secuenciales, no simultaneos.
Propiedad paralela: SOL config/models/main/docs/paquete; TERRA arduino/serial_worker/signal_processing/demo_source y sus dos tests; LUNA ui/audio_engine/data_recorder/audio/calibration y sus tres tests. Cada agente solo escribe su handoff excepcionalmente. SOL integra despues de que ambos terminen. Exactamente tres agentes: coordinador SOL actual, TERRA y LUNA.
