"""Render preserved search evidence as maps, figures and an offline report."""

import csv
import html
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gridroute.fixtures import from_record

DATA = ROOT / "results/published"
FIGURES = ROOT / "docs/figures"
FIGURES.mkdir(parents=True, exist_ok=True)
PAPER = "#f5f1e8"
INK = "#253445"
COLORS = {"dijkstra": "#6a648d", "astar": "#16766b", "weighted_astar": "#bd522c"}
LABELS = {
    "dijkstra": "Dijkstra",
    "astar": "A*",
    "weighted_astar": "Weighted A* · w = 3",
}
CMAP = LinearSegmentedColormap.from_list(
    "terrain", ["#f5edda", "#e0bd8d", "#b7774a", "#815038"]
)
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "figure.facecolor": PAPER,
        "axes.facecolor": PAPER,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#c9c4b8",
        "text.color": INK,
        "axes.labelcolor": INK,
        "xtick.color": "#6f776f",
        "ytick.color": "#6f776f",
        "savefig.dpi": 170,
    }
)
with (DATA / "summary.csv").open() as stream:
    ROWS = list(csv.DictReader(stream))
ENV = json.loads((DATA / "environment.json").read_text())


def load(name, algorithm):
    grid = from_record(json.loads((DATA / "maps" / f"{name}.json").read_text()))
    route = json.loads((DATA / "routes" / f"{name}__{algorithm}.json").read_text())
    with (DATA / "traces" / f"{name}__{algorithm}.csv").open() as stream:
        trace = list(csv.DictReader(stream))
    return grid, route, trace


def metric(name, algorithm):
    return next(
        row for row in ROWS if row["map"] == name and row["algorithm"] == algorithm
    )


def draw_map(ax, grid, route, trace, algorithm, extra_blocked=()):
    ax.imshow(grid.costs, cmap=CMAP, vmin=1, vmax=8, interpolation="nearest")
    obstacles = np.zeros((grid.rows, grid.columns, 4))
    for r, c in grid.blocked:
        obstacles[r, c] = matplotlib.colors.to_rgba(INK)
    ax.imshow(obstacles, interpolation="nearest")
    expanded = np.zeros_like(obstacles)
    for event in trace:
        r, c = int(event["row"]), int(event["column"])
        expanded[r, c] = matplotlib.colors.to_rgba(COLORS[algorithm], 0.27)
    ax.imshow(expanded, interpolation="nearest")
    if extra_blocked:
        inflated = np.zeros_like(obstacles)
        for r, c in extra_blocked:
            inflated[r, c] = matplotlib.colors.to_rgba("#b87d47")
        ax.imshow(inflated, interpolation="nearest")
    path = route["path"]
    if path:
        xx = [point[1] for point in path]
        yy = [point[0] for point in path]
        ax.plot(xx, yy, color=PAPER, lw=5, zorder=4, solid_capstyle="round")
        ax.plot(
            xx, yy, color=COLORS[algorithm], lw=2.5, zorder=5, solid_capstyle="round"
        )
    reopened = [
        (int(event["column"]), int(event["row"]))
        for event in trace
        if int(event["reopened"])
    ]
    if reopened:
        xx, yy = zip(*set(reopened))
        ax.scatter(xx, yy, s=8, facecolors="none", edgecolors="#ab3974", linewidths=0.7)
    for point, label, color in [
        (grid.start, "S", INK),
        (grid.goal, "G", COLORS[algorithm]),
    ]:
        ax.scatter(
            [point[1]],
            [point[0]],
            s=115,
            c=[color],
            edgecolors=PAPER,
            linewidths=1.5,
            zorder=6,
        )
        ax.text(
            point[1],
            point[0],
            label,
            color="white",
            fontsize=6.5,
            ha="center",
            va="center",
            weight="bold",
            zorder=7,
        )
    ax.set_xlim(-0.5, grid.columns - 0.5)
    ax.set_ylim(grid.rows - 0.5, -0.5)
    ax.set_xticks(range(0, grid.columns, 10))
    ax.set_yticks(range(0, grid.rows, 10))
    ax.tick_params(length=0, labelsize=8)
    ax.set_xlabel("column", fontsize=8)
    ax.set_ylabel("row", fontsize=8)
    ax.set_title(
        LABELS[algorithm]
        + f"\nCost {route['cost'] if route['cost'] is not None else '—'} · {route['expanded']:,} expansions",
        loc="left",
        fontsize=11,
        pad=12,
    )


