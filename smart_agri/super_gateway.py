from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse, Response, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import httpx
import uvicorn
import os
import socket
import logging

# MQTT 客户端初始化
async def init_mqtt():
    """初始化 MQTT 客户端"""
    # 这里可以添加 MQTT 客户端初始化代码
    print("[MQTT] 初始化完成")

# 检查端口是否可用
def check_port_available(port):
    """检查端口是否可用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0

# 检查下游服务状态
async def check_services():
    """检查下游服务状态"""
    services = [
        ("AI大脑", "http://localhost:8001/ping"),
        ("业务逻辑与硬件控制", "http://localhost:8003/ping"),
        ("视觉推理中心", "http://localhost:8004/ping")
    ]
    
    print("\n" + "="*50)
    print("服务依赖检查")
    print("="*50)
    
    for name, url in services:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=2.0)
                print(f"[OK] {name}: 运行正常")
        except:
            print(f"[ERROR] {name}: 未启动")
    
    print("="*50 + "\n")

# 使用新的 lifespan 事件处理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup 逻辑
    print("\n" + "="*50)
    print("超级网关启动中...")
    print("="*50)
    
    # 初始化 HTTP 客户端
    app.state.http_client = httpx.AsyncClient(timeout=60.0)
    print("[HTTP Client] 初始化完成")
    
    await init_mqtt()
    
    print("\n警告: 暂时禁用 ngrok 隧道，仅使用本地服务\n")
    print(f"[超级网关] 服务运行在: http://localhost:9000")
    print(f"[超级网关] 转发规则:")
    print(f"  - /chat, /voice_cmd, /stats/*, /api/ai/* → AI大脑 (http://localhost:8001)")
    print(f"  - /analytics/dashboard, /analytics/metrics/latest → 数据分析看板 (8001)")
    print(f"  - /feedback, /experience/history → 经验学习与反馈 (8001)")
    print(f"  - /system/status, /system/operation-logics → 系统运维 (8001)")
    print(f"  - /chat/history, /chat/messages, /chat/clear → 聊天记录管理 (8001)")
    print(f"  - /monitor, /control, /api/business/* → 业务逻辑与硬件控制 (http://localhost:8003)")
    print(f"  - /analyze, /crops/{'{filename}'}, /api/vision/* → 视觉推理中心 (http://localhost:8004)")
    print(f"  - /upload, /output/*, /reports → 视觉推理中心 (http://localhost:8004)")
    print(f"  - /dify/run → Dify 工作流 (http://localhost/v1)")
    print(f"  - /health → 健康检查")
    
    # 暂时注释掉服务依赖检查，加快启动速度
    # await check_services()
    
    # 检测 Dify 连接
    print("\n" + "="*50)
    print("Dify 连接检测")
    print("="*50)
    dify_base_url = "http://localhost/v1"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{dify_base_url}", timeout=3.0)
            # 优化：只要不是 ConnectError 就标记为已响应
            print(f"[OK] Dify 服务已响应，状态码: {resp.status_code}")
    except httpx.ConnectError:
        print("[ERROR] Dify 服务未启动或连接超时")
        # 尝试切换到 host.docker.internal
        print("[INFO] 尝试切换到 host.docker.internal...")
        dify_base_url = "http://host.docker.internal/v1"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{dify_base_url}", timeout=3.0)
                # 优化：只要不是 ConnectError 就标记为已响应
                print(f"[OK] Dify 服务已响应 (使用 host.docker.internal)，状态码: {resp.status_code}")
        except httpx.ConnectError:
            print("[ERROR] Dify 服务仍然无法连接")
        except Exception as e:
            print(f"[OK] Dify 服务已响应 (使用 host.docker.internal)，但出现异常: {str(e)}")
    except Exception as e:
        print(f"[OK] Dify 服务已响应，但出现异常: {str(e)}")
    print("="*50 + "\n")
    
    yield  # 这里应用开始运行并处理请求
    
    # Shutdown 逻辑
    print("\n" + "="*50)
    print("超级网关关闭中...")
    print("="*50)
    
    # 关闭 HTTP 客户端
    if hasattr(app.state, 'http_client'):
        await app.state.http_client.aclose()
        print("[HTTP Client] 已关闭")
    else:
        print("[HTTP Client] 未初始化，跳过关闭")

# 创建FastAPI应用实例
app = FastAPI(
    title="Super Gateway",
    description="A robust API gateway built with FastAPI",
    version="1.0.0",
    lifespan=lifespan  # 添加 lifespan 参数
)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
)

# 添加ngrok跳过浏览器警告的中间件
@app.middleware("http")
async def add_ngrok_skip_header(request, call_next):
    response = await call_next(request)
    response.headers["ngrok-skip-browser-warning"] = "69420"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response



# 通用代理请求函数
async def _proxy_request(target_base_url, request, method):
    try:
        # 构建目标URL - 注意：path已经在api_proxy中处理过，直接使用
        target_url = target_base_url
        
        # 统一将method转为大写
        method = method.upper()
        
        # 处理请求头：复制原始头部，移除host和content-length
        headers = dict(request.headers)
        headers.pop("host", None)  # 移除host以防止目标服务器身份混淆
        headers.pop("content-length", None)  # 移除content-length，让httpx根据实际payload重新计算
        headers.pop("content-encoding", None)  # 移除content-encoding
        headers.pop("transfer-encoding", None)  # 移除transfer-encoding
        
        # 关键加固：如果method为POST且原始请求包含content-type，保留并透传该Header；如果缺失，默认补齐为application/json
        if method == "POST":
            if "content-type" not in headers:
                headers["content-type"] = "application/json"
        
        # 根据目标服务设置超时时间
        timeout = 90.0 if any(keyword in target_url for keyword in ["dify", "8004", "vision"]) else 60.0
        
        # 准备请求参数
        request_kwargs = {
            "url": target_url,
            "headers": headers,
            "params": request.query_params,
            "timeout": timeout,
            "follow_redirects": True  # 启用重定向跟随，处理307等重定向
        }
        
        # 处理请求体
        if method in ["POST", "PUT"]:
            # 使用request.body()捕获完整payload
            body = await request.body()
            request_kwargs["content"] = body
        
        # 增加调试日志
        print(f"[Proxy] {method} {request.url.path} -> {target_url}")
        
        # 获取响应
        response = await request.app.state.http_client.request(method, **request_kwargs)
        if response.status_code == 422:
            error_detail = await response.aread()
            print(f"❌ 下游服务拒绝了请求，原因: {error_detail.decode()}")
        # 检查响应状态码
        status_code = response.status_code
        if status_code != 200:
            # 增加详细的 Debug 日志，特别是针对 405 错误
            print(f"[Proxy Error] {method} {request.url.path} -> {target_url} [Status: {status_code}]")
            if status_code == 405:
                print(f"[Proxy Debug] Method Not Allowed: {method} on {target_url}")
            return JSONResponse(
                status_code=status_code,
                content={"status": "error", "message": f"Failed to fetch data: {status_code}"}
            )
        
        # 增加调试日志
        print(f"[Proxy] {method} {request.url.path} -> {target_url} [Status: {status_code}]")
        
        # 获取响应头
        content_type = response.headers.get("content-type", "text/plain")
        
        # 准备响应头，过滤掉 Transfer-Encoding 头部
        response_headers = dict(response.headers)
        response_headers.pop("transfer-encoding", None)
        response_headers.pop("content-encoding", None)
        
        # 对于JSON响应，显式读取完整内容并返回JSONResponse
        if "application/json" in content_type:
            try:
                content = await response.aread()
                import json
                return JSONResponse(
                    content=json.loads(content),
                    status_code=status_code,
                    headers=response_headers
                )
            except json.JSONDecodeError:
                # 如果JSON解析失败，返回原始文本
                print(f"[Proxy Warning] JSON解析失败，返回原始文本: {content_type}")
                content = await response.aread()
                return Response(
                    content=content,
                    status_code=status_code,
                    media_type=content_type,
                    headers=response_headers
                )
        
        # 对于文本/HTML响应，显式读取内容并返回Response
        if any(media_type in content_type for media_type in ["text", "application"]):
            content = await response.aread()
            return Response(
                content=content,
                status_code=status_code,
                media_type=content_type,
                headers=response_headers
            )
        
        # 对于二进制/流式响应（如图片），使用StreamingResponse
        async def stream_generator():
            async for chunk in response.aiter_bytes():
                yield chunk
        
        return StreamingResponse(
            stream_generator(),
            status_code=status_code,
            media_type=content_type,
            headers=response_headers
        )
    except httpx.ConnectError:
        # 当目标服务未启动时的错误处理 - 返回502 Bad Gateway
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": f"Bad Gateway: {target_base_url} 未启动或连接超时"}
        )
    except httpx.RequestError as e:
        # 其他请求错误处理 - 返回502 Bad Gateway
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": f"Bad Gateway: Failed to connect to {target_base_url}: {str(e)}"}
        )
    except Exception as e:
        # 其他错误处理
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Internal server error: {str(e)}"}
        )

# 根路径 - 托管index.html
@app.get("/")
async def root():
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        # 如果index.html不存在，返回一个基本的HTML文件
        html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智慧农业系统</title>
</head>
<body>
    <h1>智慧农业系统 - 超级网关</h1>
    <p>运行在端口 9000</p>
    <p>API 路径：</p>
    <ul>
        <li>/chat, /voice_cmd, /stats/*, /api/ai/* - AI大脑 (http://localhost:8001)</li>
        <li>/monitor, /control, /api/business/* - 业务逻辑与硬件控制 (http://localhost:8003)</li>
        <li>/analyze, /crops/{filename}, /api/vision/* - 视觉推理中心 (http://localhost:8004)</li>
        <li>/health - 健康检查</li>
    </ul>
</body>
</html>"""
        return Response(content=html_content, media_type="text/html")

