import numpy as np

J_GRIPPER = 5
GRIPPER_CLOSE = 90
GRIPPER_OPEN = 130
HOME_ANGLES = np.array((90, 30, 170, 0, 90, GRIPPER_OPEN))


def transform_range(a):
    midpoint = 90
    true_range = 170
    supposed_range = 180
    return a
    return (a - midpoint) * true_range / supposed_range + midpoint


y0 = 3
z0 = 13

tool_horizontal_offset = 3

l0 = 11.8
l1 = 16.7
l2 = 10.5

_a1 = -16
_a2 = -19 - _a1
_a3 = 3 - _a2
j_angle_transforms = np.array(
    (
        lambda a: 180 - a + 5,
        lambda a: a + _a1,
        lambda a: a + _a2,
        lambda a: a + _a3,
        lambda a: a,
        lambda a: a,
    )
)
