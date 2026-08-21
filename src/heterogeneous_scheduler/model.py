from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Machine:
    id: str
    available: int = 0


@dataclass(frozen=True)
class Order:
    id: str
    release: int
    due: int
    hard_due: int
    processing: dict[str, int]


@dataclass(frozen=True)
class Instance:
    machines: tuple[Machine, ...]
    orders: tuple[Order, ...]

    def machine_map(self) -> dict[str, Machine]:
        return {machine.id: machine for machine in self.machines}


@dataclass(frozen=True)
class Assignment:
    order_id: str
    machine_id: str | None
    start: int | None
    end: int | None
    outsourced: bool = False


@dataclass
class Schedule:
    assignments: list[Assignment]
    stage_status: dict[str, str] = field(default_factory=dict)
    stage_gap: dict[str, float | None] = field(default_factory=dict)

    def by_order(self) -> dict[str, Assignment]:
        return {assignment.order_id: assignment for assignment in self.assignments}

    def metrics(self, instance: Instance) -> dict[str, int]:
        orders = {order.id: order for order in instance.orders}
        outsourced = sum(a.outsourced for a in self.assignments)
        on_time = sum(
            not a.outsourced and a.end is not None and a.end <= orders[a.order_id].due
            for a in self.assignments
        )
        tardiness = sum(
            max(0, (a.end or 0) - orders[a.order_id].due)
            for a in self.assignments
            if not a.outsourced
        )
        waiting = sum(
            max(0, (a.start or 0) - orders[a.order_id].release)
            for a in self.assignments
            if not a.outsourced
        )
        return {
            "outsourced": int(outsourced),
            "on_time": int(on_time),
            "tardiness": int(tardiness),
            "waiting": int(waiting),
        }
