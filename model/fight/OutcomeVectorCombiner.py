"""
This class serves to combine the data from outcome_vectors into single rows of fight data:

[Fa,Fb,Fa-Fb,Fa*Fb]
"""

import pandas as pd
import numpy as np

from typing import List

def combine_features(fighter_a: dict, fighter_b: dict) -> List:
    combined_vector = {}
    combined_vector["muay_thai_A"] = fighter_a["muay_thai"]
    combined_vector["muay_thai_B"] = fighter_b["muay_thai"]
    combined_vector["muay_thai_inter"] = fighter_a["muay_thai"] * fighter_b["muay_thai"]
    combined_vector["muay_thai_diff"] = fighter_a["muay_thai"] - fighter_b["muay_thai"]
    combined_vector["boxing_A"] = fighter_a["boxing"]
    combined_vector["boxing_B"] = fighter_b["boxing"]
    combined_vector["boxing_inter"] = fighter_a["boxing"] * fighter_b["boxing"]
    combined_vector["boxing_diff"] = fighter_a["boxing"] - fighter_b["boxing"]
    combined_vector["wrestling_A"] = fighter_a["wrestling"]
    combined_vector["wrestling_B"] = fighter_b["wrestling"]
    combined_vector["wrestling_inter"] = fighter_a["wrestling"] * fighter_b["wrestling"]
    combined_vector["wrestling_diff"] = fighter_a["wrestling"] - fighter_b["wrestling"]
    combined_vector["grappling_A"] = fighter_a["grappling"]
    combined_vector["grappling_B"] = fighter_b["grappling"]
    combined_vector["grappling_inter"] = fighter_a["grappling"] * fighter_b["grappling"]
    combined_vector["grappling_diff"] = fighter_a["grappling"] - fighter_b["grappling"]
    combined_vector["pace_A"] = fighter_a["pace"]
    combined_vector["pace_B"] = fighter_b["pace"]
    combined_vector["pace_inter"] = fighter_a["pace"] * fighter_b["pace"]
    combined_vector["pace_diff"] = fighter_a["pace"] - fighter_b["pace"]
    combined_vector["td_success_A"] = fighter_a["td_success"]
    combined_vector["td_success_B"] = fighter_b["td_success"]
    combined_vector["td_success_inter"] = fighter_a["td_success"] * fighter_b["td_success"]
    combined_vector["td_success_diff"] = fighter_a["td_success"] - fighter_b["td_success"]
    combined_vector["ctrl_share_A"] = fighter_a["ctrl_share"]
    combined_vector["ctrl_share_B"] = fighter_b["ctrl_share"]
    combined_vector["ctrl_share_inter"] = fighter_a["ctrl_share"] * fighter_b["ctrl_share"]
    combined_vector["ctrl_share_diff"] = fighter_a["ctrl_share"] - fighter_b["ctrl_share"]
    combined_vector["n_fights_norm_A"] = fighter_a["n_fights_norm"]
    combined_vector["n_fights_norm_B"] = fighter_b["n_fights_norm"]
    combined_vector["n_fights_norm_inter"] = fighter_a["n_fights_norm"] * fighter_b["n_fights_norm"]
    combined_vector["n_fights_norm_diff"] = fighter_a["n_fights_norm"] - fighter_b["n_fights_norm"]

    # Create a DF
    df = pd.DataFrame([combined_vector])
    return df.to_numpy(dtype=np.float32).tolist()



if __name__ == "__main__":
    createTrainingData()