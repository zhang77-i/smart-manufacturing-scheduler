def add_precedence_constraints(model, start_vars, end_vars, operations):
    for job in operations:
        for first, second in zip(job[:-1], job[1:]):
            model.Add(start_vars[second] >= end_vars[first])


def add_machine_capacity_constraints(model, machine_intervals):
    for machine, intervals in machine_intervals.items():
        model.AddNoOverlap(intervals)
