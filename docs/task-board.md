# Tablero final

- SOL: inspección completa; dos Markdown originales preservados, contratos y modelos definidos antes de delegar (commit 51b37f8).
- TERRA: adquisición, parser, firmware, filtros causales y demo completados (commit 1a12a6e); 10 pruebas propias aprobadas.
- LUNA: interfaz, CSV/JSON, calibración y sonificación completados (commit 725af0b); 12 pruebas propias aprobadas.
- SOL: integración de entrada CLI, configuración validada, scripts de arranque y empaquetado; revisión de cierres Qt, metadatos, grabador y notas pendientes; 37 pruebas integradas aprobadas con exit 0.
- Firmware Mega compilado: 3928 bytes flash / 210 bytes RAM. Demo nativa abre, recibe tres canales, dibuja y cierra con exit 0.
- Pendiente de hardware: resolver RAW A1 cerca de cero, comprobar cableado/tensiones, calidad/aislamiento, estabilidad de sesión larga, calibración muscular y escucha real. Una lectura serial breve no sustituye estas comprobaciones.

- Actualización hardware 29/10/2026: firmware cargado con autorización, GUI real/CSV verificados en COM10 (~999.7Hz, 12997 muestras, 0 pérdidas). RAW A1 cerca de cero: pendiente comprobación eléctrica, no validado EMG. Adquisición detenida.

- Actualización instrumentos: piano/violín sintetizados y pruebas WAV entregados; usuario confirmó escucha real. Suite 39 aprobadas. Calibración ENV real rechazada por activo ≤ reposo; no se guarda perfil inválido, control muscular pendiente.
