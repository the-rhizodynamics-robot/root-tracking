import sys
import os
from matplotlib import pyplot as plt
import src.myutilities.box as box
import src.myutilities.util as util
import src.retnet.model as model
import gc
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
    automatic=False
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
    """
    box_list = util.listdir_nohidden(data_path)
    print("The following experiments are available for tracking:")
    print(box_list)

    for expt in box_list:
        while True:
            track = input("Would you like to track box #" + str(expt) + "? (y) or (n): ")
            if track == "y" or track == "n":
                break
            else:
                print("Invalid character")
        if track == "y":
            box_path = os.path.join(data_path, expt)
            b = box.Box(box_path)
            b.init_seeds(seed_model_obj, automatic=automatic)
            b.germination_detection(
                save_tip_sample=save_tip_sample,
                threshold_multiplier=germination_threshold_multiplier,
                automatic=automatic
            )
            b.tip_trace_pcv(
                length=tip_trace_length,
                threshold_multiplier=tip_trace_threshold_multiplier,
                bound_radius=tip_trace_bound_radius
            )
            b.validate_save_tracking()
            del b
            gc.collect()