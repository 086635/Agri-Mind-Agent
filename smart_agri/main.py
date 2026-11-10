from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware # 导入跨域中间件
import httpx
import json
import sqlite3
import os

# ... 你之前的配置代码 (MQTT, DB_PATH等) ...

app = FastAPI()

# 【关键配置 1】允许跨域请求（让你的前端在任何地方都能发指令）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"], # 允许所有方法 (GET, POST)
    allow_headers=["*"],
)

# 【关键配置 2】根目录直接返回 index.html 网页
@app.get("/", response_class=HTMLResponse)
async def get_index():
    try:
        # 读取同目录下的 index.html
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<html><body><h1>未找到 index.html</h1><p>{str(e)}</p></body></html>"

# 【关键配置 3】提供实时数据接口 (给卡片用)
@app.get("/api/current_stats")
async def get_current_stats():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT temp, humid, light, timestamp FROM sensor_history ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"status": "success", "t": row[0], "h": row[1], "l": row[2]}
        return {"status": "error", "message": "no_data"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ... 你之前的 /chat 和 /voice_cmd 接口保持不变 ...