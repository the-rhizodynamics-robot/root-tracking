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
and the scale and cadence from the run manifest.

Two departures from the R, both deliberate (see reference/r_analysis/README.md):
  * arc length is a real Euclidean step; the R expression reduces to |dx - dy|.
  * time is measured from the germination frame, which the CSV now records, instead of from an
    assumed 15-minute cadence counted from the start of the run.

UNITS. With a scale (px_per_mm) the measurement columns are named `_mm`; without one they are named
`_px` and the numbers are raw pixels -- honest, where assuming a scale would silently produce wrong
millimetres. Likewise time is `_h` when the imaging interval is known and `_frames` when it is not.
Use column_units() rather than assuming either.
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

def column_units(data):
    """('mm' or 'px', 'h' or 'frames') for a quantified table, so callers need not guess."""
    return ("mm" if "amplitude_mm" in data.columns else "px",
            "h" if "growth_h" in data.columns else "frames")

def resolve_run_settings(px_per_mm=None, interval_min=None, data_dir : str = None,
                         results_dir : str = None, meta : dict = None, prompt : bool = True):
    """
    Settle the scale and cadence for a batch once, and remember what the operator types so the next
    run defaults to it.

    Order of precedence: explicit argument > the trace's own header > the run's run_config.json >
    the value remembered from last time > a prompt. The prompt may be skipped with Enter, in which
    case measurements stay in PIXELS (and time in frames) and the columns say so.

    px_per_mm is a property of the rig -- camera, lens, working distance -- so the remembered value
    is stored beside the data it describes (quantify_scale.json), not in the code. Its proper home
    is each robot's config.toml, from there every run_config.json; this store is the stand-in until
    capture records it.
    """
    notes = []
    meta = meta or {}
    remembered, store_path = tipcsv.read_scale_store(data_dir, results_dir)
    config = tipcsv.read_run_config(data_dir) if data_dir else {}
    cfg_scale, cfg_interval = tipcsv.scale_and_interval(config)

    def settle(name, explicit, from_meta, from_config, from_store, unit, example):
        if explicit: notes.append(f"{name}: {explicit} (given)"); return float(explicit)
        if from_meta: notes.append(f"{name}: {from_meta} (from the trace header)"); return float(from_meta)
        if from_config: notes.append(f"{name}: {from_config} (from run_config.json)"); return float(from_config)
        if not prompt:
            if from_store: notes.append(f"{name}: {from_store} (remembered)"); return float(from_store)
            return None
        default = f" [{from_store}]" if from_store else ""
        raw = input(f"{name} for this rig{default} ({unit}, e.g. {example}; Enter to skip): ").strip()
        if not raw:
            if from_store: notes.append(f"{name}: {from_store} (remembered)"); return float(from_store)
            notes.append(f"{name}: not given"); return None
        try: return float(raw)
        except ValueError:
            print(f"  '{raw}' is not a number -- skipping"); notes.append(f"{name}: not given"); return None

    scale = settle("px_per_mm", px_per_mm, meta.get("px_per_mm"), cfg_scale, remembered[0] if remembered else None,
                   "pixels per mm", "28.6")
    interval = settle("interval_min", interval_min, meta.get("interval_min"), cfg_interval,
                      remembered[1] if remembered else None, "minutes per imaging cycle", "15")

    if prompt and (scale or interval): # remember for next time, beside the data where possible
        for d in (data_dir, results_dir):
            if not d: continue
            try:
                notes.append(f"remembered in {tipcsv.write_scale_store(d, scale, interval)}"); break
            except OSError: continue # read-only mount: carry on, just do not remember
    if not scale: notes.append("NO SCALE: measurements stay in pixels (_px columns)")
    if not interval: notes.append("NO INTERVAL: time stays in frames (_frames columns)")
    return scale, interval, notes

