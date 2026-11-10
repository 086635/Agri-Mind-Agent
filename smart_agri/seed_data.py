import random
import os
from datetime import datetime, timedelta
from decimal import Decimal

os.environ.setdefault("PYTHONUTF8", "1")

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from server.models import (
    Base,
    RawEnvironmentalReading,
    AgriAnalyticalMetric,
    DeviceDigitalTwinStatus,
    ESGValueRealization,
    PolicyRiskThreshold,
    AgentActionAudit,
    LogicGraftingLog,
    SystemServiceStatus,
    SystemUserProfile,
    OperationLogicRecord,
    ChatMessageRecord,
)

SYNC_URL = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:123456789@localhost:5432/agri_ai")
engine = create_engine(SYNC_URL)

BATCH_ID = "batch_smartfarm_20260601"
DEVICES = {
    "sensor_temp_01": {"type": "temperature", "name": "1号区温度传感器"},
    "sensor_humid_01": {"type": "humidity", "name": "1号区湿度传感器"},
    "sensor_light_01": {"type": "light_par", "name": "1号区光照传感器"},
    "sensor_co2_01": {"type": "co2", "name": "1号区CO2传感器"},
    "sensor_soil_01": {"type": "soil_moisture", "name": "1号区土壤湿度"},
    "pump_01": {"type": "actuator", "name": "灌溉水泵"},
    "fan_01": {"type": "actuator", "name": "通风风扇"},
    "light_led_01": {"type": "actuator", "name": "补光灯"},
}


def seed_raw_readings(session, days=7):
    print("[SEED] 写入原始传感器数据...")
    now = datetime.now()
    count = 0
    for day_offset in range(days):
        base_time = now - timedelta(days=day_offset)
        for hour in range(0, 24, 1):
            ts = base_time.replace(hour=hour, minute=random.randint(0, 59), second=0)
            for device_id, info in DEVICES.items():
                if info["type"] == "temperature":
                    val = round(Decimal(str(22 + random.uniform(-5, 12))), 2)
                elif info["type"] == "humidity":
                    val = round(Decimal(str(45 + random.uniform(-15, 35))), 2)
                elif info["type"] == "light_par":
                    if 6 <= hour <= 18:
                        val = round(Decimal(str(random.uniform(200, 1200))), 2)
                    else:
                        val = round(Decimal(str(random.uniform(0, 50))), 2)
                elif info["type"] == "co2":
                    val = round(Decimal(str(380 + random.uniform(-50, 200))), 2)
                elif info["type"] == "soil_moisture":
                    val = round(Decimal(str(30 + random.uniform(-10, 40))), 2)
                else:
                    continue
                existing = session.query(RawEnvironmentalReading).filter(
                    RawEnvironmentalReading.timestamp == ts,
                    RawEnvironmentalReading.device_id == device_id,
                ).first()
                if existing:
                    continue
                reading = RawEnvironmentalReading(
                    timestamp=ts,
                    device_id=device_id,
                    batch_id=BATCH_ID,
                    sensor_type=info["type"],
                    raw_value=val,
                    reliability_score=round(Decimal(str(random.uniform(0.9, 1.0))), 4),
                    experiment_group="CONTROL" if random.random() > 0.5 else "TREATMENT",
                )
                session.add(reading)
                count += 1
    session.commit()
    print(f"[SEED] 原始数据写入完成，共新增 {count} 条（{days} 天 x 24 小时 x 5 个传感器）")


