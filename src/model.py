from dataclasses import dataclass
from typing import List


@dataclass
class Operation:
    job_id: int
    operation_id: int
    machine_id: int
    processing_time: int


@dataclass
class JobShopInstance:
    operations: List[Operation]
    job_count: int
    machine_count: int


@dataclass
class ScheduleResult:
    makespan: int
    assignments: dict


class SchedulingModel:
    """Core data model for heterogeneous machine scheduling.

    The model separates instance definition, solver implementation,
    and validation logic.
    """

    def __init__(self, instance: JobShopInstance):
        self.instance = instance
