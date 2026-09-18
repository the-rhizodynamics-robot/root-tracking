import csv
import json
import os
import re

"""
Read and write the per-seed tip-coordinate CSV, and locate a run's run_config.json.

Format 2 (written here) is a JSON header comment followed by a frame,x,y table:

    # {"format": "tip-coordinates/2", "box": "10", "seed": 2, "germination_frame": 159, ...}
    frame,x,y
    159,1761,1256

Format 1 -- every [x y] pair on ONE row, no frame numbers -- is still read, because every root
tracked before this change is in it. It recorded neither the germination frame nor the scale, so
coordinates could not be placed in real time or converted to millimetres; the R analysis worked
around the missing germination frame with a 10000 sentinel in the leading rows.
"""

FORMAT = "tip-coordinates/2"
RUN_CONFIG_NAME = "run_config.json"
SENTINELS = (10000, 100000) # R-era markers for "no data here" / "curl starts here"
_INT = re.compile(r"-?\d+")

def read_run_config(start_dir : str, levels : int = 3):
    """
    Find and read the capture manifest (run_config.json) for a box: look in the box folder, then
    its parents. robot-control writes it into every run folder from 2026-09-14 (`zhu-lab`); runs
    before that have none, and file-sorting does not yet copy it into per-box output, so a missing
    manifest is normal and not an error.
    """
    d = os.path.abspath(start_dir) if start_dir else None
    for _ in range(levels):
        if not d: break
        path = os.path.join(d, RUN_CONFIG_NAME)
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f: return json.load(f)
            except ValueError as e: # a corrupt manifest should not take the run down
                print(f"warning: {path} is not readable JSON ({e})"); return {}
        parent = os.path.dirname(d)
        if parent == d: break
        d = parent
    return {}

def scale_and_interval(run_config : dict):
    """(px_per_mm, interval_min) from a manifest, either None when absent.

    px_per_mm is NOT written by robot-control yet -- it belongs in config.toml per robot and from
    there in every run_config.json, since it is a property of that rig's camera, lens and working
    distance. Until then the quantifier takes it as a parameter.
    """
    return run_config.get("px_per_mm"), run_config.get("cycle_interval_min")

def write_tip_csv(path : str, coords, box, seed_number : int, germination_frame : int,
                  curl_frame : int = None, source_dir : str = None):
    """
    Write one seed's tip trace: a JSON header line, then frame,x,y rows.

    coords are frame-0-referenced pixel coordinates starting AT the germination frame (that is what
    tip_trace_pcv produces), so frame numbers are germination_frame + i and the trace can be placed
    in real time. Truncates at curl_frame when the operator marked one.
    """
    rows = [(int(germination_frame + i), int(c[0]), int(c[1])) for i, c in enumerate(coords)]
    if curl_frame is not None: rows = [r for r in rows if r[0] < curl_frame]
    px_per_mm, interval_min = scale_and_interval(read_run_config(source_dir) if source_dir else {})
    meta = {"format": FORMAT, "box": str(box), "seed": int(seed_number),
            "germination_frame": int(germination_frame), "curl_frame": curl_frame,
            "frames": len(rows), "px_per_mm": px_per_mm, "interval_min": interval_min,
            "coordinates": "pixels, frame-0 referenced (per-seed jitter removed)"}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        f.write("# " + json.dumps(meta) + "\n")
        wr = csv.writer(f)
        wr.writerow(("frame", "x", "y"))
        wr.writerows(rows)
    return meta

def read_tip_csv(path : str):
    """
    Read either format, returning {"meta": dict, "frames": [int], "x": [int], "y": [int]}.

    For format 1 the frame numbers are unknown, so they run 0..n-1 and meta["germination_frame"] is
    None: downstream code must treat time as "frames since the trace started", not since germination.
    """
    with open(path, newline="") as f: text = f.read()
    lines = [l for l in text.splitlines() if l.strip()]
    if lines and lines[0].lstrip().startswith("#"):
        meta = json.loads(lines[0].lstrip()[1:])
        rows = [l.split(",") for l in lines[2:]] # line 1 is the header comment, line 2 the column names
        frames = [int(r[0]) for r in rows]; xs = [int(r[1]) for r in rows]; ys = [int(r[2]) for r in rows]
        return {"meta": meta, "frames": frames, "x": xs, "y": ys}

    pairs = [tuple(int(v) for v in _INT.findall(cell)) for cell in next(csv.reader(lines)) if _INT.search(cell)]
    pairs = [p for p in pairs if len(p) >= 2]
    first = next((i for i, p in enumerate(pairs) if p[0] not in SENTINELS), 0) # R: which(coords[,1] != 10000)[[1]]
    pairs = [p for p in pairs[first:] if p[0] not in SENTINELS]
    name = os.path.splitext(os.path.basename(path))[0]
    box, _, seed = name.partition("_")
    meta = {"format": "tip-coordinates/1", "box": box, "seed": int(seed) if seed.isdigit() else None,
            "germination_frame": None, "curl_frame": None, "frames": len(pairs),
            "px_per_mm": None, "interval_min": None,
            "coordinates": "pixels, frame-0 referenced; frame numbers unknown (legacy format)"}
    return {"meta": meta, "frames": list(range(len(pairs))), "x": [p[0] for p in pairs], "y": [p[1] for p in pairs]}
