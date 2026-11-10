# Skill Tools Engine - 智慧农业算法引擎

## 项目概述

`skill_tools_engine` 是智慧农业 AI 网关系统的核心算法库，实现了完整的二级数据特征提取与量化分析能力。该库遵循 **OpenClaw 架构规范**，将一级传感器热数据（L1）转化为具有业务语义的二级分析指标（L2），为上层决策系统提供数据支撑。

### 核心价值

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Skill Tools Engine 数据处理流水线                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   L1 热数据 ──> 物理校验 ──> 特征提取 ──> 价值量化 ──> 决策支撑              │
│   (传感器)      (置信度)     (算法引擎)    (ESG指标)    (Agent执行)          │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  植物生理分析  │  设备效能诊断  │  资源效率评估  │  ESG价值核算     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 目录结构

```
skill_tools_engine/
├── calculate_plant_par_instant_umol.py          # 瞬时光合有效辐射计算
├── calculate_plant_gdd_daily_c.py               # 有效积温计算
├── calculate_plant_dli_daily_mol.py             # 日光积分计算
├── calculate_plant_lue_efficiency_score.py      # 光利用率评分
├── calculate_plant_carbon_sink_rate_g_hr.py     # 光合碳汇速率
├── calculate_plant_biomass_carbon_sequestration_g.py  # 生物质固碳量
├── calculate_plant_wue_efficiency_mg_l.py       # 水分利用效率
├── calculate_plant_net_zero_ratio.py            # 碳平衡率
├── calculate_device_stability_energy_ratio_pct.py    # 环境稳态能效比
├── calculate_device_onoff_duty_ratio_val.py     # 设备启停比
├── calculate_device_action_latency_ms.py        # 指令达标延迟
├── calculate_device_thermal_slope_fingerprint.py     # 设备热力响应指纹
├── calculate_device_energy_optimization_index.py     # 能耗优化指数
├── calculate_device_carbon_footprint_total_g.py      # 设备碳足迹
├── calculate_device_water_saved_total_l.py      # 节水实效
├── calculate_air_vpd_instant_kpa.py             # 瞬时蒸气压亏缺
├── calculate_soil_nutrient_consumption_rate_mg.py    # 土壤养分消耗率
├── compare_plant_strategy_efficiency_diff.py    # 策略效率对比
├── verify_soil_npk_cross_reliability_score.py   # 传感器交叉校验
├── carbon_footprint_demo.py                     # 碳足迹演示模块
└── test_*.py                                    # 单元测试文件
```

## 算法分类

### 一、植物生理分析模块 (Plant Physiology)

| 算法名称 | 功能描述 | 输出单位 | 数据去向 |
|---------|---------|---------|---------|
| `calculate_plant_par_instant_umol` | 将环境光照强度(Lux)转换为光合有效辐射(PAR) | μmol/(m²·s) | agri_analytical_metrics.par_val |
| `calculate_plant_gdd_daily_c` | 计算当日有效积温，预测作物采收期 | ℃·d | agri_analytical_metrics.gdd_daily |
| `calculate_plant_dli_daily_mol` | 基于PAR序列计算日光积分 | mol/(m²·d) | agri_analytical_metrics.dli_daily |
| `calculate_plant_lue_efficiency_score` | 综合评估光资源利用效率 | score | agri_analytical_metrics.lue_score |
| `calculate_plant_carbon_sink_rate_g_hr` | 基于CO2浓度下降计算光合碳汇速率 | g/hr | agri_analytical_metrics.carbon_sink_rate |
| `calculate_plant_biomass_carbon_sequestration_g` | 计算植物光合作用固定的生物质碳量 | g | esg_value_realization.biomass_carbon_sequestration_g |

### 二、设备效能诊断模块 (Device Diagnostics)

| 算法名称 | 功能描述 | 输出单位 | 数据去向 |
|---------|---------|---------|---------|
| `calculate_device_stability_energy_ratio_pct` | 评估AI控制相对于传统控制的能效节省 | % | esg_value_realization.energy_efficiency_ratio |
| `calculate_device_onoff_duty_ratio_val` | 分析设备启停频率，识别震荡风险 | ratio | device_digital_twin_status.duty_cycle_ratio |
| `calculate_device_action_latency_ms` | 计算设备指令响应延迟时间 | ms | device_digital_twin_status.action_latency_ms |
| `calculate_device_thermal_slope_fingerprint` | 提取设备热力响应指纹，预测故障概率 | slope, r², % | device_digital_twin_status |
| `calculate_device_energy_optimization_index` | 计算能耗自动优化指数 | delta/kJ | agri_analytical_metrics.energy_optimization_index |

