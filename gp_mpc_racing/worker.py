"""Independent trusted arbiter. Student code is extracted as inert files and run only under gVisor."""
import argparse,hashlib,json,math,os,queue,secrets,subprocess,tempfile,threading,time,zipfile
from pathlib import Path
import httpx
from .engine import Race,make_track
from .server import validate_archive,baseline_hash

MAX_LINE=32768

def command(image,path,name,teacher=False,learn=True):
    args=['docker','run','--interactive','--name',name,'--runtime=runsc','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true','--pids-limit=64','--cpus=1','--memory=768m','--memory-swap=768m','--user=65534:65534','--log-driver=none','--label=gp-mpc-race=1','--tmpfs=/tmp:rw,noexec,nosuid,size=64m']
    if teacher:args+=['--env=RACE_TEACHER=1','--env=RACE_LEARN='+str(int(learn))]
    else:args+=['--mount=type=bind,src='+str(path.resolve())+',dst=/submission,readonly']
    return args+[image]

def remove(name):
    try:subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
    except (OSError,subprocess.TimeoutExpired):pass

class Agent:
    def __init__(self,image,path,teacher=False,learn=True,expected_baseline=None):
        self.name='gp-mpc-race-'+secrets.token_hex(12);self.closed=False;self.bad=threading.Event();self.messages=queue.Queue(maxsize=2)
        self.process=subprocess.Popen(command(image,path,self.name,teacher,learn),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def read():
            try:
                while True:
                    line=self.process.stdout.readline(MAX_LINE+1)
                    if not line:break
                    if len(line)>MAX_LINE:raise ValueError()
                    self.messages.put_nowait(json.loads(line))
            except Exception:self.bad.set()
            finally:
                try:self.messages.put_nowait(None)
                except queue.Full:self.bad.set()
        def err():
            total=0
            while chunk:=self.process.stderr.read(8192):
                total+=len(chunk)
                if total>1_000_000:self.bad.set();remove(self.name);break
        self.readers=[threading.Thread(target=read,daemon=True),threading.Thread(target=err,daemon=True)]
        for thread in self.readers:thread.start()
        try:
            ready=self.next(time.monotonic()+20)
            if ready.get('ready') is not True:raise ValueError('控制器加载失败')
            if teacher and ready.get('baseline_hash')!=expected_baseline:raise ValueError('镜像与冻结教师基准不匹配')
        except Exception:self.close();raise
    def next(self,deadline):
        if self.bad.is_set():raise ValueError('控制器输出协议无效')
        try:reply=self.messages.get(timeout=max(.001,deadline-time.monotonic()))
        except queue.Empty:raise TimeoutError()
        if not isinstance(reply,dict):raise ValueError('控制器中断')
        return reply
    def act(self,observation,seconds):
        request_id=secrets.token_hex(16);started=time.monotonic();payload=json.dumps({'id':request_id,'observation':observation},separators=(',',':')).encode()+b'\n'
        if len(payload)>100000:raise ValueError('观测数据超过上限')
        # Bounded pipe request: a stalled/malicious reader must not block the arbiter forever.
        errors=[]
        def write():
            try:self.process.stdin.write(payload);self.process.stdin.flush()
            except (OSError,BrokenPipeError) as e:errors.append(e)
        writer=threading.Thread(target=write,daemon=True);writer.start();writer.join(timeout=seconds)
        if writer.is_alive():self.close();raise TimeoutError()
        if errors:raise ValueError('控制器中断')
        reply=self.next(started+seconds)
        elapsed=(time.monotonic()-started)*1000
        if elapsed>seconds*1000:raise TimeoutError()
        if reply.get('id')!=request_id or 'action' not in reply:raise ValueError('控制器响应无效')
        return reply['action'],elapsed
    def close(self):
        if self.closed:return
        self.closed=True;remove(self.name)
        if self.process.poll() is None:self.process.kill()
        self.process.wait(timeout=10)
        for pipe in (self.process.stdin,self.process.stdout,self.process.stderr):
            try:pipe.close()
            except OSError:pass
        for thread in self.readers:thread.join(timeout=1)

def execute_race(agent,config,cancelled=None):
    race=Race(make_track(config['track']),config['laps'],config['max_time'],config['seed'])
    while race.status=='running':
        if cancelled and cancelled.is_set():raise RuntimeError('任务租约失效')
        extra=config['training_ms'] if race.last and race.last['lap_finished'] else 0
        try:raw,ms=agent.act(race.observation(),(config['step_ms']+extra)/1000);race.advance(raw,ms)
        except TimeoutError:race.stop('控制器超时')
        except (ValueError,ArithmeticError):race.stop('控制器输出无效')
        except (OSError,BrokenPipeError):race.stop('控制器中断')
    return race.result()

def runtime(image):
    runtimes=json.loads(subprocess.check_output(['docker','info','--format','{{json .Runtimes}}'],text=True,timeout=10))
    if 'runsc' not in runtimes:raise RuntimeError('需要gVisor/runsc，不允许回退到本机执行学生代码')
    digest=subprocess.check_output(['docker','image','inspect',image,'--format','{{.Id}}'],text=True,timeout=10).strip()
    import platform
    source=b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))
    cpu=Path('/proc/cpuinfo').read_text() if Path('/proc/cpuinfo').exists() else platform.machine()
    runsc=runtimes['runsc'].get('path','runsc')
    version=subprocess.check_output([runsc,'--version'],text=True,timeout=10)
    # Do not hash volatile cpu MHz or per-boot fields.
    cpu='\n'.join(line for line in cpu.splitlines() if line.startswith(('model name','vendor_id')))
    fingerprint=hashlib.sha256(source+digest.encode()+cpu.encode()+version.encode()+platform.release().encode()).hexdigest()
    return digest,fingerprint

