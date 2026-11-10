import os
import io
import base64
import httpx
import threading
import logging
import json
import uuid
import shutil
from datetime import datetime

# 设置环境变量，避免 OpenMP 运行时冲突
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import chromadb
from pydantic import BaseModel, Field
from typing import List, Optional

# Pydantic models for response schema
class Detection(BaseModel):
    class_name: str
    confidence: float
    bbox: List[int]

class AnalyzedObject(BaseModel):
    id: int
    class_name: str
    confidence: float
    bbox: List[int]
    crop_url: str
    rag_context: str
    llm_analysis: str

class Summary(BaseModel):
    total_count: int
    is_healthy: bool

class Data(BaseModel):
    summary: Summary
    detections: List[Detection]
    analyzed_objects: List[AnalyzedObject]
    action_advice: str

class Header(BaseModel):
    status: str
    latency_ms: float
    device: str

class VisionResponse(BaseModel):
    header: Header
    data: Data

class AnalyzeJsonRequest(BaseModel):
    analysis_type: str  # pest, fruit, lodging, soil
    growth_stage: Optional[str] = None  # seed, growth, maturity
    test_mode: Optional[bool] = False

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ============================================================
# 目录结构定义
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
INPUT_PROCESSED_DIR = os.path.join(INPUT_DIR, "processed")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
OUTPUT_ANNOTATED_DIR = os.path.join(OUTPUT_DIR, "annotated")
OUTPUT_CROPS_DIR = os.path.join(OUTPUT_DIR, "crops")
OUTPUT_REPORTS_DIR = os.path.join(OUTPUT_DIR, "reports")

def ensure_directories():
    """确保所有必要的目录都存在"""
    for d in [INPUT_DIR, INPUT_PROCESSED_DIR, OUTPUT_DIR,
              OUTPUT_ANNOTATED_DIR, OUTPUT_CROPS_DIR, OUTPUT_REPORTS_DIR]:
        os.makedirs(d, exist_ok=True)
        logger.info(f"确保目录存在: {d}")

# 启动时创建目录
ensure_directories()

class Config:
    # 嵌入模型路径 (BGE-M3)
    BGE_PATH = os.getenv("BGE_PATH", r"D:\huggingface\hub\models--BAAI--bge-m3\snapshots\5617a9f61b028005a4858fdac845db406aefb181")

    # YOLOv11 权重路径
    YOLO_PATH = os.getenv("YOLO_PATH", r"d:\agri_project_v2\best.pt")

    # ChromaDB 数据库路径
    DB_PATH = os.getenv("DB_PATH", "vision.db")

    # 通义千问 API Key
    API_KEY = os.getenv("QWEN_API_KEY", "")

    # 阿里云百炼平台的官方 OpenAI 兼容接口地址
    QWEN_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

# 预设关键词列表 — 匹配 YOLO 模型实际类别
PEST_KEYWORDS = ['disease', 'insect', 'weed']

# YOLO 类别中文映射
CLASS_NAME_CN = {
    'seed': '种子', 'disease': '病害', 'insect': '虫害',
    'weed': '杂草', 'fruit': '果实', 'plant': '植株'
}

# 生长阶段中文映射
STAGE_NAME_CN = {
    'seed': '选种期', 'growth': '生长期', 'maturity': '采收期'
}

# ============================================================
# LLMService 单例类
# ============================================================
class LLMService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LLMService, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        self.api_key = Config.API_KEY
        self.endpoint = Config.QWEN_ENDPOINT
        self.timeout = 30
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def image_to_base64(self, image):
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    async def call_qwen_vl(self, image, prompt):
        try:
            image_base64 = await self.image_to_base64(image)

            payload = {
                "model": "qwen-vl-plus",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }
                ],
                "max_tokens": 1024
            }

            response = await self.client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload
            )

            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling Qwen-VL API: {e}")
            return {
                "choices": [{
                    "message": {
                        "content": "This is a mock LLM analysis. The API call failed, but the system is working."
                    }
                }]
            }
        except Exception as e:
            logger.error(f"Error calling Qwen-VL API: {e}")
            return {
                "choices": [{
                    "message": {
                        "content": "This is a mock LLM analysis. The API call failed, but the system is working."
                    }
                }]
            }

    async def call_qwen_vl_report(self, image, class_name, confidence):
        """调用 Qwen-VL 生成结构化的病虫害分析报告"""
        prompt = (
            f"你是一位专业的农业病虫害诊断专家。请对以下图片中检测到的目标进行分析。\n"
            f"YOLO模型检测结果：类别={class_name}，置信度={confidence:.2f}\n\n"
            f"请严格按照以下格式回答（每项一行，用中文回答）：\n"
            f"目标确认：<对该检测目标是否正确进行确认，说明理由>\n"
            f"详细分析：<对病虫害的详细分析，包括症状描述、可能原因等>\n"
            f"防治建议：<具体的防治措施和建议>\n"
            f"风险等级：<LOW/MEDIUM/HIGH>"
        )
        response = await self.call_qwen_vl(image, prompt)
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

        # 解析结构化回复
        result = {
            "qwen_vl_confirmation": "",
            "detailed_analysis": "",
            "treatment_recommendations": "",
            "risk_level": "MEDIUM"
        }

        lines = content.split("\n")
        current_key = None
        key_mapping = {
            "目标确认": "qwen_vl_confirmation",
            "详细分析": "detailed_analysis",
            "防治建议": "treatment_recommendations",
            "风险等级": "risk_level"
        }

        for line in lines:
            line = line.strip()
            if not line:
                continue
            matched = False
            for cn_key, en_key in key_mapping.items():
                if line.startswith(cn_key):
                    current_key = en_key
                    value = line.split("：", 1)[-1].strip() if "：" in line else line.split(":", 1)[-1].strip()
                    if en_key == "risk_level":
                        value = value.upper()
                        if value not in ("LOW", "MEDIUM", "HIGH"):
                            value = "MEDIUM"
                    result[en_key] = value
                    matched = True
                    break
            if not matched and current_key:
                result[current_key] += " " + line

        return result

    async def close(self):
        await self.client.aclose()

