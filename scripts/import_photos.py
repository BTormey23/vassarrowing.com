"""Import photos listed in photos/import/*.json from a public Google Drive folder.

Each manifest lists Drive file IDs and the web filename to save. Photos that
already exist at dest/name are skipped, so re-running is safe. Images are
auto-rotated from EXIF, resized so the long edge is at most max_px, and saved
as progressive JPEGs with metadata stripped.
"""
import glob, io, json, os, sys
import requests
from PIL import Image, ImageOps

URLS = [
    "https://drive.usercontent.google.com/download?id={id}&export=download&confirm=t",
    "https://drive.google.com/uc?export=download&id={id}",
]

def fetch(file_id):
    for u in URLS:
        r = requests.get(u.format(id=file_id), timeout=120)
        if r.ok and r.headers.get("content-type", "").startswith("image/"):
            return r.content
    raise RuntimeError(f"could not download {file_id} (is the folder shared 'anyone with the link'?)")

failed = 0
for manifest in sorted(glob.glob("photos/import/*.json")):
    m = json.load(open(manifest))
    dest, max_px = m["dest"], int(m.get("max_px", 1600))
    os.makedirs(dest, exist_ok=True)
    for p in m["photos"]:
        out = os.path.join(dest, p["name"])
        if os.path.exists(out):
            continue
        try:
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(fetch(p["id"])))).convert("RGB")
            im.thumbnail((max_px, max_px), Image.LANCZOS)
            im.save(out, "JPEG", quality=84, optimize=True, progressive=True)
            print("saved", out, im.size)
        except Exception as e:
            failed += 1
            print("FAILED", p.get("file"), p["id"], e, file=sys.stderr)
sys.exit(1 if failed else 0)
