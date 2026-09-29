import cv2
import numpy as np
import FreeSimpleGUI as sg

from videostream import VideoStream
from settings import load_settings, save_settings
from image_processing import remove_bg, threshold, filter_small, morph, overlay

STREAM_URL = "https://192.168.0.192:8080/video"

IMAGE_KEY = "IMAGE"
STATUS_KEY = "STATUS"

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
STEP_NAMES = [name for name, _, _ in PIPELINE]

MIN_ROI_SIZE = 3  # px; a smaller drag counts as a click and resets to full frame
BG_FRAMES = 10  # frames averaged for the background

HINT = "Drag on the image to select an area, click to reset to full frame."


def main():
    settings = load_settings()
    roi = RoiState()
    bg_capture = None
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

        ret, frame, frame_idx = stream.read()
        if not ret or frame is None:
            continue

        h, w = frame.shape[:2]
        settings.roi = roi.clamp(w, h)
        work = settings.crop(frame)

        bg_capture, status = advance_background(
            event, bg_capture, settings, frame, frame_idx
        )

        settings.update(values)
        processed = run_pipeline(work, settings)[current_step]
        display = compose_display(frame, processed, settings.roi, roi.band)

        window[IMAGE_KEY].update(data=encode(display))
        window[STATUS_KEY].update(status)

    stream.stop()
    window.close()


# ------------------------------------------------------------- state helpers


class RoiState:
    """Mouse drag on the image widget + the locked-in ROI (image pixel coords)."""

    def __init__(self):
        self.dragging = False
        self.start = None
        self.current = None
        self.roi = None  # (x1, y1, x2, y2) or None for full frame

    def clamp(self, w, h):
        """Fit the ROI inside the frame; too-small selections reset to None."""
        if self.roi is None:
            return None
        x1, y1 = max(0, self.roi[0]), max(0, self.roi[1])
        x2, y2 = min(w, self.roi[2]), min(h, self.roi[3])
        if x2 - x1 < MIN_ROI_SIZE or y2 - y1 < MIN_ROI_SIZE:
            self.roi = None
        else:
            self.roi = (x1, y1, x2, y2)
        return self.roi

    @property
    def band(self):
        """Bounding box of the in-progress drag, or None."""
        if not self.dragging or self.start is None:
            return None
        (x1, y1), (x2, y2) = self.start, self.current
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


class BackgroundCapture:
    """Averages the next BG_FRAMES distinct frames into the background."""

    def __init__(self, frame_idx):
        self.last_idx = frame_idx
        self.frames = []

    def feed(self, frame, frame_idx):
        """Add the frame if it is new; True while still collecting."""
        if frame_idx == self.last_idx:  # same camera frame as last poll
            return True
        self.last_idx = frame_idx
        self.frames.append(frame.copy())
        return len(self.frames) < BG_FRAMES

    def result(self):
        return np.round(np.mean(self.frames, axis=0, dtype=np.float32)).astype(np.uint8)


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
    ]


def bind_mouse_selection(window, key, roi):
    """Mouse events on the tk widget under sg.Image; coords are image pixels."""
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
    """Run the full chain, return {step name: image}."""
    ctx = {ORIGINAL: frame}
    for name, fn, inputs in PIPELINE:
        ctx[name] = fn(*(ctx[n] for n in inputs), settings)
    return ctx


def compose_display(frame, processed, roi, band):
    """Paste the processed crop back into the full frame and draw the selection."""
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
    """Background-averaging state machine; returns (state, status text)."""
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
