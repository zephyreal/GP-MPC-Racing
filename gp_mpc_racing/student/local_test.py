"""只运行你本人编写或教师提供的可信代码；本地成绩不用于打榜。"""
import argparse, importlib.util, json, time, html, shutil
from datetime import datetime
from pathlib import Path
from gp_mpc_racing.engine import Race, make_track

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--laps', type=int, default=1)
    parser.add_argument('--official', action='store_true', help='按下载包中的正式规则完整试跑')
    parser.add_argument('--track', choices=['oval','technical','track02-original-v1'], help='另选训练地图，不改变正式规则')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    cfg=json.loads((root/'competition.json').read_text(encoding='utf-8'))
    laps=cfg['laps'] if args.official else args.laps
    if not 1<=laps<=10:raise SystemExit('圈数须在1至10之间')
    spec=importlib.util.spec_from_file_location('student_agent',root/'agent.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    from gp_mpc_racing.function_adapter import load_controller;controller=load_controller(module)
    race=Race(make_track(args.track or cfg['track']),laps,cfg['max_time'],cfg['seed'])
    print('本地试跑：',race.track.name,'目标',laps,'圈',flush=True)
    last_lap=0
    while race.status=='running':
        start=time.monotonic()
        try:
            control=controller.act(race.observation())
            ms=(time.monotonic()-start)*1000
            budget=cfg.get('step_ms',2000)+(cfg.get('training_ms',20000) if race.last and race.last['lap_finished'] else 0)
            if ms>budget:race.stop('控制器超时')
            else:race.advance(control,ms)
        except Exception as exc:
            print('请检查 agent.py：',type(exc).__name__,str(exc));race.stop('控制器输出无效')
        if len(race.lap_times)!=last_lap:
            last_lap=len(race.lap_times);print('完成第',last_lap,'圈，用时',race.lap_times[-1],'秒',flush=True)
    result=race.result();output=root/'output';output.mkdir(exist_ok=True)
    cfg={**cfg,'track':args.track or cfg['track'],'laps':laps}
    (output/'local_result.json').write_text(json.dumps({'config':cfg,'track':race.track.public(),'student':result},ensure_ascii=False),encoding='utf-8')
    pts=race.track.points;xs=[p[0] for p in pts];ys=[p[1] for p in pts]
    x0,y0=min(xs)-8,min(ys)-8;w,h=max(xs)-x0+8,max(ys)-y0+8
    def line(points):return ' '.join(f'{p[0]:.3f},{-p[1]:.3f}' for p in points)
    summary=f"{result['status']}：{result['reason'] or '完成'}；完成 {result['completed_laps']} 圈；模拟时间 {result['simulated_seconds']} 秒"
    page=f"""<!doctype html><meta charset="utf-8"><title>本地试跑结果</title><style>body{{font:18px system-ui;max-width:960px;margin:30px auto;padding:20px}}svg{{width:100%;max-height:580px;background:#eef3ef}}pre{{white-space:pre-wrap}}</style><h1>本地试跑结果（不计正式成绩）</h1><p>{html.escape(summary)}</p><svg viewBox="{x0} {-y0-h} {w} {h}"><polyline points="{line(pts+[pts[0]])}" fill="none" stroke="#b7c9be" stroke-width="{race.track.width}"/><polyline points="{line([f['state'] for f in result['frames']])}" fill="none" stroke="#e67e22" stroke-width="0.6"/></svg><p>灰色：赛道；橙色：实际轨迹。越界可先降低目标速度，再调整前视距离。</p><p>满意后仅上传根目录 agent.py；不要上传本报告或整个案例包。</p><pre>逐圈用时：{result['lap_times']}<br>横向误差RMSE：{result['lateral_rmse']} m</pre>"""
    (output/'report.html').write_text(page,encoding='utf-8')
    history=output/datetime.now().strftime('%Y%m%d-%H%M%S-%f');history.mkdir()
    for name in ('report.html','local_result.json'):shutil.copy2(output/name,history/name)
    shutil.copy2(root/'agent.py',history/'agent.py')
    print('本次报告和代码已保留：',history)
    print(summary,'\n打开 output/report.html 查看轨迹。正式成绩以服务器为准。')
if __name__=='__main__':main()
