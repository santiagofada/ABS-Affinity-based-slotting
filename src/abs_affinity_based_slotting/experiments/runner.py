"""Run experiment tasks, in parallel, saving each result to disk as it finishes.

For every task: build (or reuse) the instance context, build the plan, then for
each evaluation re-batch the test orders, simulate and record the metrics. A
task whose result file exists is skipped, so an interrupted run resumes where
it stopped. Results:

- ``<out>/tareas/<key>.parquet``: one row per evaluation (specs + metrics).
- ``<out>/batches/<key>.parquet``: one row per simulated batch (for
  per-period breakdowns).
- ``<out>/progreso.log``: one line per finished or failed task.
"""

from __future__ import annotations

import multiprocessing
import time
import traceback
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from .specs import EvalSpec, InstanceSpec, SlottingSpec, Task

_DATASETS: OrderedDict = OrderedDict()
_CONTEXTS: OrderedDict = OrderedDict()


# --------------------------------------------------------------------------- context
def _affinity_filter(text: str):
    from ..demand import filter_registry

    if text == "none":
        return None
    name, _, value = text.partition(":")
    return filter_registry.get(name)(float(value) if name == "threshold" else int(value))


def _dataset(name: str) -> SimpleNamespace:
    """Tables, split and replenishment split of a dataset (cached, one at a time)."""
    if name not in _DATASETS:
        from ..config import dataset_dir
        from ..data import WarehouseDataLoader, split_picking_events
        from ..simulation import split_replenishments

        _DATASETS.clear()
        _CONTEXTS.clear()
        ds = WarehouseDataLoader(dataset_dir("v2", name)).load_all()
        split = split_picking_events(ds.picking_events, test_size=0.2)
        replen_train, replen_test = split_replenishments(ds.replenishment_events, split.train, ds.initial_stock, split.cutoff)
        start = ds.picking_events.groupby("batch_id")["timestamp"].min().sort_values()
        _DATASETS[name] = SimpleNamespace(
            ds=ds, split=split, replen_train=replen_train, replen_test=replen_test,
            minutes_per_batch=float(start.diff().dt.total_seconds().median() / 60),
        )
    return _DATASETS[name]


def context(spec: InstanceSpec) -> SimpleNamespace:
    """Instance, state at the cutoff and simulators for an instance spec (cached, two at a time)."""
    if spec in _CONTEXTS:
        _CONTEXTS.move_to_end(spec)
        return _CONTEXTS[spec]
    from ..evaluation import SShapeRouting
    from ..simulation import Simulator, build_event_stream, state_after_history, state_from_initial_stock
    from ..slotting import build_full_instance

    d = _dataset(spec.dataset)
    instance = build_full_instance(
        d.split.train, d.ds.initial_stock, d.ds.distances,
        affinity_metric=spec.affinity_metric, cooccurrence_col=spec.cooccurrence_col,
        affinity_filter=_affinity_filter(spec.affinity_filter), normalize=spec.normalize,
        pair_distance_model=spec.pair_distance, coordinates=d.ds.coordinates, demand_metric=spec.demand_metric,
    )
    state0 = state_from_initial_stock(instance, d.ds.initial_stock)
    state_cut, _ = state_after_history(state0, build_event_stream(d.split.train, d.replen_train, instance), instance)
    s_shape = SShapeRouting.from_tables(instance, d.ds.coordinates)
    ctx = SimpleNamespace(
        spec=spec, data=d, instance=instance, state_cut=state_cut, s_shape=s_shape,
        aisle_set_cost=s_shape.mask_costs(),
        simulators={r: Simulator.from_tables(instance, d.ds.coordinates, routing=r) for r in ("s_shape", "snake")},
    )
    _CONTEXTS[spec] = ctx
    while len(_CONTEXTS) > 2:
        _CONTEXTS.popitem(last=False)
    return ctx