def save(fig, name):
    fig.tight_layout(pad=1.5)
    for suffix in ["png", "svg"]:
        fig.savefig(FIGURES / f"{name}.{suffix}", bbox_inches="tight")
    plt.close(fig)


for name in [
    "terrain-band",
    "warehouse",
    "rooms",
    "seeded-terrain",
    "uniform",
    "narrow-passage",
    "disconnected",
]:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    for ax, algorithm in zip(axes, LABELS):
        draw_map(ax, *load(name, algorithm), algorithm)
    save(fig, f"map_{name}")

fig, axes = plt.subplots(1, 2, figsize=(12, 4.7))
base, base_route, base_trace = load("narrow-passage", "astar")
inflated, inflated_route, inflated_trace = load("narrow-passage-radius-1", "astar")
draw_map(axes[0], base, base_route, base_trace, "astar")
draw_map(
    axes[1],
    inflated,
    inflated_route,
    inflated_trace,
    "astar",
    inflated.blocked - base.blocked,
)
axes[0].set_title(
    "Radius 0 · one-cell footprint\nReachable · cost 36", loc="left", fontsize=11
)
axes[1].set_title(
    "Radius 1 · 3 × 3 footprint\nUnreachable · 437 reachable centers explored",
    loc="left",
    fontsize=11,
)
save(fig, "clearance")

names = [row["map"] for row in ROWS if row["algorithm"] == "dijkstra"]
short = {
    "terrain-band": "Terrain band",
    "warehouse": "Warehouse",
    "rooms": "Rooms",
    "seeded-terrain": "Seeded terrain",
    "uniform": "Uniform",
    "narrow-passage": "Narrow passage",
    "narrow-passage-radius-1": "Passage · radius 1",
    "disconnected": "Disconnected",
}
fig, axes = plt.subplots(1, 2, figsize=(13.4, 5.4))
positions = np.arange(len(names))
for algorithm, offset in [("dijkstra", -0.23), ("astar", 0), ("weighted_astar", 0.23)]:
    expansions = [int(metric(name, algorithm)["expanded"]) for name in names]
    medians = [float(metric(name, algorithm)["median_ns"]) / 1e6 for name in names]
    mins = [float(metric(name, algorithm)["min_ns"]) / 1e6 for name in names]
    maxs = [float(metric(name, algorithm)["max_ns"]) / 1e6 for name in names]
    axes[0].barh(
        positions + offset,
        expansions,
        height=0.22,
        color=COLORS[algorithm],
        label=LABELS[algorithm],
    )
    axes[1].barh(positions + offset, medians, height=0.22, color=COLORS[algorithm])
    axes[1].errorbar(
        medians,
        positions + offset,
        xerr=[np.array(medians) - mins, np.array(maxs) - medians],
        fmt="none",
        ecolor="#4a514c",
        elinewidth=0.7,
        capsize=1.5,
    )
for ax in axes:
    ax.set_yticks(positions, [short[name] for name in names])
    ax.invert_yaxis()
    ax.spines["left"].set_visible(False)
    ax.tick_params(length=0)
axes[0].set_xlabel("Expansion events · includes reopened cells")
axes[1].set_xlabel("Milliseconds per call · median and observed range")
axes[0].legend(frameon=False, fontsize=8, loc="lower right")
save(fig, "work_and_runtime")

