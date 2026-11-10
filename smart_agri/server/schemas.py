from pydantic import BaseModel, Field

class TelemetryPayload(BaseModel):
    device_id: str = Field(..., description="设备唯一标识", max_length=64)
    sensor_type: str = Field(..., description="传感器类型 (如 air_temp, soil_npk)", max_length=32)
    value: float = Field(..., description="传感器原始读数")