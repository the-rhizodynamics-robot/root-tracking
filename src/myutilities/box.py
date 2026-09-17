import concurrent.futures
import threading
import time
from src.myutilities import util
from src.myutilities.frames import Frames, iter_frames
import src.myutilities.io as io
import numpy as np
import src.retnet.model as retnet
import cv2
from plantcv import plantcv as pcv
import csv
import os
from matplotlib import pyplot as plt
from src.myutilities.image import Image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"} # everything else in a box folder is not a frame

class Box:
    """The box class defines the data derived from a single magenta box in an experiment.
    
    Each magenta box contains between 1-5 seeds. The proposed position of the seeds is identified by
    a retinanet neural net model. The positions are verified by the user. Then a bubble searching 
    algorithm is implemented to locate the frame of germination with an appropriate root tip starting 
    location. For experiments where the seed is obscured (such as hyrdoponic growth where the seed is in 
    a holder) ro where the neural net fails to find one or more seeds, there is a grid based manual seed location method.
    """
    
    # The box's frames: a Frames (frames.py), read from disk on demand rather than held in memory.
    images = []
    
    def __init__(self, path, save_path = "/app/data/"):
        """
        Attributes
        ----------
        
        _path : str
            argument. a string containing the full path of the directory containing the raw images the box is going to load into memory
        _save_path : str
            argument. the directory where post-tracking data is stored. Defaults to QUANTIFICATION_OUT_PATH in the constants.py module
        _qr_number : str
            the experiment number of the box, parsed from the full path, and kept as a string
        my_list : list
            list of paths to all image files associated with this experiment
        images : Frames
            the image series, read from disk on demand (frames.py)
        seeds : list
            list of seed objects within the box
        """
        self._path = path 
        self._qr_number = os.path.basename(os.path.normpath(self._path))
        self._save_path = os.path.normpath(save_path) + f"/{self._qr_number}"
        my_list = [f for f in util.listdir_nohidden(self._path)
                   if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS] # cv2 returns None for non-images, which only surfaces much later as a cryptic TypeError deep in tracking
        if not my_list: raise ValueError(f"no image files in {self._path}")
        self.images = Frames([os.path.join(self._path, l) for l in my_list]) # read on demand: a few hundred MB instead of ~2.9 GB per box; a corrupt frame raises, naming the file, when first read
        print(f"box {self._qr_number}: {len(self.images)} frames (read on demand)")
        self.seeds = [] # Seed objects
        self._reg_thread, self._reg_error = None, None # background seed registration, see start_registration()
    
        
    def init_seeds(self, seed_model: retnet.SeedModel, automatic : bool = True, seed_confidence : float = 0.05,
                   search_x : tuple = (1/6, 5/6), search_y : tuple = (0.0, 0.75)):
        """
        This method optionally runs automatic seed detection. It can also manually define regions of seeds. It then creates the appropriate number of seed objects associated with the respective box objects.

        Parameters
        ----------
        seed_model : retnet.SeedModel
            This is the trained retinanet model for detecting seeds in image
        automatic : bool
            true: attempt automatic seed detection. false: use manual seed detection.
        seed_confidence : float
            Noise floor for the detector, NOT a seed/not-seed decision -- the seed count the user
            enters decides how many detections are kept. Confidence varies hugely between boxes
            (measured 2026-09-17: a real seed scored 0.13 in one box and 0.98 in the next, at equal
            brightness and contrast), so any threshold high enough to exclude noise also drops seeds.
        search_x, search_y : tuple
            Search band, as (low, high) FRACTIONS of frame width/height. Everything outside is blanked
            before inference and any detection centred outside is dropped, which keeps the round
            seed-shaped objects at the bottom of the vessel out. Fractions, not pixels, so the band
            travels to any frame size. Measured over 8 boxes, real seeds sat at y 0.26-0.46, x 0.26-0.72.
        """

        seed_model._confidence_cutoff = seed_confidence
        #only run if "automatic mode" of seed detection is desired.
        if automatic:
            h, w = self.images[0].shape
            bx1, bx2 = int(search_x[0] * w), int(search_x[1] * w)
            by1, by2 = int(search_y[0] * h), int(search_y[1] * h)
            initial_image = np.zeros_like(self.images[0])
            initial_image[by1:by2, bx1:bx2] = self.images[0][by1:by2, bx1:bx2] # only the band reaches the model
            seeds_full, scores = seed_model.detect(image_arr=cv2.cvtColor(initial_image, cv2.COLOR_GRAY2BGR),
                                          sort=True)
            found = sorted([(s, sd) for s, sd in zip(scores, seeds_full)
                            if bx1 <= (sd.x1 + sd.x2) / 2 <= bx2 and by1 <= (sd.y1 + sd.y2) / 2 <= by2],
                           key = lambda t: -t[0]) # best first; one centred outside the band is not a seed we can track

            disp = cv2.cvtColor(self.images[0], cv2.COLOR_GRAY2BGR)
            util.show(disp, f"box {self._qr_number} · first frame · {len(found)} candidates in the search band"
                            f" (best scores: {', '.join(f'{s:.2f}' for s, _ in found[:8]) if found else 'none'})")

            while True:
                num_seeds = input("How many seeds are in this box?")
                if num_seeds.isdigit():
                    break
                else:
                    print("non-numeric entry")

            n = int(num_seeds)
            if len(found) < n: print(f"only {len(found)} candidate(s) in the search band, not {n} -- enter 'm' below for manual entry")
            chosen = sorted(found[:n], key = lambda t: t[1].x1) # the n best by score, then left to right
            self.seeds = [Seed(sd, self._qr_number, i + 1) for i, (_, sd) in enumerate(chosen)]

            for s in self.seeds:
                s.final_x1 = s.final_x1 - 50
                s.final_x2 = s.final_x2 + 50
                s.final_y1 = s.final_y1 - 50
                s.final_y2 = s.final_y2 + 100
                s.x1 = s.x1 - 50
                s.x2 = s.x2 + 50
                s.y1 = s.y1 - 50
                s.y2 = s.y2 + 100
                cv2.rectangle(disp,(s.final_x1, s.final_y1),(s.final_x2,s.final_y2),(255,0,0),5)

            util.show(disp, f"box {self._qr_number} · {len(self.seeds)} seed(s) boxed · scores {', '.join(f'{s:.2f}' for s, _ in chosen) if chosen else 'none'}")
        
        
            while True:
                manual = input("This image will have boxes around all detected seeds. If this looks good, enter 'c' to continue. If one or more seeds were missed, hit 'm' to proceed to manual mode.")
                if manual == "c" or manual == "m":
                    break
                else:
                    print("Invalid character")

            if manual == "c":
                return
        
        #manual mode is run if "automatic" is false or if the results of automatic mode are unacceptacle
        print("Manual seed localization:")
        self.seeds = []
        
        first = cv2.cvtColor(self.images[0], cv2.COLOR_GRAY2BGR)
        last = cv2.cvtColor(self.images[-1], cv2.COLOR_GRAY2BGR)
        
        for r in range(0, np.shape(first)[1], 500):
            first = cv2.line(first, (r, 0), (r, np.shape(first)[0]), (0, 255, 0), thickness=5) 
            last = cv2.line(last, (r, 0), (r, np.shape(last)[0]), (0, 255, 0), thickness=5) 
            
        for r in range(0, np.shape(first)[0], 500):
            first = cv2.line(first, (0, r), (np.shape(first)[1], r), (0, 255, 0), thickness=5) 
            last = cv2.line(last, (0, r), (np.shape(last)[1], r), (0, 255, 0), thickness=5) 
        
        disp = np.concatenate((first, last), axis = 1)
        util.show(disp, f"box {self._qr_number} · manual seed entry · first | last frame, grid lines every 500 px")
        
        while True:
            num_seeds = input("How many seeds are in this box?")
            if num_seeds.isdigit():
                break
            else:
                print("non-numeric entry")
        
        for s in range(int(num_seeds)):
            while True:
                while True:
                    top_y = input("Y-coordinate to delineate top of germination region for seed #" + str(s + 1) + ": ")
                    if top_y.isdigit():
                        break
                    else:
                        print("non-numeric entry")

                while True:
                    bottom_y = input("Y-coordinate to delineate bottom of germination region for seed #" + str(s + 1) + ": ")
                    if bottom_y.isdigit():
                        break
                    else:
                        print("non-numeric entry")

                while True:
                    left_x = input("X-coordinate to delineate left of germination region for seed #" + str(s + 1) + ": ")
                    if left_x.isdigit():
                        break
                    else:
                        print("non-numeric entry")

                while True:
                    right_x = input("X-coordinate to delineate right of germination region for seed #" + str(s + 1) + ": ")
                    if right_x.isdigit():
                        break
                    else:
                        print("non-numeric entry")

                germ_region = disp[int(top_y):int(bottom_y), int(left_x):int(right_x)]

                util.show(germ_region, f"box {self._qr_number} · seed #{s + 1} · proposed germination region")
                
                while True:
                    cont = input("Does this look good (y) or do you need to redo (r).")
                    if cont == "r" or cont == "y":
                        break
                    else:
                        print("Type (r) or (y)")
                
                if cont == "y":
                    self.seeds.append(Seed(Image(germ_region, x1 = int(left_x), y1 = int(top_y), x2 = int(right_x), y2 = int(bottom_y)), self._qr_number, s))
                    break
         


    def germination_detection(self, save_tip_sample : bool = False,  threshold_multiplier : float = 1.5, save_path : str = None, automatic : bool = True):
        count = 1
        if save_path is None:
            save_path = self._save_path
        for seed in self.seeds:
            seed.germination_detection(self.images, count, save_path, threshold_multiplier = threshold_multiplier, automatic = automatic)
            count += 1

    def start_registration(self, bottom_trim : int = 100, search_margin : int = 200):
        """
        Register every seed (Seed.register_to_seed) on a background thread. Registration needs only the
        seed boxes, not the germination frames, so its passes over the frames run while the user is
        still bisecting for germination. Its messages go to each seed's log, shown at validation.
        """
        if self._reg_thread is not None: return
        def run():
            try:
                for seed in self.seeds: seed.register_to_seed(self.images, bottom_trim = bottom_trim, search_margin = search_margin)
            except Exception as e: self._reg_error = e # re-raised in the foreground by wait_registration()
        self._reg_thread = threading.Thread(target = run, daemon = True)
        self._reg_thread.start()

    def wait_registration(self):
        if self._reg_thread is None: return
        if self._reg_thread.is_alive(): print("waiting for seed registration to finish ...")
        self._reg_thread.join()
        if self._reg_error is not None: raise self._reg_error

    def tip_trace_pcv(self, length : int = None, threshold_multiplier : float = 1.5, bound_radius : int = 30,
                      stabilize : bool = True, stabilize_bottom_trim : int = 100, stabilize_search_margin : int = 200):
        """
        Trace every germinated seed in ONE shared pass over the frames, then write all their videos in a
        second shared pass: two passes per box however many seeds, since frames are read from disk.
        """
        out = "/app/results/stabilized_videos_single_seed"
        os.makedirs(out, exist_ok=True)
        seeds = [s for s in self.seeds if s.germination_indicator and not s.germination_not_found] # no germination point = nothing to trace from
        if not seeds: return
        if stabilize: self.start_registration(stabilize_bottom_trim, stabilize_search_margin) # no-op if already running
        self.wait_registration() # tracing and video both use the offsets
        print(f"box {self._qr_number}: tracing {len(seeds)} seed(s) ...")
        spans = {s: s.trace_start(length, len(self.images), threshold_multiplier, bound_radius) for s in seeds}
        self._shared_pass(spans, lambda s, fi, frame: s.trace_frame(fi, frame))
        for s in seeds: s.trace_end()
        print(f"box {self._qr_number}: writing {len(seeds)} video(s) ...")
        shape = self.images[0].shape
        spans = {s: s.video_start(f"{out}/{self._qr_number}_{self.seeds.index(s) + 1}.mp4", shape) for s in seeds} # numbered by position among ALL seeds, as before
        self._shared_pass(spans, lambda s, fi, frame: s.video_frame(fi, frame))
        for s in seeds: s.video_end()

    def _shared_pass(self, spans : dict, step):
        """One prefetched pass over the union of the seeds' (start, stop) frame spans, calling step(seed, index, frame)."""
        spans = {s: ab for s, ab in spans.items() if ab[0] < ab[1]}
        if not spans: return
        for fi, frame in iter_frames(self.images, min(a for a, _ in spans.values()), max(b for _, b in spans.values())):
            for s, (a, b) in spans.items():
                if a <= fi < b: step(s, fi, frame)


    def set_images(self, images):
        self.images = images
        
    def print_images(self):
        print(self.images)


    def archive(self):
        pass

    def make_video(self, save_path:str = None, trace_tip: bool = False):
        count = 1
        for seed in self.seeds:
            if save_path is None:
                save_path = self._save_path
            seed.make_video(self.images, save_path + f"/{self._qr_number}_tiptrace_seed{count}.mp4", trace_tip=trace_tip)
            count += 1
            # break

    def to_json(self):
        # for x in range(len(self.images)):
        #     self.images[x] = self.images[x].tolist()
        #
        #
        # print(type(self.images[0]))
        return json.dumps(self, default = self._serialize_json,
                          sort_keys=True, indent=4)

        pass

    
    # helper method
    def _serialize_json(self):
        return {
            'path': self._path,
            'qr_number': self._qr_number
        }

    # note can get rid of the qr_number since that is derived from path
    def to_dict(self):
        seeds = [i.to_dict() for i in self.seeds]
        return {
            "path": self._path,
            "qr_number": self._qr_number,
            "save_path": self._save_path,
            "seeds": seeds
        }




    @classmethod
    def from_dict(cls, dct: dict):
        box = cls(dct.get("path"), dct.get("save_path"))
        # need to save seed_coordinates to avoid running init_seeds
        # running init_seeds would require passing seed_model
        seeds = dct.get("seeds")
        final_seeds = []
        for seed_dct in seeds:
            seed = Seed.from_dict(seed_dct, box.images[0])
            final_seeds.append(seed)
        box.seeds = final_seeds
        return box

    # override
    # def default(self, obj):
    #     if isinstance(obj, np.ndarray):
    #         return obj.tolist()
    #     return json.JSONEncoder.default(self, obj)
    def denoise_all(self):
        # 132 vs 30 seconds
        start = time.time()
        with concurrent.futures.ProcessPoolExecutor() as executor:
            images = executor.map(retnet.TipModel.denoise, self.images)
        self.images = [shift for shift in images]
        print("time", time.time() - start)

        
    def validate_save_tracking(self):
        count = 0
        for s in self.seeds:
            count = count + 1
            if(s.germination_indicator and not s.germination_not_found):
                if s.final_trace_img is None: # tracking stopped on its first frame: no trace to judge or save
                    print(f"box {self._qr_number} · seed {count}: no trace to validate", *s.log, sep = "\n"); continue
                util.show(s.final_trace_img, "\n".join([f"box {self._qr_number} · seed {count}/{len(self.seeds)} · traced {len(s.tip_coords_pcv) - 1} frames from germination frame {s.germination_frame}"] + s.log))
                while True:
                    save1 = input("Does this look good enough to save? (y) or (n). If the root curled, press (c) to identify curl frame.")
                    save2 = input("Confirm: Does this look good enough to save? (y) or (n), or (c) to identify curl frame")
                    if save1 == save2 == "y" or save1 == save2 == "n" or save1 == save2 == "c":
                        break
                    else:
                        print("Invalid response.")
                if save1 == "y":
                    print("Saving coordinates.")
                    os.makedirs("/app/results/tip_coordinates/", exist_ok=True)
                    with open("/app/results/tip_coordinates/" + f"/{self._qr_number}_{count}" + ".csv", 'w') as myfile:
                        wr = csv.writer(myfile, quoting=csv.QUOTE_ALL)
                        wr.writerow(s.tip_coords_pcv)
                        #do some other saving stuff
                elif save1 =="c":
                    first = 0
                    last = len(self.images) - 1
                    x_tip_coords = s.tip_coords_pcv[0:,0]
                    y_tip_coords = s.tip_coords_pcv[0:,1]
                    x1 = min(x_tip_coords) - 50
                    x2 = max(x_tip_coords) + 50
                    y1 = min(y_tip_coords) - 50
                    y2 = max(y_tip_coords) + 50
                    while True:
                        mid = int((first + last)/2)
                        # calculate crop boundaries for tip video

                        util.show(self.images[mid][y1:y2, x1:x2], f"box {self._qr_number} · seed {count} · curl search · frame {mid}/{len(self.images) - 1}")
                        while True:
                            direction = input("Does curling start (b)efore, (a)fter, (h)ere, do you need to (r)estart, or does it actually not curl (x)?")
                            if direction == "b" or direction == "a" or direction == "h" or direction == "r" or direction == "x":
                                break
                            else:
                                print("Invalid character")
                        if direction == "h":
                            direction = input("To confirm this as  curling frame, hit (h) again, or any other key to continue searching.")
                            if direction == "h":
                                s.curling_start_frame = mid
                                break
                        elif direction == "x":
                            direction = input("To confirm root did not curl, hit (x) again, or any other key to continue searching.")
                            if direction == "x":
                                break
                        elif direction == "r":
                            first = 0
                            last = len(self.images) - 1
                        elif direction == "a":
                            first = mid
                        elif direction == "b":
                            last = mid
                            
                    print("Saving coordinates.")
                    coords = s.tip_coords_pcv[:(s.curling_start_frame - s._tracking_start_frame)]
                    coords[-1,0] = 100000
                    coords[-1,1] = 100000
                    with open("/app/results/tip_coordinates/" + f"/{self._qr_number}_{count}" + ".csv", 'w') as myfile:
                        wr = csv.writer(myfile, quoting=csv.QUOTE_ALL)
                        wr.writerow(coords)
                        #do some other saving stuff
                    

