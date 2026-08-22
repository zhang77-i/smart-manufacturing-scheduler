"""Exact CP-SAT benchmarks for the full-scale scheduling case.

The full-scale heuristic remains the production-plan generator.  This module
uses deterministic small instances and the same candidate-machine graph to
verify the mathematical model and quantify heuristic quality.
"""

from __future__ import annotations

# Import OR-Tools before pandas on Windows to avoid protobuf DLL load-order
# conflicts in mixed Anaconda environments.
from ortools.sat.python import cp_model

import importlib.util
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports"
TABLE_DIR = REPORT_DIR / "tables"


def load_heuristic_module() -> Any:
    source = max(
        (
            path
            for path in ROOT.glob("*.py")
            if path.name not in {
                Path(__file__).name,
                "run_scheduling_experiments.py",
            }
        ),
        key=lambda path: path.stat().st_size,
    )
    spec = importlib.util.spec_from_file_location("full_scale_heuristic", source)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import heuristic solver from {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class ExactResult:
    size: int
    candidate_limit: int
    status: str
    runtime_seconds: float
    encoded_objective: float
    best_bound: float
    relative_gap: float
    exact_outsource: int
    exact_on_time: int
    exact_total_tardiness_seconds: int
    exact_total_waiting_seconds: int
    heuristic_runtime_seconds: float
    heuristic_outsource: int
    heuristic_on_time: int
    heuristic_total_tardiness_seconds: int
    heuristic_total_waiting_seconds: int
    on_time_difference: int


def deterministic_subset(
    release: list[int],
    due: list[int],
    mandatory: list[int],
    size: int,
) -> list[int]:
    required = sorted(mandatory)
    others = sorted(
        (i for i in range(len(release)) if i not in set(required)),
        key=lambda i: (due[i], release[i], i),
    )
    return (required + others)[:size]


def subset_problem(
    indices: list[int],
    release: list[int],
    due: list[int],
    hard_due: list[int],
    candidates: list[list[tuple[int, int, int, int]]],
    *,
    candidate_limit: int,
) -> tuple[
    list[int],
    list[int],
    list[int],
    list[list[tuple[int, int, int, int]]],
    list[int],
]:
    release_small = [release[i] for i in indices]
    due_small = [due[i] for i in indices]
    hard_small = [hard_due[i] for i in indices]
    candidate_small = [
        sorted(candidates[i], key=lambda row: (row[1], row[0]))[:candidate_limit]
        for i in indices
    ]
    minimum = [min(row[1] for row in options) for options in candidate_small]
    return release_small, due_small, hard_small, candidate_small, minimum


def solve_exact(
    release: list[int],
    due: list[int],
    hard_due: list[int],
    available: list[int],
    candidates: list[list[tuple[int, int, int, int]]],
    machine_count: int,
    *,
    use_machine_availability: bool,
    time_limit_seconds: float,
    workers: int = 4,
) -> tuple[dict[str, int | float | str], cp_model.CpSolver]:
    model = cp_model.CpModel()
    n = len(release)
    horizon = max(hard_due)
    machine_intervals: list[list[cp_model.IntervalVar]] = [
        [] for _ in range(machine_count)
    ]
    outsource_vars = []
    on_time_vars = []
    tardiness_vars = []
    waiting_vars = []

    for i in range(n):
        outsource = model.new_bool_var(f"outsource_{i}")
        outsource_vars.append(outsource)
        master_start = model.new_int_var(release[i], hard_due[i], f"start_{i}")
        master_end = model.new_int_var(release[i], hard_due[i], f"end_{i}")
        presences = []

        for machine, processing, _, _ in candidates[i]:
            earliest = max(
                release[i],
                available[machine] if use_machine_availability else 0,
            )
            latest_start = hard_due[i] - processing
            if earliest > latest_start:
                continue
            presence = model.new_bool_var(f"use_{i}_{machine}")
            start = model.new_int_var(
                earliest,
                latest_start,
                f"start_{i}_{machine}",
            )
            end = model.new_int_var(
                earliest + processing,
                hard_due[i],
                f"end_{i}_{machine}",
            )
            interval = model.new_optional_interval_var(
                start,
                processing,
                end,
                presence,
                f"interval_{i}_{machine}",
            )
            model.add(master_start == start).only_enforce_if(presence)
            model.add(master_end == end).only_enforce_if(presence)
            machine_intervals[machine].append(interval)
            presences.append(presence)

        model.add(sum(presences) + outsource == 1)
        model.add(master_start == release[i]).only_enforce_if(outsource)
        # The source outsourcing table uses 24 hours; missing data is explicitly
        # handled by the original project with the same conditional assumption.
        model.add(master_end == hard_due[i]).only_enforce_if(outsource)

        on_time = model.new_bool_var(f"on_time_{i}")
        model.add(master_end <= due[i]).only_enforce_if(on_time)
        model.add(master_end >= due[i] + 1).only_enforce_if(on_time.negated())
        on_time_vars.append(on_time)

        tardiness = model.new_int_var(0, horizon, f"tardiness_{i}")
        model.add_max_equality(tardiness, [0, master_end - due[i]])
        tardiness_vars.append(tardiness)

        waiting = model.new_int_var(0, horizon, f"waiting_{i}")
        model.add(waiting == master_start - release[i])
        waiting_vars.append(waiting)

    for intervals in machine_intervals:
        if intervals:
            model.add_no_overlap(intervals)

    outsource_count = sum(outsource_vars)
    late_count = n - sum(on_time_vars)
    total_tardiness = sum(tardiness_vars)
    total_waiting = sum(waiting_vars)
    continuous_bound = 2 * n * horizon
    late_weight = continuous_bound + 1
    outsource_weight = n * late_weight + continuous_bound + 1
    model.minimize(
        outsource_count * outsource_weight
        + late_count * late_weight
        + total_tardiness
        + total_waiting
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = int(workers)
    solver.parameters.random_seed = 42
    started = time.perf_counter()
    status = solver.solve(model)
    runtime = time.perf_counter() - started
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"CP-SAT failed: {solver.status_name(status)}")

    objective = float(solver.objective_value)
    bound = float(solver.best_objective_bound)
    gap = max(0.0, objective - bound) / max(abs(objective), 1.0)
    result: dict[str, int | float | str] = {
        "status": solver.status_name(status),
        "runtime_seconds": runtime,
        "encoded_objective": objective,
        "best_bound": bound,
        "relative_gap": gap,
        "outsource": int(sum(solver.value(var) for var in outsource_vars)),
        "on_time": int(sum(solver.value(var) for var in on_time_vars)),
        "total_tardiness_seconds": int(
            sum(solver.value(var) for var in tardiness_vars)
        ),
        "total_waiting_seconds": int(
            sum(solver.value(var) for var in waiting_vars)
        ),
    }
    return result, solver


def run_exact_benchmarks(
    *,
    sizes: tuple[int, ...] = (20, 50, 100),
    candidate_limit: int = 10,
    time_limit_seconds: float = 30.0,
) -> list[ExactResult]:
    heuristic = load_heuristic_module()
    orders, process, _, machines = heuristic.load_data()
    process_map, _, _ = heuristic.build_process_map(orders, process)
    (
        _,
        release,
        due,
        hard_due,
        available,
        candidates,
        _,
    ) = heuristic.build_parameters(orders, machines, process_map)
    full_outsource, _, _ = heuristic.structural_check(
        release,
        due,
        hard_due,
        available,
        candidates,
        True,
    )

    rows: list[ExactResult] = []
    for size in sizes:
        selected = deterministic_subset(release, due, full_outsource, size)
        (
            rel,
            deadlines,
            hard,
            candidate_small,
            minimum,
        ) = subset_problem(
            selected,
            release,
            due,
            hard_due,
            candidates,
            candidate_limit=candidate_limit,
        )
        unavoidable_outsource, unavoidable_late, _ = heuristic.structural_check(
            rel,
            deadlines,
            hard,
            available,
            candidate_small,
            True,
        )

        exact, _ = solve_exact(
            rel,
            deadlines,
            hard,
            available,
            candidate_small,
            len(machines),
            use_machine_availability=True,
            time_limit_seconds=time_limit_seconds,
        )

        started = time.perf_counter()
        solution, objective, _, _ = heuristic.solve_with_outsource_escalation(
            rel,
            deadlines,
            hard,
            available,
            candidate_small,
            minimum,
            len(machines),
            unavoidable_outsource,
            unavoidable_late,
            True,
        )
        heuristic_runtime = time.perf_counter() - started
        heuristic_outsource = sum(row["outsource"] for row in solution)
        heuristic_end = [
            hard[i] if row["outsource"] else int(row["end"])
            for i, row in enumerate(solution)
        ]
        heuristic_on_time = sum(
            int(end <= deadlines[i])
            for i, end in enumerate(heuristic_end)
        )
        heuristic_tardiness = sum(
            max(0, end - deadlines[i])
            for i, end in enumerate(heuristic_end)
        )
        heuristic_waiting = sum(
            0
            if row["outsource"]
            else int(row["start"]) - rel[i]
            for i, row in enumerate(solution)
        )
        rows.append(
            ExactResult(
                size=size,
                candidate_limit=candidate_limit,
                status=str(exact["status"]),
                runtime_seconds=float(exact["runtime_seconds"]),
                encoded_objective=float(exact["encoded_objective"]),
                best_bound=float(exact["best_bound"]),
                relative_gap=float(exact["relative_gap"]),
                exact_outsource=int(exact["outsource"]),
                exact_on_time=int(exact["on_time"]),
                exact_total_tardiness_seconds=int(
                    exact["total_tardiness_seconds"]
                ),
                exact_total_waiting_seconds=int(exact["total_waiting_seconds"]),
                heuristic_runtime_seconds=heuristic_runtime,
                heuristic_outsource=int(heuristic_outsource),
                heuristic_on_time=heuristic_on_time,
                heuristic_total_tardiness_seconds=int(heuristic_tardiness),
                heuristic_total_waiting_seconds=int(heuristic_waiting),
                on_time_difference=(
                    heuristic_on_time - int(exact["on_time"])
                ),
            )
        )
    return rows


def write_results(rows: list[ExactResult]) -> None:
    import pandas as pd

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([asdict(row) for row in rows])
    frame.to_csv(TABLE_DIR / "cp_sat_exact_benchmark.csv", index=False)
    metadata = {
        "sizes": frame["size"].tolist(),
        "all_optimal": bool((frame["status"] == "OPTIMAL").all()),
        "max_relative_gap": float(frame["relative_gap"].max()),
        "heuristic_matches_exact_on_time": bool(
            (frame["on_time_difference"] == 0).all()
        ),
    }
    (REPORT_DIR / "cp_sat_benchmark_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown = frame.to_markdown(index=False)
    report = f"""# CP-SAT 小实例精确求解与启发式对照

## 实验设置

- 规模：20、50、100 个订单；
- 样本：固定包含结构性必须外发订单，其余按批次交期和到达时间确定性选取；
- 候选机器：每个订单保留加工时间最短的 10 台兼容机器；
- 两种方法使用完全相同的订单、机器候选和机器最早可用时间；
- CP-SAT：OptionalInterval + ExactlyOne + NoOverlap；
- 目标优先级：最少外发 → 最少迟交订单 → 总逾期与等待；
- 单实例时间限制：30 秒。

## 结果

{markdown}

## 解释边界

该实验用于验证模型和衡量启发式在确定性小实例上的质量。候选机器剪枝后
的最优性不等于完整 145 台机器候选集上的全局最优性；全规模 887 单仍由
多起点构造与局部搜索求解。
"""
    (REPORT_DIR / "cp_sat_exact_benchmark.md").write_text(
        report,
        encoding="utf-8",
    )


if __name__ == "__main__":
    write_results(run_exact_benchmarks())
