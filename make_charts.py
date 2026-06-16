"""
FaceFair 可视化脚本

生成以下图表:
  1. 各种族识别准确率柱状图
  2. 种族×性别准确率热力图
  3. 预测种族 vs 真实种族混淆矩阵
  4. 各种族置信度分布箱线图
  5. 公平性偏差雷达图

用法:
  python make_charts.py                        # 使用默认 CSV
  python make_charts.py --input results.csv    # 指定输入文件
"""

import os
import sys
import argparse

import pandas as pd
import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")  # 非 GUI 后端
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    from matplotlib.font_manager import FontProperties
except ImportError:
    print("错误: 未安装 matplotlib。请运行: pip install matplotlib")
    sys.exit(1)

try:
    import seaborn as sns
except ImportError:
    print("错误: 未安装 seaborn。请运行: pip install seaborn")
    sys.exit(1)

from config import (
    OUTPUT_DIR,
    CHARTS_DIR,
    RESULTS_CSV,
    RACE_CATEGORIES,
    GENDER_CATEGORIES,
)


def ensure_chart_dir():
    os.makedirs(CHARTS_DIR, exist_ok=True)


def set_chinese_font():
    """尝试设置中文字体，失败则用英文标签"""
    cn_fonts = ["SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC"]
    available = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    for font in cn_fonts:
        if font in available:
            plt.rcParams["font.sans-serif"] = [font, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            return True
    return False


def load_data(csv_path):
    """加载并清洗分析结果数据"""
    if not os.path.exists(csv_path):
        print(f"错误: 未找到结果文件 {csv_path}")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    valid = df[df["pred_race"].notna()].copy()
    if len(valid) == 0:
        print("错误: 无有效分析数据")
        sys.exit(1)
    return valid


def chart_race_accuracy(df):
    """图1: 各种族识别准确率柱状图"""
    races = []
    accs = []
    counts = []

    for race in RACE_CATEGORIES:
        subset = df[df["true_race"] == race]
        if len(subset) > 0:
            races.append(race)
            accs.append(subset["match_race"].mean() * 100)
            counts.append(len(subset))

    fig, ax = plt.subplots(figsize=(12, 6))
    colors = plt.cm.RdYlGn(plt.Normalize(vmin=min(accs), vmax=max(accs))(accs))
    bars = ax.bar(range(len(races)), accs, color=colors, edgecolor="gray")

    # 标注样本数
    for i, (acc, cnt) in enumerate(zip(accs, counts)):
        ax.text(i, acc + 1, f"n={cnt}", ha="center", fontsize=9)

    ax.set_xticks(range(len(races)))
    ax.set_xticklabels(races, rotation=30, ha="right", fontsize=10)
    ax.set_ylabel("Accuracy (%)", fontsize=12)
    ax.set_title("Race Recognition Accuracy by Ethnic Group", fontsize=14, fontweight="bold")
    ax.set_ylim(0, max(accs) * 1.2 + 5)
    ax.axhline(y=np.mean(accs), color="blue", linestyle="--", linewidth=1, label=f"Mean: {np.mean(accs):.1f}%")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "01_race_accuracy.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"已保存: {path}")


def chart_gender_accuracy(df):
    """图2: 各种族×性别准确率对比"""
    data = []
    for race in RACE_CATEGORIES:
        for gender in GENDER_CATEGORIES:
            subset = df[(df["true_race"] == race) &
                        (df["true_gender"].str.lower() == gender.lower())]
            if len(subset) > 0:
                data.append({
                    "Race": race,
                    "Gender": gender,
                    "Accuracy": subset["match_race"].mean() * 100,
                    "Count": len(subset),
                })

    plot_df = pd.DataFrame(data)
    if plot_df.empty:
        print("无足够的种族×性别交叉数据")
        return

    fig, ax = plt.subplots(figsize=(12, 6))
    pivot = plot_df.pivot(index="Race", columns="Gender", values="Accuracy")

    sns.heatmap(pivot, annot=True, fmt=".1f", cmap="YlOrRd", ax=ax,
                cbar_kws={"label": "Accuracy (%)"}, linewidths=0.5)
    ax.set_title("Race Recognition Accuracy: Race × Gender", fontsize=14, fontweight="bold")
    ax.set_ylabel("")

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "02_race_gender_heatmap.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"已保存: {path}")


def chart_confusion_matrix(df):
    """图3: 预测种族 vs 真实种族混淆矩阵"""
    # 标准化种族名称
    def normalize_race(r):
        if not isinstance(r, str):
            return "Unknown"
        r = r.lower().replace(" ", "").replace("_", "")
        mapping = {
            "white": "White", "caucasian": "White",
            "black": "Black", "africanamerican": "Black",
            "eastasian": "EAsian", "asian": "EAsian",
            "southeastasian": "SEAsian",
            "indian": "Indian", "southasian": "Indian",
            "middleeastern": "MEast",
            "latino": "Latino", "hispanic": "Latino",
            "latinohispanic": "Latino",
        }
        for k, v in mapping.items():
            if k in r:
                return v
        return r[:15]

    df = df.copy()
    df["true_race_short"] = df["true_race"].apply(normalize_race)
    df["pred_race_short"] = df["pred_race"].apply(normalize_race)

    # 获取所有出现的类别
    labels = sorted(set(df["true_race_short"].unique()) | set(df["pred_race_short"].unique()))

    n = len(labels)
    matrix = np.zeros((n, n))
    label_to_idx = {l: i for i, l in enumerate(labels)}

    for _, row in df.iterrows():
        ti = label_to_idx.get(row["true_race_short"], -1)
        pi = label_to_idx.get(row["pred_race_short"], -1)
        if ti >= 0 and pi >= 0:
            matrix[ti][pi] += 1

    # 行归一化
    row_sums = matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    matrix_norm = matrix / row_sums

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(matrix_norm, annot=True, fmt=".2f", cmap="Blues",
                xticklabels=labels, yticklabels=labels, ax=ax,
                vmin=0, vmax=1, linewidths=0.5)
    ax.set_xlabel("Predicted", fontsize=12)
    ax.set_ylabel("True", fontsize=12)
    ax.set_title("Race Prediction Confusion Matrix (Row Normalized)", fontsize=14, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "03_confusion_matrix.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"已保存: {path}")


def chart_confidence_boxplot(df):
    """图4: 各种族识别置信度分布"""
    fig, ax = plt.subplots(figsize=(12, 6))

    race_data = []
    race_labels = []
    for race in RACE_CATEGORIES:
        confs = df[(df["true_race"] == race) & df["race_confidence"].notna()]["race_confidence"]
        if len(confs) > 0:
            race_data.append(confs.values)
            race_labels.append(race)

    if not race_data:
        print("无足够的置信度数据")
        return

    bp = ax.boxplot(race_data, labels=race_labels, patch_artist=True,
                    showmeans=True, meanprops=dict(marker="D", markerfacecolor="red"))

    colors = plt.cm.Set3(np.linspace(0, 1, len(race_labels)))
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)

    ax.set_ylabel("Confidence Score", fontsize=12)
    ax.set_title("Race Prediction Confidence Distribution by Ethnic Group", fontsize=14, fontweight="bold")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "04_confidence_boxplot.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"已保存: {path}")


def chart_fairness_radar(df):
    """图5: 公平性雷达图——多维度偏差评估"""
    metrics = {}
    for race in RACE_CATEGORIES:
        subset = df[df["true_race"] == race]
        if len(subset) > 4:
            race_acc = subset["match_race"].mean() * 100
            gender_acc = subset["match_gender"].mean() * 100
            detection_rate = (subset["pred_race"].notna().sum() / len(subset)) * 100
            metrics[race] = {
                "Race Acc.": race_acc,
                "Gender Acc.": gender_acc,
                "Detection Rate": detection_rate,
            }

    if len(metrics) < 2:
        print("雷达图需要至少2个种族的数据")
        return

    categories = ["Race Acc.", "Gender Acc.", "Detection Rate"]
    n_cats = len(categories)
    angles = np.linspace(0, 2 * np.pi, n_cats, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
    colors = plt.cm.tab10(np.linspace(0, 1, len(metrics)))

    for (race, vals), color in zip(metrics.items(), colors):
        values = [vals[c] for c in categories]
        values += values[:1]
        ax.fill(angles, values, alpha=0.1, color=color)
        ax.plot(angles, values, "o-", linewidth=2, color=color, label=race)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=11)
    ax.set_ylim(0, 105)
    ax.set_title("Fairness Radar: Multi-Dimensional Bias Assessment", fontsize=14, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.0))

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "05_fairness_radar.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"已保存: {path}")


def main():
    parser = argparse.ArgumentParser(description="FaceFair 可视化工具")
    parser.add_argument("--input", type=str, default=RESULTS_CSV,
                        help=f"分析结果 CSV (默认: {RESULTS_CSV})")
    parser.add_argument("--charts", type=str, nargs="+",
                        default=["race", "gender", "confusion", "confidence", "radar"],
                        help="要生成的图表类型")
    args = parser.parse_args()

    ensure_chart_dir()
    set_chinese_font()

    print("加载数据中...")
    df = load_data(args.input)
    print(f"有效数据行数: {len(df)}\n")

    chart_funcs = {
        "race": ("各种族准确率柱状图", chart_race_accuracy),
        "gender": ("种族×性别热力图", chart_gender_accuracy),
        "confusion": ("种族混淆矩阵", chart_confusion_matrix),
        "confidence": ("置信度箱线图", chart_confidence_boxplot),
        "radar": ("公平性雷达图", chart_fairness_radar),
    }

    for chart_key in args.charts:
        if chart_key in chart_funcs:
            name, func = chart_funcs[chart_key]
            print(f"生成: {name} ...")
            try:
                func(df)
            except Exception as e:
                print(f"  生成失败: {e}")
        else:
            print(f"未知图表类型: {chart_key}")

    print(f"\n所有图表已保存至: {CHARTS_DIR}")


if __name__ == "__main__":
    main()
