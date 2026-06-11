# 三维灯泡形电化学抛光模型

此模型通过 COMSOL LiveLink for MATLAB 构建一个三维灯泡形导电域，并将二维
“电化学抛光”案例中有明确证据的约束映射到三维。

## 证据映射

| 类别 | 三维模型设置 | 依据 |
|---|---|---|
| 几何 | 球体与圆柱颈部并集，单位 mm | “灯泡几何”案例的灯泡/轴对称几何思路 |
| 物理场 | Electric Currents，准静态方程 | 二维电化学抛光案例 |
| 电参数 | `V_applied=30 V`、`sigma_el=10 S/m`、`epsilonr_el=80` | 二维案例 |
| 移动边界 | `-K*(-ec.nJ)`，`K=1e-11 m^3/(A*s)` | 二维案例 |
| 网格 | `autoMeshSize(3)`、Free Tetrahedral | 二维案例的网格等级；四面体是三维实现 |
| 研究 | Transient，`range(0,10)` | 二维案例的原始时间列表 |

三维灯泡尺寸是新的显式设计参数，不是从二维电化学抛光案例推断出的设置。

## MATLAB 中运行

启动 **COMSOL with MATLAB**，切换到本目录后执行：

```matlab
model = build_electrochemical_polishing_3d_bulb;
```

若命令窗口只显示 Java 堆栈，使用诊断入口：

```matlab
clear functions
rehash
cd('D:\桌面\codex\comsol1\electrochemical_polishing_3d_bulb')
model = run_3d_bulb_diagnostic;
```

诊断入口会确认实际调用的脚本路径与 COMSOL LiveLink 连接，并将完整输出写入
`build_3d_bulb_log.txt`。普通 MATLAB 会话不能直接构建模型；应从 COMSOL 安装目录
提供的 **COMSOL with MATLAB** 快捷方式启动，或先连接正在运行的 COMSOL Server。

脚本会在求解前检查移动、接地和固定边界选择是否为空，随后保存：

```text
electrochemical_polishing_3d_bulb.mph
```

脚本运行时会输出 `[1/7]` 至 `[7/7]` 的构建阶段。若失败，会显示具体阶段，并尝试
保存 `electrochemical_polishing_3d_bulb_failed_stage.mph` 供 COMSOL 中检查。

## COMSOL 中检查

1. 检查 `Definitions > Selections` 中的 `sel_ground`、`sel_fixed` 和
   `geom1_sph1_bnd`，确认没有重叠或遗漏。
2. 检查球形表面为 `30 V` 与移动边界，底部灯口为 Ground，颈部为固定网格边界。
3. 求解时监视最小网格质量；若网格严重畸变，应缩短时间范围或减小时间步。
4. 将结果与二维案例量级比较：最大电流密度约 `9e5 A/m^2`、10 秒位移约
   `0.1 mm` 仅作为参考，不要求三维模型完全相同。

## 适用范围与风险

- 这是灯泡形导电域的电化学抛光演示，不是玻璃灯泡、灯丝和氩气的完整多物理场模型。
- 消耗速度仅按法向电流密度成比例计算，未包含完整电极动力学、传质和曲率效应。
- 三维边界编号不能沿用二维案例，因此使用命名选择；修改几何后必须重新检查选择。
- 球体与圆柱灯口必须有实体重叠，不能只在一点相切，否则三维 Union 可能形成无效几何。
