from __future__ import annotations

from collections.abc import Iterable

from .model import Assignment, Instance, Order, Schedule


def first_fit(
    intervals: list[tuple[int, int]],
    release: int,
    duration: int,
    available: int,
    hard_due: int,
) -> int | None:
    start = max(release, available)
    for left, right in sorted(intervals):
        if start + duration <= left:
            return start
        start = max(start, right)
    return start if start + duration <= hard_due else None


def _priority(order: Order, rule: str) -> tuple[int, int, str]:
    shortest = min(order.processing.values(), default=10**12)
    if rule == "release":
        return order.release, order.due, order.id
    if rule == "slack":
        return order.due - order.release - shortest, order.due, order.id
    if rule == "shortest":
        return shortest, order.due, order.id
    return order.due, order.release, order.id


def _topological_priority_order(instance: Instance, rule: str) -> list[Order]:
    orders = {order.id: order for order in instance.orders}
    successors: dict[str, list[str]] = {order_id: [] for order_id in orders}
    indegree = {
        order.id: len(order.predecessors) for order in instance.orders
    }
    for order in instance.orders:
        for predecessor in order.predecessors:
            successors[predecessor].append(order.id)

    ready = [
        orders[order_id]
        for order_id, degree in indegree.items()
        if degree == 0
    ]
    result: list[Order] = []
    while ready:
        current = min(ready, key=lambda order: _priority(order, rule))
        ready.remove(current)
        result.append(current)
        for successor in successors[current.id]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(orders[successor])
    return result


def construct(instance: Instance, rule: str = "edd") -> Schedule:
    machines = instance.machine_map()
    calendars: dict[str, list[tuple[int, int]]] = {
        machine.id: [] for machine in instance.machines
    }
    assignments: list[Assignment] = []
    assignment_by_order: dict[str, Assignment] = {}
    for order in _topological_priority_order(instance, rule):
        internal_predecessor_ends = [
            assignment_by_order[predecessor].end
            for predecessor in order.predecessors
            if not assignment_by_order[predecessor].outsourced
        ]
        effective_release = max(
            [order.release]
            + [
                int(end)
                for end in internal_predecessor_ends
                if end is not None
            ]
        )
        options: list[tuple[tuple[int, int, int, str], str, int, int]] = []
        for machine_id, duration in order.processing.items():
            machine = machines.get(machine_id)
            if machine is None:
                continue
            start = first_fit(
                calendars[machine_id],
                effective_release,
                duration,
                machine.available,
                order.hard_due,
            )
            if start is None:
                continue
            end = start + duration
            score = (
                int(end > order.due),
                max(0, end - order.due),
                start - order.release,
                machine_id,
            )
            options.append((score, machine_id, start, end))
        if not options:
            assignment = Assignment(
                order.id,
                None,
                None,
                None,
                outsourced=True,
            )
            assignments.append(assignment)
            assignment_by_order[order.id] = assignment
            continue
        _, machine_id, start, end = min(options)
        calendars[machine_id].append((start, end))
        assignment = Assignment(order.id, machine_id, start, end)
        assignments.append(assignment)
        assignment_by_order[order.id] = assignment
    return Schedule(assignments)


def solve_multistart(
    instance: Instance,
    rules: Iterable[str] = ("edd", "release", "slack", "shortest"),
) -> Schedule:
    candidates = [construct(instance, rule) for rule in rules]
    return min(
        candidates,
        key=lambda schedule: (
            schedule.metrics(instance)["outsourced"],
            -schedule.metrics(instance)["on_time"],
            schedule.metrics(instance)["tardiness"]
            + schedule.metrics(instance)["waiting"],
        ),
    )
