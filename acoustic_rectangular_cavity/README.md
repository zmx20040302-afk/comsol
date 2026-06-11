# COMSOL 声学测试模型：二维刚壁矩形声腔

该模型用于测试 COMSOL 的基础压力声学建模、网格、特征频率求解和声压模态显示。
它采用可解析验证的矩形刚壁声腔，避免引入没有依据的复杂声源或吸声边界。

## 模型设置

| 项目 | 设置 |
|---|---|
| 物理场 | Pressure Acoustics |
| 几何 | 4 m × 3 m 二维矩形空气域 |
| 材料 | `c_air = 343 m/s`，`rho_air = 1.225 kg/m³` |
| 边界条件 | Pressure Acoustics 默认 Sound Hard Boundary |
| 网格 | 自由三角形，`hmax = c_air/(6×120 Hz)` |
| 研究 | Eigenfrequency，搜索偏移 `35 Hz`，请求 8 个模态 |
| 结果 | 声压 `p` 的二维表面图 |

## 在 COMSOL 中运行

1. 确认许可证包含 Pressure Acoustics 所需功能。
2. 在 COMSOL Desktop 中打开 `Developer > Java Editor`。
3. 打开并运行 `acoustic_rectangular_cavity.java`。
4. 脚本求解后会在当前工作目录保存 `acoustic_rectangular_cavity.mph`。

## 使用 MATLAB / LiveLink

在 COMSOL with MATLAB 会话中，将当前目录切换到本文件夹并运行：

```matlab
check_matlab_comsol_environment
model = build_acoustic_rectangular_cavity;
```

仅计算解析参考频率：

```matlab
acoustic_rectangular_cavity_reference_frequencies
```

当前机器检测到 `D:\bin\matlab.exe`，但许可证返回 `License Manager Error -9`，因此尚未
实际执行 MATLAB 或 LiveLink 求解。许可证重新激活后即可运行上述脚本。

## 解析验证

刚壁矩形声腔的非零特征频率为：

```text
f_mn = c_air/2 * sqrt((m/Lx)^2 + (n/Ly)^2)
```

当前参数下，前四个预期非零模态约为：

| 模态 | 解析频率 |
|---|---:|
| `(1,0)` | 42.875 Hz |
| `(0,1)` | 57.167 Hz |
| `(1,1)` | 71.458 Hz |
| `(2,0)` | 85.750 Hz |

验证时将 COMSOL 求得的特征频率与这些值比较。建议前四个非零模态的相对误差低于
1%；若误差较大，应先细化网格，再检查几何尺寸、空气声速和边界条件。

## 修改与风险

- 可安全修改的参数均列在 `acoustic_rectangular_cavity_parameters.txt` 中。
- 修改声腔尺寸或声速后，必须同步重新计算解析参考频率。
- 该模型假设静止、均匀、无损空气和完全刚性壁面。
- 它不用于验证流动声学、热黏性损耗、吸声壁面、结构声耦合或开放域辐射。
- 脚本基于 COMSOL Java API 常用接口生成，但当前机器未检测到 COMSOL，无法在此处实际求解生成 `.mph`。
