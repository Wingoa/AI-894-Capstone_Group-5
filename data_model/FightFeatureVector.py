from dataclasses import dataclass

@dataclass(frozen=True)
class FightFeatureVector:
    fighter_id: str
    fighter_name: str
    sig_strikes_per_min: float
    td_attempts_per_min: float
    td_success_per_min: float
    ctrl_seconds_per_min: float
    sub_attempts_per_min: float
    distance_strikes_per_min: float
    clinch_strikes_per_min: float
    ground_strikes_per_min: float
    kd_per_min: float
    # The below ratios are defined as X per Significant Strike Landed
    distance_strikes_ratio: float
    clinch_strikes_ratio: float
    ground_strikes_ratio: float
    head_ratio: float
    body_ratio: float
    leg_ratio: float
    # The below ratios are defined as (X + 0.5) / (total_fights_fought + 1.0)
    ko_ratio: float
    sub_ratio: float
