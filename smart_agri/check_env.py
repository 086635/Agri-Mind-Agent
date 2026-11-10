import torch
try:
    import torchvision
    from ultralytics import YOLO
    print("✅ YOLO 环境正常")
except Exception as e:
    print(f"❌ 环境缺失: {e}")

import httpx
async def check_api():
    # 这里填你的配置
    async with httpx.AsyncClient() as client:
        # 尝试访问一个基础接口看网络和Key是否通
        print("正在检查网络...")
# ...