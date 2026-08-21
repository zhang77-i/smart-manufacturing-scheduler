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


def construct(instance: Instance, rule: str = "edd") -> Schedule:
    machines = instance.machine_map()
    calendars: dict[str, list[tuple[int, int]]] = {
        machine.id: [] for machine in instance.machines
    }
    assignments: list[Assignment] = []
    for order in sorted(instance.orders, key=lambda item: _priority(item, rule)):
        options: list[tuple[tuple[int, int, int, str], str, int, int]] = []
        for machine_id, duration in order.processing.items():
            machine = machines.get(machine_id)
            if machine is None:
                continue
            start = first_fit(
                calendars[machine_id],
                order.release,
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
            assignments.append(Assignment(order.id, None, None, None, outsourced=True))
            continue
        _, machine_id, start, end = min(options)
        calendars[machine_id].append((start, end))
        assignments.append(Assignment(order.id, machine_id, start, end))
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
