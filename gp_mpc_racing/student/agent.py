"""无人车入门：只修改本文件，测试后只上传 agent.py。
平台每0.15秒调用一次 control；不需要编写主程序、读文件或绘图。
学习顺序：先跑完 → 修改速度 → 修改前视距离 → 弯道减速/优化跑线。
"""
import math
from gp_mpc_racing.engine import Track

SPEED = 8.0       # 目标速度 m/s；首次实验改为7.0，其余不变
LOOKAHEAD = 7.0   # 前视距离 m；不是越大越好


def control(observation, reference, vehicle, memory):
    """输入（均由平台提供）：
    observation['state']: [x,y,yaw,vx,vy,yaw_rate]；m、rad、m/s、rad/s
    observation['time'/'dt']: 当前模拟时间/步长，秒
    observation['lap'/'target_laps']: 已完成圈数/目标圈数
    reference: 完整赛道字典，可用 Track.from_public 转为查询对象
    vehicle: length/width/wheelbase（m）、max_steering（rad）、dt（s）
    memory: 首次为None；返回后传给下一步，跨圈保留，每场重置

    输出：steering, drive, memory
    steering∈[-1,1]：正值左转，实际角度=steering*max_steering
    drive∈[-1,1]：正值驱动，负值制动（归一化控制量）
    可在本文件增加辅助函数；不上传地图、配置JSON、轨迹或成绩。
    """
    if memory is None:
        memory = {'track': Track.from_public(reference)}
    track = memory['track']
    x, y, yaw, vx, vy, yaw_rate = observation['state']

    # 1. 跑线：投影到中心线，寻找前方目标点。
    # project返回：距离、沿线里程、切线方向、带符号横向误差。
    distance, s, heading, lateral = track.project(x, y)
    tx, ty, _ = track.point(s + LOOKAHEAD)

    # 2. 转向：纯追踪，让车头朝向目标点。
    alpha = math.atan2(ty-y, tx-x) - yaw
    alpha = math.atan2(math.sin(alpha), math.cos(alpha))
    angle = math.atan2(2 * vehicle['wheelbase'] * math.sin(alpha), LOOKAHEAD)
    steering = max(-1.0, min(1.0, angle / vehicle['max_steering']))

    # 3. 速度：先使用固定目标速度，后续可改为弯道减速。
    target_speed = SPEED
    drive = max(-1.0, min(1.0, 0.25 * (target_speed-vx) + 0.1))
    return steering, drive, memory
