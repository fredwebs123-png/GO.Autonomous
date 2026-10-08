"""Write YOLO labels + overlays for hand-estimated boxes. Boxes are x0,y0,x1,y1 on 640x640 crops.
Class 0 = tire_front_driver, 1 = tire_rear_driver."""
import glob, os, sys, json
from PIL import Image, ImageDraw

def add(L, sheet_name):
    cols = {0: (0, 255, 0), 1: (255, 255, 0)}
    for d in ('images', 'labels', 'overlay'):
        os.makedirs(f'seed/{d}', exist_ok=True)
    names = sorted(L)
    for k in names:
        src = glob.glob(f'cropped/{k}_jpg*_crop.jpg')[0]
        im = Image.open(src).convert('RGB')
        im.save(f'seed/images/{k}.jpg', quality=95)
        with open(f'seed/labels/{k}.txt', 'w') as f:
            for c, (x0, y0, x1, y1) in L[k].items():
                f.write(f'{c} {(x0+x1)/1280:.6f} {(y0+y1)/1280:.6f} {(x1-x0)/640:.6f} {(y1-y0)/640:.6f}\n')
        o = im.copy(); d = ImageDraw.Draw(o)
        for c, bx in L[k].items():
            d.rectangle(bx, outline=cols[c], width=2)
        o.save(f'seed/overlay/{k}.jpg')
    t, W = 320, 4
    sheet = Image.new('RGB', (W * t, ((len(names) + W - 1) // W) * t))
    for i, k in enumerate(names):
        tile = Image.open(f'seed/overlay/{k}.jpg').resize((t, t))
        ImageDraw.Draw(tile).text((4, 4), k[6:], fill=(255, 255, 255))
        sheet.paste(tile, ((i % W) * t, (i // W) * t))
    sheet.save(sheet_name, quality=90)
