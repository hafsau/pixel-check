"""G6: fork 3 children from one checkpoint; each writes a different file. Parent must be unchanged.

Usage: .venv/bin/python -m gates.g6_branch
"""
from concurrent.futures import ThreadPoolExecutor
import time
from orchestrator.sandbox import Sandbox

sb = Sandbox()
parent = sb.run("mkdir -p /work && echo parent > /work/state.txt")
print(f"parent: {parent.status} checkpoint={parent.result_image} wall={parent.wall_s:.1f}s")
t0 = time.time()
with ThreadPoolExecutor(3) as ex:
    kids = list(ex.map(lambda i: sb.run(f"echo child{i} >> /work/state.txt && cat /work/state.txt", image=parent.result_image), range(3)))
print(f"3 parallel forks in {time.time() - t0:.1f}s")
outs = [k.stdout.strip().replace("\n", " | ") for k in kids]
for i, k in enumerate(kids):
    print(f"  child{i}: {k.status} checkpoint={k.result_image} stdout={outs[i]!r}")
check = sb.run("cat /work/state.txt", image=parent.result_image, disposable=True)
print(f"parent re-read: {check.stdout.strip()!r}")
ok = (all(k.ok for k in kids) and outs == [f"parent | child{i}" for i in range(3)]
      and check.stdout.strip() == "parent" and len({k.result_image for k in kids}) == 3)
print("G6", "PASS" if ok else "FAIL")