# 配置静态资源路由
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 健康检查端点
@app.get("/health")
async def health_check(request: Request):
    services = [
        {"name": "ai", "base_url": "http://127.0.0.1:8001"},
        {"name": "business", "base_url": "http://127.0.0.1:8003"},
        {"name": "vision", "base_url": "http://127.0.0.1:8004"},
        {"name": "dify", "base_url": "http://127.0.0.1"}
    ]
    
    async def check_service(service: dict) -> dict:
        """并行检查单个服务健康状态"""
        try:
            ping_url = f"{service['base_url']}/ping"
            response = await request.app.state.http_client.get(ping_url, timeout=1.0)
            if response.status_code == 200:
                return {
                    "name": service["name"],
                    "status": "healthy",
                    "status_code": response.status_code,
                    "endpoint": "/ping"
                }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                try:
                    root_url = f"{service['base_url']}/"
                    response = await request.app.state.http_client.get(root_url, timeout=1.0)
                    if response.status_code in [200, 302]:
                        return {
                            "name": service["name"],
                            "status": "healthy",
                            "status_code": response.status_code,
                            "endpoint": "/"
                        }
                except Exception:
                    pass
        except Exception:
            pass
        
        return {
            "name": service["name"],
            "status": "unhealthy",
            "error": "Service not responding"
        }
    
    # 并行检查所有服务，总耗时 = 最慢的单个服务耗时（而非累加）
    import asyncio
    results = await asyncio.gather(*[check_service(s) for s in services])
    
    health_status = {}
    for r in results:
        name = r.pop("name")
        health_status[name] = r
    
    overall_status = "healthy" if all(s["status"] == "healthy" for s in health_status.values()) else "unhealthy"
    
    return {
        "status": overall_status,
        "services": health_status
    }

