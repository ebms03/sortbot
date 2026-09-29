import numpy as np

z0 = 11

l0 = 11.8
l1 = 16.7
l2 = 10.5

l_z_offset = 2.85
l0_angle_offset = np.asin(l_z_offset / l0)
l1_angle_offset = np.asin(l_z_offset / l1)


def inverse_kinematics(target_x, target_y, target_z, target_phi):
    j0 = np.atan2(target_x, target_y)

    x = np.hypot(target_x, target_y)
    y = target_z + l2 - z0
    d = np.hypot(x, y)
    # l0**2 + l1**2 = d**2 + 2*l0*l1*cos(gamma)
    if -1 <= (temp := (l0**2 + l1**2 - d**2) / (2 * l0 * l1)) <= 1:
        gamma = np.acos(temp)
    else:
        return None
    # sin(alpha)/l1 == sin(gamma)/d == sin(beta)/l0
    alpha = np.asin(l1 * np.sin(gamma) / d)
    alpha_1 = np.sin(y / d)
    alpha_2 = gamma - j1

    j1 = np.pi - alpha - alpha_1
    j2 = np.pi - gamma
    j3 = np.pi/2 + alpha_2
    
    j4 = alpha_1 + target_phi
    
    return j0, j1 - l0_angle_offset, j2 - l1_angle_offset, j3, j4
