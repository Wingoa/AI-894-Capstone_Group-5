from dataclasses import dataclass
from typing import Iterator

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

    def __iter__(self) -> Iterator[object]:
        yield self.fighter_id
        yield self.fighter_name
        yield self.sig_strikes_per_min
        yield self.td_attempts_per_min
        yield self.td_success_per_min
        yield self.ctrl_seconds_per_min
        yield self.sub_attempts_per_min
        yield self.distance_strikes_per_min
        yield self.clinch_strikes_per_min
        yield self.ground_strikes_per_min
        yield self.kd_per_min
        yield self.distance_strikes_ratio
        yield self.clinch_strikes_ratio
        yield self.ground_strikes_ratio
        yield self.head_ratio
        yield self.body_ratio
        yield self.leg_ratio
        yield self.ko_ratio
        yield self.sub_ratio