# ============================================================
# 生长阶段提示词
# ============================================================
STAGE_PROMPTS = {
    "seed": "你是一位专业的农业种子品质分析专家。请对以下图片中检测到的目标进行分析，侧重种子品质、发芽率、品种鉴定等方面。",
    "growth": "你是一位专业的农业病虫害诊断专家。请对以下图片中检测到的目标进行分析，侧重长势、病虫害、营养状态等方面。",
    "maturity": "你是一位专业的农业采收评估专家。请对以下图片中检测到的目标进行分析，侧重成熟度、产量预估、采收时机等方面。",
}

# 阶段分析结构化提示词 — 约束 Qwen 输出格式
STAGE_ANALYSIS_PROMPTS = {
    "seed": """你是一位专业的农业种子品质分析专家。请对以下图片进行全面分析。

YOLO检测结果：{detections_info}

请严格按照以下格式输出（每个章节标题用 ## 标记，内容写在标题下方，用中文回答）：

## 种子品质评估
[对种子外观、大小、色泽、饱满度等进行评估]

## 品种鉴定
[根据种子特征鉴定可能的品种，说明判断依据]

## 发芽率预测
[基于种子品质预测发芽率，给出具体数值范围]

## 选种建议
[给出具体的选种和播种建议，包括处理方法]

## 风险等级
[LOW/MEDIUM/HIGH，并简要说明风险来源]""",

    "growth": """你是一位专业的农业生长期管理专家。请对以下图片进行全面分析。

YOLO检测结果：{detections_info}

请严格按照以下格式输出（每个章节标题用 ## 标记，内容写在标题下方，用中文回答）：

## 长势评估
[对作物长势、株高、叶色、群体结构等进行评估]

## 病虫害检测
[检测是否有病虫害，描述症状和严重程度]

## 营养状态
[评估作物营养状况，是否缺肥，给出具体缺素判断]

## 管理建议
[给出具体的水肥管理、病虫害防治建议，包括用药方案]

## 风险等级
[LOW/MEDIUM/HIGH，并简要说明风险来源]""",

    "maturity": """你是一位专业的农业采收评估专家。请对以下图片进行全面分析。

YOLO检测结果：{detections_info}

请严格按照以下格式输出（每个章节标题用 ## 标记，内容写在标题下方，用中文回答）：

## 成熟度评估
[评估作物成熟度、是否达到采收标准，给出具体成熟度百分比]

## 产量预估
[基于当前状态预估产量，给出具体数值范围]

## 采收时机
[建议最佳采收时间和方式，说明判断依据]

## 采后处理建议
[给出采收后的处理和储存建议]

## 风险等级
[LOW/MEDIUM/HIGH，并简要说明风险来源]"""
}

def get_stage_prompt(growth_stage, class_name, confidence):
    """根据生长阶段返回对应的系统提示词"""
    base_prompt = STAGE_PROMPTS.get(growth_stage, "你是一位专业的农业病虫害诊断专家。请对以下图片中检测到的目标进行分析。")
    return (
        f"{base_prompt}\n"
        f"YOLO模型检测结果：类别={class_name}，置信度={confidence:.2f}\n\n"
        f"请严格按照以下格式回答（每项一行，用中文回答）：\n"
        f"目标确认：<对该检测目标是否正确进行确认，说明理由>\n"
        f"详细分析：<对检测目标的详细分析>\n"
        f"防治建议：<具体的措施和建议>\n"
        f"风险等级：<LOW/MEDIUM/HIGH>"
    )

async def generate_stage_analysis(original_image, growth_stage, detections):
    """为整张图片生成一次性的阶段分析（替代逐检测分析），返回结构化文本"""
    # 构建检测信息摘要
    if detections:
        det_parts = []
        for d in detections:
            det_parts.append(f"{d.class_name}(置信度{d.confidence:.2f})")
        detections_info = "、".join(det_parts)
    else:
        detections_info = "未检测到明确目标"

    prompt_template = STAGE_ANALYSIS_PROMPTS.get(growth_stage, STAGE_ANALYSIS_PROMPTS["growth"])
    prompt = prompt_template.format(detections_info=detections_info)

    try:
        response = await llm_service.call_qwen_vl(original_image, prompt)
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            content = "## 分析结果\nAI分析暂时不可用，请稍后重试。"
        return content
    except Exception as e:
        logger.error(f"生成阶段分析失败: {e}")
        return f"## 分析结果\nAI分析失败: {str(e)}"

def save_stage_report(image_name, growth_stage, stage_analysis, detections):
    """保存简化的阶段分析报告（一份），文件名使用日期编号"""
    stage_cn = STAGE_NAME_CN.get(growth_stage, growth_stage)
    report_filename = f"{stage_cn}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report = {
        "image_name": image_name,
        "timestamp": datetime.now().isoformat(),
        "growth_stage": growth_stage,
        "stage_name": stage_cn,
        "stage_analysis": stage_analysis,
        "detections": [{"class_name": d.class_name, "class_name_cn": CLASS_NAME_CN.get(d.class_name, d.class_name), "confidence": round(d.confidence, 4)} for d in detections]
    }
    report_path = os.path.join(OUTPUT_REPORTS_DIR, report_filename)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"保存阶段分析报告到: {report_path}")
    return report_filename

