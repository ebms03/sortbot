def pick_up_at(x, y, phi, dz=5):
    return [
        lambda arm: arm.move_to(x, y, dz, phi),
        lambda arm: arm.open_gripper(),
        lambda arm: arm.move_to(x, y, 0, phi),
        lambda arm: arm.close_gripper(),
        lambda arm: arm.move_to(x, y, dz, phi),
    ]


def drow_off_at(x, y, phi, dz=5):
    return [
        lambda arm: arm.move_to(x, y, dz, phi),
        lambda arm: arm.move_to(x, y, 0, phi),
        lambda arm: arm.open_gripper(),
        lambda arm: arm.move_to(x, y, dz, phi),
    ]


def home():
    return [
        lambda arm: arm.home(),
    ]
