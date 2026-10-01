import numpy as np


def transform_range(a):
    midpoint = 90
    true_range = 170
    supposed_range = 180
    return (a - midpoint) * true_range / supposed_range + midpoint


z0 = 11

l0 = 11.8
l1 = 16.7
l2 = 10.5

l_z_offset = 2.85
j_angle_offsets = np.array(
    (
        0,
        -np.degrees(np.asin(l_z_offset / l0)) - 5,
        -np.degrees(np.asin(l_z_offset / l1)) - 3,
        20,
        0,
    )
)
