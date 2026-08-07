# Root Tracking Project Guidelines

## Commands
- Unspool videos → image series: `python3 unspool.py --input_dir <videos> --output_dir <out>`
- Run tracking (starts JupyterLab in Docker): `python3 tracking.py --data_dir <image_series_parent> --results_dir <results>`
- The tracking notebook lives at `code/track.ipynb` (open it from the JupyterLab URL printed in the terminal).
- Both runners pull `ghcr.io/the-rhizodynamics-robot/root-tracking-env:latest` and `docker run` it.
- Rebuild the image: it's built from `Dockerfile` by `.github/workflows/docker-publish.yml`, which
  only triggers on `Dockerfile`/workflow changes — so bump the `Dockerfile` when you change `code/`/`src/`.

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