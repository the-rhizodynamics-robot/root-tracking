import sys
import os
from matplotlib import pyplot as plt
import src.myutilities.box as box
import src.myutilities.util as util
import src.retnet.model as model
import gc
from IPython.display import clear_output
seed_model_obj = model.SeedModel("/app/models/SeedInference.h5")

plt.rcParams['figure.figsize'] = [10, 10]
data_dir = '/app/data'
results_dir = '/app/results'

def seed_localization_and_tip_tracking(
    data_path,
    germination_threshold_multiplier=1.5,
    tip_trace_length=384,
    tip_trace_threshold_multiplier=1.5,
    tip_trace_bound_radius=30,
    save_tip_sample=False,
    automatic=False,
    stabilize=True,
    stabilize_bottom_trim=100,
    stabilize_search_margin=200
):
    """
    Function to localize seeds and track root tips with specified parameters.

    Parameters:
    - data_path (str): Path to the data directory.
    - germination_threshold_multiplier (float): Threshold multiplier for germination detection.
    - tip_trace_length (int): Length of the tip trace.
    - tip_trace_threshold_multiplier (float): Threshold multiplier for tip tracing.
    - tip_trace_bound_radius (int): Bound radius for tip tracing.
    - save_tip_sample (bool): Whether to save tip samples.
    - automatic (bool): Whether to run in automatic mode.
    - stabilize (bool): Register each seed to frame 0 to remove residual gantry jitter locally.
    - stabilize_bottom_trim (int): Px trimmed off the bottom of the seed box (the root-growth region)
      before it is used as the registration template.
    - stabilize_search_margin (int): Px searched around the seed box; must exceed the worst jitter.
    """
    box_list = util.listdir_nohidden(data_path)

    for expt in box_list:
        clear_output() # the previous box's images and prompts go: one screen per step
        print("The following experiments are available for tracking:", box_list)
        while True:
            track = input("Would you like to track box #" + str(expt) + "? (y) or (n): ")
            if track == "y" or track == "n":
                break
            else:
                print("Invalid character")
        if track == "y":
            box_path = os.path.join(data_path, expt)
            b = box.Box(box_path)
            b.init_seeds(seed_model_obj, automatic=automatic)   # auto seed bounding boxes (honors `automatic`)
            if stabilize: b.start_registration(stabilize_bottom_trim, stabilize_search_margin) # background pass over the frames while you pick germination frames
            # Germination detection is ALWAYS manual: the automatic path in
            # Seed.germination_detection() is an unfinished stub that returns without
            # setting a germination frame, which silently skips tip tracing + saving.
            b.germination_detection(
                save_tip_sample=save_tip_sample,
                threshold_multiplier=germination_threshold_multiplier,
                automatic=False
            )
            b.tip_trace_pcv(
                length=tip_trace_length,
                threshold_multiplier=tip_trace_threshold_multiplier,
                bound_radius=tip_trace_bound_radius,
                stabilize=stabilize,
                stabilize_bottom_trim=stabilize_bottom_trim,
                stabilize_search_margin=stabilize_search_margin
            )
            b.validate_save_tracking()
            del b
            gc.collect()