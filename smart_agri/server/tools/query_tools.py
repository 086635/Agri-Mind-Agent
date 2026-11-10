import asyncio
from datetime import datetime

async def get_latest_telemetry() -> dict:
    """获取最新的传感器数据
    
    Returns:
        包含最新传感器数据的字典，包括 timestamp
    """
    # 模拟数据库操作延迟
    await asyncio.sleep(0.05)
    
    try:
        # 尝试导入数据库模块
        from database import SessionLocal
        from models import RawEnvironmentalReading
        
        db = SessionLocal()
        try:
            # 查询最新的传感器数据
            latest_reading = db.query(RawEnvironmentalReading).order_by(
                RawEnvironmentalReading.timestamp.desc()
            ).first()
            
            if latest_reading:
                # 构建返回数据，包含 timestamp
                sensor_data = {
                    "device_id": latest_reading.device_id,
                    "sensor_type": latest_reading.sensor_type,
                    "raw_value": latest_reading.raw_value,
                    "timestamp": latest_reading.timestamp.isoformat() if latest_reading.timestamp else None
                }
                return sensor_data
            else:
                # 如果没有数据，返回模拟数据
                return get_mock_sensor_data()
        except Exception as e:
            print(f"获取传感器数据失败: {e}")
            # 返回模拟数据
            return get_mock_sensor_data()
        finally:
            db.close()
    except ImportError:
        # 如果缺少数据库依赖，返回模拟数据
        print("数据库依赖缺失，返回模拟传感器数据")
        return get_mock_sensor_data()

def get_mock_sensor_data() -> dict:
    """获取模拟传感器数据
    
    Returns:
        包含模拟传感器数据的字典
    """
    return {
        "device_id": "sensor_001",
        "sensor_type": "temperature",
        "raw_value": 25.5,
        "timestamp": datetime.now().isoformat()
    }