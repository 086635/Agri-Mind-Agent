import os
import io
import torch
import numpy as np
from PIL import Image
import chromadb
from sentence_transformers import SentenceTransformer
from ultralytics import YOLO
import asyncio
import httpx
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VisionService:
    def __init__(self):
        self.model = None
        self.device = 'cpu'
        self.inference_lock = asyncio.Lock()
        self._load_model()
        self._warmup()
    
    def _load_model(self):
        try:
            logger.info("正在加载 YOLOv11 模型...")
            self.model = YOLO('yolo11n.pt')
            logger.info("YOLOv11 模型加载完成")
        except Exception as e:
            logger.error(f"无法加载 YOLO 模型: {e}")
            raise
    
    def _warmup(self):
        try:
            logger.info("正在进行模型暖机...")
            # 创建一张全黑伪图片
            dummy_image = np.zeros((640, 640, 3), dtype=np.uint8)
            dummy_pil = Image.fromarray(dummy_image)
            
            # 执行暖机推理
            results = self.model(dummy_pil, half=False, device=self.device)
            logger.info("模型暖机完成")
        except Exception as e:
            logger.error(f"模型暖机失败: {e}")
            raise
    
    async def detect(self, image):
        async with self.inference_lock:
            # 在单独的线程中执行推理，避免阻塞事件循环
            results = await asyncio.to_thread(
                self.model, image, half=False, device=self.device
            )
            
            # 处理检测结果
            detections = []
            total_count = 0
            has_pest = False
            
            # 预设关键词列表
            PEST_KEYWORDS = ['pest', 'wilt', 'mold', 'aphid']
            
            for result in results:
                for box in result.boxes:
                    class_name = result.names[int(box.cls[0])]
                    confidence = float(box.conf[0])
                    coords = box.xyxy[0]
                    bbox = coords.tolist() if hasattr(coords, 'tolist') else list(coords)
                    
                    detections.append({
                        "class": class_name,
                        "confidence": confidence,
                        "bbox": [int(coord) for coord in bbox]
                    })
                    
                    total_count += 1
                    
                    # 检查是否包含有害生物关键词
                    if class_name.lower() in [kw.lower() for kw in PEST_KEYWORDS]:
                        has_pest = True
            
            return detections, total_count, has_pest
    
    def crop(self, image, bbox):
        try:
            # 确保bbox是有效的
            x1, y1, x2, y2 = bbox
            if x1 < 0 or y1 < 0 or x2 > image.width or y2 > image.height:
                logger.warning(f"无效的边界框: {bbox}")
                return None
            
            # 裁剪图像
            cropped = image.crop((x1, y1, x2, y2))
            return cropped
        except Exception as e:
            logger.error(f"裁剪图像失败: {e}")
            return None

class RAGService:
    def __init__(self):
        self.client = chromadb.PersistentClient(path="./agri_db")
        self.model = SentenceTransformer('BAAI/bge-m3')
        self.collection = self.client.get_or_create_collection(name="agri_knowledge")
    
    def encode(self, text):
        try:
            embedding = self.model.encode(text).tolist()
            return embedding
        except Exception as e:
            logger.error(f"编码文本失败: {e}")
            return None
    
    def query(self, query_text, top_k=3):
        try:
            # 编码查询文本
            query_embedding = self.encode(query_text)
            if query_embedding is None:
                return []
            
            # 查询相似文档
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )
            
            # 处理结果
            documents = results.get('documents', [[]])[0]
            return documents
        except Exception as e:
            logger.error(f"查询知识库失败: {e}")
            return []

class LLMService:
    def __init__(self):
        # 这里使用一个简单的HTTP客户端来模拟LLM服务
        # 实际应用中，你可能需要集成真实的LLM API
        self.api_url = "http://localhost:3001/api/v1/workspace/smartfarm_project/chat"
        self.api_key = "GP5GB4T-E624VHB-MDYXHYN-ZEB5F7Q"
    
    async def analyze(self, prompt):
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "message": prompt,
                "mode": "chat"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(self.api_url, json=payload, headers=headers, timeout=30.0)
                
                if response.status_code != 200:
                    logger.error(f"LLM API 错误: 状态码 {response.status_code}, 内容: {response.text}")
                    return None
                
                result = response.json()
                ai_content = result.get('textResponse', '')
                return ai_content
        except Exception as e:
            logger.error(f"调用 LLM 服务失败: {e}")
            return None

# 全局服务实例
vision_service = VisionService()
rag_service = RAGService()
llm_service = LLMService()
