"""Heap, exact-priority and evidence reconciliation checks."""

import csv
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import statistics
import unittest

from gridroute.core import Grid, search
from gridroute.fixtures import cases, from_record

ROOT = Path(__file__).resolve().parents[1]


class ImplementationChecks(unittest.TestCase):
    def test_reopening_stale_entries_and_deterministic_ties(self):
        grids = {grid.name: grid for grid, _, _ in cases()}
        rooms = grids["rooms"]
        weighted = search(rooms, "weighted_astar", 3)
        self.assertGreater(weighted.reopens, 0)
        self.assertGreater(weighted.stale_pops, 0)
        self.assertEqual(weighted, search(rooms, "weighted_astar", 3))
        by_cell = {}
        for event in weighted.trace:
            if event.reopened:
                self.assertLess(event.cost, by_cell[event.cell])
            else:
                self.assertNotIn(event.cell, by_cell)
            by_cell[event.cell] = event.cost
        self.assertEqual(
            weighted.cost, sum(rooms.costs[r][c] for r, c in weighted.path[1:])
        )
        self.assertLessEqual(weighted.cost, 3 * search(rooms, "dijkstra").cost)
        uniform = Grid(((1, 1, 1), (1, 1, 1), (1, 1, 1)), frozenset(), (0, 0), (2, 2))
        self.assertEqual(search(uniform).path, ((0, 0), (0, 1), (0, 2), (1, 2), (2, 2)))

    def test_integer_priority_handles_costs_beyond_float_precision(self):
        huge = 10**400
        grid = Grid(
            ((huge, huge + 1, huge), (huge, huge, huge)), frozenset(), (0, 0), (1, 2)
        )
        for algorithm, weight in [
            ("dijkstra", 1),
            ("astar", 1),
            ("weighted_astar", 1.5),
        ]:
            result = search(grid, algorithm, weight)
            self.assertEqual(result.cost, 3 * huge)
            self.assertTrue(
                all(type(event.priority_numerator) is int for event in result.trace)
            )

    def test_invalid_model_inputs_are_rejected(self):
        for costs in [
            (),
            ((),),
            ((0,),),
            ((-1,),),
            ((True,),),
            ((1.5,),),
            ((1, 2), (1,)),
        ]:
            with self.subTest(costs=costs), self.assertRaises(ValueError):
                Grid(costs, frozenset(), (0, 0), (0, 0))
        grid = Grid(((1,),), frozenset(), (0, 0), (0, 0))
        for weight in [0, 0.5, True, float("nan"), float("inf"), "3"]:
            with self.subTest(weight=weight), self.assertRaises(ValueError):
                search(grid, "weighted_astar", weight)
        with self.assertRaises(ValueError):
            search(grid, "astar", 3)


class EvidenceChecks(unittest.TestCase):
    def test_maps_routes_traces_and_measured_summaries_reconcile(self):
        folder = Path(os.environ.get("GRID_RESULTS", ROOT / "results/published"))
        environment = json.loads((folder / "environment.json").read_text())
        for relative, expected in environment["source_sha256_lf"].items():
            source = (
                (ROOT / relative)
                .read_bytes()
                .replace(b"\r\n", b"\n")
                .replace(b"\r", b"\n")
            )
            self.assertEqual(hashlib.sha256(source).hexdigest(), expected)
        for item in json.loads((folder / "manifest.json").read_text()):
            content = (folder / item["path"]).read_bytes()
            self.assertEqual(len(content), item["bytes"])
            self.assertEqual(hashlib.sha256(content).hexdigest(), item["sha256"])
        with (folder / "measurements.csv").open() as stream:
            timings = list(csv.DictReader(stream))
        with (folder / "summary.csv").open() as stream:
            summaries = list(csv.DictReader(stream))
        self.assertEqual(
            len(timings), environment["maps"] * 3 * environment["repetitions"]
        )
        self.assertEqual(len(summaries), environment["maps"] * 3)
        for row in summaries:
            name, algorithm, weight = row["map"], row["algorithm"], int(row["weight"])
            grid = from_record(
                json.loads((folder / "maps" / f"{name}.json").read_text())
            )
            with (folder / "maps" / f"{name}.csv").open() as stream:
                cells = list(csv.DictReader(stream))
            self.assertEqual(len(cells), grid.rows * grid.columns)
            for cell in cells:
                point = int(cell["row"]), int(cell["column"])
                self.assertEqual(
                    int(cell["terrain_cost"]), grid.costs[point[0]][point[1]]
                )
                self.assertEqual(bool(int(cell["blocked"])), point in grid.blocked)
            actual = search(grid, algorithm, weight)
            saved = json.loads(
                (folder / "routes" / f"{name}__{algorithm}.json").read_text()
            )
            self.assertEqual(saved["path"], [list(point) for point in actual.path])
            for field in [
                "status",
                "cost",
                "expanded",
                "unique_expanded",
                "reopens",
                "generated",
                "stale_pops",
            ]:
                self.assertEqual(saved[field], getattr(actual, field))
            self.assertEqual(row["status"], actual.status)
            self.assertEqual(
                row["cost"], str(actual.cost) if actual.cost is not None else ""
            )
            for field in [
                "expanded",
                "unique_expanded",
                "reopens",
                "generated",
                "stale_pops",
            ]:
                self.assertEqual(int(row[field]), getattr(actual, field))
            with (folder / "traces" / f"{name}__{algorithm}.csv").open() as stream:
                trace = list(csv.DictReader(stream))
            self.assertEqual(len(trace), len(actual.trace))
            for saved_event, event in zip(trace, actual.trace):
                self.assertEqual(
                    (int(saved_event["row"]), int(saved_event["column"])), event.cell
                )
                for stored, field in [
                    ("event", "index"),
                    ("g", "cost"),
                    ("h", "heuristic"),
                    ("priority_numerator", "priority_numerator"),
                    ("priority_denominator", "priority_denominator"),
                    ("reopened", "reopened"),
                ]:
                    self.assertEqual(int(saved_event[stored]), getattr(event, field))
            samples = [
                int(t["elapsed_ns"])
                for t in timings
                if t["map"] == name and t["algorithm"] == algorithm
            ]
            self.assertEqual(len(samples), environment["repetitions"])
            self.assertTrue(all(value > 0 for value in samples))
            self.assertEqual(float(row["median_ns"]), statistics.median(samples))
            self.assertEqual(int(row["min_ns"]), min(samples))
            self.assertEqual(int(row["max_ns"]), max(samples))
            reference = search(grid, "dijkstra").cost
            if reference is not None:
                self.assertEqual(int(row["reference_cost"]), reference)
                self.assertAlmostEqual(
                    float(row["cost_ratio"]), actual.cost / reference
                )
                self.assertEqual(int(row["path_steps"]), len(actual.path) - 1)
            else:
                self.assertEqual(row["cost_ratio"], "")
                self.assertEqual(row["reference_cost"], "")


if __name__ == "__main__":
    unittest.main()
