"""Replay actual expansion CSVs; progress is normalized per search, not runtime."""

import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import matplotlib.font_manager
from PIL import Image, ImageDraw, ImageFont, __version__ as pillow_version

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results/published"
OUT = ROOT / "docs/media"
OUT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT, FPS = 1440, 620, 20
MOVING_FRAMES, HOLD_FRAMES = 200, 40
PAPER, INK = "#f5f1e8", "#253445"
ALGORITHMS = [
    ("dijkstra", "Dijkstra", "#6a648d"),
    ("astar", "A*", "#16766b"),
    ("weighted_astar", "Weighted A* / w = 3", "#bd522c"),
]
font_path = matplotlib.font_manager.findfont("DejaVu Sans")
fonts = {size: ImageFont.truetype(font_path, size) for size in [14, 17, 20, 28, 42]}
grid = json.loads((DATA / "maps/terrain-band.json").read_text())
traces = {}
routes = {}
for algorithm, _, _ in ALGORITHMS:
    with (DATA / "traces" / f"terrain-band__{algorithm}.csv").open() as stream:
        traces[algorithm] = list(csv.DictReader(stream))
    routes[algorithm] = json.loads(
        (DATA / "routes" / f"terrain-band__{algorithm}.json").read_text()
    )

ffmpeg = shutil.which("ffmpeg")
if not ffmpeg:
    raise RuntimeError("ffmpeg must be available on PATH to encode the MP4")
command = [
    ffmpeg,
    "-y",
    "-loglevel",
    "error",
    "-f",
    "rawvideo",
    "-pixel_format",
    "rgb24",
    "-video_size",
    f"{WIDTH}x{HEIGHT}",
    "-framerate",
    str(FPS),
    "-i",
    "-",
    "-an",
    "-c:v",
    "libx264",
    "-crf",
    "22",
    "-preset",
    "medium",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    str(OUT / "search-expansion.mp4"),
]
process = subprocess.Popen(command, stdin=subprocess.PIPE)
try:
    for frame in range(MOVING_FRAMES + HOLD_FRAMES):
        progress = min(1, frame / (MOVING_FRAMES - 1))
        image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
        draw = ImageDraw.Draw(image)
        draw.text((40, 24), "Grid route planning", font=fonts[42], fill=INK)
        draw.text(
            (42, 83),
            "Terrain-band map / preserved expansion sequences",
            font=fonts[20],
            fill=INK,
        )
        draw.line((40, 125, 1400, 125), fill="#c9c4b8", width=1)
        for index, (algorithm, label, color) in enumerate(ALGORITHMS):
            x0 = 40 + index * 465
            y0 = 208
            cell = 9
            route = routes[algorithm]
            trace = traces[algorithm]
            count = int(progress * len(trace))
            draw.text((x0, 148), label, font=fonts[28], fill=color)
            for r, row in enumerate(grid["costs"]):
                for c, cost in enumerate(row):
                    fill = "#eee5d3" if cost == 1 else "#d7ac82"
                    draw.rectangle(
                        (
                            x0 + c * cell,
                            y0 + r * cell,
                            x0 + (c + 1) * cell - 1,
                            y0 + (r + 1) * cell - 1,
                        ),
                        fill=fill,
                    )
            for event in trace[:count]:
                r, c = int(event["row"]), int(event["column"])
                # Expanded cells remain visible as a colored center, preserving
                # a thin terrain border so the cost band can still be read.
                draw.rectangle(
                    (
                        x0 + c * cell + 1,
                        y0 + r * cell + 1,
                        x0 + (c + 1) * cell - 2,
                        y0 + (r + 1) * cell - 2,
                    ),
                    fill=color,
                )
            if progress == 1:
                points = [
                    (x0 + c * cell + cell // 2, y0 + r * cell + cell // 2)
                    for r, c in route["path"]
                ]
                draw.line(points, fill="white", width=7, joint="curve")
                draw.line(points, fill=color, width=3, joint="curve")
            for point, letter in [(grid["start"], "S"), (grid["goal"], "G")]:
                r, c = point
                x = x0 + c * cell + 4
                y = y0 + r * cell + 4
                draw.ellipse(
                    (x - 11, y - 11, x + 11, y + 11), fill=INK, outline=PAPER, width=2
                )
                draw.text((x - 5, y - 8), letter, font=fonts[14], fill="white")
            draw.text(
                (x0, 452),
                f"Expansions {count:,} / {len(trace):,}",
                font=fonts[20],
                fill=INK,
            )
            draw.text(
                (x0, 487),
                (
                    f"Returned route cost {route['cost']}"
                    if progress == 1
                    else "Route shown after final expansion"
                ),
                font=fonts[17],
                fill=INK,
            )
            draw.rectangle((x0, 526, x0 + 432, 531), fill="#d8d0c0")
            if progress:
                draw.rectangle((x0, 526, x0 + round(432 * progress), 531), fill=color)
        draw.text(
            (42, 574),
            "Each panel advances through its own trace at normalized progress. This is not a runtime race.",
            font=fonts[17],
            fill="#68716c",
        )
        process.stdin.write(image.tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode the trace replay")
except BaseException:
    process.kill()
    process.wait()
    raise

source_files = [
    DATA / "maps/terrain-band.json",
    *[
        DATA / "traces" / f"terrain-band__{algorithm}.csv"
        for algorithm, _, _ in ALGORITHMS
    ],
]
metadata = {
    "frames": MOVING_FRAMES + HOLD_FRAMES,
    "fps": FPS,
    "seconds": (MOVING_FRAMES + HOLD_FRAMES) / FPS,
    "width": WIDTH,
    "height": HEIGHT,
    "progress": "Each algorithm's own expansion count is normalized independently; not a wall-clock race",
    "source_sha256": {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source_files
    },
    "pillow": pillow_version,
    "ffmpeg": subprocess.check_output([ffmpeg, "-version"], text=True).splitlines()[0],
}
(OUT / "animation.json").write_text(
    json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n"
)
print(OUT / "search-expansion.mp4")
