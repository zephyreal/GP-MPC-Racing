"""Executed ONLY inside the hardened evaluator container, never by the web application."""
import importlib.util,json,os,sys
if os.getenv('RACE_SANDBOX')!='1':raise SystemExit('仅允许在评测沙箱中启动')
try:
    if os.getenv('RACE_TEACHER')=='1':
        from gp_mpc_racing.controllers import MPCController
        controller=MPCController(learn=os.getenv('RACE_LEARN','1')=='1',maxiter=12)
    else:
        spec=importlib.util.spec_from_file_location('student_agent','/submission/agent.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);controller=module.Controller()
    import hashlib
    from pathlib import Path
    root=Path(__file__).parent
    sha=hashlib.sha256((root/'engine.py').read_bytes()+(root/'controllers.py').read_bytes()+(root/'data/track02-original-v1.json').read_bytes()).hexdigest()
    print(json.dumps({'ready':True,'baseline_hash':sha}),flush=True)
except Exception:
    print(json.dumps({'ready':False}),flush=True);raise SystemExit(0)
while True:
    line=sys.stdin.buffer.readline(100001)
    if not line or len(line)>100000:break
    try:
        request=json.loads(line);result=controller.act(request['observation']);reply={'id':request['id'],'action':result}
        print(json.dumps(reply,allow_nan=False,separators=(',',':')),flush=True)
    except Exception:
        print(json.dumps({'error':'controller-error'}),flush=True)