# 监控路径 - 转发到业务逻辑与硬件控制的监控端点
@app.get("/monitor")
async def monitor(request: Request):
    return await _proxy_request("http://localhost:8003/monitor", request, "GET")

# 控制路径 - 转发到业务逻辑与硬件控制的控制端点
@app.post("/control")
async def control(request: Request):
    return await _proxy_request("http://localhost:8003/control", request, "POST")

# AI 聊天接口 - 转发到 AI 网关的聊天端点
@app.post("/chat")
async def chat(request: Request):  # 必须是纯粹的 Request
    # 1. 获取原始 JSON
    try:
        body = await request.json()
        # 2. 字段适配：如果只有 message 没有 command，自动转换
        if "message" in body and "command" not in body:
            body["command"] = body.pop("message")
        
        # 3. 构造新的转发请求
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        import json
        response = await request.app.state.http_client.post(
            "http://localhost:8001/chat",
            content=json.dumps(body),
            headers=headers,
            timeout=60.0
        )
        
        # 处理响应
        if response.status_code == 200:
            # 对于JSON响应，解析并返回
            content_type = response.headers.get("content-type", "text/plain")
            if "application/json" in content_type:
                return JSONResponse(content=response.json(), status_code=response.status_code)
            else:
                content = await response.aread()
                return Response(content=content, status_code=response.status_code, media_type=content_type)
        else:
            # 错误响应
            return JSONResponse(
                status_code=response.status_code,
                content={"status": "error", "message": f"Failed to fetch data: {response.status_code}"}
            )
        
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Data format error: {str(e)}"})
# AI 语音命令接口 - 转发到 AI 网关的语音命令端点
@app.post("/voice_cmd")
async def voice_cmd(request: Request):
    return await _proxy_request("http://localhost:8001/voice_cmd", request, "POST")