# ============================================================
# VisionService 单例类
# ============================================================
class VisionService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(VisionService, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        self.model = None
        self.device = 'cuda' if __import__('torch').cuda.is_available() else 'cpu'
        # 设置PyTorch线程数为1，避免多线程冲突
        import torch
        torch.set_num_threads(1)
        # 使用新的目录结构
        self.crops_dir = OUTPUT_CROPS_DIR
        self.annotated_dir = OUTPUT_ANNOTATED_DIR
        self.reports_dir = OUTPUT_REPORTS_DIR

    def load_model(self):
        logger.info("正在加载 YOLOv11 模型...")
        try:
            try:
                from ultralytics import YOLO
                self.model = YOLO(Config.YOLO_PATH)
            except Exception as e:
                logger.error(f"无法加载 YOLO 模型: {e}")
                class MockYOLO:
                    def __call__(self, image, half=False, device=None):
                        class MockResult:
                            names = {0: "object"}
                            class MockBoxes:
                                cls = [0]
                                conf = [0.5]
                                xyxy = [[10, 10, 100, 100]]
                            boxes = [MockBoxes()]
                        return [MockResult()]
                self.model = MockYOLO()
                logger.warning("使用模拟 YOLO 模型，仅用于测试")

            logger.info(f"模型加载完成，使用设备: {self.device}")

            # 暖机推理
            logger.info("正在进行模型暖机...")
            import numpy as np
            from PIL import Image
            dummy_image = np.zeros((640, 640, 3), dtype=np.uint8)
            dummy_pil = Image.fromarray(dummy_image)
            results = self.model(dummy_pil, half=False, device=self.device)
            logger.info("模型暖机完成，服务准备就绪")

        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise

    def preprocess_image(self, image_data):
        from PIL import Image
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        image = image.resize((640, 640))
        return image

    def save_cropped_image(self, cropped_image, prefix="crop"):
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{prefix}_{unique_id}.jpg"
        file_path = os.path.join(self.crops_dir, filename)
        cropped_image.save(file_path, format='JPEG')
        logger.info(f"保存裁剪图片到: {file_path}")
        return f"/output/crops/{filename}", file_path

    def crop_image(self, image, bbox):
        cropped = image.crop(bbox)
        cropped_io = io.BytesIO()
        cropped.save(cropped_io, format='JPEG')
        cropped_io.seek(0)
        crop_url, crop_path = self.save_cropped_image(cropped)
        return cropped_io, crop_url, crop_path

    def save_annotated_image(self, results, original_filename):
        """保存带标注的图片到 output/annotated/"""
        try:
            for result in results:
                annotated = result.plot()  # ultralytics 自带的标注绘制
                from PIL import Image
                import numpy as np
                annotated_pil = Image.fromarray(annotated[..., ::-1])  # BGR -> RGB
                save_name = f"{os.path.splitext(original_filename)[0]}_annotated.jpg"
                save_path = os.path.join(self.annotated_dir, save_name)
                annotated_pil.save(save_path, format='JPEG')
                logger.info(f"保存标注图片到: {save_path}")
                return f"/output/annotated/{save_name}", save_path
        except Exception as e:
            logger.error(f"保存标注图片失败: {e}")
            return "", ""

    async def run_inference(self, image):
        import asyncio
        def _run_inference():
            return self.model(image, half=False, device=self.device)
        results = await asyncio.to_thread(_run_inference)
        return results

    def process_results(self, results):
        detections = []
        total_count = 0
        has_pest = False

        for result in results:
            for box in result.boxes:
                class_name = result.names[int(box.cls[0])]
                confidence = float(box.conf[0])
                coords = box.xyxy[0]
                bbox = coords.tolist() if hasattr(coords, 'tolist') else list(coords)

                detection = Detection(
                    class_name=class_name,
                    confidence=confidence,
                    bbox=[int(coord) for coord in bbox]
                )
                detections.append(detection)

                total_count += 1

                if class_name.lower() in [kw.lower() for kw in PEST_KEYWORDS]:
                    has_pest = True

        action_advice = ""
        if has_pest:
            action_advice = "High risk: Pest/disease/weed detected. Triggering treatment protocol."
        else:
            action_advice = "Low risk: No harmful pests or diseases detected. Continue regular monitoring."

        return {
            "detections": detections,
            "total_count": total_count,
            "has_pest": has_pest,
            "action_advice": action_advice
        }

    def cleanup(self):
        logger.info("正在清理资源...")
        if self.model is not None:
            del self.model
        logger.info("资源清理完成")

# ============================================================
# RAGService 单例类
# ============================================================
class RAGService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RAGService, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        self.embedding_model = None
        self.chroma_client = None
        self.collection = None

    def load_model(self):
        logger.info("正在加载 BGE-M3 嵌入模型...")
        try:
            try:
                self.embedding_model = SentenceTransformer(Config.BGE_PATH)
                logger.info("BGE-M3 模型加载完成")
            except Exception as e:
                logger.warning(f"无法加载 BGE-M3 模型: {e}")
                logger.info("尝试使用替代模型...")
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("替代模型加载完成")

            logger.info("正在初始化 ChromaDB 客户端...")
            self.chroma_client = chromadb.PersistentClient(path=Config.DB_PATH)
            self.collection = self.chroma_client.get_or_create_collection(name="vision_analysis")
            logger.info("ChromaDB 客户端初始化完成")

        except Exception as e:
            logger.error(f"RAGService 初始化失败: {e}")
            logger.warning("使用模拟 RAGService 实现")
            self.embedding_model = None
            self.chroma_client = None
            self.collection = None

    async def embed_text(self, text):
        import asyncio
        if self.embedding_model is None:
            return [0.0] * 384

        def _embed_text():
            return self.embedding_model.encode(text).tolist()

        embedding = await asyncio.to_thread(_embed_text)
        return embedding

    async def query(self, query_text, n_results=3):
        import asyncio
        if self.collection is None:
            return {
                'documents': [[f"Mock document for {query_text}" for _ in range(n_results)]],
                'metadatas': [[] for _ in range(n_results)],
                'ids': [f"mock_id_{i}" for i in range(n_results)]
            }

        def _query():
            query_embedding = self.embedding_model.encode(query_text).tolist()
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            return results

        results = await asyncio.to_thread(_query)
        return results

    async def add_document(self, document, metadata=None):
        import asyncio
        if self.collection is None:
            return str(uuid.uuid4())

        def _add_document():
            embedding = self.embedding_model.encode(document).tolist()
            doc_id = str(uuid.uuid4())
            self.collection.add(
                documents=[document],
                embeddings=[embedding],
                metadatas=[metadata] if metadata else None,
                ids=[doc_id]
            )
            return doc_id

        doc_id = await asyncio.to_thread(_add_document)
        return doc_id

    def cleanup(self):
        logger.info("正在清理 RAGService 资源...")
        if self.embedding_model is not None:
            del self.embedding_model
        if self.chroma_client is not None:
            pass
        logger.info("RAGService 资源清理完成")

# ============================================================
# 全局服务实例
# ============================================================
vision_service = VisionService()
rag_service = RAGService()
llm_service = LLMService()

# ============================================================
# 后台任务：清理crops目录
# ============================================================
async def cleanup_crops_directory():
    """清理crops目录，删除超过1小时的文件或保持目录大小在500MB以下"""
    try:
        crops_dir = OUTPUT_CROPS_DIR
        if not os.path.exists(crops_dir):
            return

        current_time = time.time()
        one_hour_ago = current_time - 3600
        max_size_mb = 500
        max_size_bytes = max_size_mb * 1024 * 1024

        files = []
        total_size = 0

        for filename in os.listdir(crops_dir):
            file_path = os.path.join(crops_dir, filename)
            if os.path.isfile(file_path):
                file_stat = os.stat(file_path)
                file_age = current_time - file_stat.st_mtime
                file_size = file_stat.st_size
                total_size += file_size
                files.append((file_path, file_age, file_size))

        files.sort(key=lambda x: x[1])

        for file_path, file_age, _ in files:
            if file_age > one_hour_ago:
                try:
                    os.remove(file_path)
                    logger.info(f"删除过期文件: {file_path}")
                except Exception as e:
                    logger.error(f"删除文件失败: {file_path}, 错误: {e}")

        if total_size > max_size_bytes:
            current_size = total_size
            for file_path, _, file_size in files:
                if current_size <= max_size_bytes:
                    break
                try:
                    os.remove(file_path)
                    current_size -= file_size
                    logger.info(f"删除文件以控制目录大小: {file_path}")
                except Exception as e:
                    logger.error(f"删除文件失败: {file_path}, 错误: {e}")

    except Exception as e:
        logger.error(f"清理crops目录失败: {e}")

# ============================================================
# 报告生成工具函数
# ============================================================
async def generate_report(image_name, detections, original_image, results):
    """为检测结果生成结构化的病虫害分析报告"""
    report = {
        "image_name": image_name,
        "timestamp": datetime.now().isoformat(),
        "detections": []
    }

    has_pest = False

    for i, detection in enumerate(detections):
        class_name = detection.class_name
        confidence = detection.confidence
        bbox = detection.bbox

        # 裁剪检测区域
        cropped_io, crop_url, crop_path = vision_service.crop_image(original_image, bbox)
        from PIL import Image
        cropped_image = Image.open(cropped_io)

        # 调用 Qwen-VL 生成分析报告
        qwen_result = await llm_service.call_qwen_vl_report(cropped_image, class_name, confidence)

        detection_report = {
            "id": i + 1,
            "class_name": class_name,
            "confidence": round(confidence, 4),
            "bbox": bbox,
            "qwen_vl_confirmation": qwen_result["qwen_vl_confirmation"],
            "detailed_analysis": qwen_result["detailed_analysis"],
            "treatment_recommendations": qwen_result["treatment_recommendations"],
            "risk_level": qwen_result["risk_level"]
        }
        report["detections"].append(detection_report)

        if class_name.lower() in [kw.lower() for kw in PEST_KEYWORDS]:
            has_pest = True

        del cropped_io
        del cropped_image

    # 生成摘要
    total_count = len(detections)
    action_advice = ""
    if has_pest:
        action_advice = "检测到病虫害或杂草，建议立即采取防治措施。"
    else:
        action_advice = "未检测到有害生物，建议继续常规监测。"

    report["summary"] = {
        "total_count": total_count,
        "is_healthy": not has_pest,
        "action_advice": action_advice
    }

    # 保存报告到文件
    report_filename = f"{os.path.splitext(image_name)[0]}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path = os.path.join(OUTPUT_REPORTS_DIR, report_filename)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"保存分析报告到: {report_path}")

    return report, report_filename

# ============================================================
# Input 文件夹监视器（watchdog）
# ============================================================
class ImageEventHandler:
    """watchdog 事件处理器：监视 input/ 目录中的新图片"""

    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp'}
    _processing_files = set()  # 跟踪 /upload 端点正在处理的文件，避免重复处理

    def __init__(self):
        self._loop = None

    def set_loop(self, loop):
        self._loop = loop

    def dispatch(self, event):
        """watchdog FileSystemEventHandler 的 dispatch 方法"""
        if event.is_directory:
            return
        if event.event_type not in ('created', 'modified'):
            return

        src_path = event.src_path
        ext = os.path.splitext(src_path)[1].lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            return

        # 忽略 processed 子目录中的文件
        if INPUT_PROCESSED_DIR in src_path:
            return

        # 忽略 /upload 端点正在处理的文件，避免重复处理
        filename = os.path.basename(src_path)
        if filename in ImageEventHandler._processing_files:
            logger.info(f"文件正在由 /upload 端点处理，跳过 watchdog: {filename}")
            return

        logger.info(f"检测到新图片文件: {src_path}")
        # 在事件循环中调度处理
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._process_file(src_path), self._loop)

    async def _process_file(self, file_path):
        """处理 input/ 中的新图片文件"""
        try:
            # 等待文件写入完成
            await asyncio.sleep(2)

            # 再次检查文件是否存在（可能在等待期间被删除）
            if not os.path.exists(file_path):
                logger.warning(f"文件已不存在: {file_path}")
                return

            filename = os.path.basename(file_path)
            logger.info(f"开始处理文件: {filename}")

            # 读取图片
            from PIL import Image
            image = Image.open(file_path).convert("RGB")
            original_image = image.copy()

            # 预处理
            processed_image = image.resize((640, 640))

            # YOLO 推理
            results = await vision_service.run_inference(processed_image)

            # 保存标注图片
            vision_service.save_annotated_image(results, filename)

            # 处理检测结果
            result_data = vision_service.process_results(results)
            detections = result_data["detections"]

            # 生成报告
            if detections:
                report, report_filename = await generate_report(filename, detections, original_image, results)
                logger.info(f"文件 {filename} 处理完成，报告: {report_filename}")
            else:
                logger.info(f"文件 {filename} 未检测到目标")

            # 移动文件到 processed 目录
            dest_path = os.path.join(INPUT_PROCESSED_DIR, filename)
            shutil.move(file_path, dest_path)
            logger.info(f"已将文件移动到: {dest_path}")

        except Exception as e:
            logger.error(f"处理文件 {file_path} 失败: {e}")
            import traceback
            logger.error(traceback.format_exc())


