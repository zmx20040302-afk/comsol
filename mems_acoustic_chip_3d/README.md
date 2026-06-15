# 三维 MEMS 声学芯片与声场测试

本工程通过 MATLAB LiveLink 创建并求解一个三维 MEMS 封装声腔。声学组件采用可解析验证的矩形空气微腔；芯片组件展示硅衬底和 MEMS 薄膜外形，但不在缺乏依据时虚构薄膜材料、驱动或声固耦合设置。

## 已实现模型

| 项目 | 设置 |
|---|---|
| 声学物理场 | Pressure Acoustics |
| 空气腔尺寸 | `2 mm x 1.5 mm x 0.5 mm` |
| 芯片外形 | `3 mm x 2.5 mm x 0.3 mm` 衬底及 `10 um` 薄膜外形 |
| 空气参数 | `c_air=343 m/s`，`rho_air=1.225 kg/m^3` |
| 边界条件 | Pressure Acoustics 默认 Sound Hard Boundary |
| 网格 | Free Tetrahedral；在 `400 kHz` 下至少每波长 6 个单元 |
| 研究 | Eigenfrequency；搜索偏移 `80 kHz`，求解 12 个模态 |
| 输出 | 三维声压切片、声压级切片、解析频率对比 CSV 和 PNG |

## MATLAB 中运行

推荐从 **COMSOL Multiphysics with MATLAB** 启动 MATLAB，然后运行：

```matlab
cd('D:\桌面\codex\comsol1\mems_acoustic_chip_3d')
check_mems_acoustic_environment
results = run_mems_acoustic_field_test;
```

也可以先启动 COMSOL MPH Server，再在普通 MATLAB 中运行：

```matlab
addpath('D:\COMSOL64\Multiphysics\mli')
mphstart
cd('D:\桌面\codex\comsol1\mems_acoustic_chip_3d')
results = run_mems_acoustic_field_test;
```

成功后生成：

- `mems_acoustic_chip_3d.mph`
- `mems_acoustic_mode_validation.csv`
- `mems_acoustic_mode_validation.png`
- `mems_acoustic_pressure_mode.png`
- `mems_acoustic_centerline_pressure.csv`
- `mems_acoustic_centerline_pressure.png`

## COMSOL 中检查

1. 打开生成的 `mems_acoustic_chip_3d.mph`。
2. 在 **Acoustic Test Cavity** 组件中检查空气腔、Pressure Acoustics 和 Free Tetrahedral 网格。
3. 在 **MEMS Chip Geometry - Display Only** 组件中查看芯片外形。
4. 运行 **3D Acoustic Eigenfrequency Test**。
5. 查看 **3D Acoustic Pressure Eigenmode** 和 **3D Sound Pressure Level Eigenmode**。

## 验证依据

刚壁矩形声腔的非零特征频率为：

```text
f_mnq = c_air/2 * sqrt((m/Lx)^2 + (n/Ly)^2 + (q/Hcav)^2)
```

解析模态会自动生成并按频率排序，再与 COMSOL 的前 12 个非零模态比较。第一模态还会沿声腔中心线提取压力，并与解析 `(1,0,0)` 模态形状计算相关系数。前几个参考频率约为 `85.75 kHz`、`114.33 kHz`、`142.92 kHz` 和 `171.50 kHz`。

## 适用范围与风险

- 适用于验证三维封闭空气微腔的无损压力声学模态。
- 不包含压电驱动、薄膜结构变形、声固耦合、热黏性边界层、阻尼、开放域辐射或真实封装泄漏。
- MEMS 尺度下热黏性损耗可能重要；缺少材料、间隙和边界层依据时，本工程不会自行添加这些设置。
- 若要模拟真实麦克风灵敏度或执行器输出，必须提供薄膜材料、残余应力、驱动方式、结构边界和实验校准数据。
