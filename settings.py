from dataclasses import dataclass
import os, json
from typing import Any

import numpy as np


@dataclass
class Setting:
    value: Any
    range: tuple


_SETTINGS_PATH = "settings.json"
_BACKGOUNR_PATH = "background.npy"

BLUR_SIZE = "Blur size"
MORPH_SIZE = "Morph size"
MIN_AREA = "Min Area"


class Settings:

    def __init__(self):
        self._settings = {
            BLUR_SIZE: Setting(4, (0, 20)),
            MORPH_SIZE: Setting(4, (0, 20)),
            MIN_AREA: Setting(10, (0, 100)),
        }
        self.bg = None
        self.roi = None  # (x1, y1, x2, y2) in full-frame pixels, None = full frame

    def values(self):
        return {k: v.value for k, v in self._settings.items()}

    def update(self, values):
        for k, v in self._settings.items():
            if k in values:
                v.value = values[k]

    def capture_bg(self, frame):
        self.bg = frame.copy()

    def crop(self, frame):
        """Crop a full frame down to the current ROI."""
        if self.roi is None:
            return frame
        x1, y1, x2, y2 = self.roi
        return frame[y1:y2, x1:x2]

    def __getitem__(self, key):
        return self._settings[key].value

    def items(self):
        return self._settings.items()


def load_settings():
    settings = Settings()
    if os.path.exists(_SETTINGS_PATH):
        with open(_SETTINGS_PATH, "r") as f:
            overrides = json.load(f)
            settings.update(overrides)
    if os.path.exists(_BACKGOUNR_PATH):
        bg = np.load(_BACKGOUNR_PATH)
        settings.bg = bg
    return settings


def save_settings(settings):
    with open(_SETTINGS_PATH, "w+") as f:
        json.dump(settings.values(), f, indent=2)
    if settings.bg is not None:
        np.save(_BACKGOUNR_PATH, settings.bg)
