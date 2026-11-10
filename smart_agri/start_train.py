from ultralytics import YOLO
import os

def train_my_model():
    # 1. 加载模型 (如果本地没有 yolo11n.pt，它会自动下载到当前目录)
    model = YOLO('yolo11n.pt') 

    # 2. 开始投喂数据
    # 这里直接使用 'data.yaml'，意思是寻找与本脚本在同一个文件夹下的配置文件
    model.train(
        data='data.yaml',      # 改为相对路径，再也不会因为挪动文件夹报错了
        epochs=10,             # 训练 10 轮
        imgsz=320,             # CPU 训练建议保持 320，提升速度
        batch=4,               # 每一批次处理 4 张图
        device='cpu',          # 明确指定使用 CPU 运行
        workers=0,             # Windows CPU 训练建议设为 0，防止多线程死锁
        name='my_cpu_train_v1' # 结果会保存在 runs/detect/my_cpu_train_v1 下
    )

if __name__ == '__main__':
    train_my_model()