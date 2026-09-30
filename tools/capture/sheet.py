"""Contact sheet of captured breakpoints: python sheet.py out.png slug1 slug2 ..."""
import sys
from PIL import Image, ImageDraw
out, slugs, H = sys.argv[1], sys.argv[2:], 420
rows = []
for s in slugs:
    ims = [Image.open(f"benchmarks-dev/{s}/{bp}.png").convert("RGB") for bp in ("desktop", "tablet", "mobile")]
    ims = [im.resize((int(im.width * H / im.height), H)) for im in ims]
    row = Image.new("RGB", (sum(i.width for i in ims) + 40, H + 24), "white")
    ImageDraw.Draw(row).text((4, 4), s, fill="red")
    x = 0
    for im in ims:
        row.paste(im, (x, 24)); x += im.width + 20
    rows.append(row)
sheet = Image.new("RGB", (max(r.width for r in rows), sum(r.height + 10 for r in rows)), "#888")
y = 0
for r in rows:
    sheet.paste(r, (0, y)); y += r.height + 10
sheet.save(out)
