# The original R analysis (relic)

The lab's original circumnutation quantification, kept **for provenance only**. Nothing here runs
as part of the pipeline, and it is not maintained. The working implementation is
[`src/myutilities/quantify.py`](../../src/myutilities/quantify.py).

| File | What it was |
|---|---|
| `quantifieR.R` | The driver: sets mm-per-pixel, calls the loopers, then the aggregate plots. |
| `functions/quantification_functions.R` | The analysis: `root_quant`, `plot_curve`, `root_curl_trim`, `find_peaks`, `slideFunct`. |
| `functions/plotting_functions.R` | ggplot2 aggregates: amplitude by time and by arc length, period, arc length, elongation rate. |
| `functions/experiment.R` | An unused `setRefClass` sketch (a "movies" class). |
| `quantification_troubleshooting.R` | A scratch copy of the plot looper used for debugging. |
| `quantification_python_part.ipynb` | Made the timestamped output directory tree before the R ran. |
| `quantifieR.ipynb` | Notebook form of the driver. |

## What carried over
`quantify.py` keeps the method: a loess centerline through the root's path, the **signed shortest
distance** to it (scanning a few pixels of depth either way) as the amplitude, R's own peak finder
so the peak set stays comparable, the sliding-window curl trim, and the same quantities — period,
displacement, arc length, elongation rate.

## Verified against this R (2026-09-18)
Both were run on the same trace (`10_2.csv`, 301 points, 28.6 px/mm, 15-minute cycle):

| quantity | agreement |
|---|---|
| `x`, `y` (mm) | identical — correlation 1.0000, max difference 0.0000 |
| maxima / minima | 34 / 33 in both |
| median period | 2.250 h in both |
| amplitude | correlation 0.975, max difference 0.24 mm (R −0.51..0.60, port −0.50..0.64) — `lowess` vs `loess` |
| arc length | R 30.4 mm vs port 26.5 mm — the `|dx - dy|` formula below |

To re-run the R: `docker run --rm -v <repo>:/r:ro -v <csv dir>:/in:ro -v <out>:/out r-base:4.3.2 Rscript
<script>`, sourcing `quantification_functions.R` with its `library(ggplot2)` line dropped (only the
plotting file needs it) and calling `quant_looper("/in", 1, <stop>, 1/28.6, 100)`.

## What deliberately changed
- **Arc length is now a real Euclidean step.** The R computes
  `euc.dist(x_prior - predict(...), y_prior - y_r)`, and since `euc.dist(a, b) = sqrt(sum((a - b)^2))`
  with two scalars, that reduces to `|dx - dy|`, not `sqrt(dx² + dy²)`. So `arc_length` and
  `del_arc_length` from the R are not path length. (The to-do at the top of `quantifieR.R` — "verify
  arc_length calculations are reasonable... noisy between adjacent timepoints" — fits this.)
  **Any arc-length number from the R era should be re-derived rather than compared.**
- **Time comes from real frame numbers**, not `seq(start, stop) * 0.25`, which assumed a 15-minute
  cadence; the cadence now comes from the run manifest, and t = 0 is the recorded germination frame
  rather than a `10000` sentinel scanned out of the coordinates.
- **Scale comes from the run**, not a constant per camera (`mpp1 = 10/83.435`, `mpp2 = 10/250`).
- **Fixed on the way:** box and seed were parsed from the literal `"2461_1"` rather than the
  filename; `dist` was not reset between offsets, so an `NA` prediction reused the previous value;
  and the "root stopped growing" branch relied on an assignment inside a `tryCatch` that never fired.
- **Plots are not ported.** The pipeline writes tables meant to be loaded and analysed elsewhere.
