"""Measure deterministic searches and preserve maps, routes and expansion traces."""

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gridroute.core import search
from gridroute.fixtures import SEED, cases, to_record

CONFIGURATIONS = [("dijkstra", 1), ("astar", 1), ("weighted_astar", 3)]


def write_csv(path, rows, fields=None):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=fields or list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def source_hashes():
    paths = [
        "src/gridroute/core.py",
        "src/gridroute/fixtures.py",
        "scripts/run_study.py",
    ]
    return {
        path: hashlib.sha256(
            (ROOT / path).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        ).hexdigest()
        for path in paths
    }


def run(output, repetitions):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(
            "Use a new empty directory; existing evidence is preserved"
        )
    if not 1 <= repetitions <= 50:
        raise ValueError("Repetitions must lie in 1..50")
    for folder in ["maps", "routes", "traces"]:
        (output / folder).mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    hashes = source_hashes()
    timings = []
    summaries = []
    rng = random.Random(18139)
    for grid, description, radius in cases():
        record = to_record(grid, description, radius)
        (output / "maps" / f"{grid.name}.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        write_csv(
            output / "maps" / f"{grid.name}.csv",
            [
                {
                    "row": r,
                    "column": c,
                    "terrain_cost": grid.costs[r][c],
                    "blocked": int((r, c) in grid.blocked),
                }
                for r in range(grid.rows)
                for c in range(grid.columns)
            ],
        )
        # The first untimed call also warms each configuration and records its trace.
        results = {
            algorithm: search(grid, algorithm, weight)
            for algorithm, weight in CONFIGURATIONS
        }
        reference = results["dijkstra"].cost
        for repeat in range(repetitions):
            configurations = list(CONFIGURATIONS)
            rng.shuffle(configurations)
            for order, (algorithm, weight) in enumerate(configurations):
                begin = time.perf_counter_ns()
                actual = search(grid, algorithm, weight)
                elapsed = time.perf_counter_ns() - begin
                assert actual == results[algorithm]
                timings.append(
                    {
                        "map": grid.name,
                        "algorithm": algorithm,
                        "weight": weight,
                        "repeat": repeat,
                        "order": order,
                        "elapsed_ns": elapsed,
                    }
                )
        for algorithm, weight in CONFIGURATIONS:
            result = results[algorithm]
            assert result.status == results["dijkstra"].status
            if reference is not None:
                assert result.cost <= weight * reference
                assert sum(grid.costs[r][c] for r, c in result.path[1:]) == result.cost
                if algorithm != "weighted_astar":
                    assert result.cost == reference
            saved = asdict(result)
            saved.pop("trace")
            saved.update({"algorithm": algorithm, "weight": weight, "map": grid.name})
            (output / "routes" / f"{grid.name}__{algorithm}.json").write_text(
                json.dumps(saved, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
            trace_rows = [
                {
                    "event": e.index,
                    "row": e.cell[0],
                    "column": e.cell[1],
                    "g": e.cost,
                    "h": e.heuristic,
                    "priority_numerator": e.priority_numerator,
                    "priority_denominator": e.priority_denominator,
                    "reopened": int(e.reopened),
                }
                for e in result.trace
            ]
            write_csv(
                output / "traces" / f"{grid.name}__{algorithm}.csv",
                trace_rows,
                [
                    "event",
                    "row",
                    "column",
                    "g",
                    "h",
                    "priority_numerator",
                    "priority_denominator",
                    "reopened",
                ],
            )
            samples = [
                row["elapsed_ns"]
                for row in timings
                if row["map"] == grid.name and row["algorithm"] == algorithm
            ]
            summaries.append(
                {
                    "map": grid.name,
                    "algorithm": algorithm,
                    "weight": weight,
                    "rows": grid.rows,
                    "columns": grid.columns,
                    "footprint_radius": radius,
                    "status": result.status,
                    "cost": result.cost if result.cost is not None else "",
                    "reference_cost": reference if reference is not None else "",
                    "cost_ratio": result.cost / reference if reference else "",
                    "path_steps": len(result.path) - 1 if result.path else "",
                    "expanded": result.expanded,
                    "unique_expanded": result.unique_expanded,
                    "reopens": result.reopens,
                    "generated": result.generated,
                    "stale_pops": result.stale_pops,
                    "median_ns": statistics.median(samples),
                    "min_ns": min(samples),
                    "max_ns": max(samples),
                }
            )
    write_csv(output / "measurements.csv", timings)
    write_csv(output / "summary.csv", summaries)
    environment = {
        "started_utc": started,
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "os": platform.system(),
        "architecture": platform.machine(),
        "repetitions": repetitions,
        "map_seed": SEED,
        "order_seed": 18139,
        "maps": len(cases()),
        "raw_timing_rows": len(timings),
        "source_sha256_lf": hashes,
        "source_hash_policy": "CRLF and CR normalized to LF before SHA-256, captured before timing",
        "timing_scope": "One untimed warmup then complete in-memory search calls including trace and route construction; no map I/O or rendering",
        "provenance": "All maps procedurally constructed by this repository; simulated grid planning only",
    }
    (output / "environment.json").write_text(
        json.dumps(environment, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    manifest = [
        {
            "path": path.relative_to(output).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(output.rglob("*"))
        if path.is_file()
    ]
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {"output": str(output), "maps": len(cases()), "timing_rows": len(timings)}
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/latest")
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    run(args.out, args.repetitions)
