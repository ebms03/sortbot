from arm_config import *


def inverse_kinematics(target_x, target_y, target_z, target_phi):
    # set offset "beheind tool" so gripper extends to target
    offset_x = target_x #- np.cos(np.radians(target_phi)) * tool_horizontal_offset
    offset_y = target_y #- np.sin(np.radians(target_phi)) * tool_horizontal_offset

    # "yaw"
    j0 = np.atan2(offset_y, offset_x)

    # reach in 2d plane
    x = np.hypot(offset_x, offset_y)
    y = target_z + l2 - z0
    d = np.hypot(x, y)
    # l0**2 + l1**2 = d**2 + 2*l0*l1*cos(gamma)
    if -1 <= (temp := (l0**2 + l1**2 - d**2) / (2 * l0 * l1)) <= 1:
        gamma = np.acos(temp)
    else:
        return None
    # sin(alpha)/l1 == sin(gamma)/d == sin(beta)/l0
    alpha = np.asin(l1 * np.sin(gamma) / d)
    alpha_1 = np.asin(y / d)
    j1 = np.pi - alpha - alpha_1

    j2 = np.pi - gamma

    # point tool down
    j3 = 3 * np.pi / 2 - j1 - j2

    # tool "yaw"
    j4 = j0 + np.radians(target_phi) - np.pi / 2

    res = np.degrees(np.array((j0, j1, j2, j3, j4)))
    print(res)
    return res


if __name__ == "__main__":
    print(inverse_kinematics(0, l1, z0 - l2 + l0, 90))
