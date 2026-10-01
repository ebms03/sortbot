def pick_up_at(x, y, phi, dz=10):
    return [
        lambda arm: arm.move_to(x, y, dz, phi),
        lambda arm: arm.open_gripper(),
        lambda arm: arm.move_to(x, y, 0, phi),
        lambda arm: arm.close_gripper(),
        lambda arm: arm.move_to_(x, y, dz, phi),
    ]


def drow_off_at(x, y, phi, dz=10):
    return [
        lambda arm: arm.move_to(x, y, dz, phi),
        lambda arm: arm.move_to(x, y, 0, phi),
        lambda arm: arm.open_gripper(),
        lambda arm: arm.move_to(x, y, dz, phi),
    ]
