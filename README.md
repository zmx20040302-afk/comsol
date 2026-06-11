# COMSOL 案例证据检索库

这是一个离线、可审计的案例检索原型。它递归读取 PDF、Markdown、JSON、CSV、TXT、
COMSOL 导出的 Java/M 代码，以及可直接提取文本的 MPH/PPA/PPTX 容器，将案例拆分为八类证据，并使用本地 TF-IDF 向量检索
相似案例。

核心原则：**没有来源摘录，就不输出具体 COMSOL 设置。**

## 使用

```powershell
python comsol_kb.py ingest "D:\案例目录" --output data\index.json
python comsol_kb.py ingest "D:\案例一" "D:\案例二" --output data\combined_index.json
python comsol_kb.py query "如何从图像生成 H 型梁曲线？" --index data\index.json
```

输出包含：

- 推荐案例与相似度
- 物理场、几何参数、材料、边界条件、网格、求解器、结果、适用范围的来源证据
- 仅基于已记录参数的修改候选
- 缺失证据风险
- 保守的验证步骤

## 文件与案例边界

每个直接包含受支持文件或图片的目录视为一个案例。图片文件名会用于主题检索，
但图片内容不会被当作 COMSOL 设置证据。MPH 仅提取容器内明确可读的文本文件；
无法提取时只用文件名参与主题检索。

## 限制

- 扫描版 PDF 需要先 OCR。
- MPH 的完整模型树需要 COMSOL API/导出报告；本工具不会猜测其内部设置。
- 离线 TF-IDF 适合小型知识库；大量案例可替换为嵌入模型和向量数据库，但仍应保留
  当前的证据引用与拒答策略。
