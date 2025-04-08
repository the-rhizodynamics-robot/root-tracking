# Root Tracking

A tool for tracking root growth and development in plant phenotyping applications.

## Usage

The main tracking command:

```bash
python3 tracking.py --data_dir /path/to/data/directory/ --results_dir /path/to/results/directory/
```

Example:
```bash
python3 tracking.py --data_dir /home/iwtwb8/data/unspooled/pnas.2018940118.sm01/ --results_dir /home/iwtwb8/
```

This will start a jupyter notebook running from a docker container. You can access the notebook from your browser by copying the link. The tracking notebook is located at `code/track.ipynb`.