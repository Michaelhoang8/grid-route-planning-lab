"""Deterministic Dijkstra, A* and weighted A* on positive-cost four-neighbor grids."""

from dataclasses import dataclass, replace
import heapq
import math

Point = tuple[int, int]  # (row, column)
NEIGHBORS = ((-1, 0), (0, 1), (1, 0), (0, -1))  # up, right, down, left


@dataclass(frozen=True)
class Grid:
    costs: tuple[tuple[int, ...], ...]
    blocked: frozenset[Point]
    start: Point
    goal: Point
    name: str = "grid"

    def __post_init__(self):
        if not self.costs or not self.costs[0]:
            raise ValueError("The grid must be nonempty")
        if any(len(row) != len(self.costs[0]) for row in self.costs):
            raise ValueError("Terrain rows must have equal lengths")
        if any(
            type(cost) is not int or cost <= 0 for row in self.costs for cost in row
        ):
            raise ValueError("Every terrain cost must be a positive integer")
        if not isinstance(self.blocked, frozenset):
            raise ValueError("Blocked cells must be a frozenset")
        if not isinstance(self.costs, tuple) or any(
            not isinstance(row, tuple) for row in self.costs
        ):
            raise ValueError("Terrain costs must use immutable tuples")
        for point in (self.start, self.goal, *self.blocked):
            if not self.contains(point):
                raise ValueError(
                    "Cell coordinates must be integer pairs inside the grid"
                )

    @property
    def rows(self):
        return len(self.costs)

    @property
    def columns(self):
        return len(self.costs[0])

    def contains(self, point):
        return (
            isinstance(point, tuple)
            and len(point) == 2
            and all(type(value) is int for value in point)
            and 0 <= point[0] < self.rows
            and 0 <= point[1] < self.columns
        )

    def neighbors(self, point):
        row, column = point
        for dr, dc in NEIGHBORS:
            neighbor = row + dr, column + dc
            if self.contains(neighbor) and neighbor not in self.blocked:
                yield neighbor


@dataclass(frozen=True)
class Expansion:
    index: int
    cell: Point
    cost: int
    heuristic: int
    priority_numerator: int
    priority_denominator: int
    reopened: bool


@dataclass(frozen=True)
class SearchResult:
    status: str
    path: tuple[Point, ...]
    cost: int | None
    expanded: int
    unique_expanded: int
    reopens: int
    generated: int
    stale_pops: int
    trace: tuple[Expansion, ...]


@dataclass(frozen=True)
class _RouteNode:
    cell: Point
    parent: "_RouteNode | None"


def _minimum_cost(grid):
    return min(
        (
            cost
            for row, values in enumerate(grid.costs)
            for column, cost in enumerate(values)
            if (row, column) not in grid.blocked
        ),
        default=1,
    )


def manhattan_heuristic(grid, cell):
    """Admissible destination-cost lower bound for a legal grid cell."""
    if not grid.contains(cell):
        raise ValueError("Heuristic cell must be inside the grid")
    return _minimum_cost(grid) * (
        abs(cell[0] - grid.goal[0]) + abs(cell[1] - grid.goal[1])
    )


def inflate_obstacles(grid, radius):
    """Require an entire discrete square footprint to lie in free grid cells.

    radius r means offsets [-r, r] in each axis, including the center. A center
    is blocked if this footprint touches any blocked cell or leaves the map.
    This is an exact discrete footprint policy, not continuous collision proof.
    """
    if type(radius) is not int or radius < 0:
        raise ValueError("Footprint radius must be a nonnegative integer")
    blocked = set(grid.blocked)
    for row in range(grid.rows):
        for column in range(grid.columns):
            if (
                row < radius
                or column < radius
                or row + radius >= grid.rows
                or column + radius >= grid.columns
            ):
                blocked.add((row, column))
    for row, column in grid.blocked:
        for rr in range(max(0, row - radius), min(grid.rows, row + radius + 1)):
            for cc in range(
                max(0, column - radius), min(grid.columns, column + radius + 1)
            ):
                blocked.add((rr, cc))
    return replace(
        grid, blocked=frozenset(blocked), name=f"{grid.name}-radius-{radius}"
    )


