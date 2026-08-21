def minimize_makespan(model, completion_time, horizon):
    model.Minimize(completion_time - 0)


def add_total_tardiness_objective(model, tardiness_vars):
    model.Minimize(sum(tardiness_vars))