class InputWatcher:
    """管理 input/ 目录的 watchdog 监视器"""

    def __init__(self):
        self._observer = None
        self._handler = None

    def start(self, loop):
        """启动文件监视器"""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            self._handler = ImageEventHandler()
            self._handler.set_loop(loop)

            # 创建适配器：让 ImageEventHandler 兼容 watchdog 的 FileSystemEventHandler
            class _WatchdogAdapter(FileSystemEventHandler):
                def __init__(self, handler):
                    super().__init__()
                    self._handler = handler

                def on_created(self, event):
                    self._handler.dispatch(event)

                def on_modified(self, event):
                    self._handler.dispatch(event)

            adapter = _WatchdogAdapter(self._handler)

            self._observer = Observer()
            self._observer.schedule(adapter, INPUT_DIR, recursive=False)
            self._observer.daemon = True
            self._observer.start()
            logger.info(f"Input 文件夹监视器已启动，监视目录: {INPUT_DIR}")
        except ImportError:
            logger.warning("watchdog 库未安装，input 文件夹监视功能不可用。请运行: pip install watchdog")
        except Exception as e:
            logger.error(f"启动 Input 文件夹监视器失败: {e}")

    def stop(self):
        """停止文件监视器"""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            logger.info("Input 文件夹监视器已停止")


