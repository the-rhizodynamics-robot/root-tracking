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
from typing import List, Optional, Tuple, Dict

class Box:
    """The box class defines the data derived from a single magenta box in an experiment.
    
    Each magenta box contains between 1-5 seeds. The proposed position of the seeds is identified by
    a retinanet neural net model. The positions are verified by the user. Then a bubble searching 
    algorithm is implemented to locate the frame of germination with an appropriate root tip starting 
    location. For experiments where the seed is obscured (such as hyrdoponic growth where the seed is in 
    a holder) ro where the neural net fails to find one or more seeds, there is a grid based manual seed location method.
    """
    
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
        image_paths : list
            list of paths to all images in this experiment
        _image_cache : dict
            cache to store recently accessed images
        _cache_limit : int
            maximum number of images to keep in cache
        seeds : list
            list of seed objects within the box
        """
        self._path = path 
        self._qr_number = os.path.basename(os.path.normpath(self._path))
        self._save_path = os.path.normpath(save_path) + f"/{self._qr_number}"
        
        # Store image paths instead of loading all images
        self.image_paths = util.listdir_nohidden(self._path)
        self.image_paths = [os.path.join(self._path, l) for l in self.image_paths]
        
        # Image cache system
        self._image_cache = {}
        self._cache_limit = 20  # Adjust this number based on memory requirements
        
        # For compatibility with existing code
        self.seeds = []
    
    def get_image(self, index: int) -> np.ndarray:
        """
        Load an image by its index, using the cache if available.
        
        Parameters
        ----------
        index : int
            Index of the image to load
            
        Returns
        -------
        np.ndarray
            The image as a numpy array
        """
        # Check if the image is already in cache
        if index in self._image_cache:
            return self._image_cache[index]
        
        # Load the image
        if 0 <= index < len(self.image_paths):
            image = io.read_image_single_channel(self.image_paths[index])
            
            # Add to cache
            if len(self._image_cache) >= self._cache_limit:
                # Remove the least recently used image (simple implementation)
                oldest_key = next(iter(self._image_cache))
                del self._image_cache[oldest_key]
            
            self._image_cache[index] = image
            return image
        else:
            raise IndexError(f"Image index {index} out of range (0-{len(self.image_paths)-1})")
    
    def get_images(self, start_idx: int, end_idx: int) -> List[np.ndarray]:
        """
        Get a range of images using parallel loading for efficiency.
        
        Parameters
        ----------
        start_idx : int
            Starting index (inclusive)
        end_idx : int
            Ending index (exclusive)
            
        Returns
        -------
        List[np.ndarray]
            List of loaded images
        """
        # Validate indices
        if start_idx < 0 or end_idx > len(self.image_paths) or start_idx >= end_idx:
            raise IndexError(f"Invalid range: {start_idx} to {end_idx}")
        
        # Check which images are already cached
        to_load = [i for i in range(start_idx, end_idx) if i not in self._image_cache]
        
        # Load missing images in parallel
        if to_load:
            paths_to_load = [self.image_paths[i] for i in to_load]
            with concurrent.futures.ThreadPoolExecutor() as executor:
                loaded_images = executor.map(io.read_image_single_channel, paths_to_load)
                
            # Update cache with newly loaded images
            for idx, img in zip(to_load, loaded_images):
                if len(self._image_cache) >= self._cache_limit:
                    oldest_key = next(iter(self._image_cache))
                    del self._image_cache[oldest_key]
                self._image_cache[idx] = img
        
        # Return all images in the requested range
        return [self._image_cache[i] for i in range(start_idx, end_idx)]
    
    def get_first_image(self) -> np.ndarray:
        """Get the first image for seed detection and initialization."""
        return self.get_image(0)
    
    def get_last_image(self) -> np.ndarray:
        """Get the last image for manual seed detection."""
        return self.get_image(len(self.image_paths) - 1)
    
    def get_total_images(self) -> int:
        """Get the total number of images."""
        return len(self.image_paths)
        
    def init_seeds(self, seed_model: retnet.SeedModel, automatic: bool = True):
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
            initial_image = np.copy(self.get_first_image())
            y,x = initial_image.shape
            startx = x//2-(1000)
            initial_image[:,0:startx] = 0
            initial_image[:,(startx+2000):x] = 0
            seeds_full, scores = seed_model.detect(image_arr=cv2.cvtColor(initial_image, cv2.COLOR_GRAY2BGR),
                                          sort=True)
            
            disp = cv2.cvtColor(self.get_first_image(), cv2.COLOR_GRAY2BGR)
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
          
            first_image = self.get_first_image()
            for count, seed in enumerate(seeds):
                if ((seed.y1 > (.1 * np.shape(first_image)[0])) and (seed.y1 < (.9 * np.shape(first_image)[0]))):
                    if ((seed.x1 > (.1 * np.shape(first_image)[1])) and (seed.x1 < (.9 * np.shape(first_image)[1]))):
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
        
        first = cv2.cvtColor(self.get_first_image(), cv2.COLOR_GRAY2BGR)
        last = cv2.cvtColor(self.get_last_image(), cv2.COLOR_GRAY2BGR)
        
        for r in range(0, np.shape(first)[1], 500):
            first = cv2.line(first, (r, 0), (r, np.shape(first)[0]), (0, 255, 0), thickness=5) 
            last = cv2.line(last, (r, 0), (r, np.shape(last)[0]), (0, 255, 0), thickness=5) 
            
        for r in range(0, np.shape(first)[0], 500):
            first = cv2.line(first, (0, r), (np.shape(first)[1], r), (0, 255, 0), thickness=5) 
            last = cv2.line(last, (0, r), (np.shape(last)[1], r), (0, 255, 0), thickness=5) 
        
        disp = np.concatenate((first, last), axis = 1)
        plt.imshow(disp)
        plt.show()
        
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


    def germination_detection(self, save_tip_sample: bool = False, threshold_multiplier: float = 1.5, save_path: str = None, automatic: bool = True):
        """
        Detect germination for each seed.
        
        Parameters
        ----------
        save_tip_sample : bool
            Whether to save tip samples
        threshold_multiplier : float
            Multiplier for thresholding
        save_path : str
            Path to save results
        automatic : bool
            Whether to use automatic detection
        """
        count = 1
        if save_path is None:
            save_path = self._save_path
        for seed in self.seeds:
            seed.germination_detection(self, count, save_path, threshold_multiplier=threshold_multiplier, automatic=automatic)
            count += 1

    def tip_trace_pcv(self, length: int = None, threshold_multiplier: float = 1.5, bound_radius: int = 30):
        """
        Trace the tip of each germinated seed.
        
        Parameters
        ----------
        length : int
            Number of frames to trace
        threshold_multiplier : float
            Multiplier for thresholding
        bound_radius : int
            Radius for bounding box
        """
        count = 1
        for seed in self.seeds:
            if seed.germination_indicator:
                seed.tip_trace_pcv(self, length=length, tot_length=self.get_total_images(), 
                                  threshold_multiplier=threshold_multiplier, bound_radius=bound_radius)
                # Get only the frames needed for the video
                start_frame = seed._tracking_start_frame
                end_frame = start_frame + len(seed.tip_coords_pcv)
                images_for_video = self.get_images(start_frame, end_frame)
                seed.make_video(images_for_video, "/app/results/stabilized_videos_single_seed" + f"/{self._qr_number}_{count}.mp4", trace_tip=True)
            count = count + 1

    def make_video(self, save_path: str = None, trace_tip: bool = False):
        """
        Make videos for each seed.
        
        Parameters
        ----------
        save_path : str
            Path to save videos
        trace_tip : bool
            Whether to trace tip in videos
        """
        count = 1
        for seed in self.seeds:
            if save_path is None:
                save_path = self._save_path
                
            # Only load the frames needed for this seed's video
            start_frame = seed._tracking_start_frame
            end_frame = start_frame + len(seed.tip_coords_pcv)
            images_for_video = self.get_images(start_frame, end_frame)
            
            seed.make_video(images_for_video, save_path + f"/{self._qr_number}_tiptrace_seed{count}.mp4", trace_tip=trace_tip)
            count += 1

    def validate_save_tracking(self):
        """
        Validate tracking results and save coordinates if valid.
        """
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
                elif save1 =="c":
                    first = 0
                    last = self.get_total_images() - 1
                    x_tip_coords = s.tip_coords_pcv[0:,0]
                    y_tip_coords = s.tip_coords_pcv[0:,1]
                    x1 = min(x_tip_coords) - 50
                    x2 = max(x_tip_coords) + 50
                    y1 = min(y_tip_coords) - 50
                    y2 = max(y_tip_coords) + 50
                    while True:
                        mid = int((first + last)/2)
                        # Load just the needed image for this binary search step
                        frame = self.get_image(mid)
                        plt.imshow(frame[y1:y2, x1:x2])
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
                            last = self.get_total_images() - 1
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

    def denoise_all(self):
        """
        Denoise all images using parallel processing.
        This is a resource-intensive operation, so we load images in batches.
        """
        start = time.time()
        batch_size = 10  # Adjust based on available memory
        total_images = self.get_total_images()
        
        for start_idx in range(0, total_images, batch_size):
            end_idx = min(start_idx + batch_size, total_images)
            batch = self.get_images(start_idx, end_idx)
            
            with concurrent.futures.ProcessPoolExecutor() as executor:
                denoised_batch = list(executor.map(retnet.TipModel.denoise, batch))
            
            # Update cache with denoised images
            for i, img in enumerate(denoised_batch):
                self._image_cache[start_idx + i] = img
        
        print("Denoising time:", time.time() - start)

    def to_dict(self):
        """
        Convert box to dictionary for serialization.
        
        Returns
        -------
        dict
            Dictionary representation of the box
        """
        seeds = [i.to_dict() for i in self.seeds]
        return {
            "path": self._path,
            "qr_number": self._qr_number,
            "save_path": self._save_path,
            "seeds": seeds
        }

    @classmethod
    def from_dict(cls, dct: dict):
        """
        Create box from dictionary.
        
        Parameters
        ----------
        dct : dict
            Dictionary representation of the box
            
        Returns
        -------
        Box
            Box object
        """
        box = cls(dct.get("path"), dct.get("save_path"))
        seeds = dct.get("seeds")
        final_seeds = []
        
        # Load just the first image for seed initialization
        first_image = box.get_first_image()
        
        for seed_dct in seeds:
            seed = Seed.from_dict(seed_dct, first_image)
            final_seeds.append(seed)
        box.seeds = final_seeds
        return box

class Seed(Image):
    """
    Class representing a seed and its tracking data.
    """

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

    def germination_detection(self, box, seed_number, save_path: str, threshold_multiplier: float = 1.5, 
                             save_tip_sample: bool = False, automatic: bool = True):
        """
        Detect germination frame and position for this seed.
        
        Parameters
        ----------
        box : Box
            The box containing this seed
        seed_number : int
            Number of the seed
        save_path : str
            Path to save results
        threshold_multiplier : float
            Multiplier for thresholding
        save_tip_sample : bool
            Whether to save tip samples
        automatic : bool
            Whether to use automatic detection
        """
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
            last = box.get_total_images() - 1
            while True:
                mid = int((first + last)/2)
                # Load just the image we need for this step
                image = box.get_image(mid)
                plt.imshow(image[self.y1:self.y2, self.x1:self.x2])
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
                    last = box.get_total_images() - 1
                elif direction == "a":
                    first = mid
                elif direction == "b":
                    last = mid
                
            if self.germination_indicator:                    
                # Get the image at the germination frame
                germination_image = box.get_image(self._tracking_start_frame)
                proposed = np.copy(germination_image[self.y1:self.y2, self.x1:self.x2])
                threshold_light = pcv.threshold.binary(gray_img=proposed, threshold=np.median(germination_image)*threshold_multiplier, max_value=255, object_type='light')
                binary_img = pcv.median_blur(gray_img=threshold_light, ksize=5)
                fill_image = pcv.fill(bin_img=binary_img, size=10)
                skeleton = pcv.morphology.skeletonize(mask=fill_image)
                tips_img = pcv.morphology.find_tips(skel_img=skeleton, mask=fill_image)
                locs = np.argwhere(tips_img > 0)
                             
                i = len(locs) - 1
                while i < len(locs):
                    copy = np.copy(proposed)
                    copy[(locs[i][0]-3):(locs[i][0]+3), (locs[i][1]-3):(locs[i][1]+3)] = 0
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
                
                              
                          
    def tip_trace_pcv(self, box, length: int = None, tot_length: int = None, 
                     threshold_multiplier: float = 1.5, bound_radius: int = 30):
        """
        Method to start tracking the root tip from the identified point of germination saved in each seed object.
        
        Parameters
        ----------
        box : Box
            The box containing this seed
        length : int
            Number of frames to trace
        tot_length : int
            Total number of frames available
        threshold_multiplier : float
            Multiplier for thresholding
        bound_radius : int
            Radius for bounding box
        """
        if length > tot_length - self.germination_frame:
            print("Requested length is longer than there is data for this seed. Will track as many frames as possible.")
            length = tot_length - self.germination_frame
            
        self.x1 = self.germination_x - bound_radius
        self.x2 = self.germination_x + bound_radius
        self.y1 = self.germination_y - bound_radius
        self.y2 = self.germination_y + bound_radius
        
        tip_coords = []
        tip_coords.append([self.germination_x, self.germination_y])
        last_x = bound_radius
        last_y = bound_radius
        try:
            # Process frames sequentially, loading each as needed
            for frame_idx in range(self._tracking_start_frame, self._tracking_start_frame + length):
                # Load just the current frame
                image = box.get_image(frame_idx)
                image = image[self.y1:self.y2, self.x1:self.x2]

                threshold_light = pcv.threshold.binary(gray_img=image, threshold=np.median(image)*threshold_multiplier, max_value=255, object_type='light')
                binary_img = pcv.median_blur(gray_img=threshold_light, ksize=5)
                fill_image = pcv.fill(bin_img=binary_img, size=10)
                skeleton = pcv.morphology.skeletonize(mask=fill_image)
                tips_img = pcv.morphology.find_tips(skel_img=skeleton, mask=fill_image)
                locs = np.argwhere(tips_img > 0)
                
                # Find the tip closest to the previous location
                x = locs[np.argmin([np.linalg.norm([last_y, last_x] - l) for l in locs])][1]
                y = locs[np.argmin([np.linalg.norm([last_y, last_x] - l) for l in locs])][0]
                
                self.transform_crop_coords(x - bound_radius, x + bound_radius, y - bound_radius, y + bound_radius)
                tip_coords.append([int((self.x2 + self.x1)/2), int((self.y2 + self.y1)/2)])
                last_x = x
                last_y = y
        except Exception as e: 
            print(e)
            
        self.tip_coords_pcv = tip_coords
        
    def make_video(self, images, path: str, trace_tip: bool = True):
        """
        Create a video of the seed germination and root growth.
        
        Parameters
        ----------
        images : List[np.ndarray]
            List of images to use for the video
        path : str
            Path to save the video
        trace_tip : bool
            Whether to trace the tip in the video
        """
        # Make a copy of the images to avoid modifying the originals
        frames = images.copy()
        final_frames = []
        
        # This if statement should be before inner for loop below where cv2 places lines on images
        if trace_tip:
            self.tip_coords_pcv = np.asarray(self.tip_coords_pcv)
            x_tip_coords = self.tip_coords_pcv[0:,0]
            y_tip_coords = self.tip_coords_pcv[0:,1]

            # calculate crop boundaries for tip video
            x1 = min(x_tip_coords) - 50
            x2 = max(x_tip_coords) + 50
            y1 = min(y_tip_coords) - 50
            y2 = max(y_tip_coords) + 50

            if x1 < 0:
                x1 = 0
            if x2 < 0:
                x2 = 0
            if y1 < 0:
                y1 = 0
            if y2 < 0:
                y2 = 0

            for x in range(len(frames)):
                frame = frames[x]
                original = np.copy(frame)
                black = np.zeros_like(frame)
                
                # Redraw lines in each frame, since base image is different
                for y in range(0, x):
                    if self.tip_coords_pcv[y][0] != 10000:
                        cv2.line(frame, (self.tip_coords_pcv[y][0], self.tip_coords_pcv[y][1]),
                                 (self.tip_coords_pcv[y + 1][0], self.tip_coords_pcv[y + 1][1]),
                                 (255, 0, 0), 3)

                        cv2.line(black, (self.tip_coords_pcv[y][0], self.tip_coords_pcv[y][1]),
                                 (self.tip_coords_pcv[y + 1][0], self.tip_coords_pcv[y + 1][1]),
                                 (255, 0, 0), 3)
                        
                # Crop image based on boundaries
                original = original[y1:y2, x1:x2]
                frame = frame[y1:y2, x1:x2]
                black = black[y1:y2, x1:x2]

                # cv2_videoWriter BGR color requirement
                buffer = np.full(np.shape(original), 255, dtype=np.uint8)[:,1:3]
                buffer = cv2.cvtColor(buffer, cv2.COLOR_GRAY2BGR)
                original = cv2.cvtColor(original, cv2.COLOR_GRAY2BGR)
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                black = cv2.cvtColor(black, cv2.COLOR_GRAY2BGR)
                
                complete = np.concatenate((original, buffer, frame, buffer, black), axis=1)
                
                final_frames.append(complete)

            print("___FRAME SIZE___", "x1", x1, "y1", y1, "x2", x2, "y2", y2)
            print("___PATH___", path)
        
        # Save final frame for QC
        self.final_trace_img = final_frames[-1]
        
        io.make_video_cv2(final_frames, path)

    def to_dict(self):
        """
        Convert seed to dictionary for serialization.
        
        Returns
        -------
        dict
            Dictionary representation of the seed
        """
        tip_coords = self.tip_coords
        if isinstance(tip_coords, np.ndarray):
            tip_coords = tip_coords.tolist()
            
        tip_coords = [self.array_to_dict(i) for i in tip_coords]

        return {
            "germination_frame": self._tracking_start_frame,
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
    def dict_to_array(dct: dict):
        return dct.get("coord")

    @classmethod
    def from_dict(cls, dct: dict, image):
        """
        Create seed from dictionary.
        
        Parameters
        ----------
        dct : dict
            Dictionary representation of the seed
        image : np.ndarray
            First image for initialization
            
        Returns
        -------
        Seed
            Seed object
        """
        mi = Image(image)
        mi.set_crop(dct.get("x1"), dct.get("x2"), dct.get("y1"), dct.get("y2"))
        seed = cls(mi, dct.get("qr_number"), dct.get("seed_number"))
        seed._tracking_start_frame = dct.get("germination_frame")
        seed.germination_x = dct.get("germination_x")
        seed.germination_y = dct.get("germination_y")

        # Convert array[map(array[])] back to array[array[]]
        tip_coords_arr = dct.get("tip_coords")
        tip_coords = [cls.dict_to_array(i) for i in tip_coords_arr]
        seed.tip_coords = tip_coords

        return seed