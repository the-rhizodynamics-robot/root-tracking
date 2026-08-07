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

## The tracking workflow (`code/track.ipynb`)

For each box you say `y` to, the notebook runs:

1. **Seed localization** — a RetinaNet model auto-detects seeds and draws bounding boxes; you
   confirm the seed count (`c` to accept, `m` for manual grid entry).
2. **Germination detection** — **manual** by design: an interactive bisection over the series
   (*"Is germination (b)efore / (a)fter / (h)ere / (r)estart / (x) none"*) pins the germination
   frame per seed. *(Automatic germination is an unfinished stub — see [Not yet implemented].)*
3. **Tip tracing** — PlantCV skeletonizes each frame and follows the tip from the germination
   frame; also **auto-writes a per-seed trace video**.
4. **Validation / save** — shows the final trace image; on `y` it saves the tip coordinates
   (`c` lets you mark a curl frame and truncate there).

Tunable per run in the notebook (species/lighting dependent): `germination_threshold_multiplier`,
`tip_trace_length`, `tip_trace_threshold_multiplier`, `tip_trace_bound_radius`.

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

> ⚠️ **CI only rebuilds on changes to `Dockerfile` or the workflow** — *not* on `code/`/`src/`
> changes (which are baked into the image at build time). So **when you edit the notebook or
> `src/`, also bump the `Dockerfile`** (a trivial comment change is enough) so the published image
> actually updates. This is why the history has recurring "update docker image" commits.

## Not yet implemented / un-ported

- **Automatic germination detection** — the auto path in `Seed.germination_detection()` is a
  commented-out stub ("was not reliable"). Germination is manual until it's built.
- **Downstream quantitative analysis + visualization** — the pipeline currently ends at raw tip
  coordinates + trace videos. There is **no** growth-rate / gravitropic-angle / length-over-time
  analysis or plotting here. Older **R analysis code was never ported** into this repo
  (`max_intensity_projection` / `quantify_max_intensity_projection` are empty stubs).
