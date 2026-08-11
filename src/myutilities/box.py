import concurrent.futures
import time
from src.myutilities import util
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
    
    #This is the list where the raw images will be stored in memory. This will be quite large, which is why the call to the garbage collector is necessary between analysis of each box.
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
        images : list
            list of images in memory
        seeds : list
            list of seed objects within the box
        """
        self._path = path 
        self._qr_number = os.path.basename(os.path.normpath(self._path))
        self._save_path = os.path.normpath(save_path) + f"/{self._qr_number}"
        my_list = [f for f in util.listdir_nohidden(self._path)
                   if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS] # cv2 returns None for non-images, which only surfaces much later as a cryptic TypeError deep in tracking
        my_list = [os.path.join(self._path, l) for l in my_list]
        with concurrent.futures.ThreadPoolExecutor() as executor:
            all_images = executor.map(io.read_image_single_channel, my_list)
        self.images = [img for img in all_images] # numpy array of images, grayscale mode
        bad = [p for p, img in zip(my_list, self.images) if img is None] # a corrupt/truncated frame still gets through the extension filter
        if bad: raise ValueError(f"{len(bad)} of {len(my_list)} files in {self._path} could not be read as images, e.g. {os.path.basename(bad[0])}")
        print(f"box {self._qr_number}: loaded {len(self.images)} frames")
        self.seeds = [] # Seed objects
    
        
    def init_seeds(self, seed_model: retnet.SeedModel, automatic : bool = True):
        """
        This method optionally runs automatic seed detection. It can also manually define regions of seeds. It then creates the appropriate number of seed objects associated with the respective box objects.
        
        Parameters
        ----------
        seed_model : retnet.SeedModel
            This is the trained retinanet model for detecting seeds in image
        automatic : bool
            true: attempt automatic seed detection. false: use manual seed detection.
        """
        
        seed_model._confidence_cutoff = .3
        #only run if "automatic mode" of seed detection is desired.
        if automatic:
            initial_image = np.copy(self.images[0])
            y,x =  initial_image.shape
            startx = x//2-(1000)
            initial_image[:,0:startx] = 0
            initial_image[:,(startx+2000):x] = 0
            seeds_full, scores = seed_model.detect(image_arr=cv2.cvtColor(initial_image, cv2.COLOR_GRAY2BGR),
                                          sort=True)
            
            disp = cv2.cvtColor(self.images[0], cv2.COLOR_GRAY2BGR)
            plt.imshow(disp)
            plt.show()
            
            while True:
                print(len(scores))
                num_seeds = input("How many seeds are in this box?")
                if num_seeds.isdigit():
                    break
                else:
                    print("non-numeric entry")
            
            res = sorted(sorted(range(len(scores)), key = lambda sub: scores[sub])[-int(num_seeds):])
              
            seeds = []
            for index in res:
                seeds.append(seeds_full[index])   
            print(len(seeds))
          

            for count, seed in enumerate(seeds):
                if ((seed.y1 > (.1 * np.shape(self.images[0])[0])) and (seed.y1 < (.9 * np.shape(self.images[0])[0]))):
                    if ((seed.x1 > (.1 * np.shape(self.images[0])[1])) and (seed.x1 < (.9 * np.shape(self.images[0])[1]))):
                        self.seeds.append(Seed(seed, self._qr_number, count + 1))

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

            plt.imshow(disp)
            plt.show()
        
        
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
        plt.imshow(disp)
        plt.show()
        
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

                plt.imshow(germ_region)
                plt.show()
                
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

    #Call to seed tip trace
    #seed.tip_trace_pcv(b.images, length = 250)
    def tip_trace_pcv(self, length : int = None, threshold_multiplier : float = 1.5, bound_radius : int = 30,
                      stabilize : bool = True, stabilize_bottom_trim : int = 100, stabilize_search_margin : int = 60):
        count = 1
        os.makedirs("/app/results/stabilized_videos_single_seed", exist_ok=True)
        for seed in self.seeds:
            if seed.germination_indicator:
                if stabilize: # local per-seed registration; must run before tracking uses the offsets
                    seed.register_to_seed(self.images, bottom_trim = stabilize_bottom_trim, search_margin = stabilize_search_margin)
                seed.tip_trace_pcv(self.images, length = length, tot_length = len(self.images), threshold_multiplier = threshold_multiplier, bound_radius = bound_radius)
                seed.make_video(self.images,  "/app/results/stabilized_videos_single_seed" + f"/{self._qr_number}_{count}.mp4", trace_tip=True)
            count = count + 1
            #seed.tip_trace(self.images, tip_model, length=length, save_path=self._save_path)
            # TODO remove break
            # break


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
                plt.imshow(s.final_trace_img)
                plt.show()
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

                        plt.imshow(self.images[mid][y1:y2, x1:x2])
                        plt.show()
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
                plt.imshow(images[mid][self.y1:self.y2, self.x1:self.x2])
                plt.show()
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
                             
                
                i = len(locs) - 1
                while i < len(locs):
                    copy = np.copy(proposed)
                    #copy[(locs[i][0]-3):(locs[i][0]+3), (locs[i][1]-3):(locs[i][1]+3)] = 0
                    # Create a 10x10 hollow white box (outer perimeter)
                    copy[(locs[i][0]-5):(locs[i][0]+6), (locs[i][1]-5)] = 255  # Left vertical line
                    copy[(locs[i][0]-5):(locs[i][0]+6), (locs[i][1]+5)] = 255  # Right vertical line
                    copy[(locs[i][0]-5), (locs[i][1]-5):(locs[i][1]+6)] = 255  # Top horizontal line
                    copy[(locs[i][0]+5), (locs[i][1]-5):(locs[i][1]+6)] = 255  # Bottom horizontal line
                    plt.imshow(copy)
                    plt.show()
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
                
                              
                          
    def register_to_seed(self, images, bottom_trim : int = 100, search_margin : int = 60):
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
            how far (px) around the seed box to search; must exceed the worst expected jitter
        """
        h, w = images[0].shape
        tx1, tx2 = max(self.final_x1, 0), min(self.final_x2, w)
        ty1, ty2 = max(self.final_y1, 0), min(self.final_y2, h) - bottom_trim
        if ty2 - ty1 < 20: ty2 = min(self.final_y2, h) # box too short to trim; use it whole
        template = images[0][ty1:ty2, tx1:tx2]
        sx1, sy1 = max(tx1 - search_margin, 0), max(ty1 - search_margin, 0) # search window, fixed
        sx2, sy2 = min(tx2 + search_margin, w), min(ty2 + search_margin, h)

        self.offsets = []
        for img in images:
            res = cv2.matchTemplate(img[sy1:sy2, sx1:sx2], template, cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(res)
            self.offsets.append((sx1 + loc[0] - tx1, sy1 + loc[1] - ty1, score)) # shift vs frame 0

        dx = [o[0] for o in self.offsets]; dy = [o[1] for o in self.offsets]
        worst = min(o[2] for o in self.offsets)
        print(f"seed {self.seed_number}: jitter dx {min(dx)}..{max(dx)} px, dy {min(dy)}..{max(dy)} px "
              f"(template {tx2-tx1}x{ty2-ty1}, worst match {worst:.2f})")
        if worst < 0.5: print("  WARNING: weak template match on some frames -- offsets may be unreliable.")

    def _offset(self, frame_index : int):
        """(dx, dy) of `frame_index` vs frame 0; (0, 0) when the seed was never registered."""
        if not self.offsets or frame_index >= len(self.offsets): return 0, 0
        return self.offsets[frame_index][0], self.offsets[frame_index][1]

    def tip_trace_pcv(self, images_param, length : int = None, tot_length : int = None, threshold_multiplier : float = 1.5, bound_radius : int = 30):
        """
        Method to start tracking the root tip from the identified point of germination saved in each seed object.
        """
        
       
        # preprocess is a tuple of parameters in a specific order ex. ("blur", "canny", "resize")
        # images = images_param.copy() # IMPORTANT BUG FIX, pass by reference, aka lists are mutable
        images = images_param
        if length > tot_length - self.germination_frame:
            print("Requested length is longer than there is data for this seed. Will track as many frames as possible.")
            length = tot_length - self.germination_frame
            
        #coords = self.get_transform_crop_coords(x1=self.germination_x, y1=self.germination_y)
        #self.transform_crop_coords(self.germination_x - bound_radius, self.germination_x + bound_radius, self.germination_y - bound_radius, self.germination_y + bound_radius)
#         self.transform_crop_coords(-bound_radius, +bound_radius,-bound_radius, +bound_radius)
#         self.germination_x = int((coords.x1 + coords.x2)/2)
#         self.germination_y = int((coords.y1 + coords.y2)/2)
        gdx, gdy = self._offset(self._tracking_start_frame)
        gx, gy = self.germination_x - gdx, self.germination_y - gdy # germination point in frame-0 reference

        self.x1 = gx - bound_radius
        self.x2 = gx + bound_radius
        self.y1 = gy - bound_radius
        self.y2 = gy + bound_radius

        tip_coords = []
        tip_coords.append([gx, gy])
        last_x = bound_radius
        last_y = bound_radius
        try:
            count = 0
            for fi in range(self._tracking_start_frame, self._tracking_start_frame + length):
                dx, dy = self._offset(fi) # crop follows the jitter; self.x1/y1 stay frame-0 referenced
                image = images[fi][self.y1 + dy:self.y2 + dy, self.x1 + dx:self.x2 + dx]

                threshold_light = pcv.threshold.binary(gray_img=image, threshold=np.median(image)*threshold_multiplier, max_value=255, object_type='light') #try mean?
                binary_img = pcv.median_blur(gray_img=threshold_light, ksize=5)
                fill_image = pcv.fill(bin_img=binary_img, size=10)
                skeleton = pcv.morphology.skeletonize(mask=fill_image)
                tips_img = pcv.morphology.find_tips(skel_img=skeleton, mask=fill_image)
                #tips_img = tips_img[20:-20, 20:-20]
                locs = np.argwhere(tips_img > 0)
                
                #Here we take the index of the identified end-points and use np.linalg.norm to find the identified endpoint closest to the last identified tip.
                #This solves a problem when roots grow somewhat horizontally and the old way of just choosing the bottom-most endpoint would fail because sometimes the 
                #root starts to grow transiently upward as it circumnutates, which puts the actual tip above the endpoint found where the shootward section of the ro
                x = locs[np.argmin([np.linalg.norm([last_y, last_x] - l) for l in locs])][1]
                y = locs[np.argmin([np.linalg.norm([last_y, last_x] - l) for l in locs])][0]
                
                #old algorithm which fails when the root circumnutates while growing mostly horizontal
#                 x = locs[np.argmax(locs, axis =0)[0]][1]
#                 y = locs[np.argmax(locs, axis =0)[0]][0]
                

                #self.transform_crop_coords(x, x, y, y)
                self.transform_crop_coords(x - bound_radius, x + bound_radius, y - bound_radius, y + bound_radius)
                tip_coords.append([int((self.x2 + self.x1)/2), int((self.y2 + self.y1)/2)])
                last_x = x
                last_y = y
                count = count + 1
        except Exception as e: # was silent: a lost tip truncated the trace with no visible reason
            print(f"seed {self.seed_number}: tracking STOPPED at frame {self._tracking_start_frame + count} "
                  f"after {count}/{length} frames -- {e!r}")

        #print(tip_coords)
        self.tip_coords_pcv = tip_coords
        
    def make_video(self, images, path: str, trace_tip: bool = True):

        # pass by value immutable types, pass by reference mutable types
        # images list is mutable and passed by reference so there is a need to copy the list in order to avoid overwriting

        # convert to numpy object, this will keep self.images integrity
        #frames = np.array(images)
        frames = images.copy()
        
        final_frames = []

        frames = frames[(self._tracking_start_frame):(len(self.tip_coords_pcv) + self._tracking_start_frame - 1)]
        
        #print(len(frames))
        
        #This if statement should be before inner for loop below where cv2 places lines on images
        if trace_tip:
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

            fh, fw = frames[0].shape
            x1, y1 = max(int(x1), 0), max(int(y1), 0) # clamp INTO the frame (x2/y2 were clamped to 0, not fw/fh)
            x2, y2 = min(int(x2), fw), min(int(y2), fh)
            cw, ch = (x2 - x1) & ~1, (y2 - y1) & ~1 # constant size so every frame matches; even, because mp4v mangles odd dimensions

            for x in range(len(frames)):

                frame = np.copy(frames[x]) # copy: cv2.line below would otherwise burn the trace into
                                           # self.images, corrupting later seeds in the same box
                #ret,frame = cv2.threshold(frame,np.median(frame),255,cv2.THRESH_TOZERO)
                original = np.copy(frame)
                black = np.zeros_like(frame)
                dx, dy = self._offset(self._tracking_start_frame + x)
                #frame = Pillow.fromarray(frame, "RGB")
                # redraw lines in each frame, since base image is different
                for y in range(0, x):
                    #print(x)
                    if self.tip_coords_pcv[y][0] != 10000:
                        # coords are frame-0 referenced; += offset puts them on the root in THIS frame
                        cv2.line(frame, (self.tip_coords_pcv[y][0] + dx, self.tip_coords_pcv[y][1] + dy),
                                 (self.tip_coords_pcv[y + 1][0] + dx, self.tip_coords_pcv[y + 1][1] + dy),
                                 (255, 0, 0), 3)

                        cv2.line(black, (self.tip_coords_pcv[y][0] + dx, self.tip_coords_pcv[y][1] + dy),
                                 (self.tip_coords_pcv[y + 1][0] + dx, self.tip_coords_pcv[y + 1][1] + dy),
                                 (255, 0, 0), 3)

                # crop image based on boundaries, shifted by this frame's jitter so the OUTPUT is stabilized
                cx1 = min(max(int(x1) + dx, 0), max(fw - cw, 0))
                cy1 = min(max(int(y1) + dy, 0), max(fh - ch, 0))
                original = original[cy1:cy1 + ch, cx1:cx1 + cw]
                frame = frame[cy1:cy1 + ch, cx1:cx1 + cw]
                black = black[cy1:cy1 + ch, cx1:cx1 + cw]

                # cv2_videoWriter BGR color requirement
                buffer = np.full(np.shape(original), 255, dtype=np.uint8)[:,1:3]
                buffer = cv2.cvtColor(buffer, cv2.COLOR_GRAY2BGR)
                original = cv2.cvtColor(original, cv2.COLOR_GRAY2BGR)
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                black = cv2.cvtColor(black, cv2.COLOR_GRAY2BGR)
                
                complete = np.concatenate((original, buffer, frame, buffer, black), axis=1)
                
                final_frames.append(complete)
                #print(len(final_frames))
                #print(len(frames))

            print("___FRAME SIZE___", "x1", x1, "y1", y1, "x2", x2, "y2", y2)
            print("___PATH___", path)
        
        #save final frame for QC
        self.final_trace_img = final_frames[-1]
        
        # print(np.shape(final_frames[0]))
        io.make_video_cv2(final_frames, path)




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


