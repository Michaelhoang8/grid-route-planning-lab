"""Owned procedural maps; no sensor, survey or real-world map input."""

from dataclasses import replace
import random

from .core import Grid, inflate_obstacles

SEED = 20261120


def make_grid(name, rows, columns, start, goal, cost=1, blocked=()):
    return Grid(
        tuple(tuple(cost for _ in range(columns)) for _ in range(rows)),
        frozenset(blocked),
        start,
        goal,
        name,
    )


def cases():
    rng = random.Random(SEED)
    terrain = make_grid("terrain-band", 24, 48, (12, 3), (12, 44))
    costs = tuple(
        tuple(
            4 if 7 <= r <= 17 and 13 <= c <= 33 else 1 for c in range(terrain.columns)
        )
        for r in range(terrain.rows)
    )
    terrain = replace(terrain, costs=costs)

    warehouse = make_grid("warehouse", 35, 53, (31, 3), (3, 49))
    shelves = {
        (r, c)
        for r in range(5, 30)
        for c in range(8, 46)
        if c % 8 in {0, 1, 2} and r not in {11, 12, 23, 24}
    }
    warehouse = replace(
        warehouse,
        blocked=frozenset(shelves),
        costs=tuple(
            tuple(1 if r % 6 != 0 else 2 for c in range(53)) for r in range(35)
        ),
    )

    rooms = make_grid("rooms", 37, 55, (3, 3), (33, 51))
    walls = {(r, c) for r in range(37) for c in [13, 27, 41]}
    for wall, doorway in [(13, 28), (27, 8), (41, 27)]:
        for r in range(doorway - 1, doorway + 2):
            walls.discard((r, wall))
    rooms = replace(rooms, blocked=frozenset(walls))

    random_terrain = make_grid("seeded-terrain", 28, 43, (2, 2), (25, 40))
    costs = tuple(
        tuple(rng.choices([1, 2, 4, 8], weights=[7, 2, 1, 1])[0] for _ in range(43))
        for _ in range(28)
    )
    obstacles = {(r, c) for r in range(28) for c in range(43) if rng.random() < 0.17}
    # Keep a legal top/right route. Other routes remain procedural.
    obstacles.difference_update(
        {(2, c) for c in range(2, 41)} | {(r, 40) for r in range(2, 26)}
    )
    random_terrain = replace(random_terrain, costs=costs, blocked=frozenset(obstacles))

    passage = make_grid(
        "narrow-passage",
        25,
        45,
        (12, 4),
        (12, 40),
        blocked={(r, c) for r in range(25) for c in range(21, 24) if r != 12},
    )
    inflated = inflate_obstacles(passage, 1)
    disconnected = make_grid(
        "disconnected", 25, 45, (12, 4), (12, 40), blocked={(r, 22) for r in range(25)}
    )
    uniform = make_grid("uniform", 28, 48, (2, 2), (25, 45))
    descriptions = {
        "terrain-band": "A rectangular cost-4 band in cost-1 terrain; a longer geometric route can cost less.",
        "warehouse": "Procedural shelf obstacles, cross aisles, and sparse cost-2 rows.",
        "rooms": "Three walls with alternating doorways force geometric detours.",
        "seeded-terrain": "Seeded positive terrain and obstacles, with one known feasible corridor.",
        "uniform": "Obstacle-free cost-1 grid exposes the effect of deterministic tie breaking.",
        "narrow-passage": "A one-cell-wide opening is traversable by a point-cell model.",
        "narrow-passage-radius-1": "The same map with a 3 by 3 discrete footprint has no route.",
        "disconnected": "A full-height wall separates the start and goal components.",
    }
    return [
        (grid, descriptions[grid.name], 1 if grid is inflated else 0)
        for grid in [
            terrain,
            warehouse,
            rooms,
            random_terrain,
            uniform,
            passage,
            inflated,
            disconnected,
        ]
    ]


def to_record(grid, description="", footprint_radius=0):
    return {
        "name": grid.name,
        "description": description,
        "coordinate_order": "row,column",
        "footprint_radius": footprint_radius,
        "costs": grid.costs,
        "blocked": sorted(grid.blocked),
        "start": grid.start,
        "goal": grid.goal,
    }


def from_record(record):
    return Grid(
        tuple(tuple(row) for row in record["costs"]),
        frozenset(tuple(point) for point in record["blocked"]),
        tuple(record["start"]),
        tuple(record["goal"]),
        record["name"],
    )
