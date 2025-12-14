import json
import numpy as np
import cv2
import os

ZONE_FILE = "zones_config.json"
AFFINE_FILE = "affine_params.json"


# -------------------------------------------------------
# JSON LOAD / SAVE
# -------------------------------------------------------

def load_json(path, default=None):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=4)


# -------------------------------------------------------
# ZONES
# -------------------------------------------------------

def load_zones():
    return load_json(ZONE_FILE, [])


def save_zones(z):
    save_json(ZONE_FILE, z)


# -------------------------------------------------------
# AFFINE MATRIX
# -------------------------------------------------------

def load_affine_params():
    return load_json(AFFINE_FILE, None)


def save_affine_params(data):
    save_json(AFFINE_FILE, data)


def compute_affine_matrix(pairs):
    try:
        src = np.float32([[p["cam"]["x"], p["cam"]["y"]] for p in pairs])
        dst = np.float32([[p["robot"]["x"], p["robot"]["y"]] for p in pairs])

        mtx, _ = cv2.estimateAffine2D(src, dst)

        params = {
            "a": float(mtx[0, 0]),
            "b": float(mtx[0, 1]),
            "c": float(mtx[0, 2]),
            "d": float(mtx[1, 0]),
            "e": float(mtx[1, 1]),
            "f": float(mtx[1, 2])
        }

        return True, params

    except Exception as e:
        return False, str(e)


def pixel_to_robot(px, py):
    data = load_affine_params()
    if not data:
        return px, py  # fallback

    p = data["params"]
    a, b, c = p["a"], p["b"], p["c"]
    d, e, f = p["d"], p["e"], p["f"]

    rx = a * px + b * py + c
    ry = d * px + e * py + f

    return rx, ry


def hex_to_bgr(h):
    h = h.lstrip("#")
    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))
