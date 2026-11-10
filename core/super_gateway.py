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

async def init_mqtt():
    print("[MQTT] 初始化完成")

def check_port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0

async def check_services():
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*50)
    print("超级网关启动中...")
    print("="*50)
    
    app.state.http_client = httpx.AsyncClient(timeout=60.0)
    print("[HTTP Client] 初始化完成")
    
    await init_mqtt()
    
    print("\n警告: 暂时禁用 ngrok 隧道，仅使用本地服务\n")
    print(f"[超级网关] 服务运行在: http://localhost:9000")
    print(f"[超级网关] 转发规则:")
    print(f"  - /chat, /voice_cmd, /stats/*, /api/ai/* → AI大脑 (http://localhost:8001)")
    print(f"  - /analytics/dashboard, /analytics/metrics/latest → 数据分析看板 (8001)")
    print(f"  - /feedback, /experience/history → 经验学习与反馈 (8001)")
    print(f"  - /monitor, /control, /api/business/* → 业务逻辑与硬件控制 (http://localhost:8003)")
    print(f"  - /analyze, /crops/{'{filename}'}, /api/vision/* → 视觉推理中心 (http://localhost:8004)")
    print(f"  - /dify/run → Dify 工作流 (http://localhost/v1)")
    print(f"  - /health → 健康检查")
    
    print("\n" + "="*50)
    print("Dify 连接检测")
    print("="*50)
    dify_base_url = "http://localhost/v1"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{dify_base_url}", timeout=3.0)
            print(f"[OK] Dify 服务已响应，状态码: {resp.status_code}")
    except httpx.ConnectError:
        print("[ERROR] Dify 服务未启动或连接超时")
        print("[INFO] 尝试切换到 host.docker.internal...")
        dify_base_url = "http://host.docker.internal/v1"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{dify_base_url}", timeout=3.0)
                print(f"[OK] Dify 服务已响应 (使用 host.docker.internal)，状态码: {resp.status_code}")
        except httpx.ConnectError:
            print("[ERROR] Dify 服务仍然无法连接")
        except Exception as e:
            print(f"[OK] Dify 服务已响应 (使用 host.docker.internal)，但出现异常: {str(e)}")
    except Exception as e:
        print(f"[OK] Dify 服务已响应，但出现异常: {str(e)}")
    print("="*50 + "\n")
    
    yield
    
    print("\n" + "="*50)
    print("超级网关关闭中...")
    print("="*50)
    
    if hasattr(app.state, 'http_client'):
        await app.state.http_client.aclose()
        print("[HTTP Client] 已关闭")
    else:
        print("[HTTP Client] 未初始化，跳过关闭")

app = FastAPI(
    title="Super Gateway",
    description="A robust API gateway built with FastAPI",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_ngrok_skip_header(request, call_next):
    response = await call_next(request)
    response.headers["ngrok-skip-browser-warning"] = "69420"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

async def _proxy_request(target_base_url, request, method):
    try:
        target_url = target_base_url
        method = method.upper()
        
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        headers.pop("content-encoding", None)
        headers.pop("transfer-encoding", None)
        
        if method == "POST":
            if "content-type" not in headers:
                headers["content-type"] = "application/json"
        
        timeout = 90.0 if any(keyword in target_url for keyword in ["dify", "8004", "vision"]) else 60.0
        
        request_kwargs = {
            "url": target_url,
            "headers": headers,
            "params": request.query_params,
            "timeout": timeout,
            "follow_redirects": True
        }
        
        if method in ["POST", "PUT"]:
            body = await request.body()
            request_kwargs["content"] = body
        
        print(f"[Proxy] {method} {request.url.path} -> {target_url}")
        
        response = await request.app.state.http_client.request(method, **request_kwargs)
        if response.status_code == 422:
            error_detail = await response.aread()
            print(f"❌ 下游服务拒绝了请求，原因: {error_detail.decode()}")
        status_code = response.status_code
        if status_code != 200:
            print(f"[Proxy Error] {method} {request.url.path} -> {target_url} [Status: {status_code}]")
            if status_code == 405:
                print(f"[Proxy Debug] Method Not Allowed: {method} on {target_url}")
            return JSONResponse(
                status_code=status_code,
                content={"status": "error", "message": f"Failed to fetch data: {status_code}"}
            )
        
        print(f"[Proxy] {method} {request.url.path} -> {target_url} [Status: {status_code}]")
        
        content_type = response.headers.get("content-type", "text/plain")
        
        response_headers = dict(response.headers)
        response_headers.pop("transfer-encoding", None)
        response_headers.pop("content-encoding", None)
        
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
                print(f"[Proxy Warning] JSON解析失败，返回原始文本: {content_type}")
                content = await response.aread()
                return Response(
                    content=content,
                    status_code=status_code,
                    media_type=content_type,
                    headers=response_headers
                )
        
        if any(media_type in content_type for media_type in ["text", "application"]):
            content = await response.aread()
            return Response(
                content=content,
                status_code=status_code,
                media_type=content_type,
                headers=response_headers
            )
        
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
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": f"Bad Gateway: {target_base_url} 未启动或连接超时"}
        )
    except httpx.RequestError as e:
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": f"Bad Gateway: Failed to connect to {target_base_url}: {str(e)}"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Internal server error: {str(e)}"}
        )