class Worker:
    def __init__(self,config):
        from urllib.parse import urlparse
        url=urlparse(config['url'])
        if url.scheme!='https' or not url.netloc or url.username or url.password or url.query or url.fragment:raise ValueError('只允许HTTPS课程平台地址')
        self.client=httpx.Client(base_url=config['url'].rstrip('/'),headers={'Authorization':'Bearer '+config['token'],'X-App-Request':'1'},trust_env=False,follow_redirects=False,timeout=45);self.image=config.get('image','gp-mpc-racing:v1')
    def post(self,path,payload):
        r=self.client.post('/api/vehicle/worker/'+path,json=payload);r.raise_for_status();return r.json()
    def tick(self):
        image,fingerprint=runtime(self.image);job=self.post('claim',{'fingerprint':fingerprint})['job']
        if not job:return False
        cfg=job['config'];lease=job['lease'];eid=job['id'];cancelled=threading.Event();done=threading.Event();agents=[];deadline=time.monotonic()+1800
        def heartbeat():
            failures=0
            while not done.wait(10):
                try:self.post(f'{eid}/heartbeat',{'lease':lease});failures=0
                except Exception:failures+=1
                if failures>=3 or time.monotonic()>deadline:
                    cancelled.set()
                    for agent in agents:remove(agent.name)
                    return
        thread=threading.Thread(target=heartbeat,daemon=True);thread.start();payload={'lease':lease,'fingerprint':fingerprint}
        try:
            if cfg['baseline_hash']!=baseline_hash():raise ValueError('教师基准与冻结版本不一致')
            with tempfile.TemporaryDirectory(prefix='race-input-',dir=os.getenv('RACE_WORK_DIR')) as temporary:
                folder=Path(temporary);folder.chmod(0o755);archive=bytearray()
                with self.client.stream('GET',f'/api/vehicle/worker/{eid}/source',headers={'X-Race-Lease':lease}) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes():
                        archive.extend(chunk)
                        if len(archive)>1_000_000:raise ValueError('附件过大')
                if hashlib.sha256(archive).hexdigest()!=job['sha']:raise ValueError('附件校验值错误')
                validate_archive(bytes(archive))
                import io
                with zipfile.ZipFile(io.BytesIO(archive)) as z:
                    for item in z.infolist():
                        if item.is_dir():continue
                        path=folder/item.filename;path.parent.mkdir(parents=True,exist_ok=True)
                        for directory in path.parents:
                            if directory==folder.parent:break
                            directory.chmod(0o755)
                        path.write_bytes(z.read(item));path.chmod(0o444)
                # Teacher has no student mount; neither container sees the other controller or credentials.
                teacher=Agent(image,folder,teacher=True,learn=cfg['learn'],expected_baseline=cfg['baseline_hash']);agents.append(teacher)
                payload['teacher']=execute_race(teacher,cfg,cancelled);teacher.close()
                if payload['teacher']['reason'] in ('控制器超时','控制器输出无效','控制器中断'):raise RuntimeError('教师基准运行异常')
                try:
                    student=Agent(image,folder);agents.append(student);payload['student']=execute_race(student,cfg,cancelled)
                except (ValueError,TimeoutError):
                    race=Race(make_track(cfg['track']),cfg['laps'],cfg['max_time'],cfg['seed']);race.stop('控制器中断');payload['student']=race.result()
                if cancelled.is_set():return True
                self.post(f'{eid}/result',payload)
        except Exception:
            if not cancelled.is_set():self.post(f'{eid}/result',{'lease':lease,'fingerprint':fingerprint,'error':'隔离评测或教师基准异常，请教师检查后重试'})
        finally:
            done.set();thread.join(timeout=50)
            for agent in agents:agent.close()
        return True

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--once',action='store_true');args=parser.parse_args();path=Path(args.config)
    if path.stat().st_mode&0o077:raise SystemExit('凭证文件必须chmod 600')
    import fcntl
    lock=open(path.with_suffix('.lock'),'a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    # Remove only this evaluator's labeled leftovers before beginning a new lease.
    leftovers=subprocess.check_output(['docker','ps','-aq','--filter','label=gp-mpc-race=1'],text=True,timeout=10).split()
    for container in leftovers:remove(container)
    worker=Worker(json.loads(path.read_text()))
    while True:
        try:worker.tick()
        except Exception:pass
        if args.once:break
        time.sleep(5)
if __name__=='__main__':main()
