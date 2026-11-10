import chromadb
from sentence_transformers import SentenceTransformer

client = chromadb.PersistentClient(path="./agri_db")
model = SentenceTransformer('BAAI/bge-m3')

collection = client.get_or_create_collection(name="agri_knowledge")

def upload_knowledge():
    documents = [
        "杂草处理：针对大棚内杂草，建议使用物理除草或低毒生物药剂，避免伤及作物根系。",
        "玉米大斑病：表现为长菱形斑，需控制湿度，发病初期可用代森锰锌喷施。",
        "丝绸工厂湿度：自动控制系统需维持湿度在65%-75%，防止生丝断裂。"
    ]
    metadatas = [{"label": "weed"}, {"label": "corn_disease"}, {"label": "silk_factory"}]
    ids = ["id1", "id2", "id3"]

    embeddings = model.encode(documents).tolist()
    collection.add(documents=documents, embeddings=embeddings, metadatas=metadatas, ids=ids)
    print("✅ 农艺知识库初始化完成！")

if __name__ == "__main__":
    upload_knowledge()
