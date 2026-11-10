from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import json
import re
import paho.mqtt.client as mqtt
import asyncio
import sqlite3
import os
from contextlib import asynccontextmanager
from intent_processor import SmartFarmProcessor

from pyngrok import ngrok
from dotenv import load_dotenv
from sqlalchemy import create_engine, func as sa_func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from decimal import Decimal

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "SQL", "farm_data.db")

class CommandRequest(BaseModel):
    command: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_mqtt()
    
    print("\n⚠️  暂时禁用 ngrok 隧道，仅使用本地服务\n")
    
    print("[AI Gateway] 启动完成！")
    print(f"[AI Gateway] 本地访问地址: http://localhost:8001")
    print(f"[AI Gateway] 语音指令接口: http://localhost:8001/voice_cmd")
    print(f"[AI Gateway] 聊天接口: http://localhost:8001/chat")
    print(f"[AI Gateway] 分析接口: http://localhost:8001/stats/summary")
    print(f"[AI Gateway] 健康检查接口: http://localhost:8001/ping")
    
    yield
    
    print("[AI Gateway] 正在关闭...")
    mqtt_client.loop_stop()
    print("[AI Gateway] 已关闭 MQTT 客户端")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:8001", "http://localhost:9000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883

QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

target_map = {
    "水泵": "pump", "泵": "pump",
    "风扇": "fan",
    "灯": "light", "补光灯": "light"
}

mqtt_client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] 连接成功")
    else:
        print(f"[MQTT] 连接失败，错误码: {rc}")

def on_disconnect(client, userdata, rc):
    print(f"[MQTT] 连接断开，错误码: {rc}")
    print("[MQTT] 正在尝试重连...")

async def init_mqtt():
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.reconnect_delay_set(min_delay=1, max_delay=120)
    
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        print("[MQTT] 客户端初始化成功，开始监听连接状态")
    except Exception as e:
        print(f"[MQTT] 连接超时或失败: {e}")
        print("[MQTT] 将在后台继续尝试重连")
        mqtt_client.loop_start()

