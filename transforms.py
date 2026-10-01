from arm_config import y0

# measured once, always place camera same height above floor and use same resolution anyways
assumed_resolution = (1920, 1080)
_px_to_cm = 20 / (36**2 + 552**2) ** 0.5


# world (0, 0) is center of frame...
def pos_camera_to_world(cx, cy):
    x = cx + 0.5 - assumed_resolution[0] / 2
    y = assumed_resolution[1] / 2 - cy - 0.5
    return x * _px_to_cm, y * _px_to_cm


# robot (0, 0) is j0 pivot, which is y0 behind the "front of the base"
def pos_world_to_robot(wx, wy):
    return wx, wy - y0


def pos_camera_to_robot(cx, cy):
    return pos_world_to_robot(*pos_camera_to_world(cx, cy))


# x and y axes are aligned but y is flipped
def angle_camera_to_world(ca):
    return -ca


# x and y axes are aligned
def angle_world_to_robot(wa):
    return wa


def angle_camera_to_robot(ca):
    return angle_world_to_robot(angle_camera_to_world(ca))
