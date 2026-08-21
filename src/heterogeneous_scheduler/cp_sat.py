from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from .model import Assignment, Instance, Schedule


@dataclass
class _Artifacts:
    model: cp_model.CpModel
    outsource: dict[int, cp_model.IntVar]
    start: dict[int, cp_model.IntVar]
    end: dict[int, cp_model.IntVar]
    assign: dict[tuple[int, int], cp_model.IntVar]
    on_time: dict[int, cp_model.IntVar]
    tardiness: dict[int, cp_model.IntVar]
    waiting: dict[int, cp_model.IntVar]


def _build(instance: Instance) -> _Artifacts:
    model = cp_model.CpModel()
    machines = list(instance.machines)
    horizon = max(
        [order.hard_due for order in instance.orders]
        + [machine.available for machine in machines]
    ) + 1
    outsource: dict[int, cp_model.IntVar] = {}
    start: dict[int, cp_model.IntVar] = {}
    end: dict[int, cp_model.IntVar] = {}
    assign: dict[tuple[int, int], cp_model.IntVar] = {}
    on_time: dict[int, cp_model.IntVar] = {}
    tardiness: dict[int, cp_model.IntVar] = {}
    waiting: dict[int, cp_model.IntVar] = {}
    intervals: dict[int, list[cp_model.IntervalVar]] = {
        machine: [] for machine in range(len(machines))
    }

    for i, order in enumerate(instance.orders):
        outsource[i] = model.new_bool_var(f"out_{i}")
        start[i] = model.new_int_var(0, horizon, f"start_{i}")
        end[i] = model.new_int_var(0, horizon, f"end_{i}")
        on_time[i] = model.new_bool_var(f"on_time_{i}")
        tardiness[i] = model.new_int_var(0, horizon, f"tardiness_{i}")
        waiting[i] = model.new_int_var(0, horizon, f"waiting_{i}")
        options = []
        for machine_index, machine in enumerate(machines):
            duration = order.processing.get(machine.id)
            if duration is None:
                continue
            if max(order.release, machine.available) + duration > order.hard_due:
                continue
            present = model.new_bool_var(f"x_{i}_{machine_index}")
            assign[i, machine_index] = present
            options.append(present)
            model.add(
                start[i] >= max(order.release, machine.available)
            ).only_enforce_if(present)
            model.add(end[i] == start[i] + duration).only_enforce_if(present)
            model.add(end[i] <= order.hard_due).only_enforce_if(present)
            intervals[machine_index].append(
                model.new_optional_interval_var(
                    start[i],
                    duration,
                    end[i],
                    present,
                    f"iv_{i}_{machine_index}",
                )
            )
        model.add(sum(options) + outsource[i] == 1)
        model.add(start[i] == 0).only_enforce_if(outsource[i])
        model.add(end[i] == 0).only_enforce_if(outsource[i])
        model.add(on_time[i] == 0).only_enforce_if(outsource[i])
        model.add(end[i] <= order.due).only_enforce_if(on_time[i])
        model.add(on_time[i] + outsource[i] <= 1)
        model.add(tardiness[i] >= end[i] - order.due)
        model.add(tardiness[i] == 0).only_enforce_if(outsource[i])
        model.add(waiting[i] >= start[i] - order.release)
        model.add(waiting[i] == 0).only_enforce_if(outsource[i])

    for machine_intervals in intervals.values():
        model.add_no_overlap(machine_intervals)
    return _Artifacts(
        model,
        outsource,
        start,
        end,
        assign,
        on_time,
        tardiness,
        waiting,
    )


def _solver(seconds: float) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    return solver


def _gap(
    solver: cp_model.CpSolver,
    status: cp_model.CpSolverStatus,
) -> float | None:
    if status == cp_model.OPTIMAL:
        return 0.0
    if status != cp_model.FEASIBLE:
        return None
    objective = solver.objective_value
    return abs(solver.best_objective_bound - objective) / max(
        1.0,
        abs(objective),
    )


def solve_lexicographic(
    instance: Instance,
    seconds_per_stage: float = 10.0,
) -> Schedule:
    """Solve three objectives sequentially without a big-M shortcut."""
    art = _build(instance)
    statuses: dict[str, str] = {}
    gaps: dict[str, float | None] = {}

    art.model.minimize(sum(art.outsource.values()))
    solver = _solver(seconds_per_stage)
    status = solver.solve(art.model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            f"stage 1 has no incumbent: {solver.status_name(status)}"
        )
    best_outsource = int(round(solver.objective_value))
    statuses["min_outsource"] = solver.status_name(status)
    gaps["min_outsource"] = _gap(solver, status)
    art.model.add(sum(art.outsource.values()) == best_outsource)

    art.model.maximize(sum(art.on_time.values()))
    solver = _solver(seconds_per_stage)
    status = solver.solve(art.model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            f"stage 2 has no incumbent: {solver.status_name(status)}"
        )
    best_on_time = int(round(solver.objective_value))
    statuses["max_on_time"] = solver.status_name(status)
    gaps["max_on_time"] = _gap(solver, status)
    art.model.add(sum(art.on_time.values()) == best_on_time)

    art.model.minimize(
        sum(art.tardiness.values()) + sum(art.waiting.values())
    )
    solver = _solver(seconds_per_stage)
    status = solver.solve(art.model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            f"stage 3 has no incumbent: {solver.status_name(status)}"
        )
    statuses["min_tardiness_waiting"] = solver.status_name(status)
    gaps["min_tardiness_waiting"] = _gap(solver, status)

    assignments: list[Assignment] = []
    for i, order in enumerate(instance.orders):
        if solver.value(art.outsource[i]):
            assignments.append(
                Assignment(order.id, None, None, None, outsourced=True)
            )
            continue
        selected = next(
            machine_index
            for (job, machine_index), variable in art.assign.items()
            if job == i and solver.value(variable)
        )
        assignments.append(
            Assignment(
                order.id,
                instance.machines[selected].id,
                solver.value(art.start[i]),
                solver.value(art.end[i]),
            )
        )
    return Schedule(
        assignments,
        stage_status=statuses,
        stage_gap=gaps,
    )