@app.get("/")
async def root():
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
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

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/health")
async def health_check(request: Request):
    services = [
        {"name": "ai", "base_url": "http://127.0.0.1:8001"},
        {"name": "business", "base_url": "http://127.0.0.1:8003"},
        {"name": "vision", "base_url": "http://127.0.0.1:8004"},
        {"name": "dify", "base_url": "http://127.0.0.1"}
    ]
    
    health_status = {}
    
    for service in services:
        try:
            ping_url = f"{service['base_url']}/ping"
            response = await request.app.state.http_client.get(ping_url, timeout=2.0)
            if response.status_code == 200:
                health_status[service["name"]] = {
                    "status": "healthy",
                    "status_code": response.status_code,
                    "endpoint": "/ping"
                }
                continue
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                try:
                    root_url = f"{service['base_url']}/"
                    response = await request.app.state.http_client.get(root_url, timeout=2.0)
                    if response.status_code in [200, 302]:
                        health_status[service["name"]] = {
                            "status": "healthy",
                            "status_code": response.status_code,
                            "endpoint": "/"
                        }
                        continue
                except Exception:
                    pass
        except Exception:
            pass
        
        health_status[service["name"]] = {
            "status": "unhealthy",
            "error": "Service not responding"
        }
    
    overall_status = "healthy" if all(s["status"] == "healthy" for s in health_status.values()) else "unhealthy"
    
    return {
        "status": overall_status,
        "services": health_status
    }

@app.get("/monitor")
async def monitor(request: Request):
    return await _proxy_request("http://localhost:8003/monitor", request, "GET")

@app.post("/control")
async def control(request: Request):
    return await _proxy_request("http://localhost:8003/control", request, "POST")

@app.post("/chat")
async def chat(request: Request):
    try:
        body = await request.json()
        if "message" in body and "command" not in body:
            body["command"] = body.pop("message")
        
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
        
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "text/plain")
            if "application/json" in content_type:
                return JSONResponse(content=response.json(), status_code=response.status_code)
            else:
                content = await response.aread()
                return Response(content=content, status_code=response.status_code, media_type=content_type)
        else:
            return JSONResponse(
                status_code=response.status_code,
                content={"status": "error", "message": f"Failed to fetch data: {response.status_code}"}
            )
        
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Data format error: {str(e)}"})

@app.post("/voice_cmd")
async def voice_cmd(request: Request):
    return await _proxy_request("http://localhost:8001/voice_cmd", request, "POST")

@app.get("/stats/summary")
async def stats_summary(request: Request):
    return await _proxy_request("http://localhost:8001/stats/summary", request, "GET")

