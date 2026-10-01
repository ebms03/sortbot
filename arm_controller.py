from ik import inverse_kinematics
from arm_config import (
    j_angle_offsets,
    transform_range,
    HOME_ANGLES,
    J_GRIPPER,
    GRIPPER_CLOSE,
    GRIPPER_OPEN,
)

import threading
import time
from enum import IntEnum
import numpy as np
import serial

MOVE_TIMEOUT = 30


class ArmStatus(IntEnum):
    """Return value of move_to()/move_joints(). 0 = OK, <0 = no motion started."""

    OK = 0
    OUT_OF_REACH = -1  # target not achievable (incl. joint-limit failures)
    BUSY = -2  # previous move still in flight
    SERIAL_ERROR = -3  # port not open / write failed
    BAD_ARG = -4  # malformed command


class ArmController:

    def __init__(self, port, baudrate=115200, debug=False):
        self.debug = debug
        self._ser = serial.Serial(port, baudrate, timeout=0.05)
        self._lock = threading.Lock()
        self.on_done = None  # optional callback: on_done(joint_index)
        self._running = True  # reader thread stop flag
        self._alive = True  # serial link healthy flag
        self._pending = set()  # joints still moving / awaiting "done"
        self._move_t0 = 0.0
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    # ------------------------------------------------------------------ #
    # background reader thread: consumes "done j", clears pending set
    # ------------------------------------------------------------------ #
    def _reader_loop(self):
        buf = b""
        while self._running:
            try:
                chunk = self._ser.read(64)
            except (serial.SerialException, OSError):
                if self._running:
                    self._alive = False
                break
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                self._handle(raw.decode("ascii", errors="ignore").strip())

    def _handle(self, line):
        if self.debug and line:
            print("<<", line)
        parts = line.split()
        if len(parts) == 2 and parts[0].lower() == "done":
            try:
                j = int(parts[1])
            except ValueError:
                return
            with self._lock:
                was_pending = j in self._pending
                self._pending.discard(j)
            if was_pending and self.on_done:  # echo live "done" messages
                try:
                    self.on_done(j)
                except Exception:
                    pass
        # any other firmware output is ignored

    # ------------------------------------------------------------------ #
    # command issue path (shared by move_to / move_joints)
    # ------------------------------------------------------------------ #
    def _send_move(self, j, a_deg):
        a = int(round(transform_range(a_deg + j_angle_offsets[j])))
        cmd = f"m {j} {a}\n"
        if self.debug:
            print(">>", cmd.strip())
        self._ser.write(cmd.encode("ascii"))

    def _issue(self, as_deg):
        """Send commands for changed joints only. Returns ArmStatus."""
        with self._lock:
            if not self._alive:
                return ArmStatus.SERIAL_ERROR
            if self._pending:
                return ArmStatus.BUSY
            try:
                for j in range(5):
                    self._send_move(j, as_deg[j])
                    self._pending.add(j)
            except (serial.SerialException, OSError):
                self._alive = False
                return ArmStatus.SERIAL_ERROR
            if self._pending:
                self._move_t0 = time.monotonic()
            return ArmStatus.OK

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #

    def cmd_raw(self, j, a_deg):
        if not (0 <= j <= 5):
            return ArmStatus.BAD_ARG
        try:
            with self._lock:
                if not self._alive:
                    return ArmStatus.SERIAL_ERROR
                self._send_move(j, a_deg)
                self._pending.add(j)
                if len(self._pending) == 1:
                    self._move_t0 = time.monotonic()
        except (serial.SerialException, OSError):
            self._alive = False
            return ArmStatus.SERIAL_ERROR
        return ArmStatus.OK

    def home(self):
        return self.move_joints(HOME_ANGLES)

    def move_to(self, x, y, z, phi):
        if not self._alive:
            return ArmStatus.SERIAL_ERROR
        joint_angles = inverse_kinematics(x, y, z, phi)
        if joint_angles is None:
            return ArmStatus.OUT_OF_REACH
        return self._issue(joint_angles)

    def move_joints(self, as_deg):
        return self._issue(as_deg)

    def is_moving(self):
        """True until every issued joint has reported 'done'."""
        with self._lock:
            if not self._alive or not self._pending:
                return False
            if (
                MOVE_TIMEOUT is not None
                and time.monotonic() - self._move_t0 > MOVE_TIMEOUT
            ):
                print("warning: timed out waiting for 'done', clearing state")
                self._pending.clear()
                return False
            return True

    def open_gripper(self):
        self.cmd_raw(J_GRIPPER, GRIPPER_OPEN)

    def close_gripper(self):
        self.cmd_raw(J_GRIPPER, GRIPPER_CLOSE)


    def close(self):
        self._running = False
        self._reader_thread.join(timeout=1.0)
        self._ser.close()


def interactive(arm: ArmController):
    try:
        import readline
    except ImportError:
        pass
    arm.on_done = lambda j: print(f"  [done {j}]")
    while True:
        try:
            line = input("arm> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        parts = line.split()
        cmd = parts[0].lower()
        try:
            if cmd in ("exit", "quit"):
                break
            elif cmd == "m":
                st = arm.cmd_raw(int(parts[1]), float(parts[2]))
                if st != ArmStatus.OK:
                    print("m ->", st.name)
            elif cmd == "ik":
                if len(parts) == 5:
                    st = arm.move_to(*map(float, parts[1:5]))
                else:
                    print("usage: ik x y z phi")
                    continue
                print("ik ->", st.name)
            elif cmd in ("h", "home"):
                print("home ->", arm.home().name)
            elif cmd == "w":
                print(
                    "all moves done"
                    if arm.wait_done(MOVE_TIMEOUT)
                    else "timeout waiting for moves"
                )
            elif cmd == "s":
                print("moving" if arm.is_moving() else "idle")
            else:
                print("unknown command:", cmd)
        except (ValueError, IndexError):
            print("bad arguments")


if __name__ == "__main__":
    import sys

    PORT, BAUD = "/dev/ttyACM0", 115200  # or "COM3"
    if len(sys.argv) > 1:
        PORT = sys.argv[1]
    arm = ArmController(PORT, BAUD)
    try:
        interactive(arm)
    finally:
        arm.close()
