import cv2
import numpy as np


from settings import *


def blur(x, settings):
    if settings[BLUR_SIZE] > 0:
        return cv2.blur(x, (int(settings[BLUR_SIZE]),) * 2)
    return x


def gray(x, _settings):
    return cv2.cvtColor(x, cv2.COLOR_BGR2GRAY)


def remove_bg(x, settings):
    gray_x = gray(x, settings)
    if settings.bg is None:
        return gray_x
    bg = settings.crop(settings.bg)
    if bg.shape[:2] != x.shape[:2]:
        return gray_x
    diff = cv2.absdiff(blur(x, settings), blur(bg, settings))
    return gray(diff, settings)


def threshold(x, settings):
    _, t = cv2.threshold(x, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return t


def filter_small(x, settings):
    contours, _ = cv2.findContours(x, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = x.copy()
    for cnt in contours:
        if cv2.contourArea(cnt) < settings[MIN_AREA]:
            cv2.drawContours(out, [cnt], 0, 0, -1)
    return out


def morph(x, settings):
    return cv2.morphologyEx(
        x,
        cv2.MORPH_CLOSE,
        np.ones((int(settings[MORPH_SIZE]),) * 2, dtype=np.uint8),
    )


def overlay(contours_from, draw_onto, _settings):
    out = draw_onto.copy()
    contours = find_contours(contours_from)
    for cnt in contours:
        box = np.intp(cv2.boxPoints(cv2.minAreaRect(cnt)))
        cv2.drawContours(out, [box], 0, (0, 255, 0), 2)
    return out


def find_contours(contours_from):
    contours, _ = cv2.findContours(
        contours_from, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    return contours


def fix_rect_angle(rect, roi):
    (x, y), (w, h), a = rect
    if roi:
        (dx, dy), _ = roi.bounds
        x += dx
        y += dy
    # angle of longer edge
    if w < h:
        a += 90
    if a < 0:
        a = 180 - a
    return (x, y), a
