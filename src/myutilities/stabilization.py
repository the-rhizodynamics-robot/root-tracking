import json
import os

from src.myutilities import qr_stabilize

"""
Per-frame shifts that put a box's frames on its QR-stabilized position before anything else runs.

file-sorting writes stabilization.json beside each finished box's frames: the QR label's offset per
frame, keyed by filename, and the rig's parallax factor (label -> seed plane). Shifting every frame
back by offset * parallax removes the gantry jitter -- and follows a nudged box -- so seed detection,
germination and tracing all see the seed where they expect it; register_to_seed then only removes the
few px left. A box without the file (finished before 2026-10-14, or unspooled from video) is measured
here with the same code, and the result is saved beside the frames for next time.
"""

def frame_shifts(box_dir : str, names : list, log=print):
    """(shifts, frame_space): shifts = [(dx, dy)] per name to move each frame BACK by, or None when
    the box can't be stabilized (no usable label); frame_space describes it for the tip CSV."""
    path = os.path.join(box_dir, qr_stabilize.OFFSETS_NAME)
    rec, source = None, None
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f: rec = json.load(f)
            source = "stabilization.json"
        except ValueError as e: log(f"warning: {path} is not readable JSON ({e}); measuring instead")
        if rec and rec.get("format") != qr_stabilize.OFFSETS_FORMAT:
            log(f"warning: {path} has format {rec.get('format')!r}; measuring instead"); rec = None
        if rec and any(n not in rec["frames"] for n in names): # frames on disk don't match what was measured
            missing = [n for n in names if n not in rec["frames"]]
            log(f"warning: {path} lacks {len(missing)} of {len(names)} frames (e.g. {missing[0]}); measuring instead"); rec = None
    if rec is None:
        try:
            paths = [os.path.join(box_dir, n) for n in names]
            offsets, scores, info = qr_stabilize.measure_offsets(paths, log=log)
        except Exception as e: # no label, unreadable frames, ...: track unstabilized, as before
            log(f"QR stabilization unavailable ({e}); tracking on the unstabilized frames")
            return None, {"method": "none", "reason": str(e)}
        parallax = qr_stabilize.PARALLAX_COLLEGE_STATION
        try: qr_stabilize.write_offsets(box_dir, names, offsets, scores, info, parallax) # cache for next time
        except OSError: pass # read-only data mount: fine, just measured again next time
        rec = {"parallax": parallax, "frames": {n: list(o) for n, o in zip(names, offsets)},
               "rejected": [names[k] for k in info["rejected"]], "jumps": [names[k] for k in info["jumps"]]}
        source = "measured by root-tracking"
    p = rec["parallax"]
    shifts = [(rec["frames"][n][0] * p, rec["frames"][n][1] * p) for n in names]
    frame_space = {"method": "qr-label", "source": source, "parallax": p,
                   "jumps": rec.get("jumps", []), "rejected": rec.get("rejected", [])}
    if frame_space["jumps"]: log(f"note: the label jumped at {len(frame_space['jumps'])} frame(s) -- a moved box? first: {frame_space['jumps'][0]}")
    return shifts, frame_space