# AI 统计摘要接口 - 转发到 AI 网关的统计摘要端点
@app.get("/stats/summary")
async def stats_summary(request: Request):
    return await _proxy_request("http://localhost:8001/stats/summary", request, "GET")

# Dify 对话型接口 - 转发到 Dify 对话 API
@app.post("/dify/run")
async def dify_run(request: Request):  # 必须是纯粹的 Request
    # 1. 获取原始 JSON
    try:
        body = await request.json()
        
        # 统一前端传参，支持 message、command 或 query 字段
        if "query" not in body:
            if "message" in body:
                body["query"] = body.pop("message")
            elif "command" in body:
                body["query"] = body.pop("command")
        
        # 强制注入 response_mode: "streaming" 和 user: "admin"
        body["response_mode"] = "streaming"
        body["user"] = "admin"
        
        # 2. 构造新的转发请求
        headers = dict(request.headers)
        # 从转发 Header 中剔除不需要的字段
        headers.pop("host", None)
        headers.pop("content-length", None)
        headers.pop("content-encoding", None)
        # 强制覆盖 Authorization
        headers["Authorization"] = "Bearer YOUR_DIFY_API_KEY_HERE"
        # 确保 Content-Type 为 application/json
        if "content-type" not in headers:
            headers["content-type"] = "application/json"
        
        import json
        # 手动构建请求
        client = request.app.state.http_client
        request_obj = client.build_request(
            "POST",
            "http://localhost/v1/chat-messages",
            content=json.dumps(body),
            headers=headers
        )
        
        # 发送请求并获取响应
        response = await client.send(request_obj, stream=True, timeout=90.0)
        
        # 检查响应状态码
        if response.status_code != 200:
            # 非 JSON 处理：读取错误详情并打印
            try:
                error_detail = await response.aread()
                print(f"❌ Dify 服务拒绝了请求，状态码: {response.status_code}, 原因: {error_detail.decode()}")
            except Exception as e:
                print(f"❌ 读取 Dify 错误详情失败: {str(e)}")
            finally:
                await response.aclose()
            
            return JSONResponse(
                status_code=response.status_code,
                content={"status": "error", "message": f"Failed to fetch data: {response.status_code}"}
            )
        
        # 准备响应头
        response_headers = dict(response.headers)
        response_headers.pop("transfer-encoding", None)
        response_headers.pop("content-encoding", None)
        response_headers["ngrok-skip-browser-warning"] = "69420"
        response_headers["Access-Control-Allow-Origin"] = "*"
        
        # 定义流式生成器
        async def stream_generator():
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                # 确保连接在流传输结束或异常中断后能被正确释放
                await response.aclose()
        
        # 返回流式响应，设置正确的 media_type 为 text/event-stream
        return StreamingResponse(
            stream_generator(),
            status_code=response.status_code,
            media_type="text/event-stream",
            headers=response_headers
        )
        
    except Exception as e:
        print(f"❌ Dify 接口处理异常: {str(e)}")
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Data format error: {str(e)}"})

# 视觉分析接口 - 转发到视觉推理中心的分析端点
@app.post("/analyze")
async def analyze(request: Request):
    return await _proxy_request("http://localhost:8004/analyze", request, "POST")

# 作物图像接口 - 转发到视觉推理中心的作物图像端点
@app.get("/crops/{filename}")
async def get_crop(filename: str, request: Request):
    return await _proxy_request(f"http://localhost:8004/crops/{filename}", request, "GET")

