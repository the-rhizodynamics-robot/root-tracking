import os

import numpy as np
import pandas as pd
from statsmodels.nonparametric.smoothers_lowess import lowess

from src.myutilities import tipcsv

"""
Quantify a tracked root tip: displacement from its own centerline, circumnutation peaks and
period, and elongation along the path.

Ported from the lab's R analysis (kept in reference/r_analysis/ for provenance):
quantification_functions.R's root_quant / plot_curve / root_curl_trim / find_peaks. The method is
unchanged -- a loess centerline, the signed shortest distance to it, R's peak finder -- while the
inputs it used to guess are now read from the trace: real frame numbers, the germination frame,
and the scale from the run manifest.

Two departures from the R, both deliberate (see reference/r_analysis/README.md):
  * arc length is a real Euclidean step; the R expression reduces to |dx - dy|.
  * time is measured from the germination frame, which the CSV now records, instead of from an
    assumed 15-minute cadence counted from the start of the run.
"""

def centerline(x, y, span : float = 0.2):
    """
    Smooth path of the root, as x (across) predicted from y (depth) -- R: loess(BX ~ BY, span).

    Returns a function of depth. Outside the fitted range it gives NaN, matching R's predict()
    returning NA there, which the distance scan below skips.
    """
    fit = lowess(np.asarray(x, dtype=float), np.asarray(y, dtype=float), frac=span, return_sorted=True)
    ys, xs = fit[:, 0], fit[:, 1]
    return lambda q: np.interp(q, ys, xs, left=np.nan, right=np.nan)

def distance_from_centerline(x, y, predict, offsets=range(-4, 5)):
    """
    Signed shortest distance from each point to the centerline, in pixels.

    Straight across (x - centerline(y)) overstates the distance wherever the root runs at an angle,
    so the R scans a few pixels of depth either way and keeps the shortest, preserving the sign of
    the straight-across offset. That sign is what makes this a swing rather than a magnitude.
    """
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        best = x[i] - predict(y[i])
        if np.isnan(best): continue
        sign = 1.0 if best >= 0 else -1.0
        for d in offsets:
            px = predict(y[i] + d)
            if np.isnan(px): continue
            dist = float(np.hypot(x[i] - px, d))
            if dist < abs(best): best = sign * dist
        out[i] = best
    return out

def find_peaks_r(x, m : int = 3):
    """
    Indices of local maxima: a sample greater than or equal to every sample within m either side.

    Ported from the R (stas g's find_peaks) rather than swapped for scipy.signal.find_peaks, so the
    peak set -- and therefore the period -- stays comparable with previously published numbers.
    """
    x = np.asarray(x, dtype=float)
    peaks = []
    for p in range(1, len(x) - 1):
        if not (x[p] > x[p - 1] and x[p] >= x[p + 1]): continue # a rising-then-falling turn
        lo, hi = max(p - m, 0), min(p + m + 1, len(x))
        if np.all(x[lo:p] <= x[p]) and np.all(x[p + 1:hi] <= x[p]): peaks.append(p)
    return np.array(peaks, dtype=int)

def trim_curl(x, y, window : int = 10, back : int = 5):
    """
    Number of leading points to keep, cutting the tail where the root curls back on itself.

    R's root_curl_trim: distance from the first point, smoothed over a sliding window; the window
    with the greatest distance is where the tip stops advancing, and a few points before it are
    dropped as well. A heuristic, kept as-is.
    """
    d = np.hypot(np.asarray(x, dtype=float) - x[0], np.asarray(y, dtype=float) - y[0])
    if len(d) <= window + back: return len(d)
    means = np.convolve(d, np.ones(window + 1) / (window + 1), mode="valid")
    return max(int(np.argmax(means)) - back + 1, 2)

