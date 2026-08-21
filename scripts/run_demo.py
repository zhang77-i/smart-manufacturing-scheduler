from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from heterogeneous_scheduler.cp_sat import solve_lexicographic
from heterogeneous_scheduler.heuristic import solve_multistart
from heterogeneous_scheduler.io import load_instance
from heterogeneous_scheduler.validation import validate_schedule


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--instance",
        type=Path,
        default=ROOT / "examples" / "small_instance.json",
    )
    parser.add_argument(
        "--solver",
        choices=("heuristic", "cp-sat"),
        default="heuristic",
    )
    parser.add_argument("--seconds-per-stage", type=float, default=5.0)
    args = parser.parse_args()
    instance = load_instance(args.instance)
    schedule = (
        solve_multistart(instance)
        if args.solver == "heuristic"
        else solve_lexicographic(instance, args.seconds_per_stage)
    )
    result = {
        "solver": args.solver,
        "metrics": schedule.metrics(instance),
        "stage_status": schedule.stage_status,
        "stage_gap": schedule.stage_gap,
        "validation_errors": validate_schedule(instance, schedule),
        "assignments": [
            assignment.__dict__ for assignment in schedule.assignments
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