# 全局监视器实例
input_watcher = InputWatcher()

# ============================================================
# FastAPI 应用
# ============================================================
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager
import uvicorn
import torch
import numpy as np
from PIL import Image
import asyncio
import time

# 模型加载和暖机
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时加载模型
    vision_service.load_model()
    rag_service.load_model()
    # 启动 input 文件夹监视器
    loop = asyncio.get_event_loop()
    input_watcher.start(loop)
    yield
    # 关闭时停止监视器
    input_watcher.stop()
    # 关闭时清理资源
    vision_service.cleanup()
    rag_service.cleanup()
    # 关闭 LLMService 客户端
    await llm_service.close()

# 创建FastAPI应用实例
app = FastAPI(
    title="Industrial Vision Server",
    description="工业级视觉分析服务器，运行在8002端口，支持YOLOv11目标检测、Qwen-VL分析、文件监视",
    version="2.0.0",
    lifespan=lifespan
)

# 挂载静态文件 — 新的目录结构
try:
    app.mount("/output/annotated", StaticFiles(directory=OUTPUT_ANNOTATED_DIR), name="annotated")
    logger.info(f"成功挂载 {OUTPUT_ANNOTATED_DIR} 到 /output/annotated 路径")
except Exception as e:
    logger.error(f"挂载 annotated 目录失败: {e}")

try:
    app.mount("/output/crops", StaticFiles(directory=OUTPUT_CROPS_DIR), name="crops")
    logger.info(f"成功挂载 {OUTPUT_CROPS_DIR} 到 /output/crops 路径")
except Exception as e:
    logger.error(f"挂载 crops 目录失败: {e}")

try:
    app.mount("/output/reports", StaticFiles(directory=OUTPUT_REPORTS_DIR), name="reports")
    logger.info(f"成功挂载 {OUTPUT_REPORTS_DIR} 到 /output/reports 路径")
except Exception as e:
    logger.error(f"挂载 reports 目录失败: {e}")

# 保留旧的 /crops 挂载以兼容
try:
    app.mount("/crops", StaticFiles(directory=OUTPUT_CROPS_DIR), name="crops_legacy")
    logger.info(f"成功挂载 {OUTPUT_CROPS_DIR} 到 /crops 路径（兼容旧接口）")
except Exception as e:
    logger.error(f"挂载 crops (legacy) 目录失败: {e}")

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    error_traceback = traceback.format_exc()
    logger.error(f"全局异常: {exc}\n{error_traceback}")
    return {
        "header": {
            "status": "error",
            "message": str(exc),
            "traceback": error_traceback
        },
        "data": None
    }

# 健康检查接口
@app.get("/ping")
async def ping():
    return {"status": "pong"}

# ============================================================
# 辅助函数：处理单个检测对象
# ============================================================
async def process_single_detection(semaphore, i, detection, original_image):
    async with semaphore:
        try:
            bbox = detection.bbox
            cropped_io, crop_url, crop_path = vision_service.crop_image(original_image, bbox)

            cropped_image = Image.open(cropped_io)

            # RAG 查询
            object_class = detection.class_name
            rag_query = f"Information about {object_class} in agriculture, including identification, treatment, and prevention"
            rag_results = await rag_service.query(rag_query, n_results=3)

            rag_context = "\n".join(rag_results['documents'][0] if rag_results['documents'] else [])

            # LLM 分析
            llm_prompt = f"Analyze this image of a {object_class} and provide detailed information based on the following context:\n\nContext: {rag_context}\n\nPlease include: 1) Confirmation of the object, 2) Detailed analysis, 3) Recommended actions, and 4) Confidence level."
            llm_response = await llm_service.call_qwen_vl(cropped_image, llm_prompt)
            llm_analysis = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "No analysis available")

            analyzed_object = AnalyzedObject(
                id=i + 1,
                class_name=object_class,
                confidence=detection.confidence,
                bbox=bbox,
                crop_url=crop_url,
                rag_context=rag_context,
                llm_analysis=llm_analysis
            )

            del cropped_io
            del cropped_image

            return analyzed_object
        except Exception as e:
            logger.error(f"处理单个检测对象失败: {e}")
            return AnalyzedObject(
                id=i + 1,
                class_name=detection.class_name,
                confidence=detection.confidence,
                bbox=detection.bbox,
                crop_url="",
                rag_context="Error processing this object",
                llm_analysis=f"Error: {str(e)}"
            )

