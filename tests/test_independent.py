"""Independent references for routing costs and discrete square footprints.

The reference never calls Grid.neighbors or the production heuristic. Its
explicit edge relaxation deliberately differs from the heap-based solvers.
"""

from dataclasses import replace
import random
import unittest

from gridroute.core import Grid, inflate_obstacles, manhattan_heuristic, search


def bellman_ford(grid, source=None):
    """Return shortest distances using explicit directed destination-cost edges."""
    source = grid.start if source is None else source
    cells = [
        (row, col)
        for row in range(len(grid.costs))
        for col in range(len(grid.costs[0]))
        if (row, col) not in grid.blocked
    ]
    if source not in cells:
        return {}
    edges = [
        (u, v, grid.costs[v[0]][v[1]])
        for u in cells
        for v in cells
        if abs(u[0] - v[0]) + abs(u[1] - v[1]) == 1
    ]
    distances = {source: 0}
    for _ in range(len(cells) - 1):
        changed = False
        for u, v, cost in edges:
            if u in distances and (
                v not in distances or distances[u] + cost < distances[v]
            ):
                distances[v] = distances[u] + cost
                changed = True
        if not changed:
            break
    return distances


def footprint_reference(grid, radius):
    """Enumerate each whole footprint, including contact outside the map."""
    blocked = set()
    for row in range(len(grid.costs)):
        for col in range(len(grid.costs[0])):
            footprint = (
                (row + dr, col + dc)
                for dr in range(-radius, radius + 1)
                for dc in range(-radius, radius + 1)
            )
            if any(
                not (0 <= rr < len(grid.costs) and 0 <= cc < len(grid.costs[0]))
                or (rr, cc) in grid.blocked
                for rr, cc in footprint
            ):
                blocked.add((row, col))
    return frozenset(blocked)


class IndependentRoutingTests(unittest.TestCase):
    def assert_legal_route(self, grid, result):
        self.assertEqual(result.status, "found")
        self.assertEqual(result.path[0], grid.start)
        self.assertEqual(result.path[-1], grid.goal)
        self.assertEqual(len(set(result.path)), len(result.path))
        for row, col in result.path:
            self.assertTrue(0 <= row < len(grid.costs))
            self.assertTrue(0 <= col < len(grid.costs[0]))
            self.assertNotIn((row, col), grid.blocked)
        for u, v in zip(result.path, result.path[1:]):
            self.assertEqual(abs(u[0] - v[0]) + abs(u[1] - v[1]), 1)
        self.assertEqual(
            sum(grid.costs[row][col] for row, col in result.path[1:]),
            result.cost,
        )

    def assert_against_oracle(self, grid):
        optimal = bellman_ford(grid).get(grid.goal)
        for algorithm, weight in (
            ("dijkstra", 1),
            ("astar", 1),
            ("weighted_astar", 1),
            ("weighted_astar", 1.5),
            ("weighted_astar", 3),
        ):
            with self.subTest(algorithm=algorithm, weight=weight):
                result = search(grid, algorithm, weight)
                if grid.start in grid.blocked or grid.goal in grid.blocked:
                    self.assertEqual(result.status, "blocked_endpoint")
                    self.assertEqual(result.path, ())
                    self.assertIsNone(result.cost)
                elif optimal is None:
                    self.assertEqual(result.status, "unreachable")
                    self.assertEqual(result.path, ())
                    self.assertIsNone(result.cost)
                else:
                    self.assert_legal_route(grid, result)
                    self.assertGreaterEqual(result.cost, optimal)
                    self.assertLessEqual(result.cost, weight * optimal)
                    if weight == 1:
                        self.assertEqual(result.cost, optimal)
                self.assertEqual(result.expanded, len(result.trace))
                self.assertEqual(
                    result.unique_expanded, len({step.cell for step in result.trace})
                )
                self.assertEqual(result.reopens, result.expanded - result.unique_expanded)

    def test_randomized_differential_costs_and_weighted_bound(self):
        rng = random.Random(20261120)
        for case in range(100):
            rows, cols = rng.randint(1, 7), rng.randint(1, 7)
            costs = tuple(
                tuple(rng.randint(1, 25) for _ in range(cols))
                for _ in range(rows)
            )
            start = (rng.randrange(rows), rng.randrange(cols))
            goal = (rng.randrange(rows), rng.randrange(cols))
            blocked = frozenset(
                (row, col)
                for row in range(rows)
                for col in range(cols)
                if rng.random() < 0.25
            )
            grid = Grid(costs, blocked, start, goal)
            with self.subTest(case=case, grid=grid):
                self.assert_against_oracle(grid)

    def test_destination_terrain_excludes_start_and_includes_goal(self):
        grid = Grid(((99, 2, 7),), frozenset(), (0, 0), (0, 2))
        for algorithm in ("dijkstra", "astar", "weighted_astar"):
            result = search(grid, algorithm)
            self.assertEqual(result.cost, 9)
            self.assert_legal_route(grid, result)
        reverse = replace(grid, start=grid.goal, goal=grid.start)
        self.assertEqual(search(reverse).cost, 101)

    def test_expensive_direct_route_yields_to_longer_cheap_route(self):
        grid = Grid(
            ((1, 1, 1, 1, 1), (1, 20, 20, 20, 1), (1, 1, 1, 1, 1)),
            frozenset(),
            (1, 0),
            (1, 4),
        )
        self.assertEqual(bellman_ford(grid)[grid.goal], 6)
        self.assert_against_oracle(grid)

    def test_single_cell_blocked_endpoints_and_diagonal_disconnection(self):
        grids = [
            Grid(((7,),), frozenset(), (0, 0), (0, 0)),
            Grid(((7,),), frozenset({(0, 0)}), (0, 0), (0, 0)),
            Grid(((1, 1), (1, 1)), frozenset({(0, 1), (1, 0)}), (0, 0), (1, 1)),
            Grid(((1, 1, 1),), frozenset({(0, 1)}), (0, 0), (0, 2)),
            Grid(((1, 1),), frozenset({(0, 1)}), (0, 0), (0, 1)),
        ]
        for grid in grids:
            with self.subTest(grid=grid):
                self.assert_against_oracle(grid)

    def test_manhattan_is_admissible_and_consistent_for_entry_costs(self):
        rng = random.Random(862)
        for case in range(12):
            costs = tuple(tuple(rng.randint(2, 12) for _ in range(5)) for _ in range(4))
            blocked = frozenset(
                (row, col)
                for row in range(4)
                for col in range(5)
                if (row, col) != (3, 4) and rng.random() < 0.2
            )
            grid = Grid(costs, blocked, (0, 0), (3, 4))
            self.assertEqual(manhattan_heuristic(grid, grid.goal), 0)
            free = [(r, c) for r in range(4) for c in range(5) if (r, c) not in blocked]
            for u in free:
                h = manhattan_heuristic(grid, u)
                exact = bellman_ford(grid, u).get(grid.goal)
                with self.subTest(case=case, source=u):
                    self.assertGreaterEqual(h, 0)
                    if exact is not None:
                        self.assertLessEqual(h, exact)
                    for v in free:
                        if abs(u[0] - v[0]) + abs(u[1] - v[1]) == 1:
                            self.assertLessEqual(
                                h, grid.costs[v[0]][v[1]] + manhattan_heuristic(grid, v)
                            )


