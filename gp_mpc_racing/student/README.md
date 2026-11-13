# V8示例与教师基线

最初教师基线保留，V8作为学生案例。网页“核心代码教学”展示关键片段，完整MATLAB工程单独下载。
START菜单选6自动备份当前agent.py并启用agent_v8_example.py，随后正常试跑，只上传agent.py。
这是V8思路的Python简化示例（候选预测＋反馈，不含RLS），与MATLAB原V8不数值等价。原V8的.m/.mat不能直接参加网站Python赛。
网站已经提供gp_mpc_racing中的物理、地图、教师控制器、评测与回放。不要把这些平台文件打包上传；辅助函数也写在agent.py中。

# 推荐入口：只打开 START.bat

全部解压后双击 START.bat，首次自动准备依赖，以后选择试跑即可。
详细中文图文教程：双击 START_HERE.html；网页也有“完整新手教程”入口。
第一次选1跑入门椭圆；用4打开代码，仅改变SPEED或LOOKAHEAD；再用2和3测试本场比赛。
在相同地图比较原设置与修改设置，最后只上传agent.py。旧的分步脚本仍可用。
macOS/Linux执行 python3 launch.py。

# 无人车课程设计：在电脑上完成，再上传

## 第一次使用（Windows）
1. 安装 Python 3.12（64位），安装时勾选 Add Python to PATH。
2. 将案例 ZIP **全部解压**到一个文件夹，不要在压缩包里运行。
3. 双击 01_setup.bat，首次联网安装依赖。出现“安装完成”再继续。
4. 双击 02_test_one_lap.bat，在当前比赛地图试跑1圈。打开 output/report.html 看轨迹。
5. 用 VS Code、VS 或文本编辑器打开 agent.py，先只修改 SPEED、LOOKAHEAD。保存后重新试跑。
6. 双击 03_test_official.bat，按比赛规定圈数测试（新比赛默认10圈）。
7. 回到网站，只上传根目录的 **agent.py**，简述本次修改，等待结果。提交成功后可关闭网页。

本地练习不限次数；正式上传次数以比赛设置为准。只运行本人或教师提供的可信代码。
本地试跑执行本人的代码，死循环请按 Ctrl+C；本地耗时与服务器不同，本地结果不保证正式通过。

## Linux/macOS 或命令行
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python local_test.py
.venv/bin/python local_test.py --official

## 三个循序渐进的实验
- A：只降低目标速度，观察是否更稳定。入门控制器在基础椭圆验证；复杂 Track02 不保证直接跑完。
- B：一次只改变前视距离，比较轨迹与横向误差。
- C：修改 control 函数，利用前方地图实现弯道减速，再比较10圈表现。
辅助训练：运行 .venv\Scripts\python local_test.py --track oval；此结果不混入正式比赛。
每次记下“修改内容、预期、结果”；样例不是必须战胜的优秀算法。

## 车辆与接口
统一入口：`control(observation, reference, vehicle, memory)`，返回 `steering, drive, memory`。drive由平台转换成内部torque字段。辅助函数也放在agent.py，无需编写Controller类。
这是全尺寸教学单轨仿真，不是1:43实车。车长3.8m、宽1.6m、轴距2.4m（前0.9m、后1.5m）；真实模型质量500kg，名义模型750kg；转动惯量分别600/900 kg·m²。
控制周期0.15s；最大转角±20°。steering∈[-1,1]，正值左转；torque∈[-1,1]，正值驱动（最高4000N），负值制动（最高8000N），不是直接设置速度。
observation['state']=[x,y,yaw,vx,vy,yaw_rate]；单位m、rad、m/s、rad/s。x向右、y向上、航向从+x轴逆时针为正。
地图通过第二个参数reference提供。observation 还包含 time、dt、progress、lap、target_laps、last_transition、max_steering。last_transition['action']为弧度转角与归一化驱动量，不同于返回值的归一化steering。
track.json 是本场地图，points按行驶顺序排列，第一个点为参考起点；原地图含左右边界和初始状态。map.html可直接在浏览器打开。
完整物理与越界规则见 gp_mpc_racing/engine.py；本机不能修改正式车辆参数。正式环境提供 NumPy、SciPy，不支持联网安装依赖。
同一场的memory跨圈保留，首次调用为None；重新评测时重置。正式成绩由平台计算，不上传圈数或轨迹。

## 常见问题
- 找不到Python：重新安装Python 3.12并添加PATH。
- 缺少模块：重新运行01_setup.bat，检查网络；不要直接双击agent.py。
- 车身越界：打开轨迹报告，尝试降低速度或改变前视距离。
- 上传什么：只上传含control函数的agent.py，不接受ZIP、JSON或本地结果。
- 教师GP-MPC与Python移植、原MATLAB记录分别标注；不承诺数值等价。原MATLAB回放属于进阶展示，不参与此模型赛。
