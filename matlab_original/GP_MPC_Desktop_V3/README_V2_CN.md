# GP-MPC 电脑版 V2（完整工程，2026-10-17 初始化修正版）

适用目标：先在电脑上跑通并加速原单轨赛车 GP-NMPC，不涉及 1:43 实车、建图或硬件。

本工程继承原项目的车辆方程、赛道和代价函数，重写了运行入口、GP离线训练、计时与对照流程，优化预测和核计算。不是宣称从零独立发明了原作者算法。原作者信息保留在源文件和 ORIGINAL_README.md；上传源码未附许可证，公开再分发前请核实原项目授权。

## 1. 最快运行方式

1. 解压整个文件夹。无需旧项目，也无需额外下载原来的 MAT。
2. 如果当前 MATLAB 会话已经运行旧版，先重启 MATLAB，避免同名类缓存。不要把旧/新工程同时加入路径。
3. 将 MATLAB Current Folder 切换到本文件夹。
4. 首次建议运行 `selftest_v2`。
5. 打开并运行 `START_HERE.m`，或执行：

```matlab
out = run_demo('fast');
```

默认跑15秒模拟时间，结束后画轨迹、求解耗时、横向误差和控制量，并写 results/fast_latest.mat。这个15秒只是首次运行方便，与原180秒总时长不同；提速必须比较每步耗时，不能比较总运行时间。

跑原来的180秒模拟时间：

```matlab
out = run_demo('fast',struct('tf',180));
```

环境：MATLAB R2019a 或以上，Optimization Toolbox；完整 selftest 使用 Statistics and Machine Learning Toolbox 的 pdist2。默认不启动并行池；开启并行需要 Parallel Computing Toolbox。没有 MATLAB/Octave 的机器不能直接运行本工程。

## 2. 模式选择

| 模式 | 用途 | GP在线更新 | 决策变量（N=10） |
|---|---|---|---|
| fast | 首先验证的基础快速控制 | 无，GP关闭 | 30 |
| compact | 更少控制变量 | 无，GP关闭 | 18 |
| reference | 同一V2框架的较慢预测路径，用作受控对照 | 无，GP关闭 | 30 |
| collect | 用基础控制器采集残差并保存 | 无，采集后单独训练 | 30 |
| gp | 使用离线训练好的固定GP | 无，只推理 | 30 |
| gp_compact | 固定GP与控制分组结合 | 无，只推理 | 18 |

先 fast，再 compact；不要把“GP尚未训练”误认为已经验证了GP增强控制。

```matlab
out = run_demo('compact',struct('tf',30));
```

compact 保留10步预测，分组为 [1 1 1 1 2 4]：前4步独立，后2步共享一个控制量，再后4步共享一个控制量。每组3个输入，共18个变量。第三个输入是沿参考线的虚拟进度速度，不是第三个物理执行器信号。分组会限制控制自由度，控制效果必须验证，不能声称与完整控制完全等价。

## 3. 已落实的优化

- 控制阶段默认不做GP训练。原脚本默认 useGP=false、trainGPonline=true，新默认仅运行基础控制、记录残差，避免未用GP补偿时每一步仍更新字典。
- 当前目标完全忽略协方差，且非线性额外约束为空。fast/compact 使用均值预测，跳过协方差传播与不需要的雅可比。未来若加入风险或机会约束，须恢复协方差通道。
- 固定步长的单步RK2改为显式中点公式，避免通用RK框架的临时数组和循环；reference 保留原积分实现。
- 赛道线性插值器只构造一次，reference 仍用 interp1。若手动修改 track 的地图数组，需要重新构造 RaceTrack 对象。
- GP核矩阵改用白化坐标与矩阵乘法，支持一般正定长度尺度矩阵；方差预测批量解三角系统，避免逐点循环。
- 默认不实时绘图，结果计算结束再绘图；关闭求解器逐迭代日志，定期打印进度。
- 保留滚动热启动。添加可选控制分组，不默认减小N或迭代次数。
- 修正代价时间累加 t=t+iN*dt 为 t=t+dt；当前赛车目标与时间无关。
- 修正原最近赛道点索引偏移，并使局部搜索跨起终点循环。所有V2模式都用同一修正，轨迹因此可能与原版有细微不同。
- 新版参数集中在 run_demo 的 cfg；不使用 clear all，也不依赖缺失的预训练文件。原类中的不相关演示方法保留以保持来源可追溯。

