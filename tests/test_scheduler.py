from heterogeneous_scheduler.cp_sat import solve_lexicographic
from heterogeneous_scheduler.heuristic import first_fit, solve_multistart
from heterogeneous_scheduler.io import load_instance
from heterogeneous_scheduler.validation import validate_schedule


def test_first_fit_uses_gap():
    assert (
        first_fit(
            [(0, 2), (5, 7)],
            release=1,
            duration=3,
            available=0,
            hard_due=10,
        )
        == 2
    )


def test_heuristic_is_feasible():
    instance = load_instance("examples/small_instance.json")
    schedule = solve_multistart(instance)
    assert validate_schedule(instance, schedule) == []
    assert schedule.metrics(instance)["outsourced"] >= 1


def test_cp_sat_lexicographic_solution():
    instance = load_instance("examples/small_instance.json")
    schedule = solve_lexicographic(instance, seconds_per_stage=5)
    assert validate_schedule(instance, schedule) == []
    assert schedule.metrics(instance)["outsourced"] == 1
    assert set(schedule.stage_status) == {
        "min_outsource",
        "max_on_time",
        "min_tardiness_waiting",
    }
