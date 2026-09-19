import os

import numpy as np
from matplotlib import pyplot as plt

"""
Per-root figures: tip displacement over time, and the root's path with its fitted centerline.

Displacement over time is the figure the work is read from (Rajanala, Taylor, McCaskey et al.,
PLOS ONE 2023; cf. PNAS 2018940118 fig. 1B): open circles joined by a line, symmetric y-axis in mm,
hours across. The path plot is the QC companion -- if the centerline does not sit down the middle of
the root, the displacement trace it produced is not trustworthy.

Colours are the two leading slots of the validated categorical palette (blue #2a78d6, orange
#eb6834) on a light surface; text stays in ink tokens, never the series colour. Deliberate
departures from the house mark specs, both for density: markers shrink below the 8px minimum when a
trace carries more than ~120 points (a 300-point trace at 8px is a solid band), and they are drawn
open -- white fill, coloured edge -- as in the reference figure, rather than filled. These are
static figures in a notebook, so there is no hover layer and no dark mode.
"""

BLUE, ORANGE = "#2a78d6", "#eb6834"      # categorical slots 1 and 2
INK, SECONDARY, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"

def _frame(ax):
    """Boxed axes, hairline grid, muted ticks: chrome recedes, the data is the only loud thing."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_color(AXIS); ax.spines[side].set_linewidth(1.0)
    ax.grid(True, color=GRID, linewidth=1.0, linestyle="-")
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=9, length=3)
    for label in ax.get_xticklabels() + ax.get_yticklabels(): label.set_color(SECONDARY)
    return ax

def _marker_size(n : int):
    return 5.0 if n <= 60 else (4.0 if n <= 120 else (3.0 if n <= 240 else 2.2))

def plot_displacement(data, ax=None, color : str = BLUE, symmetric : bool = True):
    """
    Tip displacement from the root's own centerline against hours since germination.

    One series, so no legend: the title says what is plotted. The extreme swing is labelled
    directly; every other value stays in the table rather than cluttering the trace.
    """
    if ax is None: _, ax = plt.subplots(figsize=(7.5, 3.2))
    t, a = data["growth_h"].values, data["amplitude_mm"].values
    ms = _marker_size(len(t))
    ax.axhline(0, color=AXIS, linewidth=1.0, zorder=1) # the centerline itself, i.e. zero displacement
    ax.plot(t, a, "-", color=color, linewidth=1.6, zorder=3)
    ax.plot(t, a, "o", markersize=ms, markerfacecolor="white", markeredgecolor=color,
            markeredgewidth=0.9, zorder=4)
    if len(a) and np.isfinite(a).any(): # label the extreme only
        i = int(np.nanargmax(np.abs(a)))
        ax.annotate(f"{a[i]:+.2f} mm", (t[i], a[i]), textcoords="offset points",
                    xytext=(6, 8 if a[i] >= 0 else -14), fontsize=9, color=SECONDARY)
        if symmetric:
            lim = max(np.nanmax(np.abs(a)) * 1.35, 0.1)
            ax.set_ylim(-lim, lim)
    ax.set_xlabel("hours since germination", fontsize=10, color=SECONDARY)
    ax.set_ylabel("tip displacement (mm)", fontsize=10, color=SECONDARY)
    return _frame(ax)

def plot_path(data, ax=None):
    """
    The root's path with the centerline the displacement was measured against (two series, so a
    legend). Depth increases downward, as in the image.
    """
    if ax is None: _, ax = plt.subplots(figsize=(3.2, 4.4))
    x, y, c = data["x_mm"].values, data["y_mm"].values, data["centerline_x_mm"].values
    ax.plot(x, y, "-", color=BLUE, linewidth=1.6, label="tip path", zorder=3)
    ax.plot(c, y, "-", color=ORANGE, linewidth=2.0, label="centerline", zorder=4)
    ax.invert_yaxis()
    ax.set_xlabel("across (mm)", fontsize=10, color=SECONDARY)
    ax.set_ylabel("depth (mm)", fontsize=10, color=SECONDARY)
    # A root drifts wherever it likes, so a fixed corner lands on the data: let matplotlib pick the
    # emptiest one, over a surface-coloured backing rather than a box, so it never sits on the trace.
    leg = ax.legend(fontsize=9, loc="best", frameon=True, facecolor=SURFACE, edgecolor="none", framealpha=0.85)
    for text in leg.get_texts(): text.set_color(SECONDARY)
    return _frame(ax)

def plot_root(data, save_dir : str = None, show : bool = True, dpi : int = 150):
    """Both figures for one root, side by side. Returns the saved path (or None)."""
    box, seed = data["box"].iloc[0], data["seed"].iloc[0]
    fig, (left, right) = plt.subplots(1, 2, figsize=(11.5, 3.6), gridspec_kw={"width_ratios": [3, 1]})
    fig.patch.set_facecolor(SURFACE)
    plot_displacement(data, ax=left)
    plot_path(data, ax=right)
    swings = int(data["is_max"].sum())
    period = data["period_h"].median()
    fig.suptitle(f"box {box} · seed {seed}", fontsize=12, color=INK, x=0.01, ha="left", y=1.02)
    left.set_title(f"{len(data)} frames · {data['growth_h'].max():.1f} h · {swings} swings · "
                   f"median period {period:.2f} h" if np.isfinite(period) else f"{len(data)} frames",
                   fontsize=9, color=MUTED, loc="left")
    right.set_title(f"grew {data['arc_length_mm'].max():.1f} mm", fontsize=9, color=MUTED, loc="left")
    fig.tight_layout()
    path = None
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        path = os.path.join(save_dir, f"{box}_{seed}.png")
        fig.savefig(path, dpi=dpi, facecolor=SURFACE, bbox_inches="tight")
    if show: plt.show()
    else: plt.close(fig)
    return path

def plot_all(tables, save_dir : str = "/app/results/plots", show : bool = True):
    """One figure per root, from the table quantify_dir() returns (or any frame with box/seed)."""
    if not len(tables): print("nothing to plot"); return []
    out = []
    for (box, seed), data in tables.groupby(["box", "seed"], sort=True):
        out.append(plot_root(data.reset_index(drop=True), save_dir=save_dir, show=show))
    if save_dir: print(f"{len(out)} figure(s) written to {save_dir}")
    return out
