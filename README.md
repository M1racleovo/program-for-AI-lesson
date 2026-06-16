# FaceFair — 人脸识别公平性审计

> 人工智能导论 课程项目  
> 基于 DeepFace / Facenet 的多维度 AI 偏见量化分析

## 项目简介

FaceFair 是一个 **AI 公平性评估工具**，用于量化人脸识别模型在不同种族、性别上的性能差异。

我们使用 Google 的 **Facenet** 模型对 **FairFace 数据集**（108,501 张已标注人脸）进行种族、性别、年龄预测，然后将预测结果与真实标签对比，检测模型是否存在系统性偏见。

**核心发现**：Facenet 在种族识别上存在显著偏见——最高准确率（East Asian 69.7%）与最低（Latino/Hispanic 22.5%）之间差距达 **47.2%**；性别维度上男性准确率 95%，女性仅 41%。

## 技术架构

```
FairFace 数据集 (108k 标注人脸)
        │
        ▼
face_fair_analyzer.py    ← DeepFace + Facenet 逐张分析
        │                   检测: OpenCV Haar Cascade
        │                   识别: Facenet (128-dim CNN)
        │                   属性: 种族 / 性别 / 年龄
        ▼
analysis_results.csv      ← 979 条完整分析记录
        │
        ├─► generate_summary()  → summary.txt     (统计摘要)
        └─► make_charts.py      → charts/*.png     (5 张可视化图表)
                    │
                    ▼
            generate_ppt.py  → FaceFair 演示文稿 (12 页)
```

## 评估指标

| 指标 | 说明 |
|------|------|
| 种族识别准确率 | 按 7 个种族分组，计算预测与真实标签的匹配率 |
| 性别识别准确率 | 按性别分组，含种族×性别交叉分析 |
| 混淆矩阵 | 行归一化，展示 AI 把某种族误判为哪些种族 |
| 置信度分布 | 箱线图，比较模型对不同种族的预测自信程度 |
| 公平性偏差 | 最优与最差种族准确率差距：<5% 轻微 / 5-15% 中度 / >15% 显著 |

## 项目结构

```
FaceFair/
├── config.py                 # 全局配置（路径、模型、类别映射）
├── face_fair_analyzer.py     # 核心分析引擎（数据加载 + DeepFace 批量分析 + 摘要生成）
├── make_charts.py            # 可视化脚本（5 张图表）
├── generate_ppt.py           # PPT 演示文稿生成（包含数据 & 图表嵌入）
├── generate_report.py        # Word 进展报告生成
├── run_test.py               # 环境验证脚本（8 项测试）
├── requirements.txt          # Python 依赖
├── .gitignore
├── data/fairface/            # [需自行下载] FairFace 数据集 + 标签 CSV
└── output/
    ├── analysis_results.csv  # [需运行生成] 逐张分析结果
    ├── summary.txt           # [需运行生成] 统计摘要
    └── charts/               # [需运行生成] 5 张可视化图表
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 下载数据集

从 [FairFace GitHub](https://github.com/joojs/fairface) 下载：

- **图片**：[train+val padding=0.25](https://drive.google.com/file/d/1Z1RqRo0_JiavaZw2yzZG6WETdZQ8qX86/view) → 解压到 `data/fairface/`
- **标签**：[train labels](https://drive.google.com/file/d/1i1L3Yqwaio7YSOCj7ftgk8ZZchPG7dmH/view) + [val labels](https://drive.google.com/file/d/1wOdja-ezstMEp81tX1a-EYkFebev4h7D/view) → 放到 `data/fairface/`

最终目录结构：

```
data/fairface/
├── train/          (86,744 张 jpg，纯数字命名)
├── val/            (10,954 张 jpg)
├── fairface_label_train.csv
└── fairface_label_val.csv
```

### 3. 验证环境

```bash
python run_test.py
```

### 4. 小规模测试（30 张，约 2 分钟）

```bash
python face_fair_analyzer.py
```

### 5. 全量分析（979 张，约 25 分钟）

```bash
python face_fair_analyzer.py --full
```

### 6. 生成图表

```bash
python make_charts.py
```

### 7. 生成演示 PPT

```bash
python generate_ppt.py
```

## 模型权重

首次运行 `face_fair_analyzer.py` 时 DeepFace 会自动下载所需权重到 `~/.deepface/weights/`：

| 文件 | 大小 | 用途 |
|------|------|------|
| facenet_weights.h5 | 88 MB | Facenet 人脸特征提取 |
| race_model_single_batch.h5 | 512 MB | 种族分类器 |
| gender_model_weights.h5 | 512 MB | 性别分类器 |
| age_model_weights.h5 | 514 MB | 年龄回归 |

（国内用户需开启代理，DeepFace 默认从 GitHub Releases 下载）

## 实验结果摘要

| 指标 | 数值 |
|------|------|
| 分析样本数 | 979（7 种族均匀采样） |
| 人脸检测成功率 | 100%（0 失败） |
| 总体种族准确率 | 51.79% |
| 总体性别准确率 | 69.87% |
| 最高种族准确率 | East Asian (69.72%) |
| 最低种族准确率 | Latino/Hispanic (22.54%) |
| 种族准确率差距 | **47.18%** → 显著偏见 |
| 性别差距 | Male 95.02% vs Female 41.14%（差距 53.88%） |

## 许可证

本项目代码仅供学术用途。FairFace 数据集采用 CC BY 4.0 许可证。
