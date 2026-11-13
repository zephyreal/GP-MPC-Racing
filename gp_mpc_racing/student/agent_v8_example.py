"""V8思路的Python教学简化版，适配网站6状态/2控制接口。
不是MATLAB V8等价移植，不含RLS、学习验证与原版稳定性筛选。
网站的物理引擎、赛道、计圈和教师基线不由本文件修改。
先修改下面三个参数，在同一赛道比较完成率、用时及误差。
"""
import math
from gp_mpc_racing.engine import Track, step, wrap, clamp, STEER

SPEED = 6.0        # 目标速度 m/s
LOOKAHEAD = 7.0    # 前视距离 m
HORIZON = 6       # 预测步数；增大也会增加计算量

class Controller:
    def __init__(self):
        self.track = None

    def feedback(self, state, speed, lookahead):
        x, y, yaw, vx, vy, yaw_rate = state
        s = self.track.project(x, y)[1]
        tx, ty, _ = self.track.point(s + lookahead)
        alpha = wrap(math.atan2(ty-y, tx-x)-yaw)
        steering = math.atan2(2*2.4*math.sin(alpha), lookahead)
        return {'steering': clamp(steering/STEER, -1, 1),
                'torque': clamp(.25*(speed-vx)+.1, -1, 1)}

    def act(self, observation):
        if self.track is None:
            self.track = Track.from_public(observation['track'])
        state = observation['state']
        # 先准备简单反馈作为备用；备用策略并不保证安全或完成。
        best = self.feedback(state, SPEED*.75, LOOKAHEAD)
        best_cost = float('inf')
        # 对4个候选策略预测，只执行最优候选的第一步。
        for speed_scale in (.75, 1.0):
            for look_scale in (1.0, 1.3):
                predicted = list(state)
                cost = 0.0
                first = None
                for _ in range(HORIZON):
                    action = self.feedback(predicted, SPEED*speed_scale, LOOKAHEAD*look_scale)
                    if first is None:
                        first = action
                    physical = [action['steering']*STEER, action['torque']]
                    predicted = step(predicted, physical, dt=observation['dt'], nominal=True)
                    distance, s, heading, lateral = self.track.project(*predicted[:2])
                    # 简化道路筛选；正式越界由网站对车身角点独立判断。
                    if distance > self.track.width/2 - 1.2:
                        cost = float('inf')
                        break
                    cost += 8*lateral*lateral + .8*(predicted[3]-SPEED)**2
                    cost += 2*wrap(predicted[2]-heading)**2
                if first is not None and cost < best_cost:
                    best_cost, best = cost, first
        return best


def control(observation, reference, vehicle, memory):
    """V8简化预测策略；memory保存本场控制器，跨圈保留。"""
    if memory is None:
        memory = Controller()
    action = memory.act({**observation, 'track': reference})
    return action['steering'], action['torque'], memory