### 三、资源效率评估模块 (Resource Efficiency)

| 算法名称 | 功能描述 | 输出单位 | 数据去向 |
|---------|---------|---------|---------|
| `calculate_plant_wue_efficiency_mg_l` | 计算每升水转化出的养分吸收量 | mg/L | esg_value_realization |
| `calculate_device_water_saved_total_l` | 对比传统灌溉与AI灌溉的节水量 | L | esg_value_realization.water_saved_liters |
| `calculate_soil_nutrient_consumption_rate_mg` | 基于NPK负斜率计算养分消耗量 | mg | agri_analytical_metrics |

### 四、ESG价值核算模块 (ESG Value)

| 算法名称 | 功能描述 | 输出单位 | 数据去向 |
|---------|---------|---------|---------|
| `calculate_device_carbon_footprint_total_g` | 将设备运行时间转化为碳排放量 | g | esg_value_realization.operational_carbon_footprint_g |
| `calculate_plant_net_zero_ratio` | 计算生物质固碳与设备碳足迹的比值 | ratio | esg_value_realization.net_zero_ratio |

### 五、环境生理分析模块 (Environmental Physiology)

| 算法名称 | 功能描述 | 输出单位 | 数据去向 |
|---------|---------|---------|---------|
| `calculate_air_vpd_instant_kpa` | 基于温湿度计算蒸气压亏缺 | kPa | agri_analytical_metrics |

### 六、实验决策分析模块 (A/B Testing)

| 算法名称 | 功能描述 | 输出字段 |
|---------|---------|---------|
| `compare_plant_strategy_efficiency_diff` | 对比不同策略的生长效率差异 | winner_strategy_id, gain_pct |

### 七、传感器诊断模块 (Sensor Diagnostics)

| 算法名称 | 功能描述 | 输出 |
|---------|---------|------|
| `verify_soil_npk_cross_reliability_score` | 通过EC与NPK物理关联性进行交叉校验 | reliability_score (0.0-1.0) |

## 核心算法详解

### 1. 光合有效辐射 (PAR) 计算

```python
from calculate_plant_par_instant_umol import PlantPhysiologyAnalytics

result = PlantPhysiologyAnalytics.calculate_plant_par_instant_umol(
    air_lux_lx=50000,           # 环境光照强度 (Lux)
    light_source="sunlight",    # 光源类型: sunlight/led/fluorescent
    reliability_score=0.95,     # 传感器置信度
    device_id="device_001"
)
# 输出: {"value": 925.93, "unit": "μmol/(m²·s)", "status": "success", ...}
```

**计算公式：**
- 日光: PAR = Lux / 54
- LED: PAR = Lux / 65
- 荧光灯: PAR = Lux / 74

### 2. 有效积温 (GDD) 计算

```python
from calculate_plant_gdd_daily_c import PlantPhysiologyAnalytics

result = PlantPhysiologyAnalytics.calculate_plant_gdd_daily_c(
    air_temp_samples=[22.5, 24.3, 26.1, 23.8, 21.2],  # 当日温度采样
    plant_base_temp_c=10.0,    # 作物基准生长温度
    harvest_target_gdd=1500,   # 收获目标积温
    current_accumulated_gdd=850  # 当前累计积温
)
# 输出: {"value": 13.8, "unit": "℃·d", "status": "success", ...}
```

**计算公式：**
```
GDD = max(T_avg - T_base, 0)
```

### 3. 日光积分 (DLI) 计算

```python
from calculate_plant_dli_daily_mol import PlantPhysiologyAnalytics
from datetime import datetime

par_series = [
    (datetime(2024, 1, 1, 6, 0), 50),
    (datetime(2024, 1, 1, 8, 0), 200),
    (datetime(2024, 1, 1, 12, 0), 800),
    (datetime(2024, 1, 1, 16, 0), 400),
    (datetime(2024, 1, 1, 18, 0), 100)
]

result = PlantPhysiologyAnalytics.calculate_plant_dli_daily_mol(
    par_time_series=par_series,
    target_dli_mol=15.0
)
# 输出: {"value": 12.5, "unit": "mol/(m2·d)", "completion_rate": 0.83, ...}
```

**计算原理：**
使用梯形法则近似积分：
```
DLI = Σ [(PAR_n + PAR_{n+1}) / 2 * Δt_n] / 1,000,000
```