# --------------------------------------------------------------------------- plans
def _method(name: str, ctx: SimpleNamespace, spec: SlottingSpec | None = None):
    from ..clustering import clustering_registry
    from ..methods import (AisleFillSlotting, BiLevelSlotting, DemandGreedySlotting, LinearAssignmentSlotting,
                           MerchantAisleFillSlotting, SwapSearchSlotting)

    coords = ctx.data.ds.coordinates
    if name == "demand_greedy":
        return DemandGreedySlotting()
    if name == "linear_assignment":
        return LinearAssignmentSlotting()
    if name == "aisle_fill":
        return AisleFillSlotting(coords)
    if name == "merchant_aisle_fill":
        return MerchantAisleFillSlotting(coords)
    if name == "bilevel":
        location_cost = None                                   # dock distance: zones are cost bands
        if spec.zone_cost == "aisle_order":                    # rank in the aisle_fill order: zones aisle by aisle
            from ..methods import aisle_fill_location_order
            location_cost = np.empty(ctx.instance.n_locations)
            location_cost[aisle_fill_location_order(ctx.instance, coords)] = np.arange(ctx.instance.n_locations)
        return BiLevelSlotting(clustering_registry.get(spec.clustering)(), DemandGreedySlotting(), location_cost=location_cost)
    if name == "swap_search":
        return SwapSearchSlotting(_method(spec.seed or "demand_greedy", ctx), lam=spec.lam, neighborhood=spec.neighborhood or "bay")
    raise ValueError(f"unknown slotting method {name!r}")


def build_plan(ctx: SimpleNamespace, spec: SlottingSpec):
    from ..slotting import Assignment

    inst = ctx.instance
    if spec.method == "vigente":
        return Assignment({inst.sku_id(s): inst.location_id(ctx.state_cut.primary_location(s)) for s in range(inst.n_skus)})
    return _method(spec.method, ctx, spec).solve(inst)


def sku_aisles(ctx: SimpleNamespace, plan) -> pd.Series:
    """Aisle position (0 = closest to the dock) of every SKU under the plan."""
    inst = ctx.instance
    loc = np.array([inst.location_index(plan.location_of(k)) for k in inst.sku_ids])
    return pd.Series(ctx.s_shape.bay_aisle[inst.location_bay[loc]], index=inst.sku_ids)


def plan_diagnostics(ctx: SimpleNamespace, plan, aisle: pd.Series) -> dict:
    from ..slotting import slotting_cost

    inst, test = ctx.instance, ctx.data.split.test
    lines = test[["order_id", "sku"]].drop_duplicates()
    per_order = lines.assign(a=lines["sku"].map(aisle)).groupby("order_id")["a"].nunique()
    demand_by_aisle = pd.Series(inst.demand).groupby(aisle.to_numpy()).sum()
    merchants_split = pd.Series(aisle.to_numpy()).groupby(inst.merchant_ids).nunique()
    return {
        "plan_L": slotting_cost(plan, inst, lam=1.0),
        "plan_Q": slotting_cost(plan, inst, lam=0.0),
        "aisles_per_order": float(per_order.mean()),
        "single_aisle_orders": float((per_order == 1).mean()),
        "demand_first_aisle": float(demand_by_aisle.get(0, 0.0) / demand_by_aisle.sum()),
        "merchants_split": int((merchants_split > 1).sum()),
    }


# --------------------------------------------------------------------------- evaluation
def evaluate(ctx: SimpleNamespace, plan, aisle: pd.Series, ev: EvalSpec, batchings: dict) -> tuple[dict, pd.DataFrame]:
    from ..batching import AisleCoverBatching, order_waits
    from ..simulation import build_event_stream, replenishment_policy_registry, reslot_state

    d, inst = ctx.data, ctx.instance
    key = (ev.window, ev.batching_passes)
    if key not in batchings:
        t0 = time.time()
        batching = AisleCoverBatching(aisle, ctx.aisle_set_cost, batch_size=25, window=ev.window, max_passes=ev.batching_passes)
        picking = batching.make_batches(d.split.test)
        waits = order_waits(picking, ev.window) * d.minutes_per_batch
        n = picking["batch_id"].nunique()
        batchings[key] = (picking, {
            "batching_seconds": time.time() - t0,
            "static_fifo": batching.stats_["fifo"] / n, "static_construction": batching.stats_["construction"] / n,
            "static_final": batching.stats_["local_search"] / n,
            "wait_mean_min": float(waits.mean()), "wait_max_min": float(waits.max()),
        })
    picking, batching_metrics = batchings[key]

    t0 = time.time()
    events = build_event_stream(picking, d.replen_test, inst)
    policy = replenishment_policy_registry.get(ev.replenishment)()
    res = ctx.simulators[ev.routing].run(reslot_state(ctx.state_cut, plan, inst), events, policy,
                                        planned=plan, lam=ev.replenishment_lam)
    log = res.batch_log
    row = {
        "mean_distance": float(log["distance"].mean()), "p95_distance": float(log["distance"].quantile(0.95)),
        "mean_aisles": float(log["n_aisles"].mean()), "n_batches": len(log),
        "shortfall_lines": res.shortfall_lines, "relocations": res.n_relocations,
        "final_off_home": res.final_off_home_fraction, "sim_seconds": time.time() - t0, **batching_metrics,
    }
    return row, log[["timestamp", "distance", "n_aisles"]]


