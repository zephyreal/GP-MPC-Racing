"""One local entry: prepare environment once, run, inspect, then upload agent.py."""
import os,subprocess,sys,webbrowser,shutil
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def open_file(path):
    if os.name=='nt':os.startfile(str(path))
    else:webbrowser.open(path.as_uri())

def prepare():
    env=ROOT/'.venv';python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.exists():subprocess.run([sys.executable,'-m','venv',str(env)],check=True)
    check=subprocess.run([str(python),'-c','import numpy,scipy'],capture_output=True)
    if check.returncode:
        print('首次准备环境，需要联网，请等待……',flush=True)
        subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/'requirements.txt')],check=True)
    return python

def main():
    print('无人车本地学习助手：只改agent.py，最后也只上传agent.py。')
    python=None
    while True:
        print('\n1 入门演示：基础椭圆1圈（不计成绩）\n2 比赛地图试跑1圈\n3 按比赛规则完整试跑\n4 打开agent.py修改速度与前视距离\n5 阅读图文教程\n6 启用V8思路Python示例（自动备份当前agent.py）\n0 退出')
        choice=input('第一次请选择1：').strip()
        if choice=='0':return
        if choice=='4':
            if os.name=='nt':subprocess.Popen(['notepad.exe',str(ROOT/'agent.py')])
            else:print('请用文本编辑器打开：',ROOT/'agent.py')
        elif choice=='6':
            backup=ROOT/'output'/('code-backup-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
            backup.mkdir(parents=True)
            shutil.copy2(ROOT/'agent.py',backup/'agent.py')
            shutil.copy2(ROOT/'agent_v8_example.py',ROOT/'agent.py')
            print('已启用V8思路简化示例。旧代码备份：',backup,'；接下来选择1或2试跑。')
        elif choice=='5':open_file(ROOT/'START_HERE.html')
        elif choice in ('1','2','3'):
            try:
                if python is None:python=prepare()
                args=['--track','oval'] if choice=='1' else ['--official'] if choice=='3' else []
                subprocess.run([str(python),str(ROOT/'local_test.py'),*args],cwd=ROOT,check=True)
                open_file(ROOT/'output/report.html')
                print('报告已打开。继续调整，满意后回网站上传agent.py。')
            except (subprocess.CalledProcessError,OSError) as exc:
                print('本次未完成，请阅读上方错误；首次请检查Python安装和网络。',exc)
        else:print('请输入0至6。')
if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('已停止，可重新打开START.bat。')
