"""Registry of experiments: one entry per configuration, with its parameters, results and description.

A configuration is an instance, a slotting plan and how it is measured: every
field of :class:`InstanceSpec`, :class:`SlottingSpec` and :class:`EvalSpec`.
:func:`register_results` reads a results folder written by
:func:`.runner.run_tasks` and adds every configuration the registry does not
have yet, so it can be called again after each run. A configuration that
appears in several blocks gives the same result in all of them, so it is
registered once, with the list of its blocks.

Each entry has:

- name: the slotting plan;
- dataset: the warehouse, with its train/test split;
- parameters: every field of the configuration, ``-`` where it is empty (the
  swap and bilevel parameters of the other methods), also in
  ``configuracion.json``;
- results: walk per batch over the test and over its last 14 days, both also
  against hoy, aisles, wait, relocations;
- description: the configuration in words and its blocks.

To browse it: ``mlflow ui --backend-store-uri sqlite:///results/registro.db``.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import fields
from pathlib import Path

import pandas as pd

from ..config import PROJECT_ROOT, dataset_dir
from .runner import load_results
from .specs import EvalSpec, InstanceSpec, SlottingSpec

REGISTRY = PROJECT_ROOT / "results" / "registro.db"
GROUP = "slotting"
GROUP_DESCRIPTION = (
    "Cada corrida es una configuracion: la instancia, el plan de slotting y como se mide. La simulacion "
    "recorre el periodo de test (las lineas de picking y las reposiciones de los datos) y mide la caminata "
    "de cada batch. Hoy = plan vigente, reposicion random y batches FIFO, en el mismo deposito. "
    "caminata_promedio: media por batch en todo el test; caminata_final: en los ultimos 14 dias; "
    "*_vs_hoy_pct: diferencia porcentual contra hoy."
)

_SPECS = {"instancia": (InstanceSpec, ""), "slotting": (SlottingSpec, "slot_"), "evaluacion": (EvalSpec, "")}
_SPEC_COLUMNS = [prefix + f.name for spec, prefix in _SPECS.values() for f in fields(spec)]
_METRICS = {                                   # registry name -> results column
    "caminata_promedio": "mean_distance",
    "caminata_final": "last14_distance",
    "pasillos_por_batch": "mean_aisles",
    "espera_media_min": "wait_mean_min",
    "mudanzas": "relocations",
    "faltantes": "shortfall_lines",
    "demanda_en_su_pasillo_final": "final_in_plan",
    "pasillos_por_orden_final": "final_aisles_per_order",
    "pasillos_por_orden_del_plan": "aisles_per_order",
    "segundos_del_plan": "plan_seconds",
}


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value))


def _plain(value):
    """numpy scalars to Python ones, missing values to None (for JSON)."""
    if _missing(value):
        return None
    return value.item() if hasattr(value, "item") else value


def _configuration_key(r: pd.Series) -> str:
    text = "|".join("-" if _missing(r[c]) else str(r[c]) for c in _SPEC_COLUMNS)
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def _configuration(r: pd.Series) -> dict:
    """The whole configuration, one dict per specification."""
    return {group: {f.name: _plain(r[prefix + f.name]) for f in fields(spec)}
            for group, (spec, prefix) in _SPECS.items()}


def _parameters(r: pd.Series) -> dict:
    """Every field of the configuration, ``-`` where the specification leaves it empty."""
    return {n: "-" if _missing(r[n]) else r[n] for n in _SPEC_COLUMNS}


def _plan(r: pd.Series) -> str:
    if r["slot_method"] == "bilevel":
        return f"bilevel {r['slot_clustering']}/{r['slot_zone_cost']}"
    return r["slot_method"]


def _replenishment(r: pd.Series) -> str:
    if r["replenishment"] == "plan_aisle":
        return f"regla {r['rule_trigger']}/{r['rule_target']}"
    if r["replenishment"] == "objective_greedy":
        return f"objective_greedy con lambda {r['replenishment_lam']}"
    return r["replenishment"]


def _description(r: pd.Series, blocks: list[str], block_text: dict) -> str:
    plan = _plan(r)
    if r["slot_method"] == "swap_search":
        plan += f" (lambda {r['slot_lam']}, vecindad {r['slot_neighborhood']}, desde {r['slot_seed']})"
    if r["slot_method"] == "random":
        plan += f" (sorteo {r['slot_seed']})"
    if r["slot_method"] == "vigente" and r["replenishment"] == "random" and r["window"] == 1:
        plan = "hoy: vigente"
    window = "batches FIFO" if r["window"] == 1 else f"re-batching con ventana {r['window']}"
    start = "con el plan aplicado de una vez (techo)" if r["start"] == "plan" else "desde el deposito real"
    named = [f"{b} ({block_text[b]})" if b in block_text else b for b in blocks]
    return (f"{plan} en {r['dataset']}, reposicion {_replenishment(r)}, {window}, recorrido {r['routing']}, "
            f"{start}. Bloques: {', '.join(named)}.")


def _dataset_input(name: str, test_size: float):
    """The warehouse as a dataset of the registry, from its manifest."""
    from mlflow.entities import Dataset, DatasetInput, InputTag
    from mlflow.utils.mlflow_tags import MLFLOW_DATASET_CONTEXT

    folder = dataset_dir("v2", name)
    manifest = (folder / "manifest.json").read_bytes()
    info = json.loads(manifest)
    profile = {"ordenes": info["num_orders"], "batches": info["num_batches"], "meses": info["calendar_months"],
               "pasillos": info["preset"]["num_aisles"], "merchants": info["preset"]["num_merchants"]}
    dataset = Dataset(name=name, digest=hashlib.sha1(manifest).hexdigest()[:16], source_type="local",
                      source=json.dumps({"uri": folder.as_uri()}), profile=json.dumps(profile))
    split = f"train {1 - test_size:.0%} / test {test_size:.0%}"
    return DatasetInput(dataset, tags=[InputTag(MLFLOW_DATASET_CONTEXT, split)])


def register_results(out_dir, *, blocks: dict | None = None, registry: Path = REGISTRY) -> int:
    """Add to the registry the configurations of ``out_dir`` it does not have; returns how many.

    ``blocks`` maps a block name to a short description, used in the
    description of its configurations. The difference against hoy (vigente,
    ``random``, FIFO, same dataset, routing and test fraction) is added when
    the folder has it.
    """
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    from mlflow.entities import Metric, Param
    from mlflow.tracking import MlflowClient

    out_dir, block_text = Path(out_dir), blocks or {}
    registry.parent.mkdir(parents=True, exist_ok=True)
    client = MlflowClient(tracking_uri=f"sqlite:///{registry}")
    group = client.get_experiment_by_name(GROUP)
    group_id = (group.experiment_id if group is not None else
                client.create_experiment(GROUP, artifact_location=(registry.parent / "registro_artefactos").as_uri()))
    client.set_experiment_tag(group_id, "mlflow.note.content", GROUP_DESCRIPTION)
    known, token = set(), None
    while True:                                          # the store returns at most 50.000 runs per page
        page = client.search_runs([group_id], max_results=50_000, page_token=token)
        known |= {run.data.tags.get("clave") for run in page}
        token = page.token
        if not token:
            break

    res = load_results(out_dir)
    if res.empty:
        return 0
    res["clave"] = res.apply(_configuration_key, axis=1)
    blocks_of = res.groupby("clave")["block"].agg(lambda s: sorted(set(s)))
    key = ["dataset", "routing", "test_size"]
    hoy = (res.query("slot_method == 'vigente' and replenishment == 'random' and window == 1 and start == 'real'")
              .groupby(key)[["mean_distance", "last14_distance"]].first())
    inputs = {}
    added = 0
    for _, r in res.drop_duplicates("clave").iterrows():
        if r["clave"] in known:
            continue
        metrics = {name: float(r[col]) for name, col in _METRICS.items() if pd.notna(r[col])}
        ref = tuple(r[k] for k in key)
        if ref in hoy.index:
            metrics["promedio_vs_hoy_pct"] = 100 * (r["mean_distance"] / hoy.loc[ref, "mean_distance"] - 1)
            metrics["final_vs_hoy_pct"] = 100 * (r["last14_distance"] / hoy.loc[ref, "last14_distance"] - 1)
        tags = {"clave": r["clave"], "bloques": ",".join(blocks_of[r["clave"]]), "resultados": out_dir.name,
                "mlflow.note.content": _description(r, blocks_of[r["clave"]], block_text)}
        run_id = client.create_run(group_id, run_name=_plan(r), tags=tags).info.run_id
        now = int(time.time() * 1000)
        client.log_batch(run_id, metrics=[Metric(k, v, now, 0) for k, v in metrics.items()],
                         params=[Param(k, str(v)) for k, v in _parameters(r).items()])
        source = (r["dataset"], r["test_size"])
        if source not in inputs:
            inputs[source] = _dataset_input(*source)
        client.log_inputs(run_id, datasets=[inputs[source]])
        client.log_dict(run_id, _configuration(r), "configuracion.json")
        client.set_terminated(run_id)
        added += 1
    return added
