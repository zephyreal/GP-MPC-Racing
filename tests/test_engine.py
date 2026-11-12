import copy,math,time
import pytest
from gp_mpc_racing.engine import *
from gp_mpc_racing.controllers import PursuitController,MPCController

CFG={'track':'oval','laps':1,'max_time':90,'seed':1,'step_ms':2000,'training_ms':20000,'learn':False}
def run(controller,cfg=CFG):
    race=Race(make_track(cfg['track']),cfg['laps'],cfg['max_time'],cfg['seed'])
    while race.status=='running':
        start=time.monotonic();race.advance(controller.act(race.observation()),(time.monotonic()-start)*1000)
    return race.result()
@pytest.fixture(scope='session')
def trusted_reports():return {'teacher':run(MPCController(learn=False)),'student':run(PursuitController())}

def test_complete_races_and_recompute(trusted_reports):
    for result in trusted_reports.values():
        assert result['status']=='completed' and len(result['lap_times'])==1
        checked=verify(make_track(),CFG,result)
        assert checked['simulated_seconds']==result['simulated_seconds'] and checked['progress']==1
    assert trusted_reports['teacher']['frames'][0]['state']==trusted_reports['student']['frames'][0]['state']

def test_never_accept_reported_positions_or_scores(trusted_reports):
    result=copy.deepcopy(trusted_reports['student']);result['score']=999;result['progress']=0
    assert verify(make_track(),CFG,result)['progress']==1
    result['frames'][10]['state'][0]+=1
    with pytest.raises(ValueError,match='位置或时间'):verify(make_track(),CFG,result)
    with pytest.raises(ValueError):action({'steering':float('nan'),'torque':0})
    with pytest.raises(ValueError):action({'steering':2,'torque':0})

def test_stopping_and_body_boundary():
    r=Race(make_track(),1,90);r.state[0]+=4;r.advance({'steering':0,'torque':0});assert r.status=='failed' and r.reason=='车身越界'
    r=Race(make_track(),1,90);r.stop('控制器超时');assert verify(make_track(),CFG,r.result())['progress']==0
    assert rank_key({'status':'completed','progress':1,'simulated_seconds':100})<rank_key({'status':'failed','progress':1,'simulated_seconds':1})

def test_full_lap_learning_is_screened_not_promised():
    controller=MPCController(learn=True,maxiter=8);cfg={**CFG,'laps':2};result=run(controller,cfg)
    assert result['status']=='completed' and len(result['lap_times'])==2
    updates=[f['telemetry'].get('gp_update','') for f in result['frames']]
    assert any(any(label in m for label in ('留出','拟合')) for m in updates)
    assert all(math.isfinite(v) for f in result['frames'] for v in f['state'])
