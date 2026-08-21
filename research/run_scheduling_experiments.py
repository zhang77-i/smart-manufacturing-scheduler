"""Run exact benchmarks plus heuristic ablation and scale experiments."""

from __future__ import annotations

from ortools.sat.python import cp_model as _cp_model  # noqa: F401

import time
from pathlib import Path

import pandas as pd

from exact_cp_sat_benchmark import (
    ROOT,
    load_heuristic_module,
    run_exact_benchmarks,
    write_results,
)


def objective_record(name: str, size: int, objective, runtime: float) -> dict:
    return {
        "size": size,
        "method": name,
        "on_time_orders": -int(objective[0]),
        "total_tardiness_seconds": int(objective[1]),
        "total_waiting_seconds": int(objective[2]),
        "runtime_seconds": runtime,
    }


def run_ablation() -> pd.DataFrame:
    module = load_heuristic_module()
    orders, process, _, machines = module.load_data()
    process_map, _, _ = module.build_process_map(orders, process)
    (
        _,
        release,
        due,
        hard_due,
        available,
        candidates,
        minimum,
    ) = module.build_parameters(orders, machines, process_map)

    rows = []
    for size in (100, 300, len(orders)):
        selected = sorted(
            range(len(orders)),
            key=lambda i: (due[i], release[i], i),
        )[:size]
        rel = [release[i] for i in selected]
        deadlines = [due[i] for i in selected]
        hard = [hard_due[i] for i in selected]
        options = [candidates[i] for i in selected]
        min_processing = [minimum[i] for i in selected]
        mandatory, unavoidable_late, _ = module.structural_check(
            rel,
            deadlines,
            hard,
            available,
            options,
            True,
        )

        sequence = module.build_sequence(
            "EDD",
            rel,
            deadlines,
            min_processing,
        )
        started = time.perf_counter()
        single = module.construct_schedule(
            sequence,
            rel,
            deadlines,
            hard,
            available,
            options,
            len(machines),
            mandatory,
            True,
            "DUE_WAIT",
        )
        runtime = time.perf_counter() - started
        if single is not None:
            rows.append(
                objective_record(
                    "EDD_single_start",
                    size,
                    module.schedule_objective(single, rel, deadlines),
                    runtime,
                )
            )

        original_improvement = module.two_job_improvement
        module.two_job_improvement = lambda result, *args, **kwargs: result
        try:
            started = time.perf_counter()
            multi, objective, _ = module.solve_heuristic(
                rel,
                deadlines,
                hard,
                available,
                options,
                min_processing,
                len(machines),
                mandatory,
                unavoidable_late,
                True,
            )
            rows.append(
                objective_record(
                    "multi_start_constructive",
                    size,
                    objective,
                    time.perf_counter() - started,
                )
            )
        finally:
            module.two_job_improvement = original_improvement

        started = time.perf_counter()
        improved, objective, _ = module.solve_heuristic(
            rel,
            deadlines,
            hard,
            available,
            options,
            min_processing,
            len(machines),
            mandatory,
            unavoidable_late,
            True,
        )
        rows.append(
            objective_record(
                "multi_start_plus_local_search",
                size,
                objective,
                time.perf_counter() - started,
            )
        )
    return pd.DataFrame(rows)


def main() -> None:
    exact = run_exact_benchmarks()
    write_results(exact)
    ablation = run_ablation()
    table_dir = ROOT / "reports" / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    ablation.to_csv(table_dir / "heuristic_ablation_scale.csv", index=False)
    report = f"""# 启发式消融与规模实验

## 结果

{ablation.to_markdown(index=False)}

## 方法说明

- `EDD_single_start`：单一 EDD 排序与 DUE_WAIT 机器评分；
- `multi_start_constructive`：多规则、多随机种子和三种机器评分，不做局部搜索；
- `multi_start_plus_local_search`：在多起点构造基础上加入关键迟交订单换机和两订单重排。

所有结果均使用独立约束校验器验证。规模实验用于展示算法随订单数量的运行时间
与方案质量变化，不把启发式可行结果表述为全局最优。
"""
    (ROOT / "reports" / "heuristic_ablation_scale.md").write_text(
        report,
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
