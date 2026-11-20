# Experimental methodology

## Inputs

Eight maps are procedurally created in `src/gridroute/fixtures.py`. They include a terrain band, shelf obstacles, alternating doorways, seeded terrain and obstacles, a uniform grid, a narrow passage, its radius-1 inflation and a disconnected map. All are synthetic. No map comes from a sensor, survey, person, workplace, simulator vendor or public robotics dataset.

Seed `20261120` controls the generated terrain and obstacles. Other maps use explicit geometric construction. The seeded map clears a known top/right corridor to guarantee at least one feasible route. It is therefore not an unbiased random-obstacle benchmark. The fixtures are selected to exercise behaviors and are not a representative sample of planning tasks.

Each map is saved as JSON containing its costs, blocked coordinates, endpoints and footprint radius, and as a CSV containing one row per cell. Coordinate order is always `(row, column)`; rendered x coordinates are columns.

## Methods and timing

The three configurations are Dijkstra, A*, and weighted A* with weight 3. The same search implementation supplies the common heap, relaxation, route and trace machinery; the priority rule changes. The Dijkstra result is the per-case cost reference. An independent Bellman–Ford implementation tests the solvers on separate small grids.

For each map, one untimed call warms each configuration and produces its deterministic preserved route and trace. Five timed repetitions follow. The order of the three configurations is shuffled each repetition with independent order seed `18139`.

`time.perf_counter_ns()` measures the complete in-memory `search()` call, including minimum-terrain computation, heap operations, immutable route snapshots and expansion trace construction. Map generation, file I/O, result equality assertions and graphics are outside the timed region. Each timed result must exactly match its untimed result, including trace sequence and counters.

The run contains `8 × 3 × 5 = 120` raw elapsed values. Summaries report the median, minimum and maximum without removing samples. Plot whiskers are observed ranges, not confidence intervals. There is no process isolation, CPU affinity, garbage-collection control or background-load control. The timings measure this instrumented Python implementation on one environment, not a bare algorithm or embedded robot controller. CI performs a fresh two-repetition smoke study with no performance thresholds.

## Route and cost comparisons

Cost includes every entered cell after the start. Geometric path length is separately reported as the number of edges. The cost ratio is `returned cost / Dijkstra cost`, only when the reference cost is positive and reachable. Unreachable cases have empty cost and ratio fields; they are not assigned zero cost. A zero-cost start-equals-goal case is covered by tests, not the timing fixtures.

The published weight is fixed before running the experiment. No weight sweep or parameter tuning is claimed. Bounds use the assumptions in [algorithms.md](algorithms.md); measured ratios use actual computed reference costs. Reopened expansions count as work. A lower count does not establish lower route cost or a guaranteed runtime improvement.

## Preserved artifacts

`results/published/` contains:

| Path | Evidence |
| --- | --- |
| `maps/*.json` | Complete grid model and provenance description |
| `maps/*.csv` | Flattened cost and obstacle cells |
| `routes/*.json` | Path coordinates, status and search counters |
| `traces/*.csv` | Every expansion, exact priority, `g`, `h` and reopening flag |
| `measurements.csv` | All raw timings and operation order |
| `summary.csv` | Costs, ratios, counts and timing summaries |
| `environment.json` | Actual UTC run times, Python/OS/architecture, seeds and source hashes |
| `manifest.json` | Exact byte size and SHA-256 for every other experiment artifact |

Source hashes cover the core, fixture generator and study runner as they existed before the measured calls, normalizing CRLF and CR to LF. Artifact hashes use exact file bytes. All generated text uses UTF-8/LF, and Git attributes preserve LF on checkout. The evidence test verifies source and artifact hashes, reconstructs the grids, reruns the search, compares full trace events and path coordinates, and reconciles counts and timing aggregates.

The default fresh output is `outputs/latest/`; the runner refuses any nonempty destination. Reproductions do not overwrite the committed run. Timing bytes will differ between runs, while deterministic paths, counts and procedural map bytes should agree for the recorded source and supported runtime.

## Figures and replay

Figure generation reads the preserved JSON/CSV artifacts. Terrain is shown as a warm color scale, obstacles in dark ink, expanded cells with a method-colored tint, routes as outlined lines, and reopened cells as magenta rings. Colors are illustrative; numerical terrain is available in the source maps. Map panels use the same terrain range of 1–8.

The MP4 animation replays the saved terrain-band expansion sequences. Each search independently advances through a normalized fraction of its trace over ten seconds, followed by a two-second hold. It is not a speed comparison. The final returned path appears only after that trace completes. `docs/media/animation.json` records frame count, frame rate, dimensions, input trace hashes and actual Pillow/ffmpeg versions.

Renderer dependencies are NumPy `2.3.5`, Matplotlib `3.11.2` and Pillow `13.0.0`. The algorithm and measurement code need none of them. The MP4 additionally uses an installed ffmpeg/libx264 encoder. No generated map image is presented as a photograph or physical demonstration.

## Limits

The project does not model dynamics, unknown obstacles, time dependence, sensing, SLAM, localization error, multi-agent conflicts, continuous steering or real-world units. It uses a small selected fixture set and a simple heuristic. Improvements such as bidirectional search, hierarchical methods, dynamic replanning and alternate heuristics are outside this study. The work was developed with AI assistance.
