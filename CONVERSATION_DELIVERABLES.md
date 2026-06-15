# COMSOL 对话成果清单

本仓库保存了本轮对话期间完成的 COMSOL 案例知识库、官方文档索引、检索工具、MATLAB LiveLink 模型和验证结果。

## 知识库

- `comsol_kb.py`：读取案例目录并提取物理场、几何、材料、边界条件、网格、求解器、结果和适用范围。
- `comsol_docs_kb.py`：建立 COMSOL 官方文档检索索引。
- `COMSOL_MASTER_KNOWLEDGE_BASE.md`：汇总知识库说明。
- `COMSOL_KNOWLEDGE_BASE_MANIFEST.json`：知识库索引清单。
- `COMSOL_64_OFFICIAL_DOCS_GUIDE.md`：COMSOL 6.4 官方文档索引说明。
- `*_index.json`：案例和文档检索索引。大型索引通过 Git LFS 保存。

知识库遵循证据约束：没有明确案例或文档依据时，不推荐或虚构 COMSOL 设置。

## 三维 MEMS 声学芯片

目录：`mems_acoustic_chip_3d/`

- `build_mems_acoustic_chip_3d.m`：使用 MATLAB LiveLink 创建并求解三维封闭 MEMS 空气微腔。
- `run_mems_acoustic_field_test.m`：执行特征频率和声场中心线验证。
- `mems_acoustic_chip_3d.mph`：已求解的 COMSOL 6.4 模型。
- `mems_acoustic_mode_validation.csv`：前 12 个解析/数值模态对比。
- `mems_acoustic_centerline_pressure.csv`：第一模态中心线压力数据。
- PNG 文件：验证曲线和声场结果。

实际验证结果：

- 前 12 个模态最大相对误差：`0.012555%`
- 第一非零模态中心线形状相关系数：`1.000000`

## 测试

```powershell
python -m unittest discover -s tests -v
```

当前测试结果：`82` 项通过。

MATLAB 静态代码检查结果：所有 `mems_acoustic_chip_3d/*.m` 文件均为 `0 issues`。
