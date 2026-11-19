"""Supported pre-turn polar reference fitted without the evaluated day."""

import numpy as np
from .dataset import assemble_dataset
from .fitting import _fit_and_predict_subset


class HeldOutReference:
    def __init__(self, details):
        self.dataset = assemble_dataset(details)
        self.models = {}
        self.grid = (
            {}
            if self.dataset is None
            else {tuple(row): i for i, row in enumerate(self.dataset.grid_keys)}
        )

    def __call__(self, sample):
        ds = self.dataset
        if ds is None:
            return None
        day = sample["date"]
        if day not in self.models:
            training = ds.date != day
            if not np.any(training):
                return None
            self.models[day] = _fit_and_predict_subset(ds, training)
        model = self.models[day]
        mode = int(sample["mode"] == "upwind")
        key = (mode, round(sample["tws_kt"]), round(sample["abs_twa_deg"] / 2.5) * 2.5)
        index = self.grid.get(key)
        if index is None or model["grid_support"][index] < 12 or model["grid_clusters"][index] < 2:
            return None
        effect = model["tack_effect"][mode][0] * (0.5 if sample["tack"] == "STARBOARD" else -0.5)
        return {
            "sog_kt": float(model["grid_mean_sog"][index] + effect),
            "evaluation_scope": "leave_one_day_out",
            "excluded_day": day,
            "support": {
                "weighted_seconds": float(model["grid_support"][index]),
                "boat_leg_clusters": int(model["grid_clusters"][index]),
            },
        }
