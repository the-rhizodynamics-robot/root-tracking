# Root Tracking

A tool for tracking root growth and development in plant phenotyping applications. There are two runner scripts to perform two funcationalities.

`unspool.py`: It is significantly more memory efficient to save experimental data as MP4s then as raw images.  This script takes a video and generates an image series that can be analyzed by the tracking pipeline (below).

`tracking.py`: This script starts a Jupyterlab instance running in a docker container. You can track root tips from it.

## Usage

The unspool command:
```bash
python3 unspool.py --input_dir /path/to/videos/directory/ --output_dir /path/to/results/directory/
```

Example:
```bash
python3 unspool.py --input_dir /home/iwtwb8/data/videos/ --output_dir /home/iwtwb8/data/unspooled/
```

The tracking command:

```bash
python3 tracking.py --data_dir /path/to/data/directory/ --results_dir /path/to/results/directory/
```

Example:
```bash
python3 tracking.py --data_dir /home/iwtwb8/data/unspooled/pnas.2018940118.sm01/ --results_dir /home/iwtwb8/
```

This will start a jupyter notebook running from a docker container. You can access the notebook from your browser by copying the link. The tracking notebook is located at `code/track.ipynb`.