def quantify_trace(frames, x, y, px_per_mm : float, interval_min : float, box=None, seed=None,
                   germination_frame : int = None, span : float = 0.2, offsets=range(-4, 5),
                   curl_trim : bool = True):
    """
    One root's trace -> a table, one row per frame.

    Columns: frame, time_h (since the run started, when frame numbers are real), growth_h (since
    germination), amplitude_mm (signed distance from the centerline), is_max/is_min, period_h,
    x_mm/y_mm (displacement from the first tracked point), arc_length_mm and del_arc_length_mm
    (distance along the centerline, cumulative and per frame), box, seed.

    `span` matters: the centerline must be smoother than the swing being measured. On synthetic roots
    of known 1.00 mm amplitude the period comes back exact at any span, but the amplitude reads
    0.15 mm at span 0.1 for a slow swing (the centerline follows the root) against 0.97 mm at 0.3,
    and overshoots 10-15% at 0.2 and above. Period is solid; treat amplitude as good to ~15%.
    """
    frames = np.asarray(frames, dtype=int); x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    if curl_trim:
        keep = trim_curl(x, y)
        frames, x, y = frames[:keep], x[:keep], y[:keep]
    if len(frames) < 3: raise ValueError(f"only {len(frames)} usable points in the trace")

    mm = 1.0 / float(px_per_mm)
    predict = centerline(x, y, span)
    amplitude = distance_from_centerline(x, y, predict, offsets) * mm

    cx = predict(y) # the centerline itself is the path length reference; the tip's own wobble is the amplitude
    step = np.hypot(np.diff(cx), np.diff(y)) * mm # NOT the R's expression, which reduces to |dx - dy|
    del_arc = np.concatenate([[0.0], step])
    arc = np.nancumsum(del_arc)

    hours = interval_min / 60.0
    growth_h = (frames - frames[0]) * hours
    data = pd.DataFrame({
        "frame": frames,
        "time_h": frames * hours if germination_frame is not None else np.full(len(frames), np.nan),
        "growth_h": growth_h,
        "amplitude_mm": amplitude,
        "is_max": False, "is_min": False, "period_h": np.nan,
        "x_mm": (x - x[0]) * mm,
        "y_mm": (y - y[0]) * mm,
        "arc_length_mm": arc,
        "del_arc_length_mm": del_arc,
        "box": box, "seed": seed,
    })
    finite = np.where(np.isfinite(amplitude), amplitude, 0.0) # peak finding needs a gap-free signal
    maxima, minima = find_peaks_r(finite), find_peaks_r(-finite)
    data.loc[maxima, "is_max"] = True
    data.loc[minima, "is_min"] = True
    for idx in (maxima, minima): # period = time since the previous extreme of the same kind
        if len(idx) > 1: data.loc[idx[1:], "period_h"] = np.diff(growth_h[idx])
    return data

def quantify_file(path : str, px_per_mm : float = None, interval_min : float = None, **kwargs):
    """Quantify one tip-coordinate CSV (either format). Explicit arguments beat the file's metadata."""
    trace = tipcsv.read_tip_csv(path)
    meta = trace["meta"]
    scale = px_per_mm if px_per_mm is not None else meta.get("px_per_mm")
    interval = interval_min if interval_min is not None else meta.get("interval_min")
    if not scale: raise ValueError(
        f"{os.path.basename(path)}: no px_per_mm. It is a property of the rig (camera, lens, working "
        f"distance): pass px_per_mm=..., or record it in the run's run_config.json.")
    if not interval: raise ValueError(
        f"{os.path.basename(path)}: no interval_min. Pass interval_min=..., or record cycle_interval_min "
        f"in the run's run_config.json.")
    return quantify_trace(trace["frames"], trace["x"], trace["y"], scale, interval, box=meta.get("box"),
                          seed=meta.get("seed"), germination_frame=meta.get("germination_frame"), **kwargs)

def quantify_dir(tip_dir : str = "/app/results/tip_coordinates", out_dir : str = "/app/results/quantification",
                 px_per_mm : float = None, interval_min : float = None, **kwargs):
    """
    Quantify every tip-coordinate CSV in a directory, writing one table per seed and returning them
    concatenated, so a session can go straight from tracking to a loadable dataset.
    """
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for name in sorted(f for f in os.listdir(tip_dir) if f.lower().endswith(".csv")):
        try:
            data = quantify_file(os.path.join(tip_dir, name), px_per_mm, interval_min, **kwargs)
        except Exception as e: # one unusable trace must not stop the batch
            print(f"{name}: SKIPPED -- {e}")
            continue
        data.to_csv(os.path.join(out_dir, name), index=False)
        print(f"{name}: {len(data)} frames, {int(data.is_max.sum())} maxima, "
              f"amplitude {np.nanmin(data.amplitude_mm):.2f}..{np.nanmax(data.amplitude_mm):.2f} mm, "
              f"grew {np.nanmax(data.arc_length_mm):.1f} mm")
        out.append(data)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()
