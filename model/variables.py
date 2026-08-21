from ortools.sat.python import cp_model


def create_interval_variables(model, jobs, machines):
    starts = {}
    ends = {}
    intervals = {}

    for job in jobs:
        for task in job:
            job_id, duration, machine = task
            start = model.NewIntVar(0, 100000, f"start_{job_id}")
            end = model.NewIntVar(0, 100000, f"end_{job_id}")
            interval = model.NewIntervalVar(
                start,
                duration,
                end,
                f"interval_{job_id}"
            )

            starts[job_id] = start
            ends[job_id] = end
            intervals.setdefault(machine, []).append(interval)

    return starts, ends, intervals