# 数据分析看板接口 - 转发到 AI 网关
@app.get("/analytics/dashboard")
async def analytics_dashboard(request: Request):
    return await _proxy_request("http://localhost:8001/analytics/dashboard", request, "GET")

# 数据分析指标接口 - 转发到 AI 网关
@app.get("/analytics/metrics/latest")
async def analytics_latest(request: Request):
    return await _proxy_request("http://localhost:8001/analytics/metrics/latest", request, "GET")

# 反馈接口 - 转发到 AI 网关
@app.post("/feedback")
async def submit_feedback(request: Request):
    return await _proxy_request("http://localhost:8001/feedback", request, "POST")

# 经验历史接口 - 转发到 AI 网关
@app.get("/experience/history")
async def experience_history(request: Request):
    return await _proxy_request("http://localhost:8001/experience/history", request, "GET")

# 系统状态接口 - 转发到 AI 网关
@app.get("/system/status")
async def system_status(request: Request):
    return await _proxy_request("http://localhost:8001/system/status", request, "GET")

# 运维逻辑接口 - 转发到 AI 网关
@app.get("/system/operation-logics")
async def operation_logics_get(request: Request):
    return await _proxy_request("http://localhost:8001/system/operation-logics", request, "GET")

@app.post("/system/operation-logics")
async def operation_logics_post(request: Request):
    return await _proxy_request("http://localhost:8001/system/operation-logics", request, "POST")

@app.delete("/system/operation-logics/{logic_id}")
async def operation_logics_delete(logic_id: str, request: Request):
    return await _proxy_request(f"http://localhost:8001/system/operation-logics/{logic_id}", request, "DELETE")

# 聊天历史接口 - 转发到 AI 网关
@app.get("/chat/history")
async def chat_history(request: Request):
    return await _proxy_request("http://localhost:8001/chat/history", request, "GET")

# 聊天消息接口 - 转发到 AI 网关
@app.post("/chat/messages")
async def chat_messages_post(request: Request):
    return await _proxy_request("http://localhost:8001/chat/messages", request, "POST")

@app.delete("/chat/messages/{message_id}")
async def chat_messages_delete(message_id: str, request: Request):
    return await _proxy_request(f"http://localhost:8001/chat/messages/{message_id}", request, "DELETE")

# 聊天清空接口 - 转发到 AI 网关
@app.delete("/chat/clear")
async def chat_clear(request: Request):
    return await _proxy_request("http://localhost:8001/chat/clear", request, "DELETE")

# 通用代理路由
@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def api_proxy(service: str, path: str, request: Request):
    # 服务映射
    service_map = {
        "ai": "http://127.0.0.1:8001",
        "business": "http://127.0.0.1:8003",
        "vision": "http://127.0.0.1:8004"
    }
    
    if service not in service_map:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": f"Service {service} not found"}
        )
    
    # 构建目标URL - 确保没有双斜杠
    target_base_url = service_map[service]
    # 处理path，确保正确拼接
    if path:
        # 确保target_base_url不以/结尾，path不以/开头
        if target_base_url.endswith("/"):
            target_base_url = target_base_url[:-1]
        if path.startswith("/"):
            path = path[1:]
        target_url = f"{target_base_url}/{path}"
    else:
        target_url = target_base_url
    
    # 打印日志 - 显示干净的目标URL
    print(f"[Proxy] {request.method} -> {target_url}")
    
    # 转发请求 - 直接传递完整的target_url
    return await _proxy_request(target_url, request, request.method)

# 视觉分析JSON接口 - 转发到视觉推理中心
@app.post("/analyze/json")
async def analyze_json(request: Request):
    return await _proxy_request("http://localhost:8004/analyze/json", request, "POST")

# 报告列表接口 - 转发到视觉推理中心
@app.get("/reports")
async def reports_list(request: Request):
    return await _proxy_request("http://localhost:8004/reports", request, "GET")

# 报告文件接口 - 转发到视觉推理中心
@app.get("/reports/{filename}")
async def reports_file(filename: str, request: Request):
    return await _proxy_request(f"http://localhost:8004/reports/{filename}", request, "GET")

