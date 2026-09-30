"""Regression harness: re-render + re-score every red-team JSX with the CURRENT pipeline (local, no API).

Final match = 0 if lint or integrity fails, else score_run match (target text on). Output:
out/redteam/rescore.json and a summary. Usage: .venv/bin/python tools/rescore_attacks.py
"""
import json, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sandbox"))
import integrity, score  # noqa: E402

DEV = ROOT / "benchmarks-dev"
OUT = ROOT / "out" / "redteam" / "rescore"
HACK = re.compile(r"^h_|dump|occl|barcode|stripe|blank|lorem|trace|fake|junk|stuff|hidden|invis|dust|blob|noise|checker|vector", re.I)


def run(jsx: Path):
    page = jsx.parent.name
    rnd = "r2" if "round2" in jsx.parts else "r1"
    out = OUT / rnd / page / jsx.stem
    out.mkdir(parents=True, exist_ok=True)
    lint = json.loads(subprocess.run(["node", "lint.mjs", str(jsx)], cwd=ROOT / "sandbox", capture_output=True, text=True).stdout or '{"ok":false}')
    subprocess.run(["node", "render.mjs", "--in", str(jsx), "--out", str(out)], cwd=ROOT / "sandbox", capture_output=True, text=True)
    if not (out / "checks.json").exists():
        return dict(round=rnd, page=page, name=jsx.stem, match=0.0, raw=None, why="build failed", hack=bool(HACK.search(jsx.stem)))
    texts = {bp: json.loads((DEV / page / f"{bp}.text.json").read_text()) for bp in score.BREAKPOINTS}
    tdir = out / "_texts"; tdir.mkdir(exist_ok=True)
    for bp, t in texts.items():
        (tdir / f"{bp}.text.json").write_text(json.dumps(t))
    res = score.score_run(DEV / page, out, tdir)
    fails = integrity.failures(json.loads((out / "checks.json").read_text()), out, [x["text"] for v in texts.values() for x in v])
    why = ([f"lint: {v['detail']}" for v in lint.get("violations", [])] + fails)
    return dict(round=rnd, page=page, name=jsx.stem, raw=res["match"], match=0.0 if why else res["match"],
                per={bp: v["score"] for bp, v in res["breakpoints"].items()}, why="; ".join(why)[:160], hack=bool(HACK.search(jsx.stem)))


def spacer_twins(files):
    """For every '+strip' attack, the same page with the strip's glyphs transparent (same height).
    A trick must not beat its own neutralised twin: that isolates the stuffing from its layout side-effect."""
    twins = []
    for f in files:
        if f.stem.endswith("+strip"):
            src = f.read_text()
            # neutral filler of the same length (transparent design text would itself be hidden stuffing → DQ)
            twin = re.sub(r"<span>([^<]*)</span>", lambda m: "<span>" + re.sub(r"[A-Za-z0-9]", "x", m.group(1)) + "</span>", src)
            twin = twin.replace('style={{color:"#888"}}', 'style={{color:"transparent"}}')
            if twin != src:
                out = f.with_name(f.stem.replace("+strip", "+spacer") + ".jsx")
                out.write_text(twin)
                twins.append(out)
    return twins


if __name__ == "__main__":
    files = [p for p in (ROOT / "out" / "redteam").rglob("*.jsx") if p.parent.name in {d.name for d in DEV.iterdir()}
             and "round3" not in p.parts and not p.stem.endswith("+spacer")]
    files += spacer_twins(files)
    with ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(run, files))
    (ROOT / "out" / "redteam" / "rescore.json").write_text(json.dumps(rows, indent=1))
    hacks = [r for r in rows if r["hack"]]
    honest = [r for r in rows if not r["hack"]]
    print(f"{len(rows)} candidates: {len(hacks)} hacks, {len(honest)} honest")
    print(f"hacks: DQ {sum(1 for r in hacks if r['why'])}, max final match {max(r['match'] for r in hacks):.1f}")
    for r in sorted(hacks, key=lambda r: -r["match"])[:10]:
        print(f"   {r['round']} {r['page']:15} {r['name']:34} final {r['match']:5.1f} raw {r['raw']}")
    print("honest disqualified:")
    for r in honest:
        if r["why"]:
            print(f"   {r['round']} {r['page']:15} {r['name']:34} raw {r['raw']} why: {r['why']}")
