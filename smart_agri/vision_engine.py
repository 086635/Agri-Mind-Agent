import cv2
import os
from ultralytics import YOLO
from sentence_transformers import SentenceTransformer
import chromadb

# 1. 加载你刚练好的 YOLO 模型
# 路径指向你 cmd 训练出的 best.pt
model_yolo = YOLO('E:/important_project/FWWBC/aidemo/runs/detect/weed_project_v1/weights/best.pt')

# 2. 加载本地 BGE-M3 (指向你刚下载完的那个 2G 文件夹路径)
embed_model = SentenceTransformer('BAAI/bge-m3') 

# 3. 连接你 init_rag.py 创建的数据库
db_client = chromadb.PersistentClient(path="./agri_db")
collection = db_client.get_collection(name="agri_knowledge")

def process_and_analyze(image_path):
    img = cv2.imread(image_path)
    results = model_yolo(image_path)
    
    analysis_results = []
    
    # 创建裁剪图目录
    if not os.path.exists("crops"): os.makedirs("crops")

    for i, box in enumerate(results[0].boxes):
        # A. 自动裁剪逻辑 (背后是矩阵切片)
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        crop_img = img[y1:y2, x1:x2]
        crop_path = f"crops/detect_{i}.jpg"
        cv2.imwrite(crop_path, crop_img)

        # B. 获取标签并进行 RAG 检索
        label = model_yolo.names[int(box.cls[0])]
        
        # 将标签转化为向量并在库中搜索最匹配的“农艺方子”
        query_vector = embed_model.encode([label]).tolist()
        doc_results = collection.query(query_embeddings=query_embedding, n_results=1)
        knowledge_context = doc_results['documents'][0][0]

        analysis_results.append({
            "label": label,
            "crop_path": crop_path,
            "knowledge": knowledge_context
        })
    
    return analysis_results