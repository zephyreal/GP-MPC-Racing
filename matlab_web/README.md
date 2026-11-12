# 保留原 MATLAB 程序，网页只负责展示

`../matlab_original/GP_MPC_Desktop_V3/` 中36个文件与上传压缩包逐字节相同。此目录内的文件不要覆盖修改；学生变体另存副本，保留原作者信息。`MANIFEST.json`记录原始文件SHA-256，可核对有没有被改动。

## 原版怎么运行

在MATLAB中，先将当前目录切换到原项目目录，按原说明运行（需要原有工具箱）：

```matlab
cd matlab_original/GP_MPC_Desktop_V3
START_LIVE
```

网页没有替换`NMPC.m`、`GP.m`、`race_cost.m`或车辆模型。原始MATLAB程序仍使用原地图、原状态/控制维度和原求解器。网页Python版本只是独立移植试验，不是这个原程序。

原上传包的`selftest_v3.m`调用`selftest_v2`，但压缩包未包含`selftest_v2.m`。这一缺失已如实保留，没有伪造补回原文件。若要运行原自检，需补齐你原环境中的该文件；`START_LIVE`是另一个独立入口。

## 导出原地图

回到仓库根目录，在MATLAB执行：

```matlab
addpath('matlab_web');
selftest_web_export;
export_original_track('results/track02-native.json');
```

该函数直接调用原`RaceTrack.loadTrack_02()`和原构造函数，输出原中心线、左边界、右边界、方向和沿程坐标。网页默认静态地图按相同采样规则翻译生成；此原生导出用于逐点交叉核对，不用椭圆代替、不重采样或平滑。

## 导出两台车的原版结果

分别得到教师原版和学生变体的`out`结构，避免同名类/函数缓存和结果文件覆盖：

```matlab
% 当前目录为原项目目录；先按原有入口运行教师版本。
teacherOut = run_learning(struct('laps',5,'learn',true,'live',true));
save('teacher_original.mat','teacherOut');
```

学生变体应在独立副本/单独MATLAB会话运行，输出同样字段的`studentOut`。不要把两套同名类同时加入MATLAB路径。

得到两个结构后，在仓库根目录：

```matlab
addpath('matlab_web');
export_web_replay(teacherOut, studentOut, 'results/matlab-original-dual-replay.json');
```

也可传入原程序保存且含`out`变量的两个可信MAT文件路径。然后在网页“导入MATLAB原版回放”选择生成的JSON。

- 原7维状态和3维控制完整保存在`original_state`、`original_control`，网页位置与速度取原记录，不重新用Python仿真。
- 原圈速、求解耗时、GP逐圈记录与配置保留。GP启用显示按原`laps.usedGP`记录重建。
- 原`run_learning`没有保存每步预测轨迹，适配器不会编造这一条线；Python试跑的预测轨迹另行标明。
- 导入只在浏览器本地用于对照展示，不调用上传代码接口，不进入正式排行榜；不能把学生自报轨迹当正式成绩。
- 适配器通过静态检查后仍须在你的MATLAB环境运行验证。当前开发环境没有MATLAB，未宣称原版闭环已经在这里运行通过。
