"""Real images for owned sites (Phase 2). The capture saves the page's own images (tools/capture/capture.mjs --assets:
bytes as served, checked by signature; inline SVG icons sanitised) with every occurrence's box at each size.

Scoring never sees them: the scored code keeps the grey blocks the compiler made (exactly what the capture shows in
place of each image) and lint still bans <img>. attach() makes the delivered code: a grey block becomes
<img src="/assets/<sha256>.<ext>"> only where one of the page's images sat in the same place at every size the
block shows; its classes stay (plus `block object-cover`). to_scoring() undoes that byte for byte, and the pipeline
delivers images only when it does — so the delivered code is the scored code with pictures in the grey boxes.
"""
from __future__ import annotations

import html
import re

EXTS = {"png", "jpg", "gif", "webp", "avif", "svg"}
_HASH = re.compile(r"^[0-9a-f]{64}$")
_GREY = re.compile(r"(?:^|\s)bg-\[#([0-9a-fA-F]{6})\](?:\s|$)")
_BLOCK = re.compile(r'<div data-pc="(?P<pc>\d+)"(?P<rest>[^<>]*?)className="(?P<cls>[^"]*)"(?P<tail>[^<>]*?)\s*/>')
_IMG = re.compile(r'<img data-pc="(?P<pc>\d+)" src="/assets/[0-9a-f]{64}\.(?:png|jpg|gif|webp|avif|svg)" '
                  r'alt="(?P<alt>[^"]*)"(?P<rest>[^<>]*?)className="(?P<cls>[^"]*) block object-cover"(?P<tail>[^<>]*?)\s*/>')
SUFFIX = " block object-cover"