class Seed(Image):


    def __init__(self, mi: Image, qr_number, seed_number):
        super().__init__(mi.image, mi.crop, mi.x1, mi.x2, mi.y1, mi.y2)
        self.germination_indicator = False
        self.germination_not_found = False
        self._tracking_start_frame = 0
        self.germination_x = None
        self.germination_y = None
        self.tip_coords_pcv = []
        self.tip_coords = []
        self.qr_number = qr_number
        self.seed_number = seed_number
        self.final_trace_img = None
        self.curling_start_frame = None
        self.offsets = None # per-frame (dx, dy, score) from register_to_seed(); None = unregistered
        self.log = [] # registration/tracking messages, shown with the trace at validation (a print would be cleared by the next image)

        # keep these and store in database to recreate this Seed object

        self.final_x1 = mi.x1
        self.final_x2 = mi.x2
        self.final_y1 = mi.y1
        self.final_y2 = mi.y2


    @property
    def germination_frame(self):
        return self._tracking_start_frame

    @germination_frame.setter
    def germination_frame(self, new_value):
        if new_value >=0 and isinstance(new_value, int):
            self._tracking_start_frame = new_value
        else:
            raise ValueError("Set germination frame to int above 0")

    def germination_detection(self, images, seed_number,  save_path : str, threshold_multiplier : float = 1.5, save_tip_sample: bool = False, automatic : bool = True):
        if automatic:
            pass
            # NEED TO DEVELOP THIS. WAS NOT RELIABLE, AND WON'T RUN AS CURRENTLY WRITTEN.
            # self._tracking_start_frame, self.germination_x, self.germination_y = \
            #     myutilities.tip_tracer.germination_detection_init(self, images, c.TMP_SHOWCASE_PATH, seed_number)
            # if save_tip_sample:
            #     tip_corners = self.get_transform_crop_coords(self.germination_x - 30, self.germination_x + 30,
            #                                                 self.germination_y - 30, self.germination_y + 30)
            #     image = images[self._tracking_start_frame]
            #     cv2.rectangle(image, (tip_corners.x1, tip_corners.y1), (tip_corners.x2, tip_corners.y2),
            #                   c.COLOR_WHITE, c.MARKER_THICKNESS, cv2.LINE_AA)

            #     io.save_image(io.to_pil(image), save_path + f"/germination_seed{seed_number}.png")
        else:
            print("Finding germination frame for seed " + str(seed_number))
            first = 0
            last = len(images) - 1
            while True:
                mid = int((first + last)/2)
                util.show(images[mid][self.y1:self.y2, self.x1:self.x2], f"box {self.qr_number} · seed {seed_number} · germination search · frame {mid}/{len(images) - 1}")
                while True:
                    direction = input("Is germination (b)efore, (a)fter, (h)ere, do you need to (r)estart, or does it not germinate (x)?")
                    if direction == "b" or direction == "a" or direction == "h" or direction == "r" or direction == "x":
                        break
                    else:
                        print("Invalid character")
                if direction == "h":
                    direction = input("To confirm this as germination frame, hit (h) again, or any other key to continue searching.")
                    if direction == "h":
                        self.germination_indicator = True
                        self._tracking_start_frame = mid
                        break
                elif direction == "x":
                    direction = input("To confirm seed did not germinate, hit (x) again, or any other key to continue searching.")
                    if direction == "x":
                        break
                elif direction == "r":
                    first = 0
                    last = len(images) - 1
                elif direction == "a":
                    first = mid
                elif direction == "b":
                    last = mid
                
            if self.germination_indicator:                    
                proposed = np.copy(images[self._tracking_start_frame][self.y1:self.y2, self.x1:self.x2])
                threshold_light = pcv.threshold.binary(gray_img=proposed, threshold=np.median(images[mid])*threshold_multiplier , max_value=255, object_type='light')
                binary_img = pcv.median_blur(gray_img=threshold_light, ksize=5)
                fill_image = pcv.fill(bin_img=binary_img, size=10)
                skeleton = pcv.morphology.skeletonize(mask=fill_image)
                tips_img = pcv.morphology.find_tips(skel_img=skeleton, mask=fill_image)
                locs = np.argwhere(tips_img > 0)
                             
                
                if len(locs) == 0: # the threshold found no tips in this crop: nothing to pick (indexing locs[-1] used to crash)
                    self.log.append(f"germination frame {mid}: no tip candidates found -- marked not found"); self.germination_not_found = True
                i = len(locs) - 1
                while i < len(locs) and not self.germination_not_found: # confirming "not found" used to leave this loop cycling forever
                    copy = cv2.cvtColor(proposed, cv2.COLOR_GRAY2RGB)
                    y, x = int(locs[i][0]), int(locs[i][1])
                    cv2.rectangle(copy, (x - 5, y - 5), (x + 5, y + 5), (255, 0, 0), 1) # red 10x10 box; clipped at the crop edge, where direct indexing raised
                    util.show(copy, f"box {self.qr_number} · seed {seed_number} · germination frame {self._tracking_start_frame} · tip candidate {len(locs) - i}/{len(locs)}")
                    while True:
                        response = input("Is this the germination point? (y) or (n)")
                        if response == "y" or response == "n":
                            break
                        else:
                            print("Invalid character")
                    if response == "y":
                        response = input("Confirm germination is here by pressing (y), any other key to keep searching.")
                        if response == "y":
                            self.germination_x = locs[i][1] + self.x1
                            self.germination_y = locs[i][0] + self.y1
                            break
                    if i == 0:
                        while True:
                            response = input("This was the last position in the list of candidate germination points. Loop through again (l) or mark as not found (n).")
                            if response == "l" or response == "n":
                                break
                            else:
                                print("Invalid character")
                        if response == "n":
                            response = input("To confirm germination was not properly found, press (n), or any other key to continue searching.")
                            if response == "n":
                                self.germination_not_found = True
                        else:
                            i = len(locs) 
                    i -= 1
                
                              
                          
    def register_to_seed(self, images, bottom_trim : int = 100, search_margin : int = 200,
                         min_score : float = 0.5, max_weak_frac : float = 0.25,
                         max_search_margin : int = 900):
        """
        Measure this seed's per-frame (dx, dy) shift relative to frame 0 by template-matching
        on the seed body, so tracking and video can undo residual gantry jitter locally.

        Upstream file-sorting stabilizes the WHOLE frame with one transform, which leaves
        residual error that grows toward the frame edges and differs per seed. The seed itself
        never moves, so it is the ideal local reference. The bottom of the seed box is trimmed
        off because that is where the root grows into (init_seeds pads y2 by +100); including it
        would let the template change over time and drift. Always matched against frame 0, so
        error cannot accumulate.

        Parameters
        ----------
        images : list
            the box's full image series
        bottom_trim : int
            pixels removed from the bottom of the seed box to exclude the root-growth region
        search_margin : int
            how far (px) around the seed box to search first; widened automatically (up to
            max_search_margin) whenever the best match lands on the boundary, since a boundary
            hit means the true shift is somewhere past it
        min_score : float
            reject a frame's match below this TM_CCOEFF_NORMED score and hold the last good shift
        max_weak_frac : float
            if more than this fraction of frames are rejected, drop the offsets entirely and track
            unstabilized -- a wrong offset is worse than no offset
        """
        h, w = images[0].shape
        tx1, tx2 = max(self.final_x1, 0), min(self.final_x2, w)
        ty1, ty2 = max(self.final_y1, 0), min(self.final_y2, h) - bottom_trim
        if ty2 - ty1 < 20: ty2 = min(self.final_y2, h) # box too short to trim; use it whole
        template = images[0][ty1:ty2, tx1:tx2]
        sx1, sy1 = max(tx1 - search_margin, 0), max(ty1 - search_margin, 0) # search window, fixed
        sx2, sy2 = min(tx2 + search_margin, w), min(ty2 + search_margin, h)

        def match(img, margin): # best (dx, dy, score) within +/-margin of the frame-0 box
            ax1, ay1 = max(tx1 - margin, 0), max(ty1 - margin, 0)
            ax2, ay2 = min(tx2 + margin, w), min(ty2 + margin, h)
            res = cv2.matchTemplate(img[ay1:ay2, ax1:ax2], template, cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(res)
            return ax1 + loc[0] - tx1, ay1 + loc[1] - ty1, score

        self.offsets = []
        lx, ly, weak, widest = 0, 0, 0, search_margin # last ACCEPTED shift; frame 0 is the reference so it starts at zero
        for img in images:
            margin = search_margin
            while True:
                ox, oy, score = match(img, margin)
                # A result sitting ON the boundary is not a measurement -- the true shift may be
                # anywhere past it -- so widen and look again rather than believing the edge.
                if max(abs(ox), abs(oy)) < margin or margin >= max_search_margin: break
                margin = min(margin * 3, max_search_margin)
            widest = max(widest, margin)
            if score < min_score or max(abs(ox), abs(oy)) >= margin:
                weak += 1; ox, oy = lx, ly # hold the last good shift; a wrong offset is far worse than none, since tip_trace_pcv crops only bound_radius*2 px around the tip
            else:
                lx, ly = ox, oy
            self.offsets.append((ox, oy, score))
        if widest > search_margin: self.log.append(f"registration: widened search to +/-{widest} px to find the seed")

        # Re-reference to the MEDIAN position, not frame 0. Frame 0 is the first imaging cycle,
        # which the firmware treats differently (longer light warm-up, first calibration) and which
        # measures ~100px off the rest -- leaving it as the zero point displaces every other frame
        # and puts a visible jump at the start of the video. Offsets are relative, so shifting the
        # baseline is consistent everywhere they are used.
        mx = int(np.median([o[0] for o in self.offsets])); my = int(np.median([o[1] for o in self.offsets]))
        self.offsets = [(o[0] - mx, o[1] - my, o[2]) for o in self.offsets]

        dx = [o[0] for o in self.offsets]; dy = [o[1] for o in self.offsets]
        worst = min(o[2] for o in self.offsets)
        self.log.append(f"registration: jitter dx {min(dx)}..{max(dx)} px, dy {min(dy)}..{max(dy)} px "
                        f"(template {tx2-tx1}x{ty2-ty1}, worst match {worst:.2f}, {weak}/{len(images)} frames rejected)")
        if weak > len(images) * max_weak_frac: # registration is unreliable for this seed; unstabilized beats mis-stabilized
            self.log.append(f"registration FAILED ({weak}/{len(images)} frames) -- stabilization DISABLED for this seed. "
                            f"If the jitter range reaches +/-{search_margin}, the real jitter exceeds the search window: raise stabilize_search_margin")
            self.offsets = None

    def _offset(self, frame_index : int):
        """(dx, dy) of `frame_index` vs frame 0; (0, 0) when the seed was never registered."""
        if not self.offsets or frame_index >= len(self.offsets): return 0, 0
        return self.offsets[frame_index][0], self.offsets[frame_index][1]

    def trace_start(self, length : int = None, tot_length : int = None, threshold_multiplier : float = 1.5, bound_radius : int = 30):
        """
        Set up tip tracing from the identified point of germination. Feed frames to trace_frame() in
        order over the returned (start, stop) span, then call trace_end(). Box.tip_trace_pcv does this
        for all of a box's seeds in one shared pass over the frames.
        """
        if length is None or length > tot_length - self.germination_frame: # track as many frames as there are
            length = tot_length - self.germination_frame
        gdx, gdy = self._offset(self._tracking_start_frame)
        gx, gy = self.germination_x - gdx, self.germination_y - gdy # germination point in frame-0 reference
        self.x1, self.x2 = gx - bound_radius, gx + bound_radius
        self.y1, self.y2 = gy - bound_radius, gy + bound_radius
        self._trace = {"coords": [[gx, gy]], "last": (bound_radius, bound_radius), "count": 0, "length": length,
                       "threshold_multiplier": threshold_multiplier, "bound_radius": bound_radius, "alive": True}
        return self._tracking_start_frame, self._tracking_start_frame + length

    def trace_frame(self, fi : int, frame):
        """Advance the tip by one frame (frames must come in order). A lost tip stops this seed's trace, logged."""
        t = self._trace
        if not t["alive"]: return
        r = t["bound_radius"]
        try:
            dx, dy = self._offset(fi) # crop follows the jitter; self.x1/y1 stay frame-0 referenced
            image = frame[self.y1 + dy:self.y2 + dy, self.x1 + dx:self.x2 + dx]
            threshold_light = pcv.threshold.binary(gray_img=image, threshold=np.median(image)*t["threshold_multiplier"], max_value=255, object_type='light') #try mean?
            binary_img = pcv.median_blur(gray_img=threshold_light, ksize=5)
            fill_image = pcv.fill(bin_img=binary_img, size=10)
            skeleton = pcv.morphology.skeletonize(mask=fill_image)
            tips_img = pcv.morphology.find_tips(skel_img=skeleton, mask=fill_image)
            locs = np.argwhere(tips_img > 0)
            # Take the endpoint closest to the last tip, not the bottom-most one: a root growing roughly
            # horizontally circumnutates upward at times, which puts the real tip above other endpoints.
            last_x, last_y = t["last"]
            y, x = locs[np.argmin([np.linalg.norm([last_y, last_x] - l) for l in locs])]
            self.transform_crop_coords(x - r, x + r, y - r, y + r)
            t["coords"].append([int((self.x2 + self.x1)/2), int((self.y2 + self.y1)/2)])
            t["last"] = (x, y)
            t["count"] += 1
        except Exception as e: # was silent: a lost tip truncated the trace with no visible reason
            self.log.append(f"tracking STOPPED at frame {fi} after {t['count']}/{t['length']} frames -- {e!r}")
            t["alive"] = False

    def trace_end(self):
        self.tip_coords_pcv = self._trace["coords"]

    def tip_trace_pcv(self, images_param, length : int = None, tot_length : int = None, threshold_multiplier : float = 1.5, bound_radius : int = 30):
        """Trace this seed on its own pass over the frames (Box.tip_trace_pcv shares one pass among all seeds)."""
        start, stop = self.trace_start(length, tot_length or len(images_param), threshold_multiplier, bound_radius)
        for fi, frame in iter_frames(images_param, start, stop): self.trace_frame(fi, frame)
        self.trace_end()
        
    def video_start(self, path : str, frame_shape : tuple):
        """
        Fix the video crop (the seed box plus the whole tip path) and prepare the writer. Feed frames to
        video_frame() in order over the returned (start, stop) span, then call video_end(). Frames are
        written as they come instead of collected first, which for a tall crop could reach gigabytes.
        """
        self.tip_coords_pcv = np.asarray(self.tip_coords_pcv)
        x_tip_coords = self.tip_coords_pcv[0:,0]
        y_tip_coords = self.tip_coords_pcv[0:,1]
        # Crop must cover the SEED as well as the root path. The tip trajectory starts at the
        # germination point, so a bbox over it alone clips the seed body to a sliver against the
        # top edge -- worst when the root grows straight down and the bbox is narrow.
        x1 = min(min(x_tip_coords), self.final_x1) - 50
        x2 = max(max(x_tip_coords), self.final_x2) + 50
        y1 = min(min(y_tip_coords), self.final_y1) - 50
        y2 = max(max(y_tip_coords), self.final_y2) + 50
        fh, fw = frame_shape
        x1, y1 = max(int(x1), 0), max(int(y1), 0) # clamp INTO the frame (x2/y2 were clamped to 0, not fw/fh)
        x2, y2 = min(int(x2), fw), min(int(y2), fh)
        cw, ch = (x2 - x1) & ~1, (y2 - y1) & ~1 # constant size so every frame matches; even, because mp4v mangles odd dimensions
        self._video = {"path": path, "x1": x1, "y1": y1, "cw": cw, "ch": ch, "fw": fw, "fh": fh, "writer": None}
        self.final_trace_img = None
        return self._tracking_start_frame, self._tracking_start_frame + len(self.tip_coords_pcv) - 1

    def video_frame(self, fi : int, frame):
        """Render and write one frame (raw | traced | trace only), shifted by this frame's jitter."""
        v = self._video
        x = fi - self._tracking_start_frame # frames since germination = trace segments drawn so far
        frame = np.copy(frame) # copy: cv2.line below would otherwise burn the trace into a shared frame
        original = np.copy(frame)
        black = np.zeros_like(frame)
        dx, dy = self._offset(fi)
        for y in range(0, x): # redraw lines in each frame, since base image is different
            if self.tip_coords_pcv[y][0] != 10000:
                # coords are frame-0 referenced; += offset puts them on the root in THIS frame
                cv2.line(frame, (self.tip_coords_pcv[y][0] + dx, self.tip_coords_pcv[y][1] + dy),
                         (self.tip_coords_pcv[y + 1][0] + dx, self.tip_coords_pcv[y + 1][1] + dy),
                         (255, 0, 0), 3)
                cv2.line(black, (self.tip_coords_pcv[y][0] + dx, self.tip_coords_pcv[y][1] + dy),
                         (self.tip_coords_pcv[y + 1][0] + dx, self.tip_coords_pcv[y + 1][1] + dy),
                         (255, 0, 0), 3)
        # crop image based on boundaries, shifted by this frame's jitter so the OUTPUT is stabilized
        cx1 = min(max(v["x1"] + dx, 0), max(v["fw"] - v["cw"], 0))
        cy1 = min(max(v["y1"] + dy, 0), max(v["fh"] - v["ch"], 0))
        original = original[cy1:cy1 + v["ch"], cx1:cx1 + v["cw"]]
        frame = frame[cy1:cy1 + v["ch"], cx1:cx1 + v["cw"]]
        black = black[cy1:cy1 + v["ch"], cx1:cx1 + v["cw"]]
        # cv2_videoWriter BGR color requirement
        buffer = np.full(np.shape(original), 255, dtype=np.uint8)[:,1:3]
        buffer = cv2.cvtColor(buffer, cv2.COLOR_GRAY2BGR)
        original = cv2.cvtColor(original, cv2.COLOR_GRAY2BGR)
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        black = cv2.cvtColor(black, cv2.COLOR_GRAY2BGR)
        complete = np.concatenate((original, buffer, frame, buffer, black), axis=1)
        if v["writer"] is None: # same codec and fps as io.make_video_cv2
            v["writer"] = cv2.VideoWriter(v["path"], cv2.VideoWriter_fourcc(*'mp4v'), 15, (complete.shape[1], complete.shape[0]))
        v["writer"].write(complete)
        self.final_trace_img = complete # the last frame is shown for QC at validation

    def video_end(self):
        if self._video["writer"] is None: return
        self._video["writer"].release()
        self.log.append(f"video: {self._video['path']}")

    def make_video(self, images, path: str, trace_tip: bool = True):
        """Write this seed's trace video on its own pass (Box.tip_trace_pcv shares one pass among all seeds)."""
        if not trace_tip: raise ValueError("make_video only implements trace_tip=True (the untraced branch never produced any frames)")
        start, stop = self.video_start(path, images[0].shape)
        for fi, frame in iter_frames(images, start, stop): self.video_frame(fi, frame)
        self.video_end()




    def max_intensity_projection(self):
        pass

    def quantify_max_intensity_projection(self):
        pass

    def to_dict(self):
        tip_coords = self.tip_coords
        if isinstance(tip_coords, np.ndarray):
            tip_coords = tip_coords.tolist()
        # print(type(tip_coords), type(tip_coords[0]), type(tip_coords[0][0]))
        print(type(tip_coords))
        if tip_coords:
            print(type(tip_coords))
            # print(tip_coords)
            print(type(tip_coords[0]))
            print(type(tip_coords[0][0]))
        print(type(self._tracking_start_frame), type(self.germination_x), type(self.germination_y), type(self.qr_number), type(self.seed_number))
        tip_coords = [self.array_to_dict(i) for i in tip_coords]

        return {
            "germination_frame":self._tracking_start_frame,
            "germination_x": int(self.germination_x),
            "germination_y": int(self.germination_y),
            "tip_coords": tip_coords,
            "qr_number": self.qr_number,
            "seed_number": self.seed_number,
            "x1": int(self.final_x1),
            "x2": int(self.final_x2),
            "y1": int(self.final_y1),
            "y2": int(self.final_y2)
        }

    @staticmethod
    def array_to_dict(arr: list):
        return {"coord": arr}

    @staticmethod
    def dict_to_array(dct:dict):
        return dct.get("coord")

    @classmethod
    def from_dict(cls, dct: dict, image):
        mi = Image(image)
        mi.set_crop(dct.get("x1"), dct.get("x2"), dct.get("y1"), dct.get("y2"))
        seed = cls(mi, dct.get("qr_number"), dct.get("seed_number"))
        seed._germination_frame = dct.get("germination_frame")
        seed.germination_x = dct.get("germination_x")
        seed.germination_y = dct.get("germination_y")

        # convert array[map(array[])] back to array[array[]]
        tip_coords_arr = dct.get("tip_coords")
        tip_coords = [cls.dict_to_array(i) for i in tip_coords_arr]
        seed.tip_coords = tip_coords

        return seed


