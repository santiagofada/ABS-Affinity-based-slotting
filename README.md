# Affinity-Based Slotting (ABS)

Trabajo de tesis sobre **optimización de la asignación de productos en un warehouse
basada en patrones de demanda** (affinity-based slotting / Storage Location
Assignment Problem).

## Documentación

- **[docs/](docs/README.md)** — documentación técnica del proyecto: problema,
  alcance, datos, pipeline, componentes y formulación. **Empezá por acá.**
  - [docs/formulacion.md](docs/formulacion.md) — formulación matemática rigurosa.
  - [docs/pipeline.md](docs/pipeline.md) — las capas y el flujo de datos.
  - [docs/bloques.md](docs/bloques.md) — componentes intercambiables y composición.
- [propuesta de tesis.md](propuesta%20de%20tesis.md) — propuesta formal.
- [Resumen y punto de partida.md](Resumen%20y%20punto%20de%20partida.md) — estado del arte.

## Inicio rápido

```bash
uv venv && uv pip install -e .
.venv/bin/python scripts/build_inputs.py
```