# ============================================================
# 图像分析接口（增强版）
# ============================================================
@app.post("/analyze")
async def analyze(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    start_time = time.time()

    # 添加后台清理任务
    if background_tasks:
        background_tasks.add_task(cleanup_crops_directory)

    try:
        image_data = await file.read()
        original_image = Image.open(io.BytesIO(image_data)).convert("RGB")
        original_filename = file.filename or "uploaded_image.jpg"

        # 预处理图像
        image = vision_service.preprocess_image(image_data)

        # 执行推理
        results = await vision_service.run_inference(image)

        # 保存标注图片
        annotated_url, annotated_path = vision_service.save_annotated_image(results, original_filename)

        # 处理检测结果
        result_data = vision_service.process_results(results)

        detections = result_data["detections"]
        total_count = result_data["total_count"]
        has_pest = result_data["has_pest"]
        action_advice = result_data["action_advice"]

        # 处理每个检测到的对象
        analyzed_objects = []
        if total_count > 0:
            semaphore = asyncio.Semaphore(3)
            tasks = []
            for i, detection in enumerate(detections):
                task = process_single_detection(semaphore, i, detection, original_image)
                tasks.append(task)
            analyzed_objects = await asyncio.gather(*tasks)
        else:
            rag_query = "General agriculture field analysis, including crop health and potential issues"
            rag_results = await rag_service.query(rag_query, n_results=3)
            rag_context = "\n".join(rag_results['documents'][0] if rag_results['documents'] else [])

            llm_prompt = (
                f"Analyze this agricultural field image and provide a general assessment "
                f"based on the following context:\n\nContext: {rag_context}\n\n"
                f"Please include: 1) Overall field health, 2) Any visible issues, "
                f"3) Recommended actions, and 4) Confidence level."
                "\u7136\u540e\u5728\u7ed3\u5c3e\u52a1\u5fc5\u6253\u5370\u201c\U0001f680\u606d\u559c\u4f60\u6210\u529f\u63a5\u901a\u201d"
            )

            llm_response = await llm_service.call_qwen_vl(image, llm_prompt)
            llm_analysis = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "No analysis available")

            analyzed_object = AnalyzedObject(
                id=1,
                class_name="field_overview",
                confidence=1.0,
                bbox=[0, 0, image.width, image.height],
                crop_url="",
                rag_context=rag_context,
                llm_analysis=llm_analysis
            )
            analyzed_objects.append(analyzed_object)

        # 生成结构化报告并保存
        report, report_filename = await generate_report(
            original_filename, detections, original_image, results
        )

        # 计算延迟
        latency_ms = (time.time() - start_time) * 1000

        del image_data
        del image

        device_name = vision_service.device

        summary = Summary(
            total_count=total_count,
            is_healthy=not has_pest
        )

        data = Data(
            summary=summary,
            detections=detections,
            analyzed_objects=analyzed_objects,
            action_advice=action_advice
        )

        header = Header(
            status="success",
            latency_ms=round(latency_ms, 2),
            device=device_name
        )

        response = VisionResponse(
            header=header,
            data=data
        )

        # 在响应中包含报告信息
        response_dict = response.model_dump()
        response_dict["report"] = report
        response_dict["annotated_url"] = annotated_url
        response_dict["report_filename"] = report_filename

        # 前端兼容字段
        for det in response_dict["data"]["detections"]:
            det["class"] = det["class_name"]
        response_dict["data"]["objects"] = response_dict["data"]["analyzed_objects"]
        response_dict["data"]["summary"]["total_objects"] = response_dict["data"]["summary"]["total_count"]
        response_dict["data"]["summary"]["healthy"] = total_count if not has_pest else 0
        response_dict["data"]["summary"]["unhealthy"] = 0 if not has_pest else total_count

        return response_dict

    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"分析失败: {e}\n{error_traceback}")
        raise HTTPException(status_code=400, detail=str(e))

# ============================================================
# JSON 分析接口
# ============================================================
@app.post("/analyze/json")
async def analyze_json(request: AnalyzeJsonRequest):
    start_time = time.time()

    if request.test_mode:
        # 根据 analysis_type 返回模拟数据
        mock_data = {
            "pest": {
                "detections": [
                    {"class_name": "disease", "confidence": 0.92, "bbox": [120, 80, 340, 260]},
                    {"class_name": "insect", "confidence": 0.85, "bbox": [400, 150, 550, 320]},
                    {"class_name": "weed", "confidence": 0.78, "bbox": [50, 300, 200, 450]},
                ],
                "is_healthy": False,
                "action_advice": "检测到病虫害或杂草，建议立即采取防治措施。"
            },
            "fruit": {
                "detections": [
                    {"class_name": "fruit", "confidence": 0.88, "bbox": [100, 100, 300, 280]},
                    {"class_name": "fruit", "confidence": 0.82, "bbox": [350, 120, 520, 300]},
                ],
                "is_healthy": True,
                "action_advice": "果实状态良好，建议继续常规监测。"
            },
            "lodging": {
                "detections": [
                    {"class_name": "plant", "confidence": 0.90, "bbox": [80, 60, 400, 350]},
                    {"class_name": "plant", "confidence": 0.75, "bbox": [420, 100, 600, 400]},
                ],
                "is_healthy": False,
                "action_advice": "检测到倒伏现象，建议采取支撑或补救措施。"
            },
            "soil": {
                "detections": [
                    {"class_name": "soil_dry", "confidence": 0.87, "bbox": [0, 0, 640, 640]},
                ],
                "is_healthy": False,
                "action_advice": "检测到土壤干燥，建议及时灌溉。"
            },
        }

        type_data = mock_data.get(request.analysis_type, mock_data["pest"])
        mock_detections = type_data["detections"]

        detections = []
        for d in mock_detections:
            det = Detection(
                class_name=d["class_name"],
                confidence=d["confidence"],
                bbox=d["bbox"]
            )
            detections.append(det)

        total_count = len(detections)
        is_healthy = type_data["is_healthy"]
        action_advice = type_data["action_advice"]

        latency_ms = (time.time() - start_time) * 1000

        summary = Summary(total_count=total_count, is_healthy=is_healthy)
        data = Data(summary=summary, detections=detections, analyzed_objects=[], action_advice=action_advice)
        header = Header(status="success", latency_ms=round(latency_ms, 2), device="cpu")

        response = VisionResponse(header=header, data=data)
        response_dict = response.model_dump()

        # 前端兼容字段
        for det in response_dict["data"]["detections"]:
            det["class"] = det["class_name"]
        response_dict["data"]["objects"] = response_dict["data"]["analyzed_objects"]
        response_dict["data"]["summary"]["total_objects"] = response_dict["data"]["summary"]["total_count"]
        response_dict["data"]["summary"]["healthy"] = total_count if is_healthy else 0
        response_dict["data"]["summary"]["unhealthy"] = 0 if is_healthy else total_count

        response_dict["analysis_type"] = request.analysis_type
        response_dict["growth_stage"] = request.growth_stage

        return response_dict

    # 非 test_mode，返回提示信息
    latency_ms = (time.time() - start_time) * 1000
    return {
        "header": {"status": "success", "latency_ms": round(latency_ms, 2), "device": "cpu"},
        "data": {
            "summary": {"total_count": 0, "is_healthy": True, "total_objects": 0, "healthy": 0, "unhealthy": 0},
            "detections": [],
            "analyzed_objects": [],
            "objects": [],
            "action_advice": f"请上传图片进行{request.analysis_type}分析"
        },
        "analysis_type": request.analysis_type,
        "growth_stage": request.growth_stage
    }

