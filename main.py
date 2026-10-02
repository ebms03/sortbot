import cv2
import numpy as np
import FreeSimpleGUI as sg
import arm_actions

from videostream import VideoStream
from settings import load_settings, save_settings
from image_processing import (
    find_contours,
    fix_rect_angle,
    remove_bg,
    threshold,
    filter_small,
    morph,
    overlay,
)
from transforms import assumed_resolution, pos_camera_to_robot, angle_camera_to_robot

STREAM_URL = "https://192.168.0.192:8080/video"

IMAGE_KEY = "IMAGE"
STATUS_KEY = "STATUS"

SORT = "Sort"

CAPTURE_BG = "Capture background"
CLEAR_ROI = "Clear selection"

ORIGINAL = "RAW STREAM"
NO_BG = "NO BG"
THRESHOLD = "THRESHOLD"
FILTER_SMALL = "FILTER SMALL"
MORPH = "MORPH"
OVERLAY = "SHOW OVERLAY"

PIPELINE = [
    (NO_BG, remove_bg, (ORIGINAL,)),
    (THRESHOLD, threshold, (NO_BG,)),
    (FILTER_SMALL, filter_small, (THRESHOLD,)),
    (MORPH, morph, (FILTER_SMALL,)),
    (OVERLAY, overlay, (MORPH, ORIGINAL)),
]
STEP_NAMES = [ORIGINAL] + [name for name, *_ in PIPELINE]

MIN_ROI_SIZE = 3  # px; a smaller drag counts as a click and resets to full frame
BG_FRAMES = 10  # frames averaged for the background

HINT = "Drag on the image to select an area, click to reset to full frame."


def main():
    settings = load_settings()
    roi = RoiState()
    arm_controller = None
    bg_capture = None
    processed = None
    pipeline_result = None
    sorting = None
    current_step = ORIGINAL

    window = sg.Window(
        "Stream processor", build_layout(settings), location=(800, 400), finalize=True
    )
    bind_mouse_selection(window, IMAGE_KEY, roi)
    stream = VideoStream(STREAM_URL)

    while True:
        event, values = window.read(timeout=10)
        if event == sg.WIN_CLOSED:
            save_settings(settings)
            break
        if event in STEP_NAMES:
            current_step = event
        elif event == CLEAR_ROI:
            roi.roi = None
        elif event == SORT:
            sorting = SortingState(pipeline_result[MORPH], roi.roi)

        if sorting:
            done = sorting.update(arm_controller)
            if done:
                sorting = None

        ret, frame, frame_idx = stream.read()
        if not ret or frame is None:
            continue

        h, w = frame.shape[:2]
        if (w, h) != assumed_resolution:
            print(f"WRONG RESOLUTION GOT {(w, h)=} but {assumed_resolution=}")
        settings.roi = roi.clamp(w, h)
        work = settings.crop(frame)

        bg_capture, status = advance_background(
            event, bg_capture, settings, frame, frame_idx
        )

        settings.update(values)
        pipeline_result = run_pipeline(work, settings)
        processed = pipeline_result[current_step]
        display = compose_display(frame, processed, settings.roi, roi.band())

        window[IMAGE_KEY].update(data=encode(display))
        window[STATUS_KEY].update(status)

    stream.stop()
    window.close()


# ------------------------------------------------------------- state helpers


class RoiState:
    def __init__(self):
        self.dragging = False
        self.start = None
        self.current = None
        self.roi = None  # (x1, y1, x2, y2) or None for full frame

    def clamp(self, w, h):
        if self.roi is None:
            return None
        x1, y1 = max(0, self.roi[0]), max(0, self.roi[1])
        x2, y2 = min(w, self.roi[2]), min(h, self.roi[3])
        if x2 - x1 < MIN_ROI_SIZE or y2 - y1 < MIN_ROI_SIZE:
            self.roi = None
        else:
            self.roi = (x1, y1, x2, y2)
        return self.roi

    def band(self):
        if not self.dragging or self.start is None:
            return None
        (x1, y1), (x2, y2) = self.start, self.current
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


class BackgroundCapture:
    def __init__(self, frame_idx):
        self.last_idx = frame_idx
        self.frames = []

    def feed(self, frame, frame_idx):
        if frame_idx == self.last_idx:  # same camera frame as last poll
            return True
        self.last_idx = frame_idx
        self.frames.append(frame.copy())
        return len(self.frames) < BG_FRAMES

    def result(self):
        return np.round(np.mean(self.frames, axis=0, dtype=np.float32)).astype(np.uint8)


