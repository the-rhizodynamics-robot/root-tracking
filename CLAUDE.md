# Root Tracking Project Guidelines

## Commands
- Unspool videos → image series: `python3 unspool.py --input_dir <videos> --output_dir <out>`
- Run tracking (starts JupyterLab in Docker): `python3 tracking.py --data_dir <image_series_parent> --results_dir <results>`
- The tracking notebook lives at `code/track.ipynb` (open it from the JupyterLab URL printed in the terminal).
- Both runners pull `ghcr.io/the-rhizodynamics-robot/root-tracking-env:latest` and `docker run` it.
- Rebuild the image: it's built from `Dockerfile` by `.github/workflows/docker-publish.yml`, which
  triggers on pushes to `main` touching `Dockerfile`, `src/**`, `code/**`, or the workflow itself.
  Merging a `src/`/`code/` change is enough — no manual `Dockerfile` bump. To force a rebuild with
  no file change, run the workflow from the Actions tab (`workflow_dispatch`).
- Only `main` builds. Feature-branch pushes never touch `:latest`, so test those with
  `python3 tracking.py --dev ...`, which mounts this checkout's `src/` and `code/` over the image's copies.
- Seed detection proposes the **N best-scoring** detections, N being the count the user enters, inside a
  search band given as **fractions** of the frame (`search_x`/`search_y`), after suppressing overlapping
  duplicates on one seed (`max_overlap`, IoU). Never reintroduce a confidence
  threshold as a seed/not-seed test: scores vary hugely per box (0.13 vs 0.98 on equally clear seeds).
- Tip traces are written by `src/myutilities/tipcsv.py` (JSON header + `frame,x,y`); the old one-row
  format is still readable. `src/myutilities/quantify.py` turns a trace into per-frame measurements —
  a port of the R in `reference/r_analysis/`, which is a relic and must not be wired into anything.
  `px_per_mm` is rig-specific: resolved by `quantify.resolve_run_settings()` (argument → trace header
  → run_config.json → remembered `quantify_scale.json` → prompt), never hardcoded. With no scale the
  columns are `_px` and time is `_frames`; never fabricate millimetres from an assumed scale.
- The germination view is WIDER than the seed box (`view_margin`/`view_margin_bottom`) so the root's
  emergence point is visible. Its crop→frame conversion (`germination_x = locs[i][1] + vx1`) must use
  the VIEW origin, not `self.x1`: an origin mismatch offsets every later tracking crop silently.
- `src/myutilities/plots.py` draws the per-root figures (displacement over time; path + centerline).
  Colours are the validated categorical slots (blue, orange) on a light surface, and text wears ink
  tokens, never the series colour. Always render and LOOK at a figure before calling it done.
- Frames are read on demand (`src/myutilities/frames.py`), never loaded whole: a 3000×3000 box is ~2.9 GB.
  Notebook images go through `util.show()` (one image at a time); don't add bare `plt.show()` calls.

## Code Style
- **Imports**: Standard library → Third-party → Local (relative paths)
- **Formatting**: 4-space indentation, PEP8-like spacing
- **Types**: Add type annotations for function parameters
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Documentation**: Use docstrings for all functions and classes
- **Error handling**: Try/except with explicit error messages
- **Architecture**: Keep utilities in src/myutilities, domain logic separate

## Project Structure
- code/: the tracking notebook (`track.ipynb`) + `unspool_core.py` (baked into the image)
- src/: Core functionality and utilities
- src/myutilities/: Helper functions for common operations
- src/retnet/: Neural network components
- src/env_setup/: Environment configuration

## Key Concepts
- Box: Bounding box representation with transformation methods
- Image: Image processing and manipulation utilities
- PlantCV integration for plant phenotyping

## Things to keep in mind
- Be succinct. Too many lines of code is confusing. Put comments at the end of lines of code to reduce the number of lines used.