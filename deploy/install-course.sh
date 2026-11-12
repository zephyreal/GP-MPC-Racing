#!/usr/bin/env bash
set -euo pipefail
umask 022
if [ "$(id -u)" -ne 0 ]; then echo '请在网站服务器root终端运行'; exit 1; fi
RACING_SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
if [ ! -f /opt/writing-class/app.py ]; then echo '未找到现有课程平台 /opt/writing-class'; exit 1; fi
/opt/writing-class/.venv/bin/python -m py_compile "$RACING_SOURCE"/gp_mpc_racing/*.py
install -d -m 700 /root/course-backups
BACKUP_NAME="/root/course-backups/before-vehicle-racing-$(date +%Y%m%d-%H%M%S).tar.gz"
backup=(etc/systemd/system/writing-class.service var/lib/writing-class)
if [ -d /opt/writing-class/gp_mpc_racing ]; then backup+=(opt/writing-class/gp_mpc_racing); fi
if [ -d /etc/systemd/system/writing-class.service.d ]; then backup+=(etc/systemd/system/writing-class.service.d); fi
tar -czf "$BACKUP_NAME" -C / "${backup[@]}"
HAD_VEHICLE_OVERRIDE=0
if [ -f /etc/systemd/system/writing-class.service.d/vehicle-racing.conf ]; then HAD_VEHICLE_OVERRIDE=1; fi
restore_if_failed(){
    status=$?
    if [ "$status" -ne 0 ]; then
        systemctl stop writing-class || true
        if [ "$HAD_VEHICLE_OVERRIDE" -eq 0 ]; then rm -f /etc/systemd/system/writing-class.service.d/vehicle-racing.conf; fi
        tar -xzf "$BACKUP_NAME" -C /
        systemctl daemon-reload
        systemctl start writing-class || true
        echo "安装失败，已尝试恢复升级前备份：$BACKUP_NAME"
    fi
}
systemctl stop writing-class
trap restore_if_failed EXIT
install -d -m 755 /opt/writing-class/gp_mpc_racing
cp -r "$RACING_SOURCE/gp_mpc_racing/." /opt/writing-class/gp_mpc_racing/
find /opt/writing-class/gp_mpc_racing -type d -exec chmod 755 {} +
find /opt/writing-class/gp_mpc_racing -type f -exec chmod 644 {} +
cd /opt/writing-class
runuser -u writingclass -- env DATA_DIR=/var/lib/writing-class TZ=Asia/Shanghai .venv/bin/python -c 'import gp_mpc_racing.integrated; print("无人车扩展与数据库准备完成")'
install -d -m 755 /etc/systemd/system/writing-class.service.d
cat > /etc/systemd/system/writing-class.service.d/vehicle-racing.conf <<'SERVICE'
[Service]
ExecStart=
ExecStart=/opt/writing-class/.venv/bin/uvicorn gp_mpc_racing.integrated:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1
SERVICE
systemctl daemon-reload
systemctl start writing-class
for attempt in 1 2 3 4 5 6 7 8; do
    if curl -fsS http://127.0.0.1:8000/healthz; then
        trap - EXIT
        echo; echo '无人车模块已接入，教师与学生继续使用原账号；进入智能制造课程设计 → 无人车竞赛。'
        echo "备份：$BACKUP_NAME"
        exit 0
    fi
    sleep 1
done
echo "启动失败。备份位于 $BACKUP_NAME，请先恢复配置。"
exit 1
