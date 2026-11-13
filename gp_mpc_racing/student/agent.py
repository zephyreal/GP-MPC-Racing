"""入门控制器：先只修改 SPEED 与 LOOKAHEAD，再在本机试跑。"""
from gp_mpc_racing.controllers import PursuitController

SPEED = 8.0       # 目标速度，单位 m/s；过快可能越界
LOOKAHEAD = 7.0   # 前视距离，单位 m；观察其对弯道跟踪的影响

class Controller(PursuitController):
    def __init__(self):
        super().__init__(speed=SPEED, lookahead=LOOKAHEAD)

# 进阶：可以重写 act(self, observation)，返回：
# {"steering": -1到1的转向量, "torque": -1到1的驱动量}
# 正转向为左转；负 torque 为制动。不要向标准输出打印调试信息。