def seed_device_twins(session):
    print("[SEED] 写入设备数字孪生数据...")
    devices_data = [
        ("pump_01", Decimal("750"), Decimal("120.5"), 320, Decimal("0.08"), 180, Decimal("0.95"), Decimal("3.2"), Decimal("0.12")),
        ("fan_01", Decimal("150"), Decimal("480.2"), 1250, Decimal("0.55"), 90, Decimal("0.92"), Decimal("1.8"), Decimal("0.05")),
        ("light_led_01", Decimal("300"), Decimal("96.8"), 680, Decimal("0.78"), 120, Decimal("0.97"), Decimal("2.1"), Decimal("0.08")),
    ]
    count = 0
    for d in devices_data:
        existing = session.query(DeviceDigitalTwinStatus).filter(
            DeviceDigitalTwinStatus.device_id == d[0]
        ).first()
        if existing:
            continue
        twin = DeviceDigitalTwinStatus(
            device_id=d[0],
            rated_power_w=d[1],
            runtime_total_hrs=d[2],
            on_off_cycles_count=d[3],
            duty_cycle_ratio_pct=d[4],
            device_thermal_slope=d[5],
            action_latency_ms=d[6],
            response_consistency_r2=d[7],
            failure_probability_pct=d[8],
        )
        session.add(twin)
        count += 1
    session.commit()
    print(f"[SEED] 设备孪生数据写入完成，共新增 {count} 台设备")