def quantify_trace(frames, x, y, px_per_mm : float = None, interval_min : float = None, box=None,
                   seed=None, germination_frame : int = None, span : float = 0.2,
                   offsets=range(-4, 5), curl_trim : bool = True):
    """
    One root's trace -> a table, one row per frame.

    Columns: frame, time_<h|frames> (since the run started, when frame numbers are real),
    growth_<h|frames> (since germination), amplitude_<mm|px> (signed distance from the centerline),
    is_max/is_min, period_<h|frames>, x_/y_/centerline_x_<mm|px> (displacement from the first
    tracked point), arc_length_ and del_arc_length_<mm|px>, box, seed. Without px_per_mm the
    measurements are pixels; without interval_min time is frames.

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

    u = "mm" if px_per_mm else "px"     # no scale: stay in pixels rather than invent millimetres
    t = "h" if interval_min else "frames"
    mm = (1.0 / float(px_per_mm)) if px_per_mm else 1.0
    per_frame = (float(interval_min) / 60.0) if interval_min else 1.0

    predict = centerline(x, y, span)
    amplitude = distance_from_centerline(x, y, predict, offsets) * mm

    cx = predict(y) # the centerline itself is the path length reference; the tip's own wobble is the amplitude
    centerline_scaled = (cx - x[0]) * mm # kept as a column so plots and QC need not refit it
    step = np.hypot(np.diff(cx), np.diff(y)) * mm # NOT the R's expression, which reduces to |dx - dy|
    del_arc = np.concatenate([[0.0], step])
    arc = np.nancumsum(del_arc)

    growth = (frames - frames[0]) * per_frame
    data = pd.DataFrame({
        "frame": frames,
        f"time_{t}": frames * per_frame if germination_frame is not None else np.full(len(frames), np.nan),
        f"growth_{t}": growth,
        f"amplitude_{u}": amplitude,
        "is_max": False, "is_min": False, f"period_{t}": np.nan,
        f"x_{u}": (x - x[0]) * mm,
        f"y_{u}": (y - y[0]) * mm,
        f"centerline_x_{u}": centerline_scaled,
        f"arc_length_{u}": arc,
        f"del_arc_length_{u}": del_arc,
        "box": box, "seed": seed,
    })
    finite = np.where(np.isfinite(amplitude), amplitude, 0.0) # peak finding needs a gap-free signal
    maxima, minima = find_peaks_r(finite), find_peaks_r(-finite)
    data.loc[maxima, "is_max"] = True
    data.loc[minima, "is_min"] = True
    for idx in (maxima, minima): # period = time since the previous extreme of the same kind
        if len(idx) > 1: data.loc[idx[1:], f"period_{t}"] = np.diff(growth[idx])
    return data

def quantify_file(path : str, px_per_mm : float = None, interval_min : float = None, **kwargs):
    """Quantify one tip-coordinate CSV (either format). Explicit arguments beat the file's metadata."""
    trace = tipcsv.read_tip_csv(path)
    meta = trace["meta"]
    scale = px_per_mm if px_per_mm is not None else meta.get("px_per_mm")
    interval = interval_min if interval_min is not None else meta.get("interval_min")
    return quantify_trace(trace["frames"], trace["x"], trace["y"], scale, interval, box=meta.get("box"),
                          seed=meta.get("seed"), germination_frame=meta.get("germination_frame"), **kwargs)

def quantify_dir(tip_dir : str = "/app/results/tip_coordinates", out_dir : str = "/app/results/quantification",
                 px_per_mm : float = None, interval_min : float = None, data_dir : str = "/app/data",
                 prompt : bool = True, **kwargs):
    """
    Quantify every tip-coordinate CSV in a directory, writing one table per seed and returning them
    concatenated, so a session can go straight from tracking to a loadable dataset.

    The scale and cadence are settled once for the batch (asked for if unknown, then remembered) --
    see resolve_run_settings. Each output CSV opens with a `# units:` line recording what was used.
    """
    os.makedirs(out_dir, exist_ok=True)
    scale, interval, notes = resolve_run_settings(px_per_mm, interval_min, data_dir=data_dir,
                                                  results_dir=os.path.dirname(out_dir), prompt=prompt)
    for note in notes: print(f"  {note}")
    units = f"{'mm' if scale else 'PIXELS'}, time in {'hours' if interval else 'FRAMES'}"
    print(f"  -> measurements in {units}\n")

    out = []
    for name in sorted(f for f in os.listdir(tip_dir) if f.lower().endswith(".csv")):
        try:
            data = quantify_file(os.path.join(tip_dir, name), scale, interval, **kwargs)
        except Exception as e: # one unusable trace must not stop the batch
            print(f"{name}: SKIPPED -- {e}")
            continue
        u, t = column_units(data)
        with open(os.path.join(out_dir, name), "w", newline="") as f:
            f.write(f"# units: {u}" + (f" (px_per_mm {scale})" if scale else " (no px_per_mm given)")
                    + f"; time in {t}" + (f" ({interval} min per frame)" if interval else "") + "\n")
            data.to_csv(f, index=False)
        print(f"{name}: {len(data)} frames, {int(data.is_max.sum())} maxima, "
              f"amplitude {np.nanmin(data['amplitude_' + u]):.2f}..{np.nanmax(data['amplitude_' + u]):.2f} {u}, "
              f"grew {np.nanmax(data['arc_length_' + u]):.1f} {u}")
        out.append(data)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()