### 4. 光利用率 (LUE) 评分

```python
from calculate_plant_lue_efficiency_score import ResourceEfficiencyAnalytics

result = ResourceEfficiencyAnalytics.calculate_plant_lue_efficiency_score(
    dli_natural_mol=10.5,       # 自然光积分
    dli_artificial_mol=4.5,     # 人工补光积分
    electricity_cost_total=2.5, # 补光电费 (CNY)
    target_dli=15.0,            # 目标DLI
    crop_type="blueberry"       # 作物类型
)
# 输出: {"value": 0.82, "unit": "score", "status": "success", ...}
```

**评分因子：**
- 达成率因子: 实际DLI / 目标DLI
- 自然光贡献率: 自然光DLI / 总DLI
- 经济效率: 基准电价 / 实际单位成本

### 5. 碳汇速率计算

```python
from calculate_plant_carbon_sink_rate_g_hr import GrowthAnalysisTool
from datetime import datetime

co2_series = [
    (datetime(2024, 1, 1, 10, 0), 420),
    (datetime(2024, 1, 1, 10, 10), 415),
    (datetime(2024, 1, 1, 10, 20), 408),
    (datetime(2024, 1, 1, 10, 30), 400)
]

result = GrowthAnalysisTool.calculate_plant_carbon_sink_rate_g_hr(
    co2_time_series=co2_series,
    chamber_volume_m3=50.0,     # 温室体积
    air_temp_c=25.0,            # 环境温度
    is_ventilation_active=False # 通风状态
)
# 输出: {"value": 2.35, "unit": "g/hr", "status": "success", ...}
```

### 6. 环境稳态能效比

```python
from calculate_device_stability_energy_ratio_pct import EnergyEfficiencyTool

result = EnergyEfficiencyTool.calculate_device_stability_energy_ratio_pct(
    actual_duty_cycle=0.35,         # 实际占空比
    target_metric_variance=0.8,     # 环境指标方差
    base_duty_cycle_limit=0.5,      # 传统控制基准占空比
    device_id="ventilation_001"
)
# 输出: {"value": 30.0, "unit": "pct", "status": "success", ...}
# 表示AI控制较传统控制节省30%能耗
```

### 7. 设备启停比分析

```python
from calculate_device_onoff_duty_ratio_val import DeviceDiagnosticsTool
from datetime import datetime, timedelta

action_logs = [
    {"start_time": datetime(2024, 1, 1, 8, 0), "end_time": datetime(2024, 1, 1, 8, 30)},
    {"start_time": datetime(2024, 1, 1, 10, 0), "end_time": datetime(2024, 1, 1, 10, 45)},
    {"start_time": datetime(2024, 1, 1, 14, 0), "end_time": datetime(2024, 1, 1, 14, 20)}
]

result = DeviceDiagnosticsTool.calculate_device_onoff_duty_ratio_val(
    action_logs=action_logs,
    observation_window_hrs=24.0
)
# 输出: {"duty_cycle_ratio": 0.066, "on_off_cycles": 3, "oscillation_risk": 0.12, ...}
```

### 8. VPD (蒸气压亏缺) 计算

```python
from calculate_air_vpd_instant_kpa import EnvironmentalPhysiologyTool

result = EnvironmentalPhysiologyTool.calculate_air_vpd_realtime_kpa(
    air_temp_c=28.0,            # 环境温度 (°C)
    air_humidity_pct=65.0,      # 相对湿度 (%)
    reliability_score=0.95
)
# 输出: {"value": 1.12, "unit": "kPa", "reasoning_context": "...处于黄金生长区间", ...}
```

**计算公式 (Tetens公式)：**
```
VPsat = 0.61078 * exp((17.27 * T) / (T + 237.3))
VPD = VPsat * (1 - RH / 100)
```

**VPD 生长区间参考：**
- < 0.4 kPa: 湿度过大，易滋生病菌
- 0.8 - 1.2 kPa: 黄金生长区间
- > 1.6 kPa: 蒸腾过快，气孔关闭

### 9. 碳平衡率计算

```python
from calculate_plant_net_zero_ratio import EcoValueSustainabilityAnalytics

result = EcoValueSustainabilityAnalytics.calculate_plant_net_zero_ratio(
    biomass_carbon_sequestration_g=150.0,      # 生物质固碳量
    operational_carbon_footprint_g=120.0,      # 设备碳足迹
    device_id="greenhouse_001"
)
# 输出: {"value": 1.25, "label": "Carbon Negative (局部碳负排放)", ...}
```