def run_task(task: Task, out_dir: Path) -> dict:
    """Build the task's plan, evaluate it under every EvalSpec and save the result."""
    out_dir = Path(out_dir)
    target = out_dir / "tareas" / f"{task.key}.parquet"
    if target.exists():
        return {"key": task.key, "status": "cached"}
    t_start = time.time()
    ctx = context(task.instance)
    t0 = time.time()
    plan = build_plan(ctx, task.slotting)
    plan_seconds = time.time() - t0
    aisle = sku_aisles(ctx, plan)
    diag = plan_diagnostics(ctx, plan, aisle)

    rows, logs, batchings = [], [], {}
    for i, ev in enumerate(task.evals):
        row, log = evaluate(ctx, plan, aisle, ev, batchings)
        spec_cols = {"block": task.block, "task": task.key, "eval": i,
                     **asdict(task.instance), **{f"slot_{k}": v for k, v in asdict(task.slotting).items()}, **asdict(ev)}
        rows.append({**spec_cols, **diag, "plan_seconds": plan_seconds, **row})
        logs.append(log.assign(task=task.key, eval=i))

    for sub in ("tareas", "batches"):
        (out_dir / sub).mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    pd.concat(logs).to_parquet(out_dir / "batches" / f"{task.key}.parquet", index=False)
    pd.DataFrame(rows).to_parquet(tmp, index=False)
    tmp.rename(target)                                   # the result file appears only when complete
    return {"key": task.key, "status": "ok", "seconds": time.time() - t_start}


def _safe_run(task: Task, out_dir: Path) -> dict:
    try:
        return run_task(task, out_dir)
    except Exception:
        return {"key": task.key, "status": "error", "error": traceback.format_exc()}


def _log(out_dir: Path, task: Task, result: dict) -> None:
    line = (f"{time.strftime('%Y-%m-%d %H:%M:%S')} {result['status']:6s} {task.key} {task.block:12s} "
            f"{task.instance.dataset:17s} {task.slotting.method:20s} {result.get('seconds', 0):8.1f}s")
    with open(Path(out_dir) / "progreso.log", "a") as fh:
        fh.write(line + "\n")
        if result["status"] == "error":
            fh.write(result["error"] + "\n")


def run_tasks(tasks: list[Task], out_dir, *, n_jobs: int | dict = 4, expected_seconds=None) -> pd.DataFrame:
    """Run every pending task, one dataset at a time, ``n_jobs`` processes in parallel.

    ``n_jobs`` is a number, or a dict ``dataset -> number`` (missing datasets
    use 1), to keep memory bounded on large datasets. Tasks that use the
    solver run one at a time. ``expected_seconds(task)`` orders each group
    longest first. Returns one row per task with its status.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pending = [t for t in dict.fromkeys(tasks) if not (out_dir / "tareas" / f"{t.key}.parquet").exists()]
    order = expected_seconds or (lambda t: 0.0)
    status = []
    datasets = list(dict.fromkeys(t.instance.dataset for t in pending))
    for dataset in datasets:
        dataset_jobs = n_jobs.get(dataset, 1) if isinstance(n_jobs, dict) else n_jobs
        for solver, jobs in ((False, dataset_jobs), (True, 1)):
            group = sorted((t for t in pending if t.instance.dataset == dataset and t.needs_solver == solver),
                           key=order, reverse=True)
            if not group:
                continue
            with ProcessPoolExecutor(jobs, mp_context=multiprocessing.get_context("spawn")) as pool:
                futures = {pool.submit(_safe_run, t, out_dir): t for t in group}
                for future in as_completed(futures):
                    result = future.result()
                    _log(out_dir, futures[future], result)
                    status.append({"key": result["key"], "status": result["status"]})
    return pd.DataFrame(status, columns=["key", "status"])


def load_results(out_dir) -> pd.DataFrame:
    files = sorted((Path(out_dir) / "tareas").glob("*.parquet"))
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True) if files else pd.DataFrame()


def load_batches(out_dir) -> pd.DataFrame:
    files = sorted((Path(out_dir) / "batches").glob("*.parquet"))
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True) if files else pd.DataFrame()
