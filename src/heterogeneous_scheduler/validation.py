from __future__ import annotations

from .model import Instance, Schedule


def validate_schedule(instance: Instance, schedule: Schedule) -> list[str]:
    errors: list[str] = []
    orders = {order.id: order for order in instance.orders}
    machines = instance.machine_map()
    assignments = schedule.by_order()
    if set(assignments) != set(orders):
        missing = sorted(set(orders) - set(assignments))
        extra = sorted(set(assignments) - set(orders))
        errors.append(f"order coverage mismatch: missing={missing}, extra={extra}")
    if len(assignments) != len(schedule.assignments):
        errors.append("duplicate order assignments")
    calendars: dict[str, list[tuple[int, int, str]]] = {
        machine_id: [] for machine_id in machines
    }
    for order_id, assignment in assignments.items():
        order = orders.get(order_id)
        if order is None or assignment.outsourced:
            continue
        if assignment.machine_id not in order.processing:
            errors.append(f"{order_id}: incompatible machine {assignment.machine_id}")
            continue
        if assignment.start is None or assignment.end is None:
            errors.append(f"{order_id}: missing start/end")
            continue
        duration = order.processing[assignment.machine_id]
        machine = machines.get(assignment.machine_id)
        if machine is None:
            errors.append(f"{order_id}: unknown machine {assignment.machine_id}")
            continue
        if assignment.end - assignment.start != duration:
            errors.append(f"{order_id}: incorrect processing duration")
        if assignment.start < max(order.release, machine.available):
            errors.append(f"{order_id}: starts before release or machine availability")
        if assignment.end > order.hard_due:
            errors.append(f"{order_id}: violates hard due")
        calendars[assignment.machine_id].append(
            (assignment.start, assignment.end, order_id)
        )
    for machine_id, jobs in calendars.items():
        jobs.sort()
        for previous, current in zip(jobs, jobs[1:]):
            if current[0] < previous[1]:
                errors.append(
                    f"{machine_id}: overlap {previous[2]} / {current[2]}"
                )
    for successor in instance.orders:
        successor_assignment = assignments.get(successor.id)
        if successor_assignment is None or successor_assignment.outsourced:
            continue
        for predecessor_id in successor.predecessors:
            predecessor_assignment = assignments.get(predecessor_id)
            if predecessor_assignment is None or predecessor_assignment.outsourced:
                continue
            if (
                predecessor_assignment.end is None
                or successor_assignment.start is None
                or successor_assignment.start < predecessor_assignment.end
            ):
                errors.append(
                    f"{predecessor_id} -> {successor.id}: precedence violated"
                )
    return errors
