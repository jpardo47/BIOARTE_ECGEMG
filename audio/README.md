# Piano y violín sintetizados

La melodía generativa ofrece piano, violín y seno simple. Son timbres sintetizados por armónicos y envolventes, no muestras acústicas profesionales. Se precalculan antes de reproducir. El botón Probar instrumento emite una nota de prueba independiente de los sensores. Cambiar timbre requiere reiniciar audio.

`preview-piano.wav` y `preview-violin.wav` contienen una frase breve de demostración generada localmente, sin música comercial ni archivos externos. Se pueden usar en Música reactiva como bucles controlados por EMG calibrado. La salida física de ambos fue reproducida y el usuario confirmó oírla.

El audio puede detenerse sin interrumpir adquisición. Los fallos de archivo/dispositivo se informan sin cerrar la adquisición. Las pruebas automatizadas usan SDL_AUDIODRIVER=dummy; la comprobación física usa el dispositivo real. Oír las demostraciones no valida las señales ni su calibración.