class SortingState:
    class Item:
        def __init__(self, cnt, roi):
            self.area = cv2.contourArea(cnt)
            (self.x, self.y), (w, h), self.angle = cv2.minAreaRect(cnt)
            if w < h:
                self.angle += 90
            if self.angle < 0:
                self.angle = 180 + self.angle
            if roi:
                dx, dy, *_ = roi
                self.x += dx
                self.y += dy

        def __repr__(self):
            return f"Item([{self.x},{self.y},{self.angle}],{self.area})"

    def __init__(self, contours_from, roi):
        self.items = [
            SortingState.Item(cnt, roi) for cnt in find_contours(contours_from)
        ]
        self.actions = []
        for item in self.items:
            cx, cy, ca = item.x, item.y, item.angle
            rx, ry = pos_camera_to_robot(cx, cy)
            ra = angle_camera_to_robot(ca)
            self.actions.extend(arm_actions.pick_up_at(rx, ry, ra))
            self.actions.extend(arm_actions.drow_off_at(10, 20, 90))

    def update(self, arm):
        if arm is None:
            print("arm is None, dumping items and finishing early")
            print(*self.items, sep="\n")
            return True
        if not self.actions:
            return True
        if not arm.is_moving():
            action = self.actions.pop(0)
            action(arm)
        return False


# ------------------------------------------------------------- UI helpers


def build_layout(settings):
    return [
        [sg.Image(filename="", key=IMAGE_KEY)],
        [
            sg.Button(CAPTURE_BG, size=(10, 1)),
            sg.Text("   "),
            *[sg.Button(name, size=(10, 1)) for name in STEP_NAMES],
            sg.Button(CLEAR_ROI, size=(12, 1)),
        ],
        [sg.Text(HINT, size=(64, 1), key=STATUS_KEY)],
        *[
            [
                sg.Text(k, size=(12, 1)),
                sg.Slider(
                    range=v.range,
                    default_value=v.value,
                    orientation="h",
                    size=(20, 15),
                    key=k,
                    enable_events=True,
                ),
            ]
            for k, v in settings.items()
        ],
        [sg.Button(SORT, size=(10, 1))],
    ]


def bind_mouse_selection(window, key, roi):
    widget = window[key].Widget
    widget.configure(cursor="crosshair")

    def press(e):
        roi.dragging = True
        roi.start = roi.current = (e.x, e.y)

    def drag(e):
        if roi.dragging:
            roi.current = (e.x, e.y)

    def release(e):
        if not roi.dragging:
            return
        roi.dragging = False
        roi.current = (e.x, e.y)
        x1, y1 = roi.start
        x2, y2 = roi.current
        if abs(x2 - x1) < MIN_ROI_SIZE or abs(y2 - y1) < MIN_ROI_SIZE:
            roi.roi = None  # plain click -> full frame
        else:
            roi.roi = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

    widget.bind("<ButtonPress-1>", press)
    widget.bind("<B1-Motion>", drag)
    widget.bind("<ButtonRelease-1>", release)


# ------------------------------------------------------------- image helpers


def run_pipeline(frame, settings):
    ctx = {ORIGINAL: frame}
    for name, fn, inputs in PIPELINE:
        ctx[name] = fn(*(ctx[n] for n in inputs), settings)
    return ctx


def compose_display(frame, processed, roi, band):
    out = processed if roi is None else frame.copy()
    if roi is not None:
        x1, y1, x2, y2 = roi
        patch = processed
        if patch.ndim == 2:  # grayscale result -> BGR so it can be pasted
            patch = cv2.cvtColor(patch, cv2.COLOR_GRAY2BGR)
        out[y1:y2, x1:x2] = patch
        cv2.rectangle(out, (x1, y1), (x2 - 1, y2 - 1), (0, 255, 0), 1)
    if band is not None:  # rubber band while dragging
        cv2.rectangle(out, (band[0], band[1]), (band[2], band[3]), (0, 255, 0), 1)
    return out


def encode(img):
    ext = ".ppm" if img.ndim == 3 else ".pgm"
    _, buf = cv2.imencode(ext, img)
    return buf.tobytes()


def advance_background(event, bg_capture, settings, frame, frame_idx):
    if event == CAPTURE_BG:  # pressing again mid-capture restarts it
        return BackgroundCapture(frame_idx), f"Background 0/{BG_FRAMES}"
    if bg_capture is not None:
        if bg_capture.feed(frame, frame_idx):
            return bg_capture, f"Background {len(bg_capture.frames)}/{BG_FRAMES}"
        settings.capture_bg(bg_capture.result())  # full-frame averaged background
        return None, "Background captured"
    if settings.bg is None:
        return None, "No background yet - press Capture background"
    if settings.roi is None:
        return None, "Full frame"
    x1, y1, x2, y2 = settings.roi
    return None, f"ROI ({x1},{y1})-({x2},{y2}), {x2 - x1}x{y2 - y1} px"


if __name__ == "__main__":
    main()