def _is_grey(cls: str) -> bool:
    m = _GREY.search(cls)
    if not m:
        return False
    r, g, b = (int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    return max(abs(r - 0xD4), abs(g - 0xD4), abs(b - 0xD8)) <= 6      # the capture's placeholder grey #d4d4d8


def same_place(a, b) -> bool:
    """Two boxes [x, y, w, h] hold the same picture: overlap ≥ 0.5 of their union, or (icons, where a few pixels
    matter) centres within 35 % of the size and both sides within 0.7–1.43×."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if min(aw, ah, bw, bh) <= 0:
        return False
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    if inter / (aw * ah + bw * bh - inter) >= 0.5:
        return True
    if not (0.7 <= aw / bw <= 1 / 0.7 and 0.7 <= ah / bh <= 1 / 0.7):
        return False
    tol = 0.35 * max(aw, ah, bw, bh)
    return abs((ax + aw / 2) - (bx + bw / 2)) <= tol and abs((ay + ah / 2) - (by + bh / 2)) <= tol


def _visible_boxes(nodes_by_bp: dict, pc: str) -> dict:
    out = {}
    for bp, nodes in (nodes_by_bp or {}).items():
        for n in nodes:
            if str(n.get("pc")) == pc and n.get("v", True) and len(n.get("b") or []) == 4 and n["b"][2] > 0 and n["b"][3] > 0:
                out[bp] = n["b"]
                break
    return out


def _esc(s: str) -> str:
    """For a JSX string attribute: quotes, tags, ampersands and braces as entities."""
    return html.escape(s or "", quote=True).replace("&#x27;", "'").replace("{", "&#123;").replace("}", "&#125;")


def attach(code: str, nodes_by_bp: dict, manifest: dict | None) -> tuple[str, list[str]]:
    """→ (delivered code, data-pc ids that became images). nodes_by_bp: the scoring render's nodes per size
    ({"pc", "v", "b"}); manifest: the capture's assets.json."""
    items = [a for a in (manifest or {}).get("assets") or []
             if _HASH.match(str(a.get("hash", ""))) and a.get("ext") in EXTS and a.get("boxes")]
    if not items:
        return code, []
    used, out, pos = [], [], 0
    for m in _BLOCK.finditer(code):
        if not _is_grey(m.group("cls")):
            continue
        seen = _visible_boxes(nodes_by_bp, m.group("pc"))
        if not seen:
            continue
        picks = []
        for bp, box in seen.items():              # the same place at EVERY size this block shows
            cands = [a for a in items if any(same_place(box, b) for b in a["boxes"].get(bp) or [])]
            if not cands:
                picks = []
                break
            picks.extend(cands)
        if not picks:
            continue
        a = max(picks, key=lambda x: (x.get("bytes") or 0, x["hash"]))   # responsive sources: the largest file
        rest = m.group("rest")
        alt = _esc(a.get("alt") or "") if ' aria-hidden="true"' in rest else ""   # keeps to_scoring() exact
        if alt:                                   # a described picture is not hidden from assistive tech
            rest = rest.replace(' aria-hidden="true"', "", 1)
        tag = (f'<img data-pc="{m.group("pc")}" src="/assets/{a["hash"]}.{a["ext"]}" alt="{alt}"{rest}'
               f'className="{m.group("cls")}{SUFFIX}"{m.group("tail")} />')
        out.append(code[pos:m.start()] + tag)
        pos = m.end()
        used.append(m.group("pc"))
    out.append(code[pos:])
    return "".join(out), used


def to_scoring(code: str) -> str:
    """The delivered code → the code that was scored (every asset image back to its grey block)."""
    def back(m):
        rest = m.group("rest")
        if m.group("alt"):
            rest = ' aria-hidden="true"' + rest
        return f'<div data-pc="{m.group("pc")}"{rest}className="{m.group("cls")}"{m.group("tail")} />'
    return _IMG.sub(back, code)


_SIG = {"png": lambda b: b[:8] == b"\x89PNG\r\n\x1a\n", "jpg": lambda b: b[:3] == b"\xff\xd8\xff",
        "gif": lambda b: b[:4] == b"GIF8", "webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
        "avif": lambda b: b[4:12] == b"ftypavif"}
_UNSAFE_SVG = re.compile(rb"<script|<foreignobject|<iframe|<use[^>]+href\s*=\s*[\"'](?!#)|\son\w+\s*=|"
                         rb"(?:xlink:)?href\s*=\s*[\"']\s*(?:javascript|data|https?):", re.I)


def _ok_bytes(ext: str, data: bytes) -> bool:
    if ext == "svg":
        head = data[:400].lstrip().lower()
        return head.startswith(b"<svg") and len(data) <= 100_000 and not _UNSAFE_SVG.search(data)
    return len(data) > 12 and _SIG[ext](data)


def verify(files: dict[str, bytes], manifest: dict | None, max_count: int = 60,
           max_total: int = 25_000_000) -> tuple[dict, dict[str, bytes]]:
    """What the capture sandbox returned → (clean manifest, {"assets/<hash>.<ext>": bytes}) holding only files whose
    name is a hash, whose bytes hash to it and match their type (signature; SVG without scripts / handlers / external
    links), within the count and total-size caps."""
    import hashlib
    clean, keep, total = [], {}, 0
    for a in (manifest or {}).get("assets") or []:
        h, ext = str(a.get("hash", "")), a.get("ext")
        name = f"assets/{h}.{ext}"
        data = files.get(name)
        if not _HASH.match(h) or ext not in EXTS or data is None or name in keep:
            continue
        if hashlib.sha256(data).hexdigest() != h or not _ok_bytes(ext, data):
            continue
        if len(clean) >= max_count or total + len(data) > max_total:
            break
        total += len(data)
        keep[name] = data
        clean.append({"hash": h, "ext": ext, "kind": a.get("kind"), "bytes": len(data),
                      "alt": str(a.get("alt") or "")[:200], "boxes": a.get("boxes") or {}})
    return {"assets": clean}, keep


def build_display(run_folder, manifest_path) -> dict | None:
    """After the loop: the best candidate's code + its scoring render's boxes + the verified manifest → display.jsx in
    the run folder. None (and no file) when nothing matched or the swap does not undo exactly."""
    import json
    from pathlib import Path
    run_folder, manifest_path = Path(run_folder), Path(manifest_path)
    try:
        manifest = json.loads(manifest_path.read_text())
        best = json.loads((run_folder / "result.json").read_text())["best"]
        cand = run_folder / "candidates" / str(best)
        code = (cand / "App.jsx").read_text()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    nodes = {}
    for bp in ("mobile", "tablet", "desktop"):
        try:
            nodes[bp] = json.loads((cand / f"{bp}.nodes.json").read_text())
        except (OSError, ValueError):
            pass
    display, used = attach(code, nodes, manifest)
    if not used or to_scoring(display) != code:
        return None
    (run_folder / "display.jsx").write_text(display)
    names = sorted(set(re.findall(r'src="/assets/([0-9a-f]{64}\.(?:png|jpg|gif|webp|avif|svg))"', display)))
    return {"images": len(used), "assets": names, "candidate": str(best)}
