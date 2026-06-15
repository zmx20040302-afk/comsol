# COMSOL 案例总知识库

- 案例总数：79
- 来源目录数：77
- 检索方式：本地 TF-IDF 向量检索，并保留逐条来源证据。
- 安全原则：缺少直接证据的 COMSOL 设置保持未知，不进行推断或虚构。

## 使用方式

```powershell
python comsol_kb.py query "用户问题" --index comsol_master_cases_index.json --top-k 5
```

查询结果包含推荐案例、可修改的已记录参数、风险点、证据缺口和验证步骤。

## 案例目录

### 传热与热耦合

| 案例 | 已记录字段 | 参数数 |
|---|---|---:|
| 含载荷突变的瞬时加热6.2 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 8 |
| 已实施反应延迟的恒温器 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 54 |
| 微执行器焦耳热 - 分布式参数版本 | physics、geometry、materials、boundary_conditions、mesh、solver、results、applicability | 19 |
| 恒温器特性建模6.2 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 44 |
| 母线板焦耳热 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 14 |
| 母线板装配的焦耳热 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 44 |
| 热微执行器的简化模型 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 23 |
| 热执行器 | physics、geometry、materials、boundary_conditions、mesh、solver、results、applicability | 30 |
| 热控制器，降阶模型 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 63 |
| 热烧蚀除料建模6.2 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 100 |
| 真空干燥 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 42 |
| 硅晶片激光加热 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 18 |
| 碳纤维编织结构的各向异性传热 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 26 |
| 稳态传导传热 - 二维 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 12 |
| 稳态辐射传热 - 一维 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 7 |
| 自然对流传热 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 8 |
| 轴对称瞬态传热 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 23 |
| 飞秒激光加热引起的超快传热 | physics、geometry、materials、boundary_conditions、mesh、solver、results、applicability | 100 |

### 其他案例

| 案例 | 已记录字段 | 参数数 |
|---|---|---:|
| COMSOL_json | 仅主题证据 | 0 |
| jsonscripts | 仅主题证据 | 0 |
| 使用 PID 控制器的过程控制 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 40 |
| 使用插值和图像数据为不规则形状建模 | geometry、mesh | 2 |
| 在轨航天器 | physics、geometry、materials、mesh、solver、results | 88 |
| 如何生成随机非均匀材料数据6.2 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 16 |
| 状态变量6.3 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 19 |
| 高尔夫球的轨迹 | physics、solver、results | 100 |

### 几何、CAD 与网格

| 案例 | 已记录字段 | 参数数 |
|---|---|---:|
| 使用网格划分序列 | geometry、mesh、applicability | 6 |
| 借助变形几何接口修改导入的 CAD 几何 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 33 |
| 在 COMSOL Multiphysics 中编辑与修复面网格 | geometry、mesh | 48 |
| 基于扫描数据生成可供仿真的网格 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 36 |
| 支架几何的扫掠网格 | geometry、mesh | 15 |
| 母线板装配几何系列教程 | geometry、mesh、results | 26 |
| 科赫雪花建模 | geometry、mesh、results | 0 |
| 蒸汽重整器几何 | geometry、mesh | 7 |
| 轮辋几何虚拟操作 | geometry、mesh、results | 1 |

### 声学、振动与波动

| 案例 | 已记录字段 | 参数数 |
|---|---|---:|
| 同频鼓 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 2 |
| 曼德勃罗集和柏林噪声 | physics、geometry、materials、mesh、solver、results | 21 |
| 汽车消声器 | physics、geometry、materials、boundary_conditions、mesh、solver、results、applicability | 3 |
| 激波管 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 42 |
| 瞬态声压级6.3 | physics、geometry、materials、mesh、solver、results | 41 |
| 衍射图样 | physics、geometry、materials、boundary_conditions、mesh、solver、results、applicability | 13 |
| 音叉 | physics、geometry、materials、mesh、solver、results、applicability | 26 |

### 数学、方程与数据工具

