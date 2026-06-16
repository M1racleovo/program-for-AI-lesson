"""
FaceFair 全局配置
"""

import os

# ============================================================
# 路径配置
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
FAIRFACE_DIR = os.path.join(DATA_DIR, "fairface")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CHARTS_DIR = os.path.join(OUTPUT_DIR, "charts")

# 输出文件
RESULTS_CSV = os.path.join(OUTPUT_DIR, "analysis_results.csv")
SUMMARY_TXT = os.path.join(OUTPUT_DIR, "summary.txt")

# ============================================================
# 模型配置
# ============================================================
# DeepFace 使用的模型
FACE_DETECTION_MODEL = "opencv"       # 人脸检测后端: opencv, retinaface, mtcnn, dlib, ssd
RECOGNITION_MODEL = "Facenet"         # 识别模型: VGG-Face, Facenet, Facenet512, ArcFace, SFace
RACE_MODEL = "race_ethnicity"         # 种族分析模型 (DeepFace 内置)

# 分析属性
ANALYSIS_ACTIONS = ["age", "gender", "race"]

# ============================================================
# FairFace 数据集配置
# ============================================================
# FairFace 种族类别 (与 DeepFace race 输出对应)
RACE_CATEGORIES = [
    "White",
    "Black",
    "East Asian",
    "Southeast Asian",
    "Indian",
    "Middle Eastern",
    "Latino_Hispanic",
]

GENDER_CATEGORIES = ["Male", "Female"]

AGE_GROUPS = {
    "0-2":   (0, 2),
    "3-9":   (3, 9),
    "10-19": (10, 19),
    "20-29": (20, 29),
    "30-39": (30, 39),
    "40-49": (40, 49),
    "50-59": (50, 59),
    "60-69": (60, 69),
    "70+":   (70, 120),
}

# ============================================================
# 测试配置 (小规模验证用)
# ============================================================
TEST_SAMPLE_SIZE = 30          # 小规模测试样本数
TEST_RACE_SAMPLES = 30         # 每种族测试样本数

# ============================================================
# 大规模分析配置 (第5-6周使用)
# ============================================================
FULL_SAMPLE_SIZE = 1000        # 全量分析目标样本数
PER_RACE_LIMIT = 200           # 每种族最多样本数

# ============================================================
# 临时目录 (处理含非英文字符的路径)
# ============================================================
TEMP_DIR = os.path.join(os.path.expanduser("~"), ".facefair_temp")

# ============================================================
# Gemini / Ollama 配置 (第7周使用)
# ============================================================
OLLAMA_MODEL = "gemma2:2b"
OLLAMA_API = "http://localhost:11434/api/generate"
