"""
FaceFair 人脸识别公平性分析主脚本

功能：
  1. 加载 FairFace 数据集中的图像
  2. 使用 DeepFace 进行种族、性别、年龄、表情分析
  3. 将模型预测结果与 FairFace 真实标注对比
  4. 输出 CSV 结果文件和摘要统计

用法：
  python face_fair_analyzer.py                    # 默认: 小规模测试
  python face_fair_analyzer.py --full             # 全量分析 (第5-6周)
  python face_fair_analyzer.py --input ./my_data  # 自定义数据集
"""

import os
import sys
import csv
import time
import argparse
from datetime import datetime

import numpy as np

# 尝试导入 DeepFace，若未安装则给出提示
try:
    from deepface import DeepFace
except ImportError:
    print("错误: 未安装 deepface 库。请运行: pip install deepface")
    sys.exit(1)

from config import (
    DATA_DIR,
    FAIRFACE_DIR,
    OUTPUT_DIR,
    CHARTS_DIR,
    RESULTS_CSV,
    SUMMARY_TXT,
    FACE_DETECTION_MODEL,
    RECOGNITION_MODEL,
    ANALYSIS_ACTIONS,
    RACE_CATEGORIES,
    GENDER_CATEGORIES,
    AGE_GROUPS,
    TEST_SAMPLE_SIZE,
    FULL_SAMPLE_SIZE,
    PER_RACE_LIMIT,
)


def ensure_dirs():
    """确保输出目录存在"""
    for d in [OUTPUT_DIR, CHARTS_DIR, DATA_DIR]:
        os.makedirs(d, exist_ok=True)


