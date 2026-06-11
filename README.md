# Affinity-Based Slotting (ABS)

Trabajo de tesis sobre **optimización de la asignación de productos en un warehouse
basada en patrones de demanda** (affinity-based slotting / Storage Location
Assignment Problem).

## Documentación

- **[GUIA.md](GUIA.md)** — documentación técnica maestra (fuente única): problema,
  formulación, evaluación, arquitectura, estado y hoja de ruta. **Empezá por acá.**
- [propuesta de tesis.md](propuesta%20de%20tesis.md) — propuesta formal.
- [Resumen y punto de partida.md](Resumen%20y%20punto%20de%20partida.md) — estado del arte.

## Inicio rápido

```bash
uv venv && uv pip install -e .
.venv/bin/python scripts/build_inputs.py
```

Ver [GUIA.md §16](GUIA.md) para el ejemplo de uso completo.
