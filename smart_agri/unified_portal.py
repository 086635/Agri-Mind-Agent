import uvicorn
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI(title="智慧农业全功能门户")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 内部地址
MONITOR_URL = "http://localhost:8000"
AI_GATEWAY_URL = "http://localhost:8001"

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <div style="font-family: sans-serif; text-align: center; padding: 50px; background: #f8fafc; min-height: 100vh;">
        <h1 style="color: #1e293b;">🌾 智慧农业云端控制中心</h1>
        <div style="display: flex; justify-content: center; gap: 20px; margin-top: 30px;">
            <a href="/monitor" target="_blank" style="padding: 12px 24px; background: #3b82f6; color: white; text-decoration: none; border-radius: 8px;">1. 监控大屏 (8000)</a>
            <a href="/docs" target="_blank" style="padding: 12px 24px; background: #10b981; color: white; text-decoration: none; border-radius: 8px;">2. AI 交互测试 (8001)</a>
        </div>
    </div>
    """

# 修复后的转发逻辑：支持 GET 传参
@app.api_route("/chat", methods=["GET", "POST"])
async def proxy_chat(request: Request, command: str = Query(None)):
    # 统一提取 command 参数
    if not command:
        # 尝试从 POST Body 中提取
        try:
            body = await request.json()
            command = body.get("command")
        except:
            pass
    
    if not command:
        return JSONResponse(content={"error": "缺少 command 参数"}, status_code=400)
    
    # 统一使用 POST 方式转发给 AI 网关，command 作为 Query Parameter
    async with httpx.AsyncClient(timeout=30.0) as client:
        target_url = f"{AI_GATEWAY_URL}/chat"
        
        # 构建要转发的请求
        # 过滤掉原始 Header 中的 host 和 content-length
        forward_headers = dict(request.headers)
        forward_headers.pop("host", None)
        forward_headers.pop("content-length", None)
        
        # 统一使用 POST 方式，command 作为 Query Parameter
        resp = await client.post(
            target_url,
            params={"command": command},
            headers=forward_headers
        )
        
        try:
            return resp.json()
        except:
            return JSONResponse(content={"detail": "后端返回格式非 JSON", "raw": resp.text}, status_code=resp.status_code)

# 监控页面转发
@app.get("/monitor", response_class=HTMLResponse)
async def proxy_monitor():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{MONITOR_URL}/monitor")
        return HTMLResponse(content=resp.text)

# 统计数据转发 (供前端 JS 调用)
@app.get("/stats/summary")
async def proxy_stats():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{MONITOR_URL}/stats/summary")
        return resp.json()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)