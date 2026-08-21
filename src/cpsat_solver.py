from ortools.sat.python import cp_model

from src.model import ScheduleResult


class CPSATScheduler:
    """CP-SAT solver for heterogeneous machine scheduling.

    Implements interval based scheduling with precedence and machine
    capacity constraints.
    """

    def __init__(self, instance):
        self.instance = instance

    def solve(self):
        model = cp_model.CpModel()

        starts = {}
        ends = {}
        intervals = {}

        horizon = sum(
            op.processing_time
            for op in self.instance.operations
        )

        for op in self.instance.operations:
            start = model.NewIntVar(
                0,
                horizon,
                f"start_{op.job_id}_{op.operation_id}"
            )

            end = model.NewIntVar(
                0,
                horizon,
                f"end_{op.job_id}_{op.operation_id}"
            )

            interval = model.NewIntervalVar(
                start,
                op.processing_time,
                end,
                f"interval_{op.job_id}_{op.operation_id}"
            )

            starts[(op.job_id, op.operation_id)] = start
            ends[(op.job_id, op.operation_id)] = end
            intervals[(op.machine_id, op.job_id, op.operation_id)] = interval

        for job_id in range(self.instance.job_count):
            job_ops = [
                op
                for op in self.instance.operations
                if op.job_id == job_id
            ]

            job_ops.sort(key=lambda x: x.operation_id)

            for prev, nxt in zip(job_ops, job_ops[1:]):
                model.Add(
                    starts[(job_id, nxt.operation_id)]
                    >= ends[(job_id, prev.operation_id)]
                )

        for machine_id in range(self.instance.machine_count):
            machine_intervals = [
                interval
                for (m, _, _), interval in intervals.items()
                if m == machine_id
            ]

            if machine_intervals:
                model.AddNoOverlap(machine_intervals)

        makespan = model.NewIntVar(0, horizon, "makespan")
        model.AddMaxEquality(
            makespan,
            list(ends.values())
        )

        model.Minimize(makespan)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            return None

        assignments = {
            key: solver.Value(value)
            for key, value in starts.items()
        }

        return ScheduleResult(
            makespan=solver.Value(makespan),
            assignments=assignments,
        )
