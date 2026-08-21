from ortools.sat.python import cp_model


def solve_schedule(jobs, machines):
    model = cp_model.CpModel()

    starts = {}
    ends = {}
    intervals = {}

    for job_id, operations in jobs.items():
        for op_id, operation in enumerate(operations):
            duration = operation["duration"]
            machine = operation["machine"]

            start = model.NewIntVar(0, 100000, f"start_{job_id}_{op_id}")
            end = model.NewIntVar(0, 100000, f"end_{job_id}_{op_id}")
            interval = model.NewIntervalVar(
                start, duration, end, f"interval_{job_id}_{op_id}"
            )

            starts[(job_id, op_id)] = start
            ends[(job_id, op_id)] = end
            intervals.setdefault(machine, []).append(interval)

    for machine, machine_intervals in intervals.items():
        model.AddNoOverlap(machine_intervals)

    makespan = model.NewIntVar(0, 100000, "makespan")
    model.AddMaxEquality(makespan, list(ends.values()))
    model.Minimize(makespan)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    return solver, status
