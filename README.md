# Root Tracking

Downstream **root-tip tracking** for the Rhizodynamics / GROOT robot — the third stage after
[file-sorting](https://github.com/the-rhizodynamics-robot/file-sorting) produces sorted image
series / stabilized videos. It locates seeds, finds the germination frame, and traces each root
tip frame-by-frame, emitting per-seed **tip-coordinate CSVs** and **trace videos**.

Everything runs inside a published Docker container, so the only host dependency is a **Docker
engine** (on Windows: **WSL2 + Docker CE**, same as file-sorting). The two runner scripts are
thin launchers that pull `ghcr.io/the-rhizodynamics-robot/root-tracking-env:latest` and
`docker run` it with your folders bind-mounted.

## Tools

### `unspool.py` — video → image series
It's far more storage-efficient to keep experiments as MP4s than raw frames. This turns a
directory of videos back into image sequences the tracker can read.

```bash
python3 unspool.py --input_dir /path/to/videos/ --output_dir /path/to/unspooled/
```

> ⚠️ **Destructive:** unspooling **deletes each source video** after extracting it
> (`unspool_video(..., remove=True)`). Copy the videos first if you need to keep them.

If your input is **already an image series** (e.g. file-sorting's `finished_exp/<box>/` folders),
skip this step and point the tracker straight at it.

### `tracking.py` — seed + tip tracking in JupyterLab
Starts JupyterLab in the container, with `--data_dir` mounted at `/app/data` and `--results_dir`
at `/app/results`, on port 8888.

```bash
python3 tracking.py --data_dir /path/to/image_series_parent/ --results_dir /path/to/results/
```

`--data_dir` is the **parent** directory containing one **subfolder per box** (each subfolder is
one box's image series). Open the tokenized URL **printed in the terminal** (not the bare
`localhost:8888`), then run `code/track.ipynb`.

To test local changes to `src/` or `code/` without waiting for a CI rebuild, add **`--dev`**: it mounts
this checkout's `src/` and `code/` over the image's copies, so notebook edits also save straight into
the checkout.

## The tracking workflow (`code/track.ipynb`)

For each box you say `y` to, the notebook runs:

1. **Seed localization** — a RetinaNet model detects seeds inside a **search band** (fractions of the
   frame: `seed_search_x` 1/6–5/6, `seed_search_y` 0–0.75, which keeps the round objects at the bottom
   of the vessel out), and you are asked how many seeds the box holds. It then suppresses overlapping
   duplicate detections on the same seed (`seed_max_overlap`, default 0.3 intersection-over-union) and
   proposes **that many**, the best-scoring ones, rather than however many clear a confidence threshold — the model's
   confidence varies a lot between boxes (0.13 on a real seed in one box, 0.98 in the next), so the
   count you give decides. `seed_confidence` (default 0.05) is only a noise floor. `c` accepts, `m`
   switches to manual grid entry.
2. **Germination detection** — **manual** by design: an interactive bisection over the series
   (*"Is germination (b)efore / (a)fter / (h)ere / (r)estart / (x) none"*) pins the germination
   frame per seed. *(Automatic germination is an unfinished stub — see [Not yet implemented].)*
3. **Tip tracing** — PlantCV skeletonizes each frame and follows the tip from the germination
   frame; also **auto-writes a per-seed trace video**.
4. **Validation / save** — shows the final trace image; on `y` it saves the tip coordinates
   (`c` lets you mark a curl frame and truncate there).

Tunable per run in the notebook (species/lighting dependent): `germination_threshold_multiplier`,
`tip_trace_length`, `tip_trace_threshold_multiplier`, `tip_trace_bound_radius`.

**One image at a time.** Each step replaces the previous image in the cell's output, headed by a status
line such as `box 9 · seed 2 · germination search · frame 159/318`. Registration and tracking messages
are shown with the trace at validation.

**Memory.** Frames are read from disk on demand rather than loaded whole, so a 319-frame 3000×3000 box
needs a few hundred MB instead of ~2.9 GB. Per-seed registration runs in the background while you pick
germination frames; tracing and video writing then take one pass over the frames each, per box.

## Outputs (under `--results_dir`)

| Output | Path | When |
|---|---|---|
| Per-seed trace video | `stabilized_videos_single_seed/<box>_<seed>.mp4` | automatic, for every germinated seed |
| Tip coordinates | `tip_coordinates/<box>_<seed>.csv` | only after you confirm `y`/`c` at validation |
| Quantification | `quantification/<box>_<seed>.csv` | when you run `code/quantify.ipynb` |
| Archived experiments | `archive/` | when you run `util.archive()` (notebook cell) |

## Quantification (`code/quantify.ipynb`)

Run it after `track.ipynb`, in the same JupyterLab session. It turns each tip trace into a table —
one row per frame — of **displacement from the root's own centerline**, circumnutation **peaks and
period**, and **elongation** along the path (`arc_length_mm`, `del_arc_length_mm`), plus `x_mm`,
`y_mm` and `growth_h`. The tables are for loading and analysing elsewhere; no plots are produced.

```python
quantify.quantify_dir(px_per_mm=28.6, interval_min=15)   # College Station rig, 15-minute cycle
```

**`px_per_mm` is a property of the rig** (camera, lens, working distance), so it must match the
robot that took the images: 28.6 px/mm was measured on the College Station rig from the 76.2 mm box
pitch. It belongs in that robot's `config.toml` and from there in every run's `run_config.json`,
which the quantifier reads when it is present (along with `cycle_interval_min`); until capture
records it, pass it explicitly. A missing scale is an error, never a guess.

**Choosing `span`.** The centerline has to be smoother than the swing being measured. On synthetic
roots of known 1.00 mm amplitude, the **period is recovered exactly at every span**, but amplitude is
not: a slow swing (4 cycles over the trace) reads 0.15 mm at `span=0.1` — the centerline simply
follows the root — and 0.97 mm at 0.3, while fast swings (20 cycles) are fine anywhere. Spans of 0.2
and above overshoot by 10–15%. Start at 0.2 (0.5–0.6 when growth is slow, as the R did) and treat
amplitude as good to ~15%, period as solid.

Ported from the lab's original R analysis, kept in [`reference/r_analysis/`](reference/r_analysis/)
for provenance, and **checked against it**: identical x/y, identical peak counts (34/33) and median
period (2.250 h), amplitude correlated 0.975. Arc length deliberately differs — see that README, since
**R-era arc-length numbers are not path length** and should be re-derived.

The coordinate CSV is a JSON header line (box, seed, **germination frame**, curl frame, scale,
imaging interval) followed by `frame,x,y` rows, so a trace can be placed in real time. Coordinates
are pixels in the frame-0 reference, with per-seed jitter already removed.

> Traces saved before 2026-09-18 are in the old format — every `[x,y]` pair on a **single row**, no
> frame numbers — which `tipcsv.read_tip_csv()` still reads (treating time as frames since the trace
> started, since the germination frame went unrecorded).

## How the container is built & updated

`Dockerfile` builds `FROM ghcr.io/the-rhizodynamics-robot/file-sorting-env` (which carries OpenCV,
PlantCV, TensorFlow/RetinaNet, and the `SeedInference.h5` model) + JupyterLab + this repo's
`code/` and `src/`. CI (`.github/workflows/docker-publish.yml`) builds and pushes
`root-tracking-env:latest` to GHCR.

CI rebuilds on pushes to `main` that touch `Dockerfile`, `src/**`, `code/**`, or the workflow, so merging
a code change is enough — no `Dockerfile` bump needed. Only `main` builds; test a branch with
`tracking.py --dev`.

## Not yet implemented / un-ported

- **Automatic germination detection** — the auto path in `Seed.germination_detection()` is a
  commented-out stub ("was not reliable"). Germination is manual until it's built.
- **Visualization** — quantification is ported (see above), but the R's **plots are not**: no
  amplitude-by-time / by-arc-length figures, period or elongation-rate plots, and no grouping of
  boxes into treatments. The quantification tables are meant to be loaded and plotted elsewhere.
  (`max_intensity_projection` / `quantify_max_intensity_projection` remain empty stubs.)
