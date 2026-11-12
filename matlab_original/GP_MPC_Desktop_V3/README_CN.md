# GP-MPC Desktop V3：实时可视化、多圈、圈间学习

## 一键开始

解压整个文件夹，重启MATLAB以清除V2同名类缓存，将Current Folder切换到V3目录，运行：

```matlab
selftest_v3
START_LIVE
```

等价命令：

```matlab
out = run_learning(struct('laps',5,'learn',true,'live',true));
```

V2的 run_demo、benchmark_v2 和离线训练入口也保留；它们仍是V2工作流。V3新功能从 START_LIVE / run_learning 进入。

## 界面

- 左侧：地图、红色车辆方向三角形、蓝色历史轨迹、橙色当前预测轨迹。
- 右上：车辆速度曲线。
- 右下：已完成圈的模拟圈速。
- 顶部：模拟时间、电脑真实耗时、当前圈、速度(m/s与km/h)、求解耗时、exitflag、GP是否启用。
- Stop and save 按钮：在下一控制步边界停止并保存；关闭图窗也会停止。fmincon 或单次圈间训练期间需要等该调用结束，不是即时中断。

车辆仍是原全尺寸车辆模型。图形不是1:43物理尺度。

实时显示表示计算中持续刷新，不表示计算速度已经达到物理实时。默认每2个模拟步刷新一次，没有额外播放延时。图形刷新会增加电脑总耗时。

## 为什么原来只看到一段

V2默认 tf=15、dt=0.15，所以100步完成即正常结束，不代表已完成一圈。V3默认目标5圈、最大模拟时间600秒；达到任一限制结束，不无限运行。

圈数按当前点出发的沿程净进展累计到一整条赛道长度计数，不依赖固定地图起点；跨圈采用时间线性插值。该计时依赖位置投影，使用合成测试检查跨起终点行为，但未经过MATLAB闭环实测；复杂自交赛道需要更可靠的定位与过线规则。

## 学习如何工作

1. 第一圈使用无GP的compact控制，采集名义模型与仿真模型的速度/横摆状态残差。
2. 圈末暂停模拟时间，使用该圈前80%时间样本中均匀选出的至多80点训练GP，最后20%用于预测筛查。
3. 候选模型以0.3比例补偿残差。三个超参数优化必须正常退出；归一化验证均方误差总值至少改善2%，且任一输出不能恶化超过5%，才启用候选。
4. 下一圈固定模型，只进行推理，不逐步训练。圈末重新训练/筛查。
5. 当前圈有检测到的超宽，不从该圈推广新模型；新模型试运行一圈后出现超宽则退回旧模型。严重状态异常时停止，并在保存前退回上一模型。

以上是保守的实验性筛查，不是稳定性证明。尤其当前MPC可能仍有大量exitflag=0，未在该模式解决所有收敛问题。候选被拒绝时继续使用旧模型，界面和圈日志会记录原因；并非每圈都一定更新。

留出预测误差改善不保证闭环更快。采用相同控制目标和权重，GP通过提高动力学预测准确度可能改善圈速；不人为每圈加油门来制造“学习更快”。本版没有最优整圈轨迹学习或安全集终端约束，不应称为严格LMPC，也不保证圈速单调下降。

## 对比试验

先不开学习跑相同圈数，再开学习：

```matlab
baseline = run_learning(struct('laps',5,'learn',false,'live',true));
learned  = run_learning(struct('laps',5,'learn',true,'live',true));
```

两次默认使用相同初值、随机种子、控制目标和求解配置。第一圈从固定初速启动，后续圈是飞驰圈，不能仅把第一圈与第二圈对比就归因于GP。对比无学习与学习的对应圈，并结合越界和求解状态。

输出：results/baseline_laps_latest.mat、results/learning_latest.mat，以及对应的 _laps.csv。输出文件为各模式最新一次运行，会覆盖同名旧结果。

圈日志包括：seconds(模拟秒)、meanSpeed、lateralRMSE、outsideSamples、nonconverged、samples、usedGP、acceptedNext、reverted、trainingSeconds、screenOld、screenNew、updateReason。

注意usedGP描述本圈实际使用的模型；acceptedNext描述圈末接受、供下一圈使用的模型。第5圈结束后不再额外训练。

计时字段：solve_seconds为fmincon耗时；core_seconds含控制/仿真与数据收集；loop_seconds还包含绘图、圈间训练和控制台输出。训练时模拟时间暂停，所以圈速不计训练耗时；这是电脑版分圈学习实验，不是可直接部署的实时在线学习。

## 可调参数

```matlab
out = run_learning(struct('laps',10,'maxSimTime',900,'drawEvery',3));
% 尝试SQP（尚未证明比原内点算法好）
out = run_learning(struct('laps',5,'algorithm','sqp'));
% 无图计算，便于计时
out = run_learning(struct('laps',5,'live',false));
```

默认保留你已跑通的compact设置：10步预测、18个决策变量、内点算法、最多30次迭代。没有因加入学习而自动提速或更改奖励权重。

## 验证状态与边界

- 已通过全部32个MATLAB文件的MISS_HIT静态检查。
- 已用独立Python合成序列检查沿程跨圈计数/插值与反向跨界行为。
- 提供 selftest_v3：V2的数值自检、GP混合接口、跨圈计数测试。
- 当前环境无MATLAB/Octave，未实际运行GUI、闭环多圈、训练或圈速实验。
- 继承原全尺寸车辆、名义/真实模型差异、完美状态观测与原目标，非实车验证。
- 图形中的三角形只表示方向和位置，超宽计数不等于完整车身碰撞检测。

来源与旧优化细节见 README_V2_CN.md 和 ORIGINAL_README.md；保留原代码作者信息。
