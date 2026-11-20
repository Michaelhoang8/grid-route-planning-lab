# Algorithms and assumptions

## Graph model

A cell is identified by `(row, column)`. A legal state is an unblocked cell inside a finite rectangular grid. From a state, moves go only up, right, down or left. Diagonal motion is absent. Every terrain entry is a strictly positive Python integer, including entries at blocked cells that are never traversed.

An edge from `u` to neighboring `v` costs `terrain[v]`. The start has initial cost zero, so its terrain is not charged; the goal's terrain is charged when entered. The same geometric path reversed can have a different cost because the endpoints differ. For a start equal to the goal, a free cell produces a one-point route of cost zero. A blocked start or goal produces `blocked_endpoint`; a disconnected free goal produces `unreachable`.

## Dijkstra and A*

Dijkstra orders the heap by accumulated cost `g`. A* orders it by `g + h`, where:

```text
c_min = minimum terrain cost over every unblocked cell
h(v) = c_min * (abs(v.row - goal.row) + abs(v.column - goal.column))
```

Any four-neighbor route requires at least that Manhattan number of moves, each costing at least `c_min`. Thus `h` is admissible. Across one move the Manhattan distance decreases by at most one, and the edge cost is at least `c_min`; therefore `h(u) <= cost(u,v) + h(v)`, establishing consistency for this model.

The first nonstale popped goal terminates each search. Dijkstra and A* return minimum-cost routes under these assumptions. The foundational A* formulation is described by Hart, Nilsson and Raphael in [“A Formal Basis for the Heuristic Determination of Minimum Cost Paths” (1968)](https://ai.stanford.edu/~nilsson/OnlinePubs-Nils/PublishedPapers/astar.pdf). The implementation and model-specific argument here are independently inspectable; no universal expansion-optimality claim is made.

## Weighted A* and its scope

Weighted A* orders by `g + w*h` for a finite numeric weight `w >= 1`. The published study uses `w = 3`. The unweighted `h` remains admissible, while `w*h` generally does not. The implementation reopens a previously expanded state whenever a strictly better `g` is discovered.

For a reachable goal in this finite positive-cost graph, let `C*` be the optimal cost. Before termination an optimal path has a frontier state `n` with its optimal prefix cost `g*(n)`; reopening preserves this property after later improvements. Admissibility gives:

```text
g*(n) + w*h(n) <= w * (g*(n) + h(n)) <= w*C*
```

The popped goal has `h = 0` and no larger priority than that frontier state, so its returned cost is at most `w*C*`. This bounds route cost only. It does not bound the number of expansions or wall-clock time relative to A*, and it does not apply to a physical route outside the declared graph model. General bounded-suboptimal heuristic-search context is provided by Thayer, Ruml and Bitton, [“Fast and Loose in Bounded Suboptimal Heuristic Search”](https://www.cs.unh.edu/~ruml/papers/stair-08-george.pdf).

The tests compare returned costs to an independent Bellman–Ford oracle, including `w = 1`, `1.5` and `3`. Published comparisons use the actual per-map Dijkstra cost, not the loose theoretical bound as a substitute for measurement.

## Exact priority ordering

Input weights may be integers or finite floats. A float's exact binary rational value is recovered using `as_integer_ratio()`. For weight `a/b`, the heap stores `b*g + a*h` and compares integers. A shared positive denominator preserves priority order without rounding terrain costs to float. The trace records both the numerator and denominator. A weight other than 1 is accepted only with `weighted_astar`.

Equal priorities prefer smaller unweighted `h`, then insertion order. Dijkstra has `h = 0` and therefore uses insertion order for equal costs. Neighbor order is up, right, down, left. These policies can select different but equal-cost routes and affect expansion counts.

## Improvements, stale entries and routes

The heap may hold older candidates after an improvement is inserted. Each entry snapshots its `g`; on pop, a mismatch with the state's current best distance makes it stale. A state expanded earlier at a higher `g` may be reopened. Relaxation uses strict improvement only.

Each improving candidate owns an immutable linked route snapshot. This avoids reconstructing a route through parent pointers that may have changed after a later reopening. The final route's destination-terrain sum is checked against its stored `g`.

Counters have precise meanings:

| Counter | Meaning |
| --- | --- |
| `expanded` | Nonstale expansion events, including the terminating goal |
| `unique_expanded` | Distinct cells expanded at least once |
| `reopens` | Expansion events at cells previously expanded with a higher cost |
| `generated` | Heap insertions, including the initial state and improving candidates |
| `stale_pops` | Discarded entries actually popped before termination; entries left in the heap are not counted |

`reopens = expanded - unique_expanded`. Expansion traces preserve repeats rather than silently collapsing them into one visited cell.

## Discrete footprint and inflation

For nonnegative integer radius `r`, a center cell represents an axis-aligned square footprint containing every offset `(dr, dc)` with `-r <= dr, dc <= r`. A valid center requires every footprint cell to be inside the map and unblocked. This excludes:

- Every center within Chebyshev distance `r` of an original blocked cell, including diagonal offsets.
- Every center within `r` cells of the map edge, because part of its footprint would leave the map.

The implementation's inflation is exact for this discrete square-footprint policy. It is conservative relative to any chosen discrete footprint contained in that square, because it may reject additional centers. Terrain cost still samples the center cell; it is not summed over the footprint. Inflation is applied to an original map once, not cumulatively to previously inflated fixtures.

This does not certify continuous motion between cells, swept geometry, orientation, circular robot clearance, steering dynamics or uncertain localization. There is no conversion to real units or claim of physical collision safety. Tests enumerate the complete footprint independently to verify the stated grid rule.