| 案例 | 已记录字段 | 参数数 |
|---|---|---:|
| 延迟微分方程 | physics、geometry、solver、results | 31 |
| 曲线数字化仪 | physics、geometry、materials、mesh、solver、results | 0 |
| 洛伦兹吸引子 | physics、geometry、materials、mesh、solver、results | 21 |
| 浅水方程 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 27 |
| 积分-偏微分方程 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 23 |

### 流体、传质与反应

| 案例 | 已记录字段 | 参数数 |
|---|---|---:|
| 化学蚀刻 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 42 |
| 圆柱绕流 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 10 |
| 岩石裂隙流 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 12 |
| 微混合器 | physics、geometry、materials、boundary_conditions、mesh、solver、results、applicability | 15 |
| 球对称传递 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 29 |
| 砂粒的自由沉降速度 | physics、geometry、materials、boundary_conditions、mesh、solver、results、applicability | 41 |
| 自由流体中的浮力流 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 40 |
| 螺旋静态混合器 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 21 |
| 钢罐中的壳扩散 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 5 |

### 电磁、生物电与量子

| 案例 | 已记录字段 | 参数数 |
|---|---|---:|
| 四极透镜 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 32 |
| 心脏电信号 | physics、geometry、materials、boundary_conditions、mesh、solver、results、applicability | 41 |
| 用 Hodgkin-Huxley 模型模拟动作电位 | physics、geometry、materials、mesh、solver、results | 21 |
| 起搏器电极 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 5 |
| 起搏器电极模型中添加注释 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 3 |
| 锥形量子点 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 21 |

### 结构力学

| 案例 | 已记录字段 | 参数数 |
|---|---|---:|
| 两种载荷工况下的锥形悬臂梁 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 10 |
| 受载弹簧 - 使用全局方程满足约束条件 | physics、geometry、materials、boundary_conditions、mesh、solver、results、applicability | 6 |
| 曲轴子模型分析 | physics、geometry、materials、boundary_conditions、mesh、solver、results、applicability | 0 |
| 涡轮增压器转子的特征值分析 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 4 |
| 通信塔桅斜撑支架的刚度分析 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 24 |
| 通信塔桅零件的灵敏度分析 | physics、geometry、materials、boundary_conditions、mesh、solver、results、applicability | 35 |
| 馈线夹的变形 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 11 |

### 部署、App 与自动化

| 案例 | 已记录字段 | 参数数 |
|---|---|---:|
| 使用 Microsoft® Azure 运行 COMSOL® 软件 | 仅主题证据 | 0 |
| 使用文本文件自动进行模型预处理 | physics、geometry、mesh、results | 0 |
| 如何在求解后自动导出图像仅6.3 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 26 |
| 微混合器 - 批处理和集群版本 | physics、geometry、materials、boundary_conditions、mesh、solver、results、applicability | 15 |
| 求解模型后保存数据的作业序列6.3 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 21 |
| 热执行器代理模型 App | physics、geometry、materials、boundary_conditions、mesh、solver、results | 42 |
| 管式反应器代理模型 App | physics、geometry、materials、boundary_conditions、mesh、solver、results、applicability | 86 |
| 通过 Amazon EC2™ 运行 COMSOL® 软件 | 仅主题证据 | 0 |
| 限时和硬件锁定的 App | physics、geometry、materials、mesh、solver、results | 12 |
| 集群设置验证 | physics、geometry、materials、boundary_conditions、mesh、solver、results | 1 |

## 验证原则

1. 首先确认物理接口、维度假设、材料和边界选择。
2. 检查质量、动量、电流或能量守恒。
3. 对网格、时间步、容差和参数范围执行收敛或敏感性分析。
4. 使用解析解、实验数据或可信基准案例交叉验证。
5. App、云部署、几何和网格教程不得被解释为未记录的物理设置。

## 官方文档库

案例总库用于查找可参考模型；COMSOL 6.4 官方文档索引用于核对软件操作与 API。

```powershell
python comsol_docs_kb.py query "操作问题" --index comsol_64_all_docs_index.json --top-k 5
```
