import collections
import concurrent.futures
import threading

import cv2
import numpy as np

"""
Read-on-demand access to a box's image series.

A box used to be loaded whole into memory (319 frames at 3000x3000 is ~2.9 GB in grayscale), which
does not fit a laptop-class WSL VM. Frames instead reads each image when it is used, keeps a small
cache for the interactive steps (which revisit a handful of frames), and decodes ahead on a thread
pool for full passes (registration, tip tracing, video), which then cost ~12 s per pass on a
4-core machine rather than ~40 s of up-front loading.
"""

def read_gray(path: str) -> np.ndarray:
    """Read an image as grayscale in ONE file read, then decode in memory.

    cv2.imread issues many small reads; on a WSL /mnt/c mount each one crosses the VM boundary,
    which made it ~5x slower (630 ms vs ~115 ms per 3000x3000 PNG, measured 2026-09-15).
    """
    with open(path, "rb") as f: img = cv2.imdecode(np.frombuffer(f.read(), np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None: raise ValueError(f"could not read {path} as an image") # corrupt/truncated frame: fail loudly, naming the file
    return img

class Frames:
    """Sequence of grayscale frames, read from disk on demand. Supports len(), indexing, slicing,
    plain iteration, and iter(start, stop) for prefetched sequential passes."""

    def __init__(self, paths: list, cache_size: int = 12, workers: int = 4, lookahead: int = 8):
        self.paths = list(paths)
        self.cache_size, self.workers, self.lookahead = cache_size, workers, lookahead # cache: ~110 MB at 3000x3000
        self._cache = collections.OrderedDict() # LRU: frame index -> read-only array
        self._lock = threading.Lock() # background registration and the foreground UI read concurrently

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        if isinstance(i, slice): return Frames(self.paths[i], self.cache_size, self.workers, self.lookahead)
        i = range(len(self.paths))[i] # normalises negative indices; raises IndexError like a list
        with self._lock:
            if i in self._cache:
                self._cache.move_to_end(i); return self._cache[i]
        img = read_gray(self.paths[i])
        img.setflags(write=False) # cached arrays are shared: an in-place edit would silently corrupt later reads
        with self._lock:
            self._cache[i] = img
            while len(self._cache) > self.cache_size: self._cache.popitem(last=False)
        return img

    def iter(self, start: int = 0, stop: int = None):
        """Yield (index, frame) for start..stop-1, decoding up to `lookahead` frames ahead in the
        background. Bypasses the cache, so a full pass doesn't evict what the viewer is using."""
        stop = len(self.paths) if stop is None else min(stop, len(self.paths))
        with concurrent.futures.ThreadPoolExecutor(self.workers) as ex:
            pending = collections.deque()
            for i in range(start, stop):
                pending.append((i, ex.submit(read_gray, self.paths[i])))
                if len(pending) > self.lookahead:
                    j, fut = pending.popleft(); yield j, fut.result()
            while pending:
                j, fut = pending.popleft(); yield j, fut.result()

    def __iter__(self):
        return (img for _, img in self.iter())

def iter_frames(images, start: int, stop: int):
    """(index, frame) pairs over start..stop-1 for either a Frames or a plain list of arrays."""
    return images.iter(start, stop) if isinstance(images, Frames) else ((i, images[i]) for i in range(start, min(stop, len(images))))
