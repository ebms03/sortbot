import numpy as np


def transform_range(a):
    midpoint = 90
    true_range = 170
    supposed_range = 180
    return (a - midpoint) * true_range / supposed_range + midpoint


z0 = 11

tool_horizontal_offset = 3

l0 = 11.8
l1 = 16.7
l2 = 10.5

_a1 = -24
_a2 = -24 - _a1
_a3 = 35 - _a2
j_angle_offsets = np.array(
    (
        0,
        _a1,
        _a2,
        _a3,
        0,
    )
)
