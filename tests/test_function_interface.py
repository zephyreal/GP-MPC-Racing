import importlib.util
from pathlib import Path
from gp_mpc_racing.function_adapter import load_controller
from gp_mpc_racing.engine import Race,make_track,action
from test_server import setup,create


def test_function_memory_and_legacy():
    class Module:
        @staticmethod
        def control(o,r,v,m):
            assert v['wheelbase']==2.4 and 'points' in r
            return .1,.2,(m or 0)+1
    controller=load_controller(Module)
    obs=Race(make_track('oval')).observation()
    for n in range(3):
        action(controller.act(obs));assert controller.memory==n+1
    assert 'track' in obs
    class Legacy:
        class Controller:
            def act(self,o):return {'steering':0,'torque':0}
    action(load_controller(Legacy).act(obs))


def test_beginner_completes_lap():
    path=Path(__file__).resolve().parents[1]/'gp_mpc_racing/student/agent.py'
    spec=importlib.util.spec_from_file_location('beginner',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    controller=load_controller(module);race=Race(make_track('oval'),1,180,1)
    while race.status=='running':race.advance(controller.act(race.observation()),0)
    assert race.status=='completed'


def test_upload_requires_single_function_file(setup):
    c,_=setup;url=f'/api/vehicle/competitions/{create(c)}/entries'
    for filename,source in [('agent.zip',b'zip'),('result.json',b'{}'),('agent.py',b'class Controller: pass'),('agent.py',b'def control(o): pass')]:
        assert c.post(url,headers={'X-User':'2'},files={'file':(filename,source)}).status_code==400