terrain_a = metric("terrain-band", "astar")
terrain_w = metric("terrain-band", "weighted_astar")
table = "".join(
    (
        f"<tr><td>{short[name]}</td><td>{metric(name,'dijkstra')['cost'] or 'Unreachable'}</td><td>{metric(name,'astar')['cost'] or '—'}</td><td>{metric(name,'weighted_astar')['cost'] or '—'}</td><td>{float(metric(name,'weighted_astar')['cost_ratio']):.3f}×</td></tr>"
        if metric(name, "weighted_astar")["cost_ratio"]
        else f"<tr><td>{short[name]}</td><td>Unreachable</td><td>—</td><td>—</td><td>—</td></tr>"
    )
    for name in names
)
report = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Grid route planning | Measured search study</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:{PAPER};color:{INK};font:17px/1.6 Arial,sans-serif}}header{{border-bottom:1px solid #cac5b8;padding:18px 4vw;display:flex;justify-content:space-between;font:12px Consolas,monospace}}main{{max-width:1420px;margin:auto;padding:0 46px}}section{{padding:46px 0;border-bottom:1px solid #cac5b8}}h1{{font-size:62px;line-height:1.06;letter-spacing:-.04em;margin:18px 0}}h2{{font-size:34px;line-height:1.15;letter-spacing:-.025em;margin:12px 0 18px}}h3{{font-size:17px}}p{{max-width:980px}}.label{{font:12px Consolas,monospace;color:#8b5635;letter-spacing:.1em}}.intro{{display:grid;grid-template-columns:1.2fr 1fr;gap:70px;align-items:center}}.lead{{font-size:20px}}.legend{{display:flex;gap:25px;font:13px Consolas,monospace;flex-wrap:wrap;margin:20px 0}}.dot{{width:11px;height:11px;display:inline-block;margin-right:8px}}img{{display:block;width:100%;height:auto;margin:20px 0}}video{{display:block;width:100%;background:{INK};margin:20px 0;border:1px solid #cac5b8}}.note{{border-left:3px solid #b87d47;padding:12px 18px;background:#eae4d7;font-size:15px}}.split{{display:grid;grid-template-columns:1fr 1fr;gap:45px}}table{{width:100%;border-collapse:collapse;font-size:14px;margin:24px 0}}td,th{{text-align:left;border-bottom:1px solid #ccc6b8;padding:11px 14px}}th{{font:12px Consolas,monospace;color:#6f776f}}pre{{background:{INK};color:#f2e7d0;padding:22px;font:14px/1.7 Consolas,monospace;overflow:auto}}figcaption,footer{{font-size:13px;color:#6f776f}}a{{color:#16766b}}footer{{padding:28px 0}}.stats{{display:flex;gap:45px}}.stats strong{{font:32px Consolas,monospace;display:block}}.stats span{{font-size:12px;color:#6f776f}}@media(max-width:800px){{main{{padding:0 18px}}.intro,.split{{display:block}}h1{{font-size:42px}}.stats{{gap:20px}}table{{font-size:14px}}}}
.table-scroll{{max-width:100%;overflow-x:auto;overscroll-behavior-inline:contain}}.table-scroll:focus-visible{{outline:2px solid currentColor;outline-offset:4px}}.table-scroll:first-child{{min-width:0}}.split>* , .grid>*{{min-width:0}}.table-scroll table{{min-width:650px}}@media(max-width:800px){{header{{flex-wrap:wrap;gap:10px}}.stats,.metrics{{flex-wrap:wrap;row-gap:18px}}.bits{{flex-wrap:wrap}}pre{{overflow-wrap:anywhere}}}}</style><header><span>ALGORITHMS / DISCRETE PATH PLANNING</span><span>SIMULATED GRIDS · {ENV['started_utc'][:10]}</span></header><main>
<section id="overview"><div class="intro"><div><div class="label">DIJKSTRA / A* / WEIGHTED A*</div><h1>Grid route planning</h1></div><p class="lead">Three source-built graph searches on positive-cost terrain. Each route is measured against the Dijkstra reference and preserved with its map and expansion trace.</p></div><div class="stats"><div><strong>8</strong><span>procedural maps</span></div><div><strong>24</strong><span>preserved routes / attempts</span></div><div><strong>120</strong><span>timed search calls</span></div></div><div class="legend"><span><i class="dot" style="background:#6a648d"></i>Dijkstra</span><span><i class="dot" style="background:#16766b"></i>A*</span><span><i class="dot" style="background:#bd522c"></i>Weighted A*</span><span>Filled cells: expanded · line: returned route</span></div><img src="figures/map_terrain-band.png" alt="Three searches on the terrain band map; weighted A star returns a costlier straight route"><p class="note">Terrain-band result: A* returns cost {terrain_a['cost']}; weighted A* returns {terrain_w['cost']} ({float(terrain_w['cost_ratio']):.3f}× optimal). Its {terrain_w['expanded']} expansions are only slightly fewer than A*'s {terrain_a['expanded']}. Fewer expansions do not establish a better route.</p></section>
<section id="search"><div class="label">01 / SEARCH BEHAVIOR</div><h2>Search traces and reopened cells</h2><p>The rooms map forces repeated detours. Weighted A* expands 775 times across 624 distinct cells, including 151 reopened expansions. Small magenta rings mark cells that were expanded again after a lower cost was found.</p><img src="figures/map_rooms.png" alt="Rooms map with three path searches and reopened weighted A star cells"><div class="split"><p>All searches reject stale heap entries and relax only strict cost improvements. Equal priorities prefer lower remaining heuristic, then insertion order. Neighbors are considered up, right, down, left.</p><p>A* uses minimum free-cell terrain cost × Manhattan distance. Weighted A* uses g + 3h and permits reopening. Under this finite positive-cost model its returned cost is bounded by three times optimal; it is not guaranteed to reduce runtime.</p></div></section>
<section id="clearance"><div class="label">02 / FOOTPRINT MODEL</div><h2>Obstacle inflation and map boundaries</h2><p>A radius-r footprint contains every offset in the square [−r, r] × [−r, r]. A center is excluded if any footprint cell is blocked or outside the map. Brown cells show the additional exclusions at radius 1.</p><img src="figures/clearance.png" alt="A narrow passage succeeds with a single-cell footprint and is disconnected with a three by three footprint"><p class="note">The same one-cell passage changes from reachable to unreachable. This is an exact discrete square-footprint rule, with center-cell terrain costs. It is not a continuous collision certificate, a robot dynamics model or evidence from a physical robot.</p></section>
<section id="comparison"><div class="label">03 / MEASURED RESULTS</div><h2>Route cost and search work</h2><div class="table-scroll" role="region" aria-label="Route costs (scroll horizontally)" tabindex="0"><table class="responsive-data"><tr><th>MAP</th><th>DIJKSTRA COST</th><th>A* COST</th><th>WEIGHTED COST</th><th>WEIGHTED / OPTIMAL</th></tr>{table}</table></div><img src="figures/work_and_runtime.png" alt="Expansion events and measured runtime for eight maps and three search methods"><figcaption>Five warmed repetitions per configuration; whiskers show minimum and maximum, not confidence intervals. Timing includes heap operations, route snapshots and trace construction. Unreachable maps have no cost ratio.</figcaption><p>All six reachable cases give equal costs for Dijkstra and A*. Weighted A* raises cost on two cases and matches optimal cost on four. No claim is made that weighting always saves work; the unreachable cases exhaust the same reachable component.</p></section>
<section id="replay"><div class="label">04 / TRACE REPLAY</div><h2>Expansion sequence</h2><p>The animation replays the stored terrain-band CSV traces. Each panel uses its own normalized expansion progress; it is not a wall-clock race. Final routes appear after the trace completes.</p><video controls muted loop preload="metadata" poster="figures/map_terrain-band.png"><source src="media/search-expansion.mp4" type="video/mp4"></video><p><a href="../results/published/traces/terrain-band__astar.csv">A* trace CSV</a> · <a href="../results/published/routes/terrain-band__astar.json">A* path coordinates</a> · <a href="../results/published/maps/terrain-band.json">Input map JSON</a></p></section>
<section id="validation"><div class="label">05 / VALIDATION</div><h2>Independent references and reproduction</h2><div class="split"><div><h3>Correctness checks</h3><p>12 tests include an independent Bellman–Ford reference on 100 seeded grids, five search settings per grid, heuristic admissibility and consistency checks, 140 enumerated footprint comparisons, blocked endpoints, unreachable cases, stale heap entries and exact priorities beyond floating-point range.</p><p><a href="../tests">Tests</a> · <a href="algorithms.md">Algorithms and bound assumptions</a></p></div><div><h3>Preserved evidence</h3><p>Maps in JSON and CSV, route coordinates, complete expansion traces, raw timings and SHA-256 manifests are committed. Source hashes normalize line endings to LF. Fresh runs use separate directories.</p><p><a href="../results/published/summary.csv">Summary CSV</a> · <a href="../results/published/measurements.csv">Raw timings</a> · <a href="../results/published/environment.json">Run environment</a> · <a href="methodology.md">Methodology</a> · <a href="findings.md">Findings</a></p></div></div><pre>python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/run_study.py --out outputs/my-run</pre></section>
<footer>AI-assisted engineering study · Procedural simulated grids · No sensor, SLAM or physical-robot data.</footer></main></html>"""
(ROOT / "docs/report.html").write_text(report, encoding="utf-8", newline="\n")
(ROOT / "docs/figures/environment.json").write_text(
    json.dumps(
        {
            "numpy": np.__version__,
            "matplotlib": matplotlib.__version__,
            "source": "results/published",
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
    newline="\n",
)
print(ROOT / "docs/report.html")
