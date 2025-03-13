# Root Tracking Project Guidelines

## Commands
- Run Jupyter: `docker run -it --rm -p 8888:8888 jupyterlab`
- Run tracking: `python tracking_runner.py`
- Start interactive notebook: `jupyter notebook notebooks/track.ipynb`

## Code Style
- **Imports**: Standard library → Third-party → Local (relative paths)
- **Formatting**: 4-space indentation, PEP8-like spacing
- **Types**: Add type annotations for function parameters
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Documentation**: Use docstrings for all functions and classes
- **Error handling**: Try/except with explicit error messages
- **Architecture**: Keep utilities in src/myutilities, domain logic separate

## Project Structure
- notebooks/: Interactive experiments and workflows
- src/: Core functionality and utilities
- src/myutilities/: Helper functions for common operations
- src/retnet/: Neural network components
- src/env_setup/: Environment configuration

## Key Concepts
- Box: Bounding box representation with transformation methods
- Image: Image processing and manipulation utilities
- PlantCV integration for plant phenotyping