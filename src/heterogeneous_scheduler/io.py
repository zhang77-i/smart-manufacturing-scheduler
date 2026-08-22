from __future__ import annotations

import json
from pathlib import Path

from .model import Instance, Machine, Order


def load_instance(path: str | Path) -> Instance:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    machines = tuple(Machine(**row) for row in payload["machines"])
    orders = tuple(
        Order(
            id=row["id"],
            release=int(row["release"]),
            due=int(row["due"]),
            hard_due=int(row["hard_due"]),
            processing={key: int(value) for key, value in row["processing"].items()},
            predecessors=tuple(row.get("predecessors", ())),
        )
        for row in payload["orders"]
    )
    return Instance(machines=machines, orders=orders)