## 4. GP的正确使用流程

```matlab
% 先采集，过程中不训练
out = run_demo('collect',struct('tf',60));
% 离线优化超参数，最多选100个训练样本
metrics = train_gp_offline;
% 检查预测误差是否改善，再验证闭环
out = run_demo('gp',struct('tf',60));
```

训练脚本按时间把最后20%留作预测验证，前80%中均匀选择最多100点，分别拟合三个输出的超参数。此划分只是初步筛查，不代表跨工况泛化。模型保存在 results/gp_model.mat，加载时检查采样间隔。gp_residual_rmse 应与 nominal_residual_rmse 比较；即使预测误差改善，也仍需验证闭环轨迹、求解器状态与控制抖动。没有提供预训练“保证有效”的模型。

训练点数可配置：

```matlab
metrics = train_gp_offline(fullfile(pwd,'results','collect_latest.mat'),50);
```

新模型文件用结构体保存，而不是直接保存类对象，不兼容旧MAT直接加载；旧模型需要明确转换。

## 5. 如何判断真的变快且好用

```matlab
results = benchmark_v2(3,3);
```

先预热一次，再对 reference/fast/compact 每种跑3秒、重复3次并轮换次序，报告每步求解中位耗时、横向RMSE和非正退出标志数量。结果保存到 results/benchmark_latest.mat。

reference 是受控对照，不是原版全量复现：三种模式都关闭GP更新与实时图形、修正定位索引，且使用同一配置。不要把 reference 与 fast 的比值当作对原始脚本的全部提速倍数。要测原始程序，需要在原环境加 tic/toc，使用相同模拟时长、初值、dt和求解参数。

run_demo 输出包括：
- solve_seconds：单次 fmincon 调用耗时；不含每次构造选项的成本。
- step_seconds：整个计算循环耗时，含上述准备、仿真、残差采集，不含进度打印与最终绘图/保存。
- exitflag/iterations/function_evaluations：检查是否仅因提前退出而更快。
- contour_error/outside：相对进度参考点的横向误差与超宽计数，不是完整几何碰撞判定。
- summary：中位、P95、最大求解耗时、计算周期超限比例等。

fast 相对 reference 应主要体现实现提速；compact 需额外比较轨迹质量。建议先用3秒对照排查，再扩大到30秒、最后180秒完整测试。

当前沿用原局部优化算法，不保证全局最优或硬实时；maxiter=30也不是耗时上限。求解达到迭代上限时保留有限数值解并记录标志，便于离线分析，不是实车安全控制策略。

## 6. 已验证与未验证

已完成：
- MISS_HIT 对26个 MATLAB 文件进行静态语法/代码检查，无报告错误。
- 独立Python数值对照验证一般正定矩阵下的Mahalanobis核计算、批量方差求解及分组展开公式。
- 打包完整性检查。

未完成（当前执行环境没有 MATLAB/Octave）：
- selftest_v2 在 MATLAB 中的实际执行。
- fmincon 闭环求解、工具箱兼容性、全圈稳定性与运行时间测试。
- 对原版的实测提速倍数、GP补偿收益和精简模式轨迹质量。

不要将公式检查理解为已完成MATLAB运行验证。首次运行遇到报错，请保留完整错误与行号；运行成功后，把命令窗口的 summary 以及轨迹图反馈即可继续定位瓶颈。

## 7. 文件入口

- START_HERE.m：一键运行入口。
- run_demo.m：仿真、配置、计时、保存。
- race_cost.m：原赛车目标函数，保留原权重。
- train_gp_offline.m：采样筛选、超参数优化、预测验证。
- benchmark_v2.m：受控性能对比。
- selftest_v2.m / validate_fast_paths.m：数值一致性测试。
- plot_result.m：运行结束后的绘图。
- classes / CODEGEN / functions：完整依赖代码。
- source_changes.diff：相对上传版本的类修改差异。

## 初始化修复记录

修复 NMPC 构造函数遗漏 blockIndex=1:N 和 blockStarts=1:N 的问题。此前默认控制序列展开为空数组，导致 selftest_v2 的 costfun 报索引越界。增加默认30变量与3×10展开结果的自检，并添加决策向量/控制矩阵尺寸断言。此次修复经静态检查，尚未在MATLAB执行。
