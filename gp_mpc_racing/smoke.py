"""Run on the independent evaluator: real gVisor teacher and starter, full race and verifier."""
import argparse,tempfile,os
from pathlib import Path
from .worker import Agent,runtime,execute_race
from .server import baseline_hash
from .engine import make_track,verify

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--image',default='gp-mpc-racing:v1');args=parser.parse_args();image,fingerprint=runtime(args.image)
    cfg={'track':'oval','laps':2,'max_time':90,'seed':1,'step_ms':2000,'training_ms':20000,'learn':True,'baseline_hash':baseline_hash()}
    with tempfile.TemporaryDirectory(dir=os.getenv('RACE_WORK_DIR')) as temporary:
        folder=Path(temporary);folder.chmod(0o755);path=folder/'agent.py';path.write_text('from gp_mpc_racing.controllers import PursuitController\nController=PursuitController\n');path.chmod(0o444)
        for teacher in (True,False):
            agent=Agent(image,folder,teacher=teacher,learn=True,expected_baseline=cfg['baseline_hash'])
            try:result=verify(make_track(cfg['track']),cfg,execute_race(agent,cfg))
            finally:agent.close()
            if result['status']!='completed':raise SystemExit('隔离验收失败：'+str(result['reason']))
            print(('教师' if teacher else '学生模板')+'两圈验收通过：'+str(result['simulated_seconds'])+'模拟秒')
    print('gVisor真实对照与轨迹复核通过；环境指纹：'+fingerprint)
if __name__=='__main__':main()
