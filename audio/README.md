# Audio

La aplicación sintetiza notas pentatónicas y un pulso corto con Pygame; no requiere archivos para el modo generativo. El modo de música reactiva acepta WAV, OGG y MP3 mediante el decodificador disponible en el sistema. El audio se controla desde la interfaz y puede detenerse sin interrumpir la adquisición.

Si no hay una salida de audio disponible, la aplicación muestra el error y mantiene activa la adquisición. En pruebas sin hardware de audio puede usarse `SDL_AUDIODRIVER=dummy`.
