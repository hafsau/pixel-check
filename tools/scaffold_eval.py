import json, pathlib, subprocess, sys
sys.path.insert(0,'sandbox'); import score, integrity
from orchestrator.scaffold import compile_scaffold
from orchestrator.fluid import compile_fluid
import fluidity
V2='--v2' in sys.argv or '--oracle' in sys.argv
ORACLE='--oracle' in sys.argv
INTENTS='--intents' in sys.argv
pages=[a for a in sys.argv[1:] if not a.startswith('--')]
from PIL import Image
for page in pages:
    spec=json.loads(pathlib.Path(f"out/specs/{page}{'.oracle' if ORACLE else ''}.json").read_text())
    if V2 and INTENTS:
        from orchestrator import intent
        from orchestrator.tf_client import TFClient
        pf=pathlib.Path(f"out/specs/{page}{'.oracle' if ORACLE else ''}.plan.json")
        raw=json.loads(pf.read_text()) if pf.exists() else intent.plan_intents(TFClient(run_id='plan-'+page), spec)[1]['raw']
        pf.write_text(json.dumps(raw))
        code=compile_fluid(spec, intent.revalidate(spec, raw))
    else:
        code=(compile_fluid if V2 else compile_scaffold)(spec)
    p=pathlib.Path(f"out/{'fluid-oracle' if ORACLE else 'fluid' if V2 else 'scaffold'}{'-plan' if INTENTS else ''}/{page}"); p.mkdir(parents=True,exist_ok=True); (p/"App.jsx").write_text(code)
    lint=json.loads(subprocess.run(["node","lint.mjs",str((p/"App.jsx").resolve())],cwd="sandbox",capture_output=True,text=True).stdout)
    subprocess.run(["node","render.mjs","--in",str((p/"App.jsx").resolve()),"--out",str(p.resolve())],cwd="sandbox",capture_output=True)
    if not (p/"checks.json").exists(): print(page,"BUILD FAILED"); continue
    t=p/"_t"; t.mkdir(exist_ok=True)
    for bp in score.BREAKPOINTS: (t/f"{bp}.text.json").write_text(pathlib.Path(f"benchmarks-dev/{page}/{bp}.text.json").read_text())
    res=score.score_run(pathlib.Path(f"benchmarks-dev/{page}"),p,t)
    fails=integrity.failures(json.loads((p/"checks.json").read_text()),p,[x["text"] for bp in score.BREAKPOINTS for x in json.loads((t/f"{bp}.text.json").read_text())])
    print(f"{page:15} match {res['match']:5.1f} per", {bp:v['score'] for bp,v in res['breakpoints'].items()}, "lint", lint["ok"], "integ", fails)
    fl=fluidity.report(json.loads((p/"checks.json").read_text()))
    print(f"{'':15} fluid {'PASS' if fl['pass'] else 'FAIL'}", fl['fails'][:8])
    ims=[]
    for bp in ("desktop","tablet","mobile"):
        ims+=[Image.open(f"benchmarks-dev/{page}/{bp}.png").convert("RGB"),Image.open(p/f"{bp}.png").convert("RGB")]
    H=360; ims=[i.resize((int(i.width*H/i.height),H)) for i in ims]
    sh=Image.new("RGB",(sum(i.width for i in ims)+100,H),"#f0f"); x=0
    for j,i in enumerate(ims): sh.paste(i,(x,0)); x+=i.width+(6 if j%2==0 else 30)
    sh.save(f"/private/tmp/claude-501/-Users-hafsa-Nebius/0a939223-70d2-49fe-906e-a904d0d99676/scratchpad/sc_{page}{"_v2" if V2 else ""}.png")
