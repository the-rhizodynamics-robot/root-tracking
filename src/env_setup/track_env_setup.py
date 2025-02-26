import sys
import os
from matplotlib import pyplot as plt
plt.rcParams['figure.figsize'] = [10, 10]

def setup_paths():
    # Add the /app/src directory to the Python path
    sys.path.append('/app/src')

    import src.myutilities.constants as c
    import src.myutilities.box as box
    import src.myutilities.util as util
    import src.retnet.model as model
    return c, box, util, model

def seed_localization_and_tip_tracking(data_path, seed_model):
    import src.myutilities.box as box
    import src.myutilities.util as util
    import gc

    box_list = util.listdir_nohidden(os.path.join(data_path, "stabilized"))
    outputs = []
    print(box_list)

    for expt in box_list:
        while True:
            track = input("Would you like to track box #" + str(expt) + "? (y) or (n): ")
            if track == "y" or track == "n":
                break
            else:
                print("Invalid character")
        if track == "y":
            box_path = os.path.join(data_path, "stabilized", expt, "")
            b = box.Box(box_path)
            b.init_seeds(seed_model, automatic=True)
            b.germination_detection(save_tip_sample=False, threshold_multiplier=1.5, automatic=False)
            b.tip_trace_pcv(384, threshold_multiplier=1.5, bound_radius=30)
            b.validate_save_tracking()
            del 
            gc.collect() 