def load_fairface_samples(data_dir, max_per_category=None, total_limit=None):
    """
    加载 FairFace 数据集样本。
    FairFace 目录结构 (GitHub release 格式):
      fairface/
        train/        ← 图片平铺 (1.jpg, 2.jpg, ...)
        val/          ← 图片平铺
        fairface_label_train.csv   ← 标注文件
        fairface_label_val.csv     ← 标注文件

    CSV 列: file, age, gender, race, service_test

    返回: [(image_path, race_label, gender_label, age_label), ...]
    """
    samples = []

    for split in ["train", "val"]:
        split_dir = os.path.join(data_dir, split)
        label_csv = os.path.join(data_dir, f"fairface_label_{split}.csv")

        if not os.path.isdir(split_dir) or not os.path.exists(label_csv):
            continue

        with open(label_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # CSV 中 file 列为 "train/1.jpg" 格式
                filename = os.path.basename(row["file"].strip())
                img_path = os.path.join(split_dir, filename)

                if not os.path.exists(img_path):
                    continue

                race_label = row["race"].strip()
                gender_label = row["gender"].strip()
                age_label = row["age"].strip()

                samples.append((img_path, race_label, gender_label, age_label))

                if max_per_category and len(samples) >= max_per_category * len(RACE_CATEGORIES):
                    break

    # 按种族均匀采样
    if total_limit and len(samples) > total_limit:
        race_buckets = {}
        for s in samples:
            race_buckets.setdefault(s[1], []).append(s)

        per_race = max(1, total_limit // max(len(race_buckets), 1))
        balanced = []
        for race in RACE_CATEGORIES:
            items = race_buckets.get(race, [])
            balanced.extend(items[:per_race])
        samples = balanced[:total_limit]
    elif max_per_category:
        race_buckets = {}
        for s in samples:
            race_buckets.setdefault(s[1], []).append(s)
        limited = []
        for race in RACE_CATEGORIES:
            items = race_buckets.get(race, [])
            limited.extend(items[:max_per_category])
        samples = limited

    return samples


def analyze_single_image(image_path, detector=FACE_DETECTION_MODEL):
    """
    使用 DeepFace 分析单张图像，返回属性预测结果。

    返回: dict 或 None (检测不到人脸时)
    """
    import shutil
    import uuid

    # DeepFace 不支持含非英文字符的路径, 需要先复制到纯英文临时目录
    original_path = image_path
    temp_path = None

    try:
        if not _is_ascii_path(image_path):
            temp_path = _copy_to_temp(image_path)
            image_path = temp_path

        results = DeepFace.analyze(
            img_path=image_path,
            actions=ANALYSIS_ACTIONS,
            detector_backend=detector,
            enforce_detection=False,
            silent=True,
        )
        if not results or (isinstance(results, list) and len(results) == 0):
            return None

        result = results[0] if isinstance(results, list) else results
        return {
            "age": result.get("age", None),
            "dominant_gender": result.get("dominant_gender", None),
            "dominant_race": result.get("dominant_race", None),
            "dominant_emotion": result.get("dominant_emotion", None),
            "gender_scores": result.get("gender", {}),
            "race_scores": result.get("race", {}),
            "emotion_scores": result.get("emotion", {}),
            "region": result.get("region", {}),
        }

    except Exception as e:
        err_msg = str(e).encode("ascii", errors="replace").decode("ascii")
        print(f"    分析失败 [{os.path.basename(original_path)}]: {err_msg}")
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def _is_ascii_path(path):
    """检查路径是否仅含 ASCII 字符 (DeepFace 限制)"""
    try:
        path.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _copy_to_temp(src_path):
    """将图像复制到纯 ASCII 临时目录"""
    import shutil
    import uuid
    from config import TEMP_DIR

    os.makedirs(TEMP_DIR, exist_ok=True)
    ext = os.path.splitext(src_path)[1]
    dst = os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}{ext}")
    shutil.copy2(src_path, dst)
    return dst


def run_analysis(samples, output_csv=RESULTS_CSV, resume=False):
    """
    批量分析图像，将结果写入 CSV。

    参数:
      samples: [(path, race_label, gender_label, age_label), ...]
      output_csv: 输出 CSV 路径
      resume: 是否断点续传 (跳过已处理的图像)
    """
    ensure_dirs()

    # 读取已处理的图像路径
    processed = set()
    if resume and os.path.exists(output_csv):
        with open(output_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                processed.add(row.get("image_path", ""))
        print(f"断点续传: 已跳过 {len(processed)} 张已处理图像\n")

    fieldnames = [
        "image_path", "true_race", "true_gender", "true_age",
        "pred_age", "pred_gender", "pred_race", "pred_emotion",
        "gender_confidence", "race_confidence",
        "match_race", "match_gender", "error_info",
    ]

    write_header = not (resume and os.path.exists(output_csv))

    with open(output_csv, "a" if resume and not write_header else "w",
              newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        total = len(samples)
        success = 0
        skipped = 0
        failed = 0

        start_time = time.time()
        for idx, (img_path, true_race, true_gender, true_age) in enumerate(samples, 1):
            if img_path in processed:
                skipped += 1
                continue

            elapsed = time.time() - start_time
            eta = (elapsed / max(idx - skipped, 1)) * (total - idx) if idx > skipped else 0
            print(f"\r[{idx}/{total}] 已分析: {success} | 失败: {failed} | ETA: {eta:.0f}s ",
                  end="", flush=True)

            prediction = analyze_single_image(img_path)

            if prediction is None:
                writer.writerow({
                    "image_path": img_path,
                    "true_race": true_race,
                    "true_gender": true_gender,
                    "true_age": true_age,
                    "pred_age": None, "pred_gender": None, "pred_race": None,
                    "pred_emotion": None, "gender_confidence": None,
                    "race_confidence": None, "match_race": False,
                    "match_gender": False, "error_info": "FACE_NOT_DETECTED",
                })
                failed += 1
                continue

            # 种族匹配检查
            pred_race = prediction["dominant_race"]
            race_match = _compare_race(pred_race, true_race) if pred_race else False

            # 性别匹配检查 (DeepFace 返回 Man/Woman, 标签为 Male/Female)
            pred_gender = prediction["dominant_gender"]
            gender_map = {"man": "male", "woman": "female"}
            pred_gender_norm = gender_map.get(pred_gender.lower(), pred_gender.lower()) if pred_gender else None
            true_gender_norm = true_gender.lower() if true_gender else None
            gender_match = pred_gender_norm == true_gender_norm if pred_gender_norm and true_gender_norm else False

            # 置信度提取
            race_scores = prediction.get("race_scores", {})
            gender_scores = prediction.get("gender_scores", {})
            race_conf = race_scores.get(pred_race, None) if pred_race and race_scores else None
            gender_conf = gender_scores.get(pred_gender, None) if pred_gender and gender_scores else None

            writer.writerow({
                "image_path": img_path,
                "true_race": true_race,
                "true_gender": true_gender,
                "true_age": true_age,
                "pred_age": prediction["age"],
                "pred_gender": pred_gender,
                "pred_race": pred_race,
                "pred_emotion": prediction["dominant_emotion"],
                "gender_confidence": gender_conf,
                "race_confidence": race_conf,
                "match_race": race_match,
                "match_gender": gender_match,
                "error_info": "",
            })
            success += 1

    print(f"\n\n分析完成: 成功 {success}, 失败 {failed}, 跳过 {skipped}, 总计 {total}")
    return output_csv


def _compare_race(pred_race, true_race):
    """
    比较预测种族与真实标签是否匹配。
    使用模糊匹配处理不同命名规范。
    """
    if not pred_race or not true_race:
        return False

    pred = pred_race.lower().replace(" ", "").replace("_", "")
    true = true_race.lower().replace(" ", "").replace("_", "")

    # 定义同义映射
    synonym_map = {
        "eastasian": ["eastasian", "asian", "eastasia"],
        "southeastasian": ["southeastasian", "southeastasia"],
        "middleeastern": ["middleeastern", "mideast"],
        "latino": ["latino", "hispanic", "latino_hispanic", "latinohispanic"],
        "white": ["white", "caucasian", "european"],
        "black": ["black", "african"],
        "indian": ["indian", "southasian"],
    }

    for standard, aliases in synonym_map.items():
        if any(a in pred for a in aliases) and true.startswith(
            standard.capitalize()[:5]
        ):
            return True
        if standard in true and any(a in pred for a in aliases):
            return True

    # 直接子串匹配
    if pred[:4] in true or true[:4] in pred:
        return True

    return False


def generate_summary(csv_path=RESULTS_CSV, output_txt=SUMMARY_TXT):
    """
    生成分析摘要: 各人群准确率统计。

    参数:
      csv_path: 分析结果 CSV 路径
      output_txt: 输出摘要文件路径
    """
    import pandas as pd

    if not os.path.exists(csv_path):
        print(f"错误: 未找到结果文件 {csv_path}")
        return

    df = pd.read_csv(csv_path)

    # 过滤掉未检测到人脸的行
    valid = df[df["pred_race"].notna()].copy()

    lines = []
    lines.append("=" * 60)
    lines.append("FaceFair 公平性分析摘要")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"总样本数: {len(df)}")
    lines.append(f"有效样本数 (检测到人脸): {len(valid)}")
    lines.append(f"人脸检测失败数: {len(df) - len(valid)}")
    lines.append("=" * 60)

    if len(valid) == 0:
        lines.append("\n无有效分析结果, 请检查数据集和模型配置。")
        summary = "\n".join(lines)
        print(summary)
        with open(output_txt, "w", encoding="utf-8") as f:
            f.write(summary)
        return

    # 总体准确率
    race_acc = valid["match_race"].mean() * 100
    gender_acc = valid["match_gender"].mean() * 100
    lines.append(f"\n总体种族识别准确率: {race_acc:.2f}%")
    lines.append(f"总体性别识别准确率: {gender_acc:.2f}%")

    # 按种族统计
    lines.append(f"\n{'─' * 50}")
    lines.append("各人种准确率统计:")
    lines.append(f"{'人种':<20s} {'样本数':<8s} {'种族准确率':<12s} {'性别准确率':<12s} {'平均年龄':<10s}")
    lines.append(f"{'─' * 50}")

    for race in RACE_CATEGORIES:
        subset = valid[valid["true_race"] == race]
        if len(subset) == 0:
            continue
        r_acc = subset["match_race"].mean() * 100
        g_acc = subset["match_gender"].mean() * 100
        avg_age = subset["pred_age"].astype(float).mean()
        lines.append(f"{race:<20s} {len(subset):<8d} {r_acc:<12.2f}% {g_acc:<12.2f}% {avg_age:<10.1f}")

    # 按性别统计
    lines.append(f"\n{'─' * 50}")
    lines.append("各性别准确率统计:")
    lines.append(f"{'性别':<10s} {'样本数':<8s} {'性别准确率':<12s}")
    lines.append(f"{'─' * 50}")
    for gender in GENDER_CATEGORIES:
        subset = valid[valid["true_gender"].str.lower() == gender.lower()]
        if len(subset) == 0:
            continue
        g_acc = subset["match_gender"].mean() * 100
        lines.append(f"{gender:<10s} {len(subset):<8d} {g_acc:<12.2f}%")

    # 偏差评估
    lines.append(f"\n{'─' * 50}")
    lines.append("公平性偏差评估:")
    race_accs = []
    for race in RACE_CATEGORIES:
        subset = valid[valid["true_race"] == race]
        if len(subset) > 0:
            race_accs.append((race, subset["match_race"].mean()))

    if race_accs:
        race_accs.sort(key=lambda x: x[1])
        best_race, best_acc = race_accs[-1]
        worst_race, worst_acc = race_accs[0]
        gap = best_acc - worst_acc
        lines.append(f"  最高种族准确率: {best_race} ({best_acc*100:.1f}%)")
        lines.append(f"  最低种族准确率: {worst_race} ({worst_acc*100:.1f}%)")
        lines.append(f"  种族准确率差距: {gap*100:.1f}%")
        if gap > 0.15:
            lines.append("  评估: 存在显著种族偏见 (差距 > 15%)")
        elif gap > 0.05:
            lines.append("  评估: 存在中度种族偏见 (差距 5%-15%)")
        else:
            lines.append("  评估: 种族偏见程度较低 (差距 < 5%)")

    summary = "\n".join(lines)
    print("\n" + summary)

    with open(output_txt, "w", encoding="utf-8") as f:
        f.write(summary)

    return summary


def main():
    parser = argparse.ArgumentParser(description="FaceFair 人脸识别公平性分析")
    parser.add_argument("--full", action="store_true",
                        help="全量分析 (1000+ 样本, 用于第5-6周)")
    parser.add_argument("--input", type=str, default=FAIRFACE_DIR,
                        help=f"FairFace 数据集目录 (默认: {FAIRFACE_DIR})")
    parser.add_argument("--limit", type=int, default=None,
                        help="最大分析样本数")
    parser.add_argument("--per-race", type=int, default=None,
                        help="每个种族最多样本数")
    parser.add_argument("--resume", action="store_true",
                        help="从上次中断处继续 (断点续传)")
    parser.add_argument("--summarize", action="store_true",
                        help="仅根据已有 CSV 生成摘要")
    parser.add_argument("--detector", type=str, default=FACE_DETECTION_MODEL,
                        choices=["opencv", "retinaface", "mtcnn", "dlib", "ssd"],
                        help="人脸检测后端")

    args = parser.parse_args()

    # 仅生成摘要模式
    if args.summarize:
        generate_summary()
        return

    # 确定样本配置
    if args.full:
        limit = args.limit or FULL_SAMPLE_SIZE
        per_race = args.per_race or PER_RACE_LIMIT
        print(f"=== FaceFair 全量分析模式 ===")
        print(f"目标样本数: {limit}, 每种族上限: {per_race}")
    else:
        limit = args.limit or TEST_SAMPLE_SIZE
        per_race = args.per_race or 10
        print(f"=== FaceFair 小规模测试模式 ===")
        print(f"目标样本数: {limit}, 每种族上限: {per_race}")

    print(f"数据集目录: {args.input}")
    print(f"人脸检测后端: {args.detector}")
    print(f"分析属性: {ANALYSIS_ACTIONS}\n")

    # 加载数据
    samples = load_fairface_samples(
        data_dir=args.input,
        max_per_category=per_race,
        total_limit=limit,
    )

    if not samples:
        print(f"错误: 在 {args.input} 中未找到图像文件。")
        print("请确认 FairFace 数据集已下载并解压到正确位置。")
        print(f"预期目录结构: {args.input}/train/White/, {args.input}/train/Black/, ...")
        sys.exit(1)

    print(f"已加载 {len(samples)} 个样本\n")

    # 运行分析
    run_analysis(samples, resume=args.resume)

    # 生成摘要
    generate_summary()


if __name__ == "__main__":
    main()
