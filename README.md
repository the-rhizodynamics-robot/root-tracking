# Root Tracking

Downstream **root-tip tracking** for the Rhizodynamics / GROOT robot — the third stage after
[file-sorting](https://github.com/the-rhizodynamics-robot/file-sorting) produces sorted image
series / stabilized videos. It locates seeds, finds the germination frame, and traces each root
tip frame-by-frame, emitting per-seed **tip-coordinate CSVs** and **trace videos**.

Everything runs inside a published Docker container, so the only host dependency is a **Docker
engine** (on Windows: **WSL2 + Docker CE**, same as file-sorting). The two runner scripts are
thin launchers that pull `ghcr.io/the-rhizodynamics-robot/root-tracking-env:latest` and
`docker run` it with your folders bind-mounted.

## Two tools

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
| Archived experiments | `archive/` | when you run `util.archive()` (notebook cell) |

> The coordinate CSV is written as **all `[x,y]` pairs on a single row** (`writerow(tip_coords_pcv)`),
> not one row per frame — downstream analysis must parse that shape.

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
- **Downstream quantitative analysis + visualization** — the pipeline currently ends at raw tip
  coordinates + trace videos. There is **no** growth-rate / gravitropic-angle / length-over-time
  analysis or plotting here. Older **R analysis code was never ported** into this repo
  (`max_intensity_projection` / `quantify_max_intensity_projection` are empty stubs).