**判定标准：**
- Ratio > 1.0: 碳负排放 (Carbon Negative)
- Ratio ≈ 1.0: 碳中和 (Carbon Neutral)
- Ratio < 1.0: 碳正排放

### 10. 传感器交叉校验

```python
from verify_soil_npk_cross_reliability_score import SensorDiagnosticAnalytics

result = SensorDiagnosticAnalytics.verify_soil_npk_cross_reliability_score(
    soil_ec_raw_ms_cm=1.2,              # 电导率
    soil_npk_raw_group={'n': 120, 'p': 60, 'k': 150},  # NPK读数
    base_reliability_score=1.0
)
# 输出: 1.0 (逻辑自洽)
```

**校验逻辑：**
- EC与NPK应呈正相关
- 若EC低但NPK高，判定传感器漂移

## 统一返回格式

所有算法均返回标准化的字典结构：

```python
{
    "value": float,              # 计算结果值
    "unit": str,                 # 单位
    "status": str,               # 状态: "success" | "warning" | "error"
    "reasoning_context": str,    # 计算过程说明与决策建议
    "device_id": str,            # 设备ID (可选)
    "batch_id": str,             # 批次ID (可选)
    "strategy_id": str           # 策略ID (可选)
}
```

## 数据流架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OpenClaw 架构数据流                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  L1 热数据层          L2 分析层              L3 孪生层         L4 价值层    │
│  ┌──────────┐        ┌──────────┐          ┌──────────┐      ┌──────────┐  │
│  │ 传感器   │ ────> │ 算法引擎 │ ────>    │ 数字孪生 │ ───> │ ESG核算  │  │
│  │          │        │          │          │          │      │          │  │
│  │ - 温度   │        │ - PAR    │          │ - 占空比 │      │ - 碳足迹 │  │
│  │ - 湿度   │        │ - GDD    │          │ - 延迟   │      │ - 碳平衡 │  │
│  │ - 光照   │        │ - DLI    │          │ - 指纹   │      │ - 节水量 │  │
│  │ - CO2    │        │ - LUE    │          │          │      │          │  │
│  │ - NPK    │        │ - VPD    │          │          │      │          │  │
│  └──────────┘        └──────────┘          └──────────┘      └──────────┘  │
│       │                    │                    │                  │        │
│       ▼                    ▼                    ▼                  ▼        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        PostgreSQL 数据库                              │   │
│  │  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐ │   │
│  │  │ sensor_raw_data │ │agri_analytical_ │ │ esg_value_realization   │ │   │
│  │  │                 │ │    metrics      │ │                         │ │   │
│  │  └─────────────────┘ └─────────────────┘ └─────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 依赖说明

```python
# 核心依赖
pandas>=1.5.0          # 数据处理
numpy>=1.21.0          # 数值计算
scikit-learn>=1.0.0    # 线性回归 (设备指纹算法)

# 标准库
datetime               # 时间处理
typing                 # 类型注解
math                   # 数学函数
statistics             # 统计函数
```

## 测试

每个算法模块都配有对应的测试文件：

```bash
# 运行单个测试
python test_calculate_plant_par_instant_umol.py

# 运行所有测试
python -m pytest test_*.py -v
```

## 扩展指南

### 添加新算法

1. 创建新的算法文件，命名遵循 `calculate_<domain>_<metric>_<unit>.py`
2. 实现计算类和静态方法
3. 添加 SQL COMMENT 注释说明数据映射
4. 创建对应的测试文件
5. 更新本 README 文档

### 算法命名规范

```
calculate_<领域>_<指标>_<单位>.py

领域:
  - plant: 植物生理
  - device: 设备效能
  - air: 空气环境
  - soil: 土壤环境

指标:
  - par: 光合有效辐射
  - gdd: 有效积温
  - dli: 日光积分
  - vpd: 蒸气压亏缺
  - carbon_sink: 碳汇
  - ...

单位:
  - umol: 微摩尔
  - mol: 摩尔
  - kpa: 千帕
  - g: 克
  - pct: 百分比
```

## 版本历史

- **v1.0.0**: 初始版本，包含核心植物生理和设备诊断算法
- **v1.1.0**: 新增ESG价值核算模块
- **v1.2.0**: 新增传感器交叉校验功能
- **v1.3.0**: 新增A/B Testing实验决策分析

## 许可证

内部项目，仅供团队使用。