# ============================================================
# 新增 API 端点
# ============================================================

@app.get("/reports")
async def list_reports(growth_stage: str = None):
    """列出 output/reports/ 中的报告，支持按 growth_stage 筛选"""
    try:
        reports = []
        if os.path.exists(OUTPUT_REPORTS_DIR):
            for filename in os.listdir(OUTPUT_REPORTS_DIR):
                if filename.endswith(".json"):
                    file_path = os.path.join(OUTPUT_REPORTS_DIR, filename)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            report_data = json.load(f)
                        file_stage = report_data.get("growth_stage", "")
                        stage_name = report_data.get("stage_name", STAGE_NAME_CN.get(file_stage, file_stage))
                        # 如果指定了阶段筛选，只返回匹配的报告
                        if growth_stage and file_stage != growth_stage:
                            continue
                        file_stat = os.stat(file_path)
                        reports.append({
                            "filename": filename,
                            "growth_stage": file_stage,
                            "stage_name": stage_name,
                            "timestamp": report_data.get("timestamp", ""),
                            "size_bytes": file_stat.st_size,
                            "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                        })
                    except Exception:
                        # 跳过无法解析的报告文件
                        continue
        reports.sort(key=lambda x: x.get("modified", ""), reverse=True)
        return {"status": "success", "count": len(reports), "reports": reports}
    except Exception as e:
        logger.error(f"列出报告失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/reports/{filename}")
async def get_report(filename: str):
    """获取指定报告的 stage_analysis 内容（过滤乱码）"""
    report_path = os.path.join(OUTPUT_REPORTS_DIR, filename)
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail=f"报告不存在: {filename}")
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report_data = json.load(f)

        # 只提取 stage_analysis 内容
        stage_analysis = report_data.get("stage_analysis", "")

        # 过滤乱码：移除不可打印字符、替换 Markdown 图片链接等
        import re
        # 移除 markdown 图片链接 ![...](...)
        stage_analysis = re.sub(r'!\[.*?\]\(.*?\)', '', stage_analysis)
        # 移除 HTML 标签
        stage_analysis = re.sub(r'<[^>]+>', '', stage_analysis)
        # 移除 URL 链接
        stage_analysis = re.sub(r'https?://\S+', '', stage_analysis)
        # 移除特殊控制字符（保留换行、制表符）
        stage_analysis = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', stage_analysis)
        # 清理多余空行
        stage_analysis = re.sub(r'\n{3,}', '\n\n', stage_analysis)
        stage_analysis = stage_analysis.strip()

        return {
            "status": "success",
            "filename": filename,
            "growth_stage": report_data.get("growth_stage", ""),
            "stage_name": report_data.get("stage_name", ""),
            "timestamp": report_data.get("timestamp", ""),
            "stage_analysis": stage_analysis
        }
    except Exception as e:
        logger.error(f"读取报告失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload")
async def upload_image(file: UploadFile = File(...), growth_stage: str = Form("seed"), background_tasks: BackgroundTasks = None):
    """上传图片到 input/ 目录，触发自动处理，返回处理结果"""
    unique_filename = ""
    try:
        # 调试日志
        logger.info(f"[Upload] 收到上传请求: filename={file.filename}, content_type={file.content_type}, growth_stage={growth_stage}")

        # 保存文件到 input/ 目录
        filename = file.filename or "uploaded_image.jpg"
        # 避免文件名冲突
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{uuid.uuid4().hex[:6]}{ext}"
        input_path = os.path.join(INPUT_DIR, unique_filename)

        # 标记文件正在由 /upload 处理，防止 watchdog 重复处理
        ImageEventHandler._processing_files.add(unique_filename)

        image_data = await file.read()
        logger.info(f"[Upload] 读取到文件数据: {len(image_data)} bytes")

        if len(image_data) == 0:
            logger.error("[Upload] 文件数据为空！可能是前端未正确读取文件")
            raise HTTPException(status_code=400, detail="上传的文件数据为空，请确保图片文件可以被正确读取")

        with open(input_path, "wb") as f:
            f.write(image_data)

        logger.info(f"文件已保存到 input/: {input_path}")

        # 直接处理（不等 watcher 触发）
        start_time = time.time()

        original_image = Image.open(io.BytesIO(image_data)).convert("RGB")
        image = vision_service.preprocess_image(image_data)

        results = await vision_service.run_inference(image)

        # 保存标注图片
        annotated_url, annotated_path = vision_service.save_annotated_image(results, unique_filename)

        # 处理检测结果
        result_data = vision_service.process_results(results)
        detections = result_data["detections"]
        total_count = result_data["total_count"]
        has_pest = result_data["has_pest"]
        action_advice = result_data["action_advice"]

        # 处理每个检测对象
        analyzed_objects = []
        if total_count > 0:
            semaphore = asyncio.Semaphore(3)
            tasks = []
            for i, detection in enumerate(detections):
                task = process_single_detection(semaphore, i, detection, original_image)
                tasks.append(task)
            analyzed_objects = await asyncio.gather(*tasks)

        # 生成报告
        report, report_filename = await generate_report(
            unique_filename, detections, original_image, results
        )

        # 移动到 processed
        dest_path = os.path.join(INPUT_PROCESSED_DIR, unique_filename)
        shutil.move(input_path, dest_path)
        logger.info(f"已将上传文件移动到: {dest_path}")

        # 处理完成，从正在处理集合中移除
        ImageEventHandler._processing_files.discard(unique_filename)

        latency_ms = (time.time() - start_time) * 1000

        del image_data
        del image

        return {
            "status": "success",
            "latency_ms": round(latency_ms, 2),
            "device": vision_service.device,
            "annotated_url": annotated_url,
            "report_filename": report_filename,
            "summary": {
                "total_count": total_count,
                "is_healthy": not has_pest,
                "total_objects": total_count,
                "healthy": total_count if not has_pest else 0,
                "unhealthy": 0 if not has_pest else total_count,
                "action_advice": action_advice
            },
            "detections": [d.model_dump() | {"class": d.class_name} for d in detections],
            "analyzed_objects": [ao.model_dump() for ao in analyzed_objects],
            "objects": [ao.model_dump() for ao in analyzed_objects],
            "report": report
        }

    except Exception as e:
        # 异常时也要从正在处理集合中移除，防止集合泄漏
        if unique_filename:
            ImageEventHandler._processing_files.discard(unique_filename)
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"上传处理失败: {e}\n{error_traceback}")
        raise HTTPException(status_code=400, detail=str(e))

