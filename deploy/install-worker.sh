#!/usr/bin/env bash
set -euo pipefail
umask 022
if [ "$(id -u)" -ne 0 ]; then echo '请在独立评测机的root终端执行'; exit 1; fi
if systemctl is-active --quiet writing-class; then echo '请勿在课程网站服务器运行学生代码，使用独立评测机'; exit 1; fi
RACING_SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
RACING_CONFIG="$(realpath "${1:?请传入教师网页生成的worker.json路径}")"
python3 - "$RACING_CONFIG" <<'PY'
import json,sys,os
from urllib.parse import urlparse
p=sys.argv[1];assert os.stat(p).st_mode&0o077==0,'配置文件须chmod 600'
c=json.load(open(p));assert urlparse(c['url']).scheme=='https' and c['token'],'需要教师网页生成的HTTPS配置'
assert c.get('image','gp-mpc-racing:v1')=='gp-mpc-racing:v1','此安装脚本使用标准镜像名'
PY
docker info --format '{{json .Runtimes}}' | python3 -c 'import json,sys;assert "runsc" in json.load(sys.stdin),"缺少gVisor/runsc，不允许降级"'
systemctl stop course-vehicle-worker.service 2>/dev/null || true
id vehicle-evaluator >/dev/null 2>&1 || useradd --system --home /var/lib/vehicle-race --shell /usr/sbin/nologin vehicle-evaluator
usermod -aG docker vehicle-evaluator
install -d -m 755 /opt/gp-mpc-racing
if [ "$RACING_SOURCE" != /opt/gp-mpc-racing ]; then
    cp -r "$RACING_SOURCE/gp_mpc_racing" /opt/gp-mpc-racing/
    cp "$RACING_SOURCE/Dockerfile" "$RACING_SOURCE/requirements.txt" "$RACING_SOURCE/.dockerignore" /opt/gp-mpc-racing/
fi
install -d -o vehicle-evaluator -g vehicle-evaluator -m 700 /var/lib/vehicle-race /etc/vehicle-race
if [ "$RACING_CONFIG" != /etc/vehicle-race/worker.json ]; then install -o vehicle-evaluator -g vehicle-evaluator -m 600 "$RACING_CONFIG" /etc/vehicle-race/worker.json; fi
chown vehicle-evaluator:vehicle-evaluator /etc/vehicle-race/worker.json
chmod 600 /etc/vehicle-race/worker.json
cd /opt/gp-mpc-racing
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
docker build -t gp-mpc-racing:v1 .
runuser -u vehicle-evaluator -- env RACE_WORK_DIR=/var/lib/vehicle-race .venv/bin/python -m gp_mpc_racing.smoke
install -m 644 "$RACING_SOURCE/deploy/course-vehicle-worker.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now course-vehicle-worker.service
systemctl restart course-vehicle-worker.service
echo '独立评测机已完成真实隔离验收并启动。'
