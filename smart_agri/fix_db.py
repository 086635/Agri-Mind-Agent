import chromadb
import os
from sentence_transformers import SentenceTransformer

# 1. 配置绝对路径
DB_PATH = r"E:\important_project\FWWBC\aidemo\agri_db"
BGE_PATH = r"D:\huggingface\hub\models--BAAI--bge-m3\snapshots\5617a9f61b028005a4858fdac845db406aefb181"

# 2. 初始化数据库连接
print("⏳ 正在连接本地数据库...")
client = chromadb.PersistentClient(path=DB_PATH)

# 3. 加载你 D 盘的 BGE 模型（确保产生 1024 维向量）
print("⏳ 正在加载 BGE 模型以对齐维度...")
model = SentenceTransformer(BGE_PATH)

# 4. 获取或创建集合
# 注意：这里我们手动传入计算好的向量，不让 ChromaDB 自己去联网下载默认模型
collection = client.get_or_create_collection(name="agri_knowledge")

# 5. 准备我们要存入的数据
text_data = "这是一株常见的杂草（牛筋草），建议使用10%草甘膦水剂，按1:50兑水喷雾处理。"
# 核心步骤：手动将文字转为向量
print("🔄 正在将知识文本转换为 1024 维向量...")
vector_data = model.encode([text_data]).tolist() 

# 6. 存入数据库
collection.add(
    ids=["weed_001"],
    embeddings=vector_data,  # 显式传入 1024 维向量
    documents=[text_data],
    metadatas=[{"type": "herbicide_advice"}]
)

print("\n✅ 奇迹发生了！维度完美对齐（1024）。")
print(f"✅ 知识库已就绪，位置：{DB_PATH}")