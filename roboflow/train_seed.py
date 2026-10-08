"""Train a small YOLOv8 tire detector on seed/ and run it over cropped/.

Run with the venv python:  .venv\\Scripts\\python.exe train_seed.py
Outputs (all under Desktop/roboflow):
  tire_model.pt            best weights
  predictions/labels/*.txt YOLO labels (with confidence) for every crop
  predictions/overlay/*.jpg boxes drawn on each crop
  predictions/summary.csv  per-image detection counts and best confidences
Horizontal flip is disabled on purpose: a flip swaps driver and passenger sides.
"""
import csv
import random
import shutil
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).parent
SEED = ROOT / "seed"
SPLIT = ROOT / "seed_split"
random.seed(7)

# 80/20 split so there is a held-out check
names = sorted(p.stem for p in (SEED / "images").glob("*.jpg"))
random.shuffle(names)
n_val = max(4, len(names) // 5)
val, train = names[:n_val], names[n_val:]
if SPLIT.exists():
    shutil.rmtree(SPLIT)
for part, items in (("train", train), ("val", val)):
    for sub in ("images", "labels"):
        (SPLIT / part / sub).mkdir(parents=True)
    for n in items:
        shutil.copy(SEED / "images" / f"{n}.jpg", SPLIT / part / "images")
        shutil.copy(SEED / "labels" / f"{n}.txt", SPLIT / part / "labels")
(SPLIT / "data.yaml").write_text(
    f"path: {SPLIT.as_posix()}\ntrain: train/images\nval: val/images\n"
    "names:\n  0: tire_front_driver\n  1: tire_rear_driver\n"
)
print(f"train {len(train)}  val {len(val)}")

model = YOLO("yolov8n.pt")
model.train(
    data=str(SPLIT / "data.yaml"),
    epochs=150,
    imgsz=640,
    batch=8,
    device=0,
    workers=0,
    fliplr=0.0,       # never flip: driver side must stay driver side
    flipud=0.0,
    mosaic=0.5,
    degrees=0,
    project=str(ROOT / "runs"),
    name="tire",
    exist_ok=True,
    patience=60,
    verbose=False,
)
best = ROOT / "runs" / "tire" / "weights" / "best.pt"
shutil.copy(best, ROOT / "tire_model.pt")

pred_dir = ROOT / "predictions"
if pred_dir.exists():
    shutil.rmtree(pred_dir)
(pred_dir / "overlay").mkdir(parents=True)
(pred_dir / "labels").mkdir()
model = YOLO(str(ROOT / "tire_model.pt"))
rows = []
for img in sorted((ROOT / "cropped").glob("*_crop.jpg")):
    r = model.predict(str(img), conf=0.25, imgsz=640, device=0, verbose=False)[0]
    r.save(filename=str(pred_dir / "overlay" / img.name))
    best_conf = {0: 0.0, 1: 0.0}
    with open(pred_dir / "labels" / (img.stem + ".txt"), "w") as f:
        for box in r.boxes:
            c = int(box.cls)
            conf = float(box.conf)
            x, y, w, h = box.xywhn[0].tolist()
            f.write(f"{c} {x:.6f} {y:.6f} {w:.6f} {h:.6f} {conf:.3f}\n")
            best_conf[c] = max(best_conf[c], conf)
    rows.append([img.name, best_conf[0], best_conf[1]])
with open(pred_dir / "summary.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["image", "front_conf", "rear_conf"])
    w.writerows(rows)
print("front found:", sum(r[1] > 0 for r in rows), " rear found:", sum(r[2] > 0 for r in rows), " of", len(rows))
