# COMSOL 6.4 官方文档操作路线图

本文件依据本机 `D:\COMSOL64\Multiphysics\doc\pdf` 中的 COMSOL 6.4 官方 PDF 整理。
具体模型设置必须以对应物理模块手册、当前模型树和许可证实际可用功能为准。

## 1. 建模基本流程

1. 使用 Model Wizard 创建模型并选择空间维度、物理场和研究类型。
2. 在 Global Definitions 中定义跨组件使用的参数、函数和变量。
3. 在 Component 下依次配置 Definitions、Geometry、Materials、Physics 和 Mesh。
4. 在 Study 中选择稳态、瞬态、频域、特征频率或参数化扫描等求解步骤。
5. 计算后在 Results 中检查场分布、积分量、探针、派生值和收敛性。

依据：

- `COMSOL_ReferenceManual.pdf` 第 122 页：Model Wizard 与 Blank Model。
- `COMSOL_ReferenceManual.pdf` 第 167 页：Model Builder 默认节点。
- `COMSOL_ReferenceManual.pdf` 第 221 页：多物理场建模工作流。

## 2. 稳健选择几何实体

优先在 `Component > Definitions` 中创建 Named Selection，并用描述性名称表示入口、
出口、壁面、受热面或载荷面。修改选择后，引用该选择的材料、物理边界和其他节点会同步更新。
数字边界编号可用于检查，但不应作为可迁移模型的唯一依据。

依据：

- `COMSOL_ReferenceManual.pdf` 第 548 页：Named Selections。
- `COMSOL_ReferenceManual.pdf` 第 552 页：从 Selection List 创建 Explicit Selection。

## 3. 网格与求解验证

- 先检查几何和选择，再生成网格。
- 针对目标量逐级细化网格，而不是只观察网格外观。
- 在 Study 中启用或查看 convergence plots，检查非线性、线性和时间步求解过程。
- 多步骤研究需要确认中间解是否保存，以及后续步骤使用的初始值来源。
- 参数扫描必须记录参数值、失败点和每个解对应的工况。

依据：

- `COMSOL_ReferenceManual.pdf` 第 1582 页：Study settings 与 convergence plots。
- `COMSOL_ReferenceManual.pdf` 第 1712-1713 页：初始值、Progress Window 和求解进度。

## 4. MATLAB 与 COMSOL

典型 LiveLink for MATLAB 工作流程：

```matlab
% MATLAB 已通过 LiveLink 启动或连接到 COMSOL Server 后
model = mphload('model_file.mph');
mphrun(model);
mphsave(model, 'model_file_updated.mph');
```

常用操作：

- `mphstart`：连接 MATLAB 与 COMSOL Server。
- `mphload`：加载 MPH 文件或连接服务器中已有模型。
- `mphsave`：保存模型。
- `mphrun`：运行研究或求解器。
- `model.sol('sol1').runAll`：运行完整求解器序列。
- `model.sol('sol1').run('featureTag')`：运行到指定求解器特征。
- `model.sol('sol1').runFrom('featureTag')`：从指定求解器特征继续运行。

使用相对文件名时，MATLAB 会在 MATLAB path 中查找模型；为了避免加载错误文件，自动化脚本应优先使用绝对路径。

依据：

- `LiveLinkForMATLABUsersGuide.pdf` 第 45 页：加载和保存模型。
- `LiveLinkForMATLABUsersGuide.pdf` 第 52 页：连接 COMSOL Server。
- `LiveLinkForMATLABUsersGuide.pdf` 第 142、145 页：Study、Solver Sequence 和 `mphrun`。
- `LiveLinkForMATLABUsersGuide.pdf` 第 333-334 页：`mphload` 命令参考。

## 5. 使用本地官方文档检索

查询核心文档：

```powershell
python comsol_docs_kb.py query `
  --index D:\桌面\codex\comsol1\comsol_64_core_docs_index.json `
  --top-k 5 `
  "How to create named selections?"
```

检索结果包含文档名称、模块、PDF 路径、页码和原文摘录。回答 COMSOL 操作问题时，应优先引用这些
官方文档证据；官方文档没有明确给出的具体边界编号、材料值或求解器参数保持未知。