def search(grid, algorithm="astar", weight=1.0):
    """Search with improving relaxations, stale-entry rejection and reopening.

    The first popped goal terminates the search. Dijkstra and A* return optimal
    cost. For weighted A*, weight >= 1 multiplies the admissible heuristic;
    reopening supports a returned-cost bound of weight * optimal cost.
    """
    if algorithm not in {"dijkstra", "astar", "weighted_astar"}:
        raise ValueError("Unknown search algorithm")
    if (
        isinstance(weight, bool)
        or not isinstance(weight, (int, float))
        or (isinstance(weight, float) and not math.isfinite(weight))
        or weight < 1
    ):
        raise ValueError("Weight must be finite and at least one")
    if algorithm != "weighted_astar" and weight != 1:
        raise ValueError("A weight other than one requires weighted_astar")
    if grid.start in grid.blocked or grid.goal in grid.blocked:
        return SearchResult("blocked_endpoint", (), None, 0, 0, 0, 0, 0, ())

    minimum = _minimum_cost(grid)
    # Scale all priorities by the same positive denominator. Integer arithmetic
    # preserves order even for large terrain costs or a nonintegral float weight.
    numerator, denominator = (
        weight.as_integer_ratio() if isinstance(weight, float) else (weight, 1)
    )
    if algorithm == "dijkstra":
        numerator = 0

    def heuristic(point):
        if algorithm == "dijkstra":
            return 0
        return minimum * (abs(point[0] - grid.goal[0]) + abs(point[1] - grid.goal[1]))

    start_h = heuristic(grid.start)
    # Priority, lower h, then insertion order. The cost snapshot detects stale
    # heap entries when an improved route was inserted after an earlier one.
    frontier = [(numerator * start_h, start_h, 0, 0, grid.start)]
    distances = {grid.start: 0}
    routes = {grid.start: _RouteNode(grid.start, None)}
    expanded_at = {}
    trace = []
    sequence = reopens = stale_pops = 0
    generated = 1
    while frontier:
        priority, h, _, current_cost, current = heapq.heappop(frontier)
        if distances[current] != current_cost:
            stale_pops += 1
            continue
        if current in expanded_at and current_cost >= expanded_at[current]:
            stale_pops += 1
            continue
        reopened = current in expanded_at
        reopens += int(reopened)
        expanded_at[current] = current_cost
        trace.append(
            Expansion(
                len(trace), current, current_cost, h, priority, denominator, reopened
            )
        )
        if current == grid.goal:
            path = []
            route = routes[current]
            while route is not None:
                path.append(route.cell)
                route = route.parent
            return SearchResult(
                "found",
                tuple(reversed(path)),
                current_cost,
                len(trace),
                len(expanded_at),
                reopens,
                generated,
                stale_pops,
                tuple(trace),
            )
        for neighbor in grid.neighbors(current):
            candidate = current_cost + grid.costs[neighbor[0]][neighbor[1]]
            if candidate < distances.get(neighbor, math.inf):
                distances[neighbor] = candidate
                # Keep a persistent route snapshot. A later reopening may
                # improve an ancestor without changing this candidate's g.
                routes[neighbor] = _RouteNode(neighbor, routes[current])
                sequence += 1
                generated += 1
                next_h = heuristic(neighbor)
                heapq.heappush(
                    frontier,
                    (
                        candidate * denominator + numerator * next_h,
                        next_h,
                        sequence,
                        candidate,
                        neighbor,
                    ),
                )
    return SearchResult(
        "unreachable",
        (),
        None,
        len(trace),
        len(expanded_at),
        reopens,
        generated,
        stale_pops,
        tuple(trace),
    )
