from pathlib import Path
import pytest
from gp_mpc_racing.worker import command,runtime

def test_hardened_two_separate_controllers(monkeypatch):
    for teacher in (False,True):
        c=command('sha256:fixed',Path('/tmp/source'),'name',teacher)
        for flag in ('--runtime=runsc','--network=none','--read-only','--cap-drop=ALL','--cpus=1','--memory=768m','--user=65534:65534'):assert flag in c
        assert any('dst=/submission' in v for v in c)==(not teacher)
        assert not any('token' in v or 'docker.sock' in v for v in c)
    monkeypatch.setattr('gp_mpc_racing.worker.subprocess.check_output',lambda *a,**k:'{"runc":{}}')
    with pytest.raises(RuntimeError,match='runsc'):runtime('image')
