import os
import io
import base64
import httpx
import threading
import logging
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

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

load_dotenv()

class Config:
    BGE_PATH = os.getenv("BGE_PATH", r"D:\huggingface\hub\models--BAAI--bge-m3\snapshots\5617a9f61b028005a4858fdac845db406aefb181")
    YOLO_PATH = os.getenv("YOLO_PATH", r"E:\important_project\FWWBC\aidemo\runs\detect\my_cpu_train_v16\weights\best.pt")
    DB_PATH = os.getenv("DB_PATH", "vision.db")
    API_KEY = os.getenv("QWEN_API_KEY", "YOUR_QWEN_API_KEY_HERE")
    QWEN_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

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
    
    async def close(self):
        await self.client.aclose()

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import torch
import numpy as np
from PIL import Image
import asyncio
import threading
import time

PEST_KEYWORDS = ['pest', 'wilt', 'mold', 'aphid']

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
        self.device = 'cpu'
        torch.set_num_threads(1)
        self.crops_dir = "crops"
        if not os.path.exists(self.crops_dir):
            os.makedirs(self.crops_dir)
            logger.info(f"创建crops目录: {self.crops_dir}")
    
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
            logger.info("正在进行模型暖机...")
            dummy_image = np.zeros((640, 640, 3), dtype=np.uint8)
            dummy_pil = Image.fromarray(dummy_image)
            results = self.model(dummy_pil, half=False, device=self.device)
            logger.info("模型暖机完成，服务准备就绪")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise
    
    def preprocess_image(self, image_data):
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        image = image.resize((640, 640))
        return image
    
    def save_cropped_image(self, cropped_image):
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        filename = f"crop_{unique_id}.jpg"
        file_path = os.path.join(self.crops_dir, filename)
        cropped_image.save(file_path, format='JPEG')
        logger.info(f"保存裁剪图片到: {file_path}")
        return f"/crops/{filename}"
    
    def crop_image(self, image, bbox):
        cropped = image.crop(bbox)
        cropped_io = io.BytesIO()
        cropped.save(cropped_io, format='JPEG')
        cropped_io.seek(0)
        file_path = self.save_cropped_image(cropped)
        return cropped_io, file_path
    
    async def run_inference(self, image):
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
            action_advice = "High risk: Pest detected. Triggering insecticide protocol."
        else:
            action_advice = "Low risk: No harmful pests detected. Continue regular monitoring."
        
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

vision_service = VisionService()

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
        if self.embedding_model is None:
            return [0.0] * 384
        
        def _embed_text():
            return self.embedding_model.encode(text).tolist()
        
        embedding = await asyncio.to_thread(_embed_text)
        return embedding
    
    async def query(self, query_text, n_results=3):
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
        if self.collection is None:
            import uuid
            return str(uuid.uuid4())
        
        def _add_document():
            embedding = self.embedding_model.encode(document).tolist()
            import uuid
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

rag_service = RAGService()
llm_service = LLMService()

async def cleanup_crops_directory():
    try:
        crops_dir = "crops"
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    vision_service.load_model()
    rag_service.load_model()
    yield
    vision_service.cleanup()
    rag_service.cleanup()
    await llm_service.close()

app = FastAPI(
    title="Industrial Vision Server",
    description="工业级视觉分析服务器，运行在8004端口，支持YOLOv11目标检测",
    version="1.0.0",
    lifespan=lifespan
)

try:
    app.mount("/crops", StaticFiles(directory="crops"), name="crops")
    logger.info("成功挂载crops目录到 /crops 路径")
except Exception as e:
    logger.error(f"挂载crops目录失败: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/ping")
async def ping():
    return {"status": "pong"}

async def process_single_detection(semaphore, i, detection, original_image):
    async with semaphore:
        try:
            bbox = detection.bbox
            cropped_io, crop_path = vision_service.crop_image(original_image, bbox)
            cropped_image = Image.open(cropped_io)
            object_class = detection.class_name
            rag_query = f"Information about {object_class} in agriculture, including identification, treatment, and prevention"
            rag_results = await rag_service.query(rag_query, n_results=3)
            rag_context = "\n".join(rag_results['documents'][0] if rag_results['documents'] else [])
            llm_prompt = f"Analyze this image of a {object_class} and provide detailed information based on the following context:\n\nContext: {rag_context}\n\nPlease include: 1) Confirmation of the object, 2) Detailed analysis, 3) Recommended actions, and 4) Confidence level."
            llm_response = await llm_service.call_qwen_vl(cropped_image, llm_prompt)
            llm_analysis = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "No analysis available")
            
            analyzed_object = AnalyzedObject(
                id=i + 1,
                class_name=object_class,
                confidence=detection.confidence,
                bbox=bbox,
                crop_url=crop_path,
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

@app.post("/analyze")
async def analyze(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    start_time = time.time()
    
    if background_tasks:
        background_tasks.add_task(cleanup_crops_directory)
    
    try:
        image_data = await file.read()
        original_image = Image.open(io.BytesIO(image_data)).convert("RGB")
        image = vision_service.preprocess_image(image_data)
        results = await vision_service.run_inference(image)
        result_data = vision_service.process_results(results)
        
        detections = result_data["detections"]
        total_count = result_data["total_count"]
        has_pest = result_data["has_pest"]
        action_advice = result_data["action_advice"]
        
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
            llm_prompt = f"Analyze this agricultural field image and provide a general assessment based on the following context:\n\nContext: {rag_context}\n\nPlease include: 1) Overall field health, 2) Any visible issues, 3) Recommended actions, and 4) Confidence level.然后在结尾务必打印"🚀恭喜你成功接通""
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
        
        return response
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"分析失败: {e}\n{error_traceback}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/")
async def root():
    return {
        "status": "success",
        "message": "工业级视觉分析服务器运行中",
        "endpoints": [
            "/ping",
            "/analyze"
        ]
    }

if __name__ == "__main__":
    uvicorn.run("vision_server:app", host="0.0.0.0", port=8004, reload=False, log_level="info")