class IndependentFootprintTests(unittest.TestCase):
    def test_square_inflation_matches_enumerated_footprints(self):
        rng = random.Random(218)
        for case in range(35):
            rows, cols = rng.randint(1, 9), rng.randint(1, 9)
            blocked = frozenset(
                (row, col)
                for row in range(rows)
                for col in range(cols)
                if rng.random() < 0.15
            )
            grid = Grid(tuple((1,) * cols for _ in range(rows)), blocked, (0, 0), (rows - 1, cols - 1))
            for radius in range(4):
                with self.subTest(case=case, radius=radius):
                    inflated = inflate_obstacles(grid, radius)
                    self.assertEqual(inflated.blocked, footprint_reference(grid, radius))
                    self.assertEqual(inflated.costs, grid.costs)
                    self.assertEqual(inflated.start, grid.start)
                    self.assertEqual(inflated.goal, grid.goal)
                    self.assertEqual(grid.blocked, blocked)

    def test_inflation_includes_diagonals_and_outside_map(self):
        grid = Grid(tuple((1,) * 7 for _ in range(7)), frozenset({(3, 3)}), (1, 1), (5, 5))
        inflated = inflate_obstacles(grid, 1)
        self.assertIn((2, 2), inflated.blocked)
        self.assertIn((4, 4), inflated.blocked)
        self.assertNotIn((1, 1), inflated.blocked)
        self.assertTrue(all((0, c) in inflated.blocked for c in range(7)))
        self.assertTrue(all((r, 6) in inflated.blocked for r in range(7)))
        self.assertEqual(inflate_obstacles(grid, 0).blocked, grid.blocked)
        self.assertEqual(len(inflate_obstacles(grid, 4).blocked), 49)

    def test_invalid_footprint_radii_are_rejected(self):
        grid = Grid(((1,),), frozenset(), (0, 0), (0, 0))
        for radius in (-1, 0.5, True, "1"):
            with self.subTest(radius=radius), self.assertRaises(ValueError):
                inflate_obstacles(grid, radius)


if __name__ == "__main__":
    unittest.main()
