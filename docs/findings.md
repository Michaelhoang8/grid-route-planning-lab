# Findings

## Optimal and weighted route costs

Dijkstra and A* agree on the minimum cost in all six reachable published maps. The separate independent test suite also checks them against Bellman–Ford on 100 seeded small grids.

Weighted A* with weight 3 matches the reference cost on four reachable maps. It returns cost 104 instead of 53 on the terrain-band map, a ratio of 1.962. The shorter geometric route takes 41 moves instead of the optimal route's 53, but enters more cost-4 terrain. This is why minimizing path length and minimizing terrain cost are different objectives.

On seeded terrain, weighted A* returns cost 76 instead of 71, a ratio of 1.070. Both observed ratios remain below the declared factor-3 bound. These selected results do not estimate a typical suboptimality ratio on arbitrary maps.

## Search work

On the uniform map, A* expands 67 states compared with Dijkstra's 1,332 while returning the same cost 66. The consistent Manhattan heuristic and preference for smaller `h` direct it along one optimal route. This result is sensitive to the model and deterministic tie rule; it is not a universal expansion claim.

The rooms map exposes reopening: weighted A* records 775 expansion events over 624 distinct cells, including 151 reopens and 94 stale pops. It still returns cost 114, matching the reference. Treating the expanded set as permanently closed would describe a different algorithm than the one tested here.

On the terrain-band map, weighted A* expands 172 states versus A*'s 190, despite nearly doubling cost. The measured medians are about 0.763 milliseconds for both. A slightly smaller expansion count does not automatically provide a useful timing or route-quality advantage.

On the warehouse map, weighted A* expands 75 states versus A*'s 998 and Dijkstra's 1,516, all at cost 79. This contrasts with the terrain-band result and demonstrates why each configuration needs case-by-case measurement.

## Footprint feasibility

The original narrow passage has a cost-36 route under the single-cell model. After radius-1 square inflation, a 3 × 3 footprint cannot traverse it. All searches report unreachable after exploring 437 legal centers in the start component. This is a feasibility change caused by a specified discrete footprint, not evidence about an actual robot's swept motion.

The separate disconnected map has 550 reachable cells from the start. All three searches exhaust that component. A heuristic cannot create a path across the full-height obstacle wall.

## Runtime limits

The figures use five warmed calls per configuration, preserving every sample. The implementation captures traces and route snapshots during search, so the measurements include those inspection costs. Background machine state is not controlled, and the observed range is not a confidence interval. The study supports the reported behaviors on these maps, not a universal recommendation of one search method.