def calculate_secondary_metrics(session):
    print("[SEED] 计算二级农业指标...")
    from sqlalchemy import func
    now_date = datetime.now().date()
    for day_offset in range(7):
        record_date = now_date - timedelta(days=day_offset)
        day_start = datetime.combine(record_date, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        temp_avg = session.query(func.avg(RawEnvironmentalReading.raw_value)).filter(
            RawEnvironmentalReading.device_id == "sensor_temp_01",
            RawEnvironmentalReading.timestamp >= day_start,
            RawEnvironmentalReading.timestamp < day_end,
        ).scalar() or 0

        humid_avg = session.query(func.avg(RawEnvironmentalReading.raw_value)).filter(
            RawEnvironmentalReading.device_id == "sensor_humid_01",
            RawEnvironmentalReading.timestamp >= day_start,
            RawEnvironmentalReading.timestamp < day_end,
        ).scalar() or 0

        light_sum = session.query(func.sum(RawEnvironmentalReading.raw_value)).filter(
            RawEnvironmentalReading.device_id == "sensor_light_01",
            RawEnvironmentalReading.timestamp >= day_start,
            RawEnvironmentalReading.timestamp < day_end,
        ).scalar() or 0

        co2_avg = session.query(func.avg(RawEnvironmentalReading.raw_value)).filter(
            RawEnvironmentalReading.device_id == "sensor_co2_01",
            RawEnvironmentalReading.timestamp >= day_start,
            RawEnvironmentalReading.timestamp < day_end,
        ).scalar() or 0

        soil_avg = session.query(func.avg(RawEnvironmentalReading.raw_value)).filter(
            RawEnvironmentalReading.device_id == "sensor_soil_01",
            RawEnvironmentalReading.timestamp >= day_start,
            RawEnvironmentalReading.timestamp < day_end,
        ).scalar() or 0

        par_val = round(Decimal(str(float(light_sum) / 24)), 2) if light_sum else Decimal("0")
        dli_val = round(par_val * Decimal("0.0036") * Decimal("12"), 2)
        gdd_val = round(max(float(temp_avg or 0) - 10, 0) * 24, 2)
        gdd_val_dec = Decimal(str(gdd_val))
        temp_f = float(temp_avg or 0)
        humid_f = float(humid_avg or 0)
        vpd_raw = 0.6108 * pow(2.71828, (17.27 * temp_f / (temp_f + 237.3))) * (1 - humid_f / 100)
        vpd_val = round(Decimal(str(vpd_raw)), 4)
        carbon_rate = round(gdd_val_dec * Decimal("0.12"), 4)
        nutrient_rate = round(gdd_val_dec * Decimal("0.35"), 2)
        lue = round(min(float(dli_val) / 50 * 100, 99), 2)
        energy_idx = round(Decimal(str(lue)) / 100 * Decimal("0.92"), 4)
        r_sq = round(Decimal(str(random.uniform(0.82, 0.98))), 4)
        completion = round(Decimal(str(random.uniform(75, 99))), 2)

        metric = AgriAnalyticalMetric(
            batch_id=BATCH_ID,
            device_id="sensor_temp_01",
            strategy_id=f"strategy_auto_{day_offset}",
            record_date=record_date,
            par_val_umol=par_val,
            dli_daily_mol=dli_val,
            carbon_sink_rate_g_hr=carbon_rate,
            vpd_val_kpa=vpd_val,
            nutrient_consumption_rate_mg_hr=nutrient_rate,
            current_accumulated_gdd_c=gdd_val_dec,
            lue_score_pct=Decimal(str(lue)),
            energy_optimization_index=energy_idx,
            r_squared_val=r_sq,
            completion_rate_pct=completion,
            data_status="VALID",
        )
        existing_m = session.query(AgriAnalyticalMetric).filter(
            AgriAnalyticalMetric.batch_id == BATCH_ID,
            AgriAnalyticalMetric.record_date == record_date,
        ).first()
        if not existing_m:
            session.add(metric)

        esg = ESGValueRealization(
            batch_id=BATCH_ID,
            device_id="sensor_temp_01",
            record_date=record_date,
            biomass_carbon_sequestration_g=round(carbon_rate * Decimal("24"), 2),
            operational_carbon_footprint_g=round(Decimal(str(random.uniform(80, 200))), 2),
            net_zero_ratio=round(Decimal(str(random.uniform(0.3, 0.8))), 4),
            water_saved_liters=round(Decimal(str(random.uniform(100, 500))), 2),
            energy_efficiency_ratio=round(Decimal(str(random.uniform(0.65, 0.92))), 4),
            cost_reduction_amount_cny=round(Decimal(str(random.uniform(5, 25))), 2),
        )
        existing_e = session.query(ESGValueRealization).filter(
            ESGValueRealization.batch_id == BATCH_ID,
            ESGValueRealization.record_date == record_date,
        ).first()
        if not existing_e:
            session.add(esg)

    session.commit()
    print("[SEED] 二级指标计算完成，共 7 天的聚合数据")


def seed_policy_thresholds(session):
    print("[SEED] 写入策略风险阈值...")
    thresholds = [
        PolicyRiskThreshold(
            metric_name="温度过高预警",
            threshold_logic={"operator": "gt", "value": 35, "unit": "celsius", "action": "开启风扇"},
            priority=1,
        ),
        PolicyRiskThreshold(
            metric_name="湿度过低预警",
            threshold_logic={"operator": "lt", "value": 40, "unit": "percent", "action": "启动灌溉"},
            priority=2,
        ),
        PolicyRiskThreshold(
            metric_name="光照不足预警",
            threshold_logic={"operator": "lt", "value": 300, "unit": "umol_m2_s", "action": "开启补光"},
            priority=3,
        ),
        PolicyRiskThreshold(
            metric_name="VPD过高预警",
            threshold_logic={"operator": "gt", "value": 1.5, "unit": "kpa", "action": "增加湿度"},
            priority=1,
        ),
    ]
    count = 0
    for t in thresholds:
        existing = session.query(PolicyRiskThreshold).filter(
            PolicyRiskThreshold.metric_name == t.metric_name
        ).first()
        if existing:
            continue
        session.add(t)
        count += 1
    session.commit()
    print(f"[SEED] 策略阈值写入完成，共新增 {count} 条")


def seed_audit_logs(session):
    print("[SEED] 写入 Agent 审计日志...")
    audits = [
        AgentActionAudit(
            actor_id="qwen_agent_v1",
            action_type="DEVICE_CONTROL",
            reasoning_context="检测到温度34.5°C超过阈值，建议开启通风",
            expected_delta={"target_temp": 30},
            actual_delta={"target_temp": 29.8},
            skill_invoked="device_control_skill",
            execution_status="executed",
            is_experience_source=True,
            session_id="session_001",
        ),
        AgentActionAudit(
            actor_id="qwen_agent_v1",
            action_type="IRRIGATION_DECISION",
            reasoning_context="土壤湿度38%，低于作物最佳范围(50-70%)",
            expected_delta={"soil_moisture": 55},
            skill_invoked="irrigation_skill",
            execution_status="executed_without_feedback",
            session_id="session_002",
        ),
        AgentActionAudit(
            actor_id="qwen_agent_v1",
            action_type="LIGHT_CONTROL",
            reasoning_context="DLI值偏低，建议延长补光时长至14小时",
            expected_delta={"dli_increase": 5},
            skill_invoked="light_control_skill",
            execution_status="pending_logic_confirmation",
            session_id="session_003",
        ),
    ]
    count = 0
    for a in audits:
        existing = session.query(AgentActionAudit).filter(
            AgentActionAudit.session_id == a.session_id,
            AgentActionAudit.action_type == a.action_type,
        ).first()
        if existing:
            continue
        session.add(a)
        count += 1
    session.commit()
    print(f"[SEED] 审计日志写入完成，共新增 {count} 条")


def seed_system_service_status(session):
    """写入微服务健康状态虚拟数据"""
    print("[SEED] 写入微服务状态数据...")
    services = [
        SystemServiceStatus(
            service_name="super_gateway", service_display="超级网关",
            port=9000, latency_ms=12, status="online", status_color="#10b981",
            last_sync="刚刚",
        ),
        SystemServiceStatus(
            service_name="ai_gateway", service_display="AI大脑网关",
            port=8001, latency_ms=45, status="online", status_color="#10b981",
            last_sync="刚刚",
        ),
        SystemServiceStatus(
            service_name="vision_server", service_display="视觉推理服务",
            port=8004, latency_ms=85, status="offline", status_color="#f59e0b",
            last_sync="--",
        ),
        SystemServiceStatus(
            service_name="stm32_sim", service_display="硬件模拟器",
            port=8000, latency_ms=120, status="warning", status_color="#f59e0b",
            last_sync="5分钟前",
        ),
    ]
    count = 0
    for s in services:
        existing = session.query(SystemServiceStatus).filter(
            SystemServiceStatus.service_name == s.service_name
        ).first()
        if existing:
            continue
        session.add(s)
        count += 1
    session.commit()
    print(f"[SEED] 微服务状态写入完成，共新增 {count} 条")


def seed_user_profile(session):
    """写入用户档案虚拟数据"""
    print("[SEED] 写入用户档案数据...")
    profile = SystemUserProfile(
        user_id="default_user",
        name="李技术",
        role="管理员",
        avatar_letter="李",
        last_login_time="今天 08:30",
        last_login_device="iPhone 14",
    )
    existing = session.query(SystemUserProfile).filter(
        SystemUserProfile.user_id == "default_user"
    ).first()
    if not existing:
        session.add(profile)
        session.commit()
        print(f"[SEED] 用户档案写入完成")
    else:
        print(f"[SEED] 用户档案已存在，跳过")


def seed_operation_logics(session):
    """写入操作逻辑记录虚拟数据"""
    print("[SEED] 写入操作逻辑记录...")
    logics = [
        OperationLogicRecord(
            logic_id="logic_001",
            input_text="检测到温度34.5°C超过阈值，建议开启通风设备降温",
            operation_logic="IF temp > 35 THEN fan ON ELSE fan OFF; 持续监控至temp < 30",
            create_time="2026-06-03 14:22:10",
        ),
        OperationLogicRecord(
            logic_id="logic_002",
            input_text="土壤湿度38%偏低，需要启动灌溉系统补充水分",
            operation_logic="IF soil_moisture < 50 THEN pump ON FOR 15min; CHECK soil_moisture AFTER 30min",
            create_time="2026-06-02 09:15:33",
        ),
        OperationLogicRecord(
            logic_id="logic_003",
            input_text="光照强度不足，DLI值低于作物最佳生长范围",
            operation_logic="IF DLI < 20 THEN light_led ON 14h/day; ADJUST light_intensity TO 80%",
            create_time="2026-06-01 16:40:05",
        ),
    ]
    count = 0
    for l in logics:
        existing = session.query(OperationLogicRecord).filter(
            OperationLogicRecord.logic_id == l.logic_id
        ).first()
        if existing:
            continue
        session.add(l)
        count += 1
    session.commit()
    print(f"[SEED] 操作逻辑记录写入完成，共新增 {count} 条")


def seed_chat_messages(session):
    """写入聊天记录虚拟数据"""
    print("[SEED] 写入聊天记录数据...")
    messages = [
        ChatMessageRecord(
            message_id="msg_sys_001", role="system",
            content="10:05 AM · 系统初始化完成", session_id=None,
        ),
        ChatMessageRecord(
            message_id="msg_ai_001", role="ai",
            content="您好！我是 Agri-Sync 智能大脑。目前监控系统运行平稳。您可以直接下达设备控制指令，或询问数据分析。",
            session_id=None,
        ),
        ChatMessageRecord(
            message_id="msg_user_001", role="user",
            content="帮我查看当前大棚的温度和湿度情况", session_id="session_chat_001",
        ),
        ChatMessageRecord(
            message_id="msg_ai_002", role="ai",
            content="根据最新传感器数据：\n\n🌡️ 当前温度：26.8°C（适宜范围 20-30°C）\n💧 空气湿度：62%（适宜范围 50-70%）\n🌱 土壤湿度：55%（作物最佳范围）\n\n整体环境状态良好，所有指标均在正常范围内。建议继续保持当前的通风策略。",
            session_id="session_chat_001",
        ),
        ChatMessageRecord(
            message_id="msg_user_002", role="user",
            content="打开水泵进行灌溉", session_id="session_chat_002",
        ),
        ChatMessageRecord(
            message_id="msg_ai_002b", role="ai",
            content="已下达灌溉指令！\n\n🚰 设备控制: 灌溉水泵 [ON]\n✓ 指令已通过MQTT发送至执行端\n⏱️ 预计灌溉时长：15分钟\n\n建议：灌溉完成后我会自动通知你检查土壤湿度变化。",
            session_id="session_chat_002",
        ),
    ]
    count = 0
    for m in messages:
        existing = session.query(ChatMessageRecord).filter(
            ChatMessageRecord.message_id == m.message_id
        ).first()
        if existing:
            continue
        session.add(m)
        count += 1
    session.commit()
    print(f"[SEED] 聊天记录写入完成，共新增 {count} 条")


def seed_rag_knowledge():
    """向 ChromaDB farm_experience_rules 集合写入农业常识种子数据"""
    import asyncio
    from server.tools.rag_vector_store import rag_vector_store

    print("[SEED] 写入 RAG 农业常识知识...")

    knowledge_rules = [
        {
            "metric_name": "番茄生长适宜条件",
            "condition": "番茄全生育期环境管理",
            "action": "调控温光水肥",
            "value": "温度20-28°C / 湿度60-70% / 光照4万-7万lux / 土壤湿度60-80%",
            "unit": "综合",
            "reasoning": "番茄喜温喜光，白天最适温度25-28°C，夜间15-18°C有利于养分积累。空气湿度60-70%可减少病害发生，土壤湿度60-80%保证根系正常吸水。光照不足会导致徒长和落花落果，CO2浓度补充至800-1000ppm可显著增产。开花期避免高温高湿，否则影响授粉。"
        },
        {
            "metric_name": "黄瓜生长适宜条件",
            "condition": "黄瓜全生育期环境管理",
            "action": "调控温光水肥",
            "value": "温度22-30°C / 湿度70-85% / 光照3万-5万lux / 土壤湿度70-90%",
            "unit": "综合",
            "reasoning": "黄瓜喜温喜湿，对低温敏感，低于10°C生长停滞。白天适温25-30°C，夜间15-18°C。黄瓜需水量大，土壤湿度需保持在70-90%，空气湿度70-85%有利于茎叶生长。光照过强会导致叶片灼伤，适度遮阴有利于夏季生产。结瓜期需肥量大，注意钾肥补充。"
        },
        {
            "metric_name": "辣椒生长适宜条件",
            "condition": "辣椒全生育期环境管理",
            "action": "调控温光水肥",
            "value": "温度20-30°C / 湿度60-75% / 光照3万-5万lux / 土壤湿度60-80%",
            "unit": "综合",
            "reasoning": "辣椒喜温但不耐高温，超过35°C花器发育异常导致落花。白天适温25-28°C，夜间18-20°C。辣椒对干旱有一定耐受力，但土壤湿度60-80%产量最佳。空气湿度过高易引发疫病和灰霉病。辣椒需磷钾肥较多，结果期追施钾肥可提升果实品质和辣度。"
        },
        {
            "metric_name": "白菜生长适宜条件",
            "condition": "白菜全生育期环境管理",
            "action": "调控温光水肥",
            "value": "温度15-22°C / 湿度70-85% / 光照2万-4万lux / 土壤湿度70-90%",
            "unit": "综合",
            "reasoning": "白菜属半耐寒蔬菜，喜冷凉气候，生长适温15-22°C，超过25°C品质下降易感病。结球期昼夜温差大有利于包心紧实。白菜需水量大，特别是莲座期和结球期需保持土壤湿润。氮肥需求量大但不可过量，否则硝酸盐积累超标。注意轮作防根肿病。"
        },
        {
            "metric_name": "病虫害防治基础知识",
            "condition": "温室大棚常见病虫害综合防治",
            "action": "预防为主综合防治",
            "value": "温度<28°C / 湿度<75% / 通风良好",
            "unit": "综合",
            "reasoning": "温室大棚高温高湿是病虫害高发的根本原因。白粉虱在25-30°C活跃繁殖，蚜虫在干旱条件下暴发，红蜘蛛偏好高温低湿环境。灰霉病在湿度>85%且温度18-23°C时最易发生，霜霉病在叶面结露条件下侵染。防治策略：控制温湿度环境、合理密植保证通风、定期巡查早期发现、生物防治优先、化学防治交替用药避免抗药性。"
        },
        {
            "metric_name": "环境参数标准范围",
            "condition": "温室大棚通用环境参数监控",
            "action": "实时监测与预警",
            "value": "温度15-30°C / 湿度50-80% / 光照2万-7万lux / 土壤湿度50-80% / CO2 400-1000ppm / VPD 0.8-1.2kPa",
            "unit": "综合",
            "reasoning": "温室环境参数需综合调控：温度15-30°C为多数蔬菜适宜区间，超限需启动通风或加温；空气湿度50-80%低于50%影响蒸腾，高于80%易发真菌病害；光照2万-7万lux满足大部分果菜类需求，不足时补光，过强时遮阳；土壤湿度50-80%保证根系正常呼吸和吸水；CO2浓度白天补充至800-1000ppm可增产20-30%；VPD值0.8-1.2kPa为蒸腾作用最佳区间，过高导致萎蔫，过低影响养分运输。"
        },
    ]

    async def _seed():
        count = 0
        for rule in knowledge_rules:
            try:
                await rag_vector_store.add_rule(
                    quantized_logic=rule,
                    metadata={"source": "seed_knowledge", "is_active": True}
                )
                count += 1
            except Exception as e:
                print(f"[SEED] RAG 写入失败 ({rule['metric_name']}): {e}")
        return count

    count = asyncio.run(_seed())
    print(f"[SEED] RAG 农业常识写入完成，共新增 {count} 条")


if __name__ == "__main__":
    with Session(engine) as session:
        seed_raw_readings(session, days=7)
        seed_device_twins(session)
        calculate_secondary_metrics(session)
        seed_policy_thresholds(session)
        seed_audit_logs(session)
        # 系统设置相关虚拟数据
        seed_system_service_status(session)
        seed_user_profile(session)
        seed_operation_logics(session)
        # 聊天记录虚拟数据
        seed_chat_messages(session)
    # RAG 向量库种子数据
    seed_rag_knowledge()
    print("\n========================================")
    print("  全部种子数据写入完成！")
    print("  - 原始传感器数据：~840 条")
    print("  - 设备数字孪生：3 台")
    print("  - 二级分析指标：7 天")
    print("  - ESG 数据：7 天")
    print("  - 策略风险阈值：4 条")
    print("  - Agent 审计日志：3 条")
    print("  - 微服务状态：4 条（新增）")
    print("  - 用户档案：1 条（新增）")
    print("  - 操作逻辑记录：3 条（新增）")
    print("  - 聊天记录：6 条（新增）")
    print("  - RAG 农业常识：6 条（新增）")
    print("========================================")