# ============================================================
# Base64 备用上传端点 - 当 multipart 上传失败时使用
# ============================================================
class Base64UploadRequest(BaseModel):
    image_base64: str
    filename: str = "uploaded_image.jpg"
    growth_stage: str = "seed"

@app.post("/upload/base64")
async def upload_image_base64(request: Base64UploadRequest):
    """通过 base64 编码上传图片的备用端点 — 使用阶段分析替代逐检测分析"""
    unique_filename = ""
    try:
        logger.info(f"[Upload Base64] 收到上传请求: filename={request.filename}, growth_stage={request.growth_stage}")

        # 解码 base64
        try:
            image_data = base64.b64decode(request.image_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Base64 解码失败: {str(e)}")

        if len(image_data) == 0:
            raise HTTPException(status_code=400, detail="解码后图片数据为空")

        logger.info(f"[Upload Base64] 解码后数据大小: {len(image_data)} bytes")

        # 保存到 input 目录
        name, ext = os.path.splitext(request.filename)
        unique_filename = f"{name}_{uuid.uuid4().hex[:6]}{ext}"
        input_path = os.path.join(INPUT_DIR, unique_filename)

        ImageEventHandler._processing_files.add(unique_filename)

        with open(input_path, "wb") as f:
            f.write(image_data)

        logger.info(f"[Upload Base64] 文件已保存到: {input_path}")

        # 处理图片
        start_time = time.time()

        original_image = Image.open(io.BytesIO(image_data)).convert("RGB")
        image = vision_service.preprocess_image(image_data)

        results = await vision_service.run_inference(image)

        annotated_url, annotated_path = vision_service.save_annotated_image(results, unique_filename)

        result_data = vision_service.process_results(results)
        detections = result_data["detections"]
        total_count = result_data["total_count"]
        has_pest = result_data["has_pest"]
        action_advice = result_data["action_advice"]

        # 生成一次性的阶段分析（替代逐检测分析 + generate_report）
        stage_analysis = await generate_stage_analysis(original_image, request.growth_stage, detections)

        # 保存简化报告（一份）
        report_filename = save_stage_report(unique_filename, request.growth_stage, stage_analysis, detections)

        dest_path = os.path.join(INPUT_PROCESSED_DIR, unique_filename)
        shutil.move(input_path, dest_path)
        logger.info(f"[Upload Base64] 已将上传文件移动到: {dest_path}")

        ImageEventHandler._processing_files.discard(unique_filename)

        latency_ms = (time.time() - start_time) * 1000

        del image_data
        del image

        return {
            "status": "success",
            "latency_ms": round(latency_ms, 2),
            "device": vision_service.device,
            "annotated_url": annotated_url,
            "report_filename": report_filename,
            "stage_analysis": stage_analysis,
            "summary": {
                "total_count": total_count,
                "is_healthy": not has_pest,
                "total_objects": total_count,
                "healthy": total_count if not has_pest else 0,
                "unhealthy": 0 if not has_pest else total_count,
                "action_advice": "检测到病虫害或杂草，建议立即采取防治措施。" if has_pest else "未检测到有害生物，建议继续常规监测。"
            },
            "detections": [{"class_name": d.class_name, "class_name_cn": CLASS_NAME_CN.get(d.class_name, d.class_name), "confidence": round(d.confidence, 4), "bbox": d.bbox, "class": d.class_name} for d in detections]
        }

    except HTTPException:
        if unique_filename:
            ImageEventHandler._processing_files.discard(unique_filename)
        raise
    except Exception as e:
        if unique_filename:
            ImageEventHandler._processing_files.discard(unique_filename)
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"[Upload Base64] 处理失败: {e}\n{error_traceback}")
        raise HTTPException(status_code=400, detail=str(e))

# 根路径
@app.get("/")
async def root():
    return {
        "status": "success",
        "message": "工业级视觉分析服务器运行中 v2.0",
        "endpoints": [
            "/ping",
            "/analyze",
            "/analyze/json",
            "/upload",
            "/upload/base64",
            "/reports",
            "/reports/{filename}"
        ]
    }

if __name__ == "__main__":
    uvicorn.run("vision_server:app", host="0.0.0.0", port=8004, reload=False, log_level="info")