async def call_qwen_llm(prompt: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {QWEN_API_KEY}"
    }

    payload = {
        "model": "qwen-plus",
        "messages": [
            {
                "role": "system",
                "content": "你是一个智慧农业助手，请根据用户指令和农场状态给出建议和控制指令。控制指令必须包含JSON格式的payload，target字段必须是pump/fan/light中的一个。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(QWEN_API_URL, json=payload, headers=headers, timeout=30.0)

            if response.status_code != 200:
                print(f"[AI Error] 状态码: {response.status_code}, 内容: {response.text}")
                return None

            result = response.json()
            ai_content = result.get('choices', [{}])[0].get('message', {}).get('content', '')

            if not ai_content:
                print("[AI Error] AI 返回内容为空")
                return None

            print(f"[AI] 收到 AI 响应: {ai_content[:50]}...")
            return ai_content
    except httpx.TimeoutException:
        print("[AI Error] 连接阿里云超时")
        return None
    except httpx.ConnectError:
        print("[AI Error] 无法连接到阿里云API")
        return None
    except Exception as e:
        print(f"[AI Error] 调用失败: {e}")
        return None

@app.post("/voice_cmd")
async def voice_command(request: CommandRequest):
    command = request.command
    try:
        context = await get_latest_farm_context()
        prompt = f"{context}\n\n用户指令：{command}\n\n请根据上述农场状态，给出相应的控制指令，并结合知识库给出有关回答。请在回复中包含 JSON 格式的控制指令，例如：\n{{\"payload\": {{\"target\": \"fan\", \"cmd\": \"1\"}}}}\n\nResponse must contain a JSON block. Target must be one of: [pump, fan, light]. Do not use Chinese for target field."
        
        ai_raw_text = await call_qwen_llm(prompt)

        if not ai_raw_text:
            print("[WARN] AI 返回内容为空，启用兜底逻辑")
            return {"status": "error", "error": "AI 服务离线或返回为空"}
        
        result = await processor.process_ai_response(ai_raw_text)
        
        if result["type"] == "control" and result["payload"]:
            payload = result["payload"]
            target = payload.get("target", "pump")
            
            final_target = target_map.get(target, target)
            
            ai_cmd = str(payload.get("cmd", "2"))
            if any(word in command for word in ["关", "停", "闭", "off", "stop"]):
                final_cmd = "2"
            elif any(word in command for word in ["开", "启", "闷", "热", "湿", "启动"]) or ai_cmd == "1":
                final_cmd = "1"
            else:
                final_cmd = ai_cmd
            
            final_payload = {
                "cmd": final_cmd,
                "target": final_target
            }
            
            target_topic = "farm/HD_STUDENT_001/control"
            
            print(f"[DEBUG] 指令: {command}")
            print(f"[DEBUG] 目标 Topic: {target_topic}")
            print(f"[DEBUG] 下发 Payload: {final_payload}")

            if mqtt_client.is_connected():
                mqtt_client.publish(target_topic, json.dumps(final_payload))
                return {"status": "success", "topic": target_topic, "dispatched": final_payload}
            else:
                return {"status": "mqtt_error", "error": "MQTT未连接"}
        else:
            return {"status": "error", "error": "未解析到控制指令"}

    except Exception as e:
        print(f"[Error] 处理失败: {e}")
        return {"status": "error", "error": str(e)}

@app.get("/stats/summary")
async def get_sensor_summary():
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT temp, humid, light, timestamp FROM sensor_history ORDER BY id DESC LIMIT 10")
                rows = await cursor.fetchall()
        
        return {
            "status": "success",
            "data": {
                "temps": [r[0] for r in rows][::-1],
                "times": [r[3][-8:] for r in rows][::-1]
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

processor = SmartFarmProcessor()

async def get_latest_farm_context() -> str:
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT temp, humid, light, soil_status, timestamp FROM sensor_history ORDER BY id DESC LIMIT 1")
                row = await cursor.fetchone()
        
        if row:
            temp, humid, light, soil_status, timestamp = row
            context = f"农场实时状态:\n"
            context += f"温度: {temp}℃\n"
            context += f"湿度: {humid}%\n"
            context += f"光照: {light} lux\n"
            context += f"土壤状态: {'湿润' if soil_status == 1 else '干燥'}\n"
            context += f"更新时间: {timestamp}\n"
            return context
        else:
            return "暂无农场状态数据"
    except Exception as e:
        print(f"[Error] 获取上下文失败: {e}")
        return "获取农场状态失败"

def parse_ai_response(ai_raw_text: str) -> dict:
    analysis_match = re.search(r'【自然语言回复】([\s\S]*?)【控制指令】', ai_raw_text, re.S)
    if not analysis_match:
        analysis_match = re.search(r'【分析建议】([\s\S]*?)【控制指令】', ai_raw_text, re.S)
    analysis = analysis_match.group(1).strip() if analysis_match else ""
    
    control_match = re.search(r'【控制指令】([\s\S]*)$', ai_raw_text, re.S)
    control_text = control_match.group(1).strip() if control_match else ""
    
    payload = None
    if control_text and control_text != "None":
        json_match = re.search(r'```json[\s\S]*?\{[\s\S]*?\}[\s\S]*?```', control_text, re.S)
        if not json_match:
            json_match = re.search(r'\{[\s\S]*\}', control_text, re.S)
        
        if json_match:
            json_str = json_match.group()
            json_str = re.sub(r'```json|```', '', json_str).strip()
            try:
                data = json.loads(json_str)
                payload = data.get("payload", None)
            except json.JSONDecodeError:
                print("[Parser] JSON 解析失败")
    
    return {
        "analysis": analysis,
        "payload": payload
    }

@app.post("/chat")
async def chat(request: CommandRequest):
    print(f"\n{'='*20} 收到新指令 {'='*20}")
    
    command = request.command
    print(f"[RECV] 用户输入: {command}")

    try:
        context = await get_latest_farm_context()
        print(f"[DATA] 注入实时上下文 (Len: {len(context)})")

        print(f"[AI] 构建增强 Prompt...")
        
        prompt = f"【环境背景】\n{context}\n\n【核心任务】\n{command}\n\n请先查阅农艺知识库，给出针对性建议，再判断是否需要操作设备。"
        prompt += "\n\n请严格按预设提示词规约执行决策并输出。"

        print(f"[AI] 正在请求通义千问...")
        ai_raw_text = await call_qwen_llm(prompt)
        
        if not ai_raw_text:
            print("[WARN] AI 返回内容为空，启用兜底逻辑")
            return {"status": "success", "message": "抱歉，由于网络波动，我暂时没能理解您的意思。", "type": "qa", "data": None}

        print(f"[AI] 原始回复内容: \n{'-'*10}\n{ai_raw_text}\n{'-'*10}")

        print(f"[PROC] 精细化解析 AI 回复...")
        parse_result = parse_ai_response(ai_raw_text)
        analysis = parse_result["analysis"]
        payload = parse_result["payload"]
        print(f"[PROC] 解析完成 | 分析建议: {analysis[:30]}... | 是否含指令: {payload is not None}")

        execution_log = ""

        if payload:
            target = payload.get("target")
            cmd = payload.get("cmd")
            
            if target and cmd:
                standard_target = target_map.get(target, target)
                
                device_name = processor._device_mapping(standard_target)
                action = "开启" if str(cmd) == "1" else "关闭"
                
                final_payload = {"cmd": str(cmd), "target": standard_target}
                
                target_topic = "farm/HD_STUDENT_001/control"
                
                print(f"[MQTT] 执行控制逻辑，下发至: {standard_target}")
                print(f"[MQTT] 目标 Topic: {target_topic}")
                print(f"[MQTT] 下发 Payload: {final_payload}")
                
                execution_log = f"\n\n--- 硬件执行日志 ---\n系统操作：🌱 正在{action}{device_name}\n执行状态：指令已通过 MQTT 下发"
                
                if mqtt_client.is_connected():
                    mqtt_client.publish(target_topic, json.dumps(final_payload))
                else:
                    print("[WARN] MQTT未连接，无法执行控制指令")
                    execution_log = f"\n\n--- 硬件执行日志 ---\n系统操作：🌱 正在{action}{device_name}\n执行状态：MQTT未连接，无法下发指令"

        response_message = analysis
        response_message = re.sub(r'```json[\s\S]*?```', '', response_message).strip()
        
        if not response_message:
            print("[PROC] 结构化解析未提取到文本，使用AI原始回复")
            response_message = ai_raw_text
            response_message = re.sub(r'```json[\s\S]*?```', '', response_message).strip()
            response_message = re.sub(r'【执行指令】[\s\S]*$', '', response_message).strip()
        
        if execution_log:
            response_message += execution_log
        
        if not response_message:
            response_message = "抱歉，我无法理解您的指令"
        
        print(f"[DONE] 接口处理完毕，返回前端内容预览: {response_message[:20]}...")

        session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        _write_audit_log(
            command=command,
            ai_raw_text=ai_raw_text,
            response_message=response_message,
            payload=payload,
            execution_log=execution_log,
            session_id=session_id,
        )

        return {
            "status": "success",
            "message": response_message,
            "type": "control" if payload else "qa",
            "data": payload,
            "session_id": session_id
        }

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"[CRITICAL] 链路崩溃: {error_msg}")
        return {"status": "error", "message": "系统正在分析农场数据，请稍后再试", "type": "error", "data": None}

@app.get("/analytics/dashboard")
async def get_analytics_dashboard(days: int = 7):
    try:
        sync_url = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai")
        engine = create_engine(sync_url)
        from server.models import (
            RawEnvironmentalReading, AgriAnalyticalMetric,
            DeviceDigitalTwinStatus, ESGValueRealization,
            AgentActionAudit,
        )
        with Session(engine) as session:
            now_date = datetime.now().date()
            day_start = datetime.combine(now_date - timedelta(days=days), datetime.min.time())

            raw_latest = session.query(
                RawEnvironmentalReading.device_id,
                RawEnvironmentalReading.sensor_type,
                sa_func.max(RawEnvironmentalReading.timestamp).label("latest_ts"),
                sa_func.avg(RawEnvironmentalReading.raw_value).label("avg_val"),
            ).filter(RawEnvironmentalReading.timestamp >= day_start).group_by(
                RawEnvironmentalReading.device_id, RawEnvironmentalReading.sensor_type
            ).all()

            sensor_summary = {}
            for r in raw_latest:
                key = r.sensor_type
                if key not in sensor_summary:
                    sensor_summary[key] = []
                sensor_summary[key].append({
                    "device": r.device_id,
                    "latest": str(r.latest_ts) if r.latest_ts else None,
                    "avg": round(float(r.avg_val), 2) if r.avg_val else None,
                })

            metrics = session.query(AgriAnalyticalMetric).filter(
                AgriAnalyticalMetric.record_date >= now_date - timedelta(days=days)
            ).order_by(AgriAnalyticalMetric.record_date.desc()).all()

            metrics_list = []
            for m in metrics:
                metrics_list.append({
                    "date": str(m.record_date),
                    "par": float(m.par_val_umol) if m.par_val_umol else None,
                    "dli": float(m.dli_daily_mol) if m.dli_daily_mol else None,
                    "gdd": float(m.current_accumulated_gdd_c) if m.current_accumulated_gdd_c else None,
                    "vpd": float(m.vpd_val_kpa) if m.vpd_val_kpa else None,
                    "carbon_rate": float(m.carbon_sink_rate_g_hr) if m.carbon_sink_rate_g_hr else None,
                    "lue": float(m.lue_score_pct) if m.lue_score_pct else None,
                    "energy_idx": float(m.energy_optimization_index) if m.energy_optimization_index else None,
                    "completion": float(m.completion_rate_pct) if m.completion_rate_pct else None,
                })

            devices = session.query(DeviceDigitalTwinStatus).all()
            device_list = []
            for d in devices:
                device_list.append({
                    "device_id": d.device_id,
                    "power_w": float(d.rated_power_w) if d.rated_power_w else None,
                    "runtime_hrs": float(d.runtime_total_hrs) if d.runtime_total_hrs else None,
                    "cycles": d.on_off_cycles_count,
                    "duty_cycle": float(d.duty_cycle_ratio_pct) if d.duty_cycle_ratio_pct else None,
                    "failure_prob": float(d.failure_probability_pct) if d.failure_probability_pct else None,
                    "r2": float(d.response_consistency_r2) if d.response_consistency_r2 else None,
                })

            esg = session.query(ESGValueRealization).filter(
                ESGValueRealization.record_date >= now_date - timedelta(days=days)
            ).order_by(ESGValueRealization.record_date.desc()).limit(7).all()

            esg_list = []
            for e in esg:
                esg_list.append({
                    "date": str(e.record_date),
                    "carbon_seq": float(e.biomass_carbon_sequestration_g) if e.biomass_carbon_sequestration_g else None,
                    "carbon_footprint": float(e.operational_carbon_footprint_g) if e.operational_carbon_footprint_g else None,
                    "net_zero": float(e.net_zero_ratio) if e.net_zero_ratio else None,
                    "water_saved": float(e.water_saved_liters) if e.water_saved_liters else None,
                    "energy_eff": float(e.energy_efficiency_ratio) if e.energy_efficiency_ratio else None,
                    "cost_save": float(e.cost_reduction_amount_cny) if e.cost_reduction_amount_cny else None,
                })

            recent_actions = session.query(AgentActionAudit).order_by(
                AgentActionAudit.created_at.desc()
            ).limit(10).all()

            actions_list = []
            for a in recent_actions:
                actions_list.append({
                    "actor": a.actor_id,
                    "action": a.action_type,
                    "reason": a.reasoning_context[:100] if a.reasoning_context else None,
                    "status": a.status.value if a.status else None,
                    "time": str(a.created_at) if a.created_at else None,
                })

        return {
            "status": "success",
            "data": {
                "sensor_summary": sensor_summary,
                "metrics_7day": metrics_list,
                "devices": device_list,
                "esg": esg_list,
                "recent_actions": actions_list,
                "generated_at": datetime.now().isoformat(),
            }
        }
    except Exception as e:
        print(f"[ANALYTICS] Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/analytics/metrics/latest")
async def get_latest_metrics():
    try:
        sync_url = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai")
        engine = create_engine(sync_url)
        from server.models import AgriAnalyticalMetric, RawEnvironmentalReading
        from sqlalchemy import func as sa_func
        with Session(engine) as s:
            latest_metric = s.query(AgriAnalyticalMetric).order_by(
                AgriAnalyticalMetric.record_date.desc()
            ).first()
            temp_avg = s.query(sa_func.avg(RawEnvironmentalReading.raw_value)).filter(
                RawEnvironmentalReading.device_id == "sensor_temp_01",
                RawEnvironmentalReading.timestamp >= datetime.now() - timedelta(hours=6),
            ).scalar() or 0
            humid_avg = s.query(sa_func.avg(RawEnvironmentalReading.raw_value)).filter(
                RawEnvironmentalReading.device_id == "sensor_humid_01",
                RawEnvironmentalReading.timestamp >= datetime.now() - timedelta(hours=6),
            ).scalar() or 0

        context_text = f"当前农场状态："
        if temp_avg:
            context_text += f"平均温度{float(temp_avg):.1f}°C，"
        if humid_avg:
            context_text += f"平均湿度{float(humid_avg):.1f}%，"
        if latest_metric:
            context_text += f"GDD累计{float(latest_metric.current_accumulated_gdd_c):.1f}°C·天，"
            context_text += f"VPD{float(latest_metric.vpd_val_kpa):.2f}kPa，"
            context_text += f"LUE{float(latest_metric.lue_score_pct):.1f}%，"
            context_text += f"碳汇速率{float(latest_metric.carbon_sink_rate_g_hr):.3f}g/hr"

        return {"status": "success", "context": context_text}
    except Exception as e:
        return {"status": "error", "context": "暂无数据", "message": str(e)}

def _write_audit_log(command, ai_raw_text, response_message, payload=None, execution_log="", action_type="CHAT", session_id=None):
    try:
        if session_id is None:
            session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        sync_url = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai")
        engine = create_engine(sync_url)
        from server.models import AgentActionAudit
        from sqlalchemy.orm import Session as Sess
        with Sess(engine) as s:
            audit = AgentActionAudit(
                actor_id="qwen_agent_v1",
                action_type=action_type,
                reasoning_context=command,
                expected_delta=payload if payload else None,
                actual_delta=None,
                skill_invoked="device_control_skill" if payload else "qa_skill",
                execution_status="executed" if payload else "executed_without_feedback",
                is_experience_source=True,
                session_id=session_id,
                env_snapshot_ref={"ai_response": (ai_raw_text or "")[:500]},
            )
            s.add(audit)
            s.commit()
            print(f"[AUDIT] 操作已记录到数据库: {action_type}")
    except Exception as e:
        print(f"[AUDIT] 写入失败（不影响主流程）: {e}")

@app.post("/feedback")
async def submit_feedback(request: Request):
    try:
        body = await request.json()
        session_id = body.get("session_id")
        feedback_type = body.get("feedback_type", "positive")
        comment = body.get("comment", "")
        matched_logic_id = body.get("matched_logic_id")

        sync_url = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai")
        engine = create_engine(sync_url)
        from server.models import LogicGraftingLog, AgentActionAudit
        from sqlalchemy.orm import Session as Sess

        with Sess(engine) as s:
            graft = LogicGraftingLog(
                session_id=session_id or f"manual_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                feedback_type=feedback_type,
                selected_logic_id=int(matched_logic_id) if matched_logic_id else None,
                new_reasoning=comment,
                confidence_score=Decimal(str(0.9)) if feedback_type == "positive" else Decimal(str(0.3)),
            )
            s.add(graft)

            if session_id:
                audit = s.query(AgentActionAudit).filter(
                    AgentActionAudit.session_id == session_id
                ).first()
                if audit:
                    audit.user_feedback = {"type": feedback_type, "comment": comment}
                    audit.is_experience_source = True

            s.commit()

        return {"status": "success", "message": "反馈已记录"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/experience/history")
async def get_experience_history(limit: int = 20):
    try:
        sync_url = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai")
        engine = create_engine(sync_url)
        from server.models import AgentActionAudit, LogicGraftingLog, ChatMessageRecord
        from sqlalchemy.orm import Session as Sess

        with Sess(engine) as s:
            actions = s.query(AgentActionAudit).order_by(
                AgentActionAudit.created_at.desc()
            ).limit(limit).all()

            history = []
            for a in actions:
                history.append({
                    "session_id": a.session_id,
                    "action": a.action_type,
                    "reason": (a.reasoning_context or "")[:100],
                    "status": a.status.value if a.status else None,
                    "skill": a.skill_invoked,
                    "has_feedback": a.user_feedback is not None,
                    "feedback": a.user_feedback,
                    "time": str(a.created_at) if a.created_at else None,
                })

            grafts = s.query(LogicGraftingLog).order_by(
                LogicGraftingLog.created_at.desc()
            ).limit(limit).all()

            graft_list = []
            for g in grafts:
                graft_list.append({
                    "session_id": g.session_id,
                    "feedback_type": g.feedback_type,
                    "reasoning": (g.new_reasoning or "")[:200],
                    "confidence": float(g.confidence_score) if g.confidence_score else None,
                    "time": str(g.created_at) if g.created_at else None,
                })

            # 查询聊天记录（来自AI协作界面的真实对话）
            chat_msgs = s.query(ChatMessageRecord).order_by(
                ChatMessageRecord.created_at.desc()
            ).limit(limit).all()

            chat_msg_list = []
            for cm in chat_msgs:
                chat_msg_list.append({
                    "message_id": cm.message_id,
                    "role": cm.role,  # 'user' 或 'assistant'
                    "content": cm.content[:200],  # 截断过长内容
                    "session_id": cm.session_id,
                    "chat_mode": cm.chat_mode or "expert",  # 'expert'农艺 / 'device'设备
                    "feedback": cm.feedback,
                    "time": str(cm.created_at) if cm.created_at else None,
                })

        return {
            "status": "success",
            "data": {
                "actions": history,
                "feedback_log": graft_list,
                "chat_messages": chat_msg_list,
                "total_actions": len(history),
                "total_feedback": len(graft_list),
                "total_chat_messages": len(chat_msg_list),
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ==================== 系统设置相关API ====================

@app.get("/system/status")
async def get_system_status():
    """返回微服务状态 + 用户档案 + 系统健康度"""
    try:
        sync_url = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai")
        engine = create_engine(sync_url)
        from server.models import SystemServiceStatus, SystemUserProfile
        from sqlalchemy.orm import Session as Sess

        with Sess(engine) as s:
            services = s.query(SystemServiceStatus).all()
            svc_list = []
            online_count = 0
            total_latency = 0
            for svc in services:
                svc_list.append({
                    "service_name": svc.service_name,
                    "service_display": svc.service_display,
                    "port": svc.port,
                    "latency_ms": svc.latency_ms,
                    "status": svc.status,
                    "status_color": svc.status_color,
                    "last_sync": svc.last_sync,
                })
                if svc.status == "online":
                    online_count += 1
                total_latency += svc.latency_ms or 0

            user = s.query(SystemUserProfile).filter(
                SystemUserProfile.user_id == "default_user"
            ).first()

        health_percent = round(online_count / max(len(svc_list), 1) * 100) if svc_list else 98
        avg_latency = round(total_latency / max(len(svc_list), 1))

        return {
            "status": "success",
            "data": {
                "services": svc_list,
                "user_profile": {
                    "name": user.name if user else "李技术",
                    "role": user.role if user else "管理员",
                    "avatar_letter": user.avatar_letter if user else "李",
                    "last_login_time": user.last_login_time if user else "今天 08:30",
                    "last_login_device": user.last_login_device if user else "iPhone 14",
                } if user else None,
                "health_percent": health_percent,
                "avg_latency_ms": avg_latency,
                "online_count": online_count,
                "total_services": len(svc_list),
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/system/operation-logics")
async def get_operation_logics():
    """获取操作逻辑记录列表"""
    try:
        sync_url = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai")
        engine = create_engine(sync_url)
        from server.models import OperationLogicRecord
        from sqlalchemy.orm import Session as Sess

        with Sess(engine) as s:
            records = s.query(OperationLogicRecord).order_by(
                OperationLogicRecord.created_at.desc()
            ).all()

            logic_list = []
            for r in records:
                logic_list.append({
                    "id": r.logic_id,
                    "inputText": r.input_text,
                    "operationLogic": r.operation_logic or "",
                    "createTime": r.create_time or (str(r.created_at)[:19] if r.created_at else ""),
                })

        return {"status": "success", "data": logic_list}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/system/operation-logics")
async def create_operation_logic(request: Request):
    """新增操作逻辑记录"""
    try:
        body = await request.json()
        input_text = body.get("input_text", "")
        operation_logic = body.get("operation_logic", "")

        if not input_text:
            return {"status": "error", "message": "input_text 不能为空"}

        import uuid
        logic_id = f"logic_{uuid.uuid4().hex[:8]}"
        create_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sync_url = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai")
        engine = create_engine(sync_url)
        from server.models import OperationLogicRecord
        from sqlalchemy.orm import Session as Sess

        with Sess(engine) as s:
            record = OperationLogicRecord(
                logic_id=logic_id,
                input_text=input_text,
                operation_logic=operation_logic,
                create_time=create_time,
            )
            s.add(record)
            s.commit()

        return {"status": "success", "data": {"id": logic_id, "createTime": create_time}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.delete("/system/operation-logics/{logic_id}")
async def delete_operation_logic(logic_id: str):
    """删除操作逻辑记录"""
    try:
        sync_url = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai")
        engine = create_engine(sync_url)
        from server.models import OperationLogicRecord
        from sqlalchemy.orm import Session as Sess

        with Sess(engine) as s:
            record = s.query(OperationLogicRecord).filter(
                OperationLogicRecord.logic_id == logic_id
            ).first()
            if not record:
                return {"status": "error", "message": "记录不存在"}
            s.delete(record)
            s.commit()

        return {"status": "success", "message": "已删除"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ==================== 聊天记录API ====================

@app.get("/chat/history")
async def get_chat_history(limit: int = 50):
    """获取聊天记录历史"""
    try:
        sync_url = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai")
        engine = create_engine(sync_url)
        from server.models import ChatMessageRecord
        from sqlalchemy.orm import Session as Sess

        with Sess(engine) as s:
            records = s.query(ChatMessageRecord).order_by(
                ChatMessageRecord.created_at.asc()
            ).limit(limit).all()

            msg_list = []
            for r in records:
                msg_list.append({
                    "id": r.message_id,
                    "role": r.role,
                    "content": r.content,
                    "sessionId": r.session_id,
                    "feedback": r.feedback,
                    "time": str(r.created_at)[:19] if r.created_at else "",
                })

        return {"status": "success", "data": msg_list, "total": len(msg_list)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/chat/messages")
async def save_chat_message(request: Request):
    """保存单条聊天记录（用户发送或AI回复时调用）"""
    try:
        body = await request.json()
        role = body.get("role", "")
        content = body.get("content", "")
        session_id = body.get("session_id")
        feedback = body.get("feedback")

        if not role or not content:
            return {"status": "error", "message": "role和content不能为空"}

        import uuid
        message_id = f"msg_{uuid.uuid4().hex[:12]}"

        sync_url = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai")
        engine = create_engine(sync_url)
        from server.models import ChatMessageRecord
        from sqlalchemy.orm import Session as Sess

        with Sess(engine) as s:
            record = ChatMessageRecord(
                message_id=message_id,
                role=role,
                content=content,
                session_id=session_id,
                feedback=feedback,
            )
            s.add(record)
            s.commit()

        return {"status": "success", "data": {"id": message_id}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.delete("/chat/messages/{message_id}")
async def delete_chat_message(message_id: str):
    """删除单条聊天记录"""
    try:
        sync_url = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai")
        engine = create_engine(sync_url)
        from server.models import ChatMessageRecord
        from sqlalchemy.orm import Session as Sess

        with Sess(engine) as s:
            record = s.query(ChatMessageRecord).filter(
                ChatMessageRecord.message_id == message_id
            ).first()
            if not record:
                return {"status": "error", "message": "消息不存在"}
            s.delete(record)
            s.commit()

        return {"status": "success", "message": "已删除"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.delete("/chat/clear")
async def clear_all_chat_messages():
    """清空所有聊天记录"""
    try:
        sync_url = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai")
        engine = create_engine(sync_url)
        from server.models import ChatMessageRecord
        from sqlalchemy.orm import Session as Sess

        with Sess(engine) as s:
            count = s.query(ChatMessageRecord).delete()
            s.commit()

        return {"status": "success", "message": f"已清空 {count} 条聊天记录"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/ping")
async def ping():
    return {"status": "pong"}

if __name__ == "__main__":
    try:
        import uvicorn
        import logging
        logging.basicConfig(level=logging.INFO)
        
        print("[AI Gateway] 启动中...")
        uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"[AI Gateway] 启动失败: 端口 8001 已被占用")
            print("[AI Gateway] 请检查是否有其他服务正在使用该端口")
        else:
            print(f"[AI Gateway] 启动失败: {e}")
    except Exception as e:
        print(f"[AI Gateway] 启动失败: {e}")
        import traceback
        traceback.print_exc()