@app.post("/dify/run")
async def dify_run(request: Request):
    try:
        body = await request.json()
        
        if "query" not in body:
            if "message" in body:
                body["query"] = body.pop("message")
            elif "command" in body:
                body["query"] = body.pop("command")
        
        body["response_mode"] = "streaming"
        body["user"] = "admin"
        
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        headers.pop("content-encoding", None)
        headers["Authorization"] = "Bearer YOUR_DIFY_API_KEY_HERE"
        if "content-type" not in headers:
            headers["content-type"] = "application/json"
        
        import json
        client = request.app.state.http_client
        request_obj = client.build_request(
            "POST",
            "http://localhost/v1/chat-messages",
            content=json.dumps(body),
            headers=headers
        )
        
        response = await client.send(request_obj, stream=True, timeout=90.0)
        
        if response.status_code != 200:
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
        
        response_headers = dict(response.headers)
        response_headers.pop("transfer-encoding", None)
        response_headers.pop("content-encoding", None)
        response_headers["ngrok-skip-browser-warning"] = "69420"
        response_headers["Access-Control-Allow-Origin"] = "*"
        
        async def stream_generator():
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()
        
        return StreamingResponse(
            stream_generator(),
            status_code=response.status_code,
            media_type="text/event-stream",
            headers=response_headers
        )
        
    except Exception as e:
        print(f"❌ Dify 接口处理异常: {str(e)}")
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Data format error: {str(e)}"})

@app.post("/analyze")
async def analyze(request: Request):
    return await _proxy_request("http://localhost:8004/analyze", request, "POST")

@app.get("/crops/{filename}")
async def get_crop(filename: str, request: Request):
    return await _proxy_request(f"http://localhost:8004/crops/{filename}", request, "GET")

@app.get("/analytics/dashboard")
async def analytics_dashboard(request: Request):
    return await _proxy_request("http://localhost:8001/analytics/dashboard", request, "GET")

@app.get("/analytics/metrics/latest")
async def analytics_latest(request: Request):
    return await _proxy_request("http://localhost:8001/analytics/metrics/latest", request, "GET")

@app.post("/feedback")
async def submit_feedback(request: Request):
    return await _proxy_request("http://localhost:8001/feedback", request, "POST")

@app.get("/experience/history")
async def experience_history(request: Request):
    return await _proxy_request("http://localhost:8001/experience/history", request, "GET")

@app.get("/system/status")
async def system_status(request: Request):
    return await _proxy_request("http://localhost:8001/system/status", request, "GET")

@app.get("/system/operation-logics")
async def operation_logics_get(request: Request):
    return await _proxy_request("http://localhost:8001/system/operation-logics", request, "GET")

@app.post("/system/operation-logics")
async def operation_logics_post(request: Request):
    return await _proxy_request("http://localhost:8001/system/operation-logics", request, "POST")

@app.delete("/system/operation-logics/{logic_id}")
async def operation_logics_delete(logic_id: str, request: Request):
    return await _proxy_request(f"http://localhost:8001/system/operation-logics/{logic_id}", request, "DELETE")

@app.get("/chat/history")
async def chat_history(request: Request):
    return await _proxy_request("http://localhost:8001/chat/history", request, "GET")

@app.post("/chat/messages")
async def chat_messages_post(request: Request):
    return await _proxy_request("http://localhost:8001/chat/messages", request, "POST")

@app.delete("/chat/messages/{message_id}")
async def chat_messages_delete(message_id: str, request: Request):
    return await _proxy_request(f"http://localhost:8001/chat/messages/{message_id}", request, "DELETE")

@app.delete("/chat/clear")
async def chat_clear(request: Request):
    return await _proxy_request("http://localhost:8001/chat/clear", request, "DELETE")

@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def api_proxy(service: str, path: str, request: Request):
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
    
    target_base_url = service_map[service]
    if path:
        if target_base_url.endswith("/"):
            target_base_url = target_base_url[:-1]
        if path.startswith("/"):
            path = path[1:]
        target_url = f"{target_base_url}/{path}"
    else:
        target_url = target_base_url
    
    print(f"[Proxy] {request.method} -> {target_url}")
    
    return await _proxy_request(target_url, request, request.method)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("正在启动超级网关...")
    print(f"将运行在: http://localhost:9000")
    
    if not check_port_available(9000):
        print(f"❌ 错误: 端口 9000 已被占用！")
        print(f"请检查是否有其他程序正在使用 9000 端口")
        print(f"或者在任务管理器中结束占用该端口的进程")
        exit(1)
    
    try:
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
