import pytest

from heterogeneous_scheduler.cp_sat import solve_lexicographic
from heterogeneous_scheduler.heuristic import first_fit, solve_multistart
from heterogeneous_scheduler.io import load_instance
from heterogeneous_scheduler.model import (
    Assignment,
    Instance,
    Machine,
    Order,
    Schedule,
)
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


def precedence_instance() -> Instance:
    return Instance(
        machines=(Machine("M1"),),
        orders=(
            Order("A", 0, 10, 12, {"M1": 4}),
            Order("B", 0, 3, 12, {"M1": 2}, predecessors=("A",)),
        ),
    )


def test_heuristic_respects_precedence():
    instance = precedence_instance()
    schedule = solve_multistart(instance)
    assignments = schedule.by_order()
    assert validate_schedule(instance, schedule) == []
    assert assignments["B"].start >= assignments["A"].end


def test_cp_sat_respects_precedence():
    instance = precedence_instance()
    schedule = solve_lexicographic(instance, seconds_per_stage=5)
    assignments = schedule.by_order()
    assert validate_schedule(instance, schedule) == []
    assert assignments["B"].start >= assignments["A"].end


def test_validator_detects_precedence_violation():
    instance = precedence_instance()
    schedule = Schedule(
        [
            Assignment("A", "M1", 2, 6),
            Assignment("B", "M1", 0, 2),
        ]
    )
    assert "A -> B: precedence violated" in validate_schedule(instance, schedule)


def test_instance_rejects_precedence_cycle():
    with pytest.raises(
        ValueError,
        match="precedence graph contains a cycle",
    ):
        Instance(
            machines=(Machine("M1"),),
            orders=(
                Order("A", 0, 5, 10, {"M1": 1}, predecessors=("B",)),
                Order("B", 0, 5, 10, {"M1": 1}, predecessors=("A",)),
            ),
        )
