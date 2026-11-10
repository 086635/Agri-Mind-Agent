import requests
import asyncio

# 城市代码映射
def get_city_code(city_name: str) -> str:
    """根据城市名称获取城市代码"""
    city_code_map = {
        "杭州": "101210101",
        "北京": "101010100",
        "上海": "101020100",
        "广州": "101280101",
        "深圳": "101280601"
    }
    return city_code_map.get(city_name, city_name)  # 如果是代码则直接返回

async def get_weather_info(city_code: str) -> dict:
    """获取天气信息
    
    Args:
        city_code: 城市代码或城市名称
    
    Returns:
        包含天气信息的字典
    """
    # 自动处理城市名称
    if not city_code.isdigit():
        city_code = get_city_code(city_code)
    
    # 模拟网络延迟
    await asyncio.sleep(0.1)
    
    # 预留真实 API URL 位置
    # API_URL = f"https://api.weather.com/v1/{city_code}"
    # response = await requests.get(API_URL)
    # return response.json()
    
    # 使用 Mock 数据
    mock_weather_data = {
        "city": "杭州",
        "city_code": city_code,
        "temperature": 25,
        "humidity": 65,
        "wind_speed": 12,
        "wind_direction": "东南风",
        "condition": "晴",
        "rain_probability": 10,  # 降雨概率
        "extreme_weather_alert": False,  # 极端天气预警
        "update_time": "2026-04-01 12:00:00"
    }
    
    return mock_weather_data