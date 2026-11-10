import httpx
import base64
import os

# --- 1. 工具函数：保持单纯，只负责转码 ---
def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# --- 2. API 调用函数：负责发请求和 Debug ---
async def call_qwen_vl(base64_image, user_prompt):
    # ⚠️ 计科提醒：比赛完记得重置这个 Key，安全第一
    api_key = "sk-796078737537417bb00d90732b2f1b69" 
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" 
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # 目前官方 api.deepseek.com 主要是文本接口
    # 如果你要用视觉能力，模型名必须支持 Vision (如 deepseek-vl2 系列)
    payload = {
        "model": "qwen-vl-plus", 
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url", 
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    }
    
    async with httpx.AsyncClient() as client:
        print(f"📡 正在呼叫阿里云 Qwen-VL 视觉模型...")
        # 视觉模型由于要处理图片，建议超时时间给足 90s
        response = await client.post(url, headers=headers, json=payload, timeout=90.0)
        
        result = response.json()
        
        # --- DEBUG 逻辑 ---
        if response.status_code != 200:
            print(f"🔍 DEBUG: HTTP 状态码 = {response.status_code}")
            print(f"❌ 阿里云报错详情: {result}")
        
        return result