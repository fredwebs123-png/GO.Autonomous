"""Crop each frame tightly around the red toy car.

Finds red pixels (HSV-style test with numpy), takes the largest connected
cluster, pads the bounding box, forces a fixed aspect ratio, crops, and
upscales so the car fills the frame. Needs only Pillow and numpy.

Usage:
    python crop_car.py INPUT_DIR [OUTPUT_DIR] [--size 640] [--pad 0.35] [--unstretch 4:3]

--unstretch W:H undoes a Roboflow "Stretch to 640x640" resize by restoring the
original aspect ratio before cropping.

Writes cropped images plus crop_log.csv (source file, crop box, status).
Frames where no car is found are skipped and logged, never guessed.
Originals are never modified.
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from PIL import Image

EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def red_mask(rgb):
    """Boolean mask of saturated red pixels (the car body)."""
    arr = rgb.astype(np.int16)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    return (r > 110) & (r - g > 60) & (r - b > 40)


def largest_cluster_box(mask, min_pixels=40):
    """Bounding box of the densest red region, (x0, y0, x1, y1) or None.

    Uses a coarse grid so a few stray red pixels do not stretch the box.
    """
    h, w = mask.shape
    cell = 8
    gh, gw = h // cell, w // cell
    if gh == 0 or gw == 0:
        return None
    grid = mask[: gh * cell, : gw * cell].reshape(gh, cell, gw, cell).sum(axis=(1, 3))
    active = grid >= 6  # cells with at least 6 red pixels
    if active.sum() == 0:
        return None

    seen = np.zeros_like(active, dtype=bool)
    best, best_count = None, 0
    for gy, gx in zip(*np.nonzero(active)):
        if seen[gy, gx]:
            continue
        stack, cells = [(gy, gx)], []
        seen[gy, gx] = True
        while stack:
            cy, cx = stack.pop()
            cells.append((cy, cx))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < gh and 0 <= nx < gw and active[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        count = sum(int(grid[c]) for c in cells)
        if count > best_count:
            best, best_count = cells, count

    if best is None or best_count < min_pixels:
        return None
    ys = [c[0] for c in best]
    xs = [c[1] for c in best]
    return (min(xs) * cell, min(ys) * cell, (max(xs) + 1) * cell, (max(ys) + 1) * cell)


def square_crop_box(box, img_w, img_h, pad):
    """Pad the box, make it square, shift to stay inside the image."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    side = max(x1 - x0, y1 - y0) * (1 + 2 * pad)
    side = min(side, img_w, img_h)
    left = min(max(cx - side / 2, 0), img_w - side)
    top = min(max(cy - side / 2, 0), img_h - side)
    return int(round(left)), int(round(top)), int(round(left + side)), int(round(top + side))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir", type=Path)
    ap.add_argument("output_dir", type=Path, nargs="?", default=None)
    ap.add_argument("--size", type=int, default=640, help="output width/height in px")
    ap.add_argument("--pad", type=float, default=0.35, help="padding around car, fraction of car size per side")
    ap.add_argument("--unstretch", default=None, help="original aspect ratio W:H, e.g. 4:3")
    args = ap.parse_args()
    aspect = None
    if args.unstretch:
        aw, ah = (float(v) for v in args.unstretch.split(":"))
        aspect = ah / aw

    out_dir = args.output_dir or args.input_dir.parent / "cropped"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in args.input_dir.rglob("*") if p.suffix.lower() in EXTS)
    if not files:
        sys.exit(f"No images found in {args.input_dir}")

    rows, ok = [], 0
    for path in files:
        img = Image.open(path).convert("RGB")
        if aspect:
            img = img.resize((img.width, round(img.width * aspect)), Image.LANCZOS)
        box = largest_cluster_box(red_mask(np.asarray(img)))
        if box is None:
            rows.append([path.name, "", "no_car_found"])
            continue
        crop_box = square_crop_box(box, img.width, img.height, args.pad)
        crop = img.crop(crop_box).resize((args.size, args.size), Image.LANCZOS)
        crop.save(out_dir / f"{path.stem}_crop.jpg", quality=95)
        rows.append([path.name, " ".join(map(str, crop_box)), "ok"])
        ok += 1

    with open(out_dir / "crop_log.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "crop_box_x0_y0_x1_y1", "status"])
        writer.writerows(rows)
    print(f"{ok}/{len(files)} cropped -> {out_dir}")


if __name__ == "__main__":
    main()