# 图片上传接口 - 转发到视觉推理中心
@app.post("/upload")
async def upload_image(request: Request):
    # 调试日志：记录上传请求的关键信息
    content_type = request.headers.get("content-type", "unknown")
    content_length = request.headers.get("content-length", "unknown")
    print(f"[Upload Debug] Content-Type: {content_type}")
    print(f"[Upload Debug] Content-Length: {content_length}")
    print(f"[Upload Debug] Query Params: {dict(request.query_params)}")

    # 读取 body 并记录大小
    body = await request.body()
    print(f"[Upload Debug] Body size: {len(body)} bytes")

    # 检查是否为 multipart 请求
    if "multipart/form-data" in content_type:
        print(f"[Upload Debug] Multipart request detected, forwarding to vision server")
    else:
        print(f"[Upload Debug] WARNING: Not a multipart request! Content-Type={content_type}")

    # 重新构建转发请求（body 已读取，需要传递）
    try:
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        headers.pop("content-encoding", None)
        headers.pop("transfer-encoding", None)

        # multipart 请求必须保留原始 Content-Type（含 boundary）
        # 不要覆盖 Content-Type

        timeout = 90.0
        target_url = "http://localhost:8004/upload"

        request_kwargs = {
            "url": target_url,
            "headers": headers,
            "params": request.query_params,
            "timeout": timeout,
            "follow_redirects": True,
            "content": body
        }

        response = await request.app.state.http_client.request("POST", **request_kwargs)

        print(f"[Upload Debug] Vision server response status: {response.status_code}")

        if response.status_code != 200:
            error_body = await response.aread()
            print(f"[Upload Debug] Vision server error: {error_body.decode()[:500]}")
            return JSONResponse(
                status_code=response.status_code,
                content={"status": "error", "message": f"Vision server returned {response.status_code}", "detail": error_body.decode()[:500]}
            )

        # 返回成功响应
        content_type_resp = response.headers.get("content-type", "text/plain")
        resp_headers = dict(response.headers)
        resp_headers.pop("transfer-encoding", None)
        resp_headers.pop("content-encoding", None)

        if "application/json" in content_type_resp:
            import json
            content = await response.aread()
            return JSONResponse(
                content=json.loads(content),
                status_code=response.status_code,
                headers=resp_headers
            )
        else:
            content = await response.aread()
            return Response(
                content=content,
                status_code=response.status_code,
                media_type=content_type_resp,
                headers=resp_headers
            )

    except httpx.ConnectError:
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": "Vision server (8004) not running"}
        )
    except Exception as e:
        print(f"[Upload Debug] Proxy error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Proxy error: {str(e)}"}
        )

# 视觉输出静态文件代理 - 转发到视觉推理中心
@app.get("/output/{path:path}")
async def output_static(path: str, request: Request):
    return await _proxy_request(f"http://localhost:8004/output/{path}", request, "GET")

# Base64 备用上传接口 - 转发到视觉推理中心
@app.post("/upload/base64")
async def upload_base64(request: Request):
    return await _proxy_request("http://localhost:8004/upload/base64", request, "POST")

# Silicon网关通用代理 - 转发到Silicon网关
@app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def silicon_proxy(path: str, request: Request):
    target_url = f"http://localhost:7000/api/v1/{path}"
    return await _proxy_request(target_url, request, request.method)

if __name__ == "__main__":
    # 配置详细日志
    logging.basicConfig(level=logging.INFO)
    
    print("正在启动超级网关...")
    print(f"将运行在: http://localhost:9000")
    
    # 检查端口是否可用
    if not check_port_available(9000):
        print(f"❌ 错误: 端口 9000 已被占用！")
        print(f"请检查是否有其他程序正在使用 9000 端口")
        print(f"或者在任务管理器中结束占用该端口的进程")
        exit(1)
    
    try:
        # 使用 reload=False 避免热重载问题
        uvicorn.run("super_gateway:app", host="0.0.0.0", port=9000, reload=False, log_level="info")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ 错误: 端口 9000 已被占用！")
            print(f"请检查是否有其他程序正在使用 9000 端口")
            print(f"或者在任务管理器中结束占用该端口的进程")
        else:
            print(f"❌ 启动失败: {e}")
    except KeyboardInterrupt:
        print("\n\n服务器被用户中断")
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("服务已停止")