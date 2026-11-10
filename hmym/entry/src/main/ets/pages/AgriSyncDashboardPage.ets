import { promptAction, router } from '@kit.ArkUI';
import { http } from '@kit.NetworkKit';
import { ApiConfig } from '../common/ApiConfig';

interface Point {
  x: number;
  y: number;
}

// ================= 主题颜色配置 (严格模式安全版) =================
class ThemeColors {
  static readonly base: string = '#f8f7f4';
  static readonly card: string = '#ffffff';
  static readonly primary: string = '#0b5934';
  static readonly primaryHover: string = '#084226';
  static readonly primaryLight: string = '#e8f3ee';
  static readonly textMain: string = '#1a2922';
  static readonly textMuted: string = '#6b7d73';
  static readonly borderLight: string = '#e2e6e3';
  static readonly accent: string = '#10b981';
  static readonly danger: string = '#ef4444';
  static readonly warning: string = '#f59e0b';
}

interface SensorValueItem {
  current: number;
  avg_24h: number;
  min_24h: number;
  max_24h: number;
}

interface DashboardSensorSummary {
  temperature: SensorValueItem;
  humidity: SensorValueItem;
  light: SensorValueItem;
  co2: SensorValueItem;
  soil_temp: SensorValueItem;
  soil_moisture: SensorValueItem;
}

interface DashboardDeviceItem {
  device_id: string;
  status: string;
  duty_cycle_ratio_pct: number;
  runtime_total_hrs: number;
}

interface DashboardESGItem {
  biomass_carbon_sequestration_g: number;
  operational_carbon_footprint_g: number;
  net_zero_ratio: number;
  water_saved_liters: number;
  energy_efficiency_ratio: number;
}

interface DashboardResponse {
  sensor_summary: DashboardSensorSummary;
  metrics_7day: MetricsDayItem[];
  devices: DashboardDeviceItem[];
  esg: DashboardESGItem | null;
  recent_actions: Object[];
}

interface MetricsDayItem {
  record_date?: string;
  par_val_umol: number;
  dli_daily_mol: number;
  current_accumulated_gdd_c: number;
  vpd_val_kpa: number;
  carbon_sink_rate_g_hr: number;
  lue_score_pct: number;
  energy_optimization_index: number;
  nutrient_consumption_rate_mg: number;
}

//this.BottomNav()
//@Builder BottomNav()
@Component
export struct AgriSyncDashboardPage {
  // ================= 状态管理 =================
  @State showNotifications: boolean = false;
  @State showGreenhouseSelectModal: boolean = false;
  @State viewMode: string = '全息监测';

  // 环境监测
  @State showEnvDetailModal: boolean = false;
  @State selectedEnvType: string = '';

  // 设备控制
  @State showDeviceDetailModal: boolean = false;
  @State selectedDevice: string = '';

  // 植物生长
  @State showPlantDetailModal: boolean = false;
  @State showStageDetailModal: boolean = false;
  @State selectedStage: string = '';
  @State selectedPlant: string = '白萝卜';

  // 农事待办
  @State alarmCount: number = 3;
  @State showWarningDetailModal: boolean = false;
  @State showDiagnosisImage: boolean = false;
  @State isWarningExpanded: boolean = false;
  @State isDiagnosisExpanded: boolean = false;

  // 消息通知已读状态
  @State notificationReadStatus: boolean[] = [false, false, false, false];

  // 底部导航
  @State selectedNav: string = '首页';
  @State aiPulseScale: number = 1;

  // 设备开关状态
  @State isCurtainOn: boolean = false;
  @State isPumpOn: boolean = false;
  @State isFanOn: boolean = false;
  @State isLightOn: boolean = false;
  @State isHeaterOn: boolean = false;

  // 设备动画状态
  @State curtainScale: number = 1;
  @State curtainOpacity: number = 1;
  @State pumpScale: number = 1;
  @State pumpOpacity: number = 1;
  @State fanScale: number = 1;
  @State fanOpacity: number = 1;
  @State fanRotation: number = 0;
  @State lightScale: number = 1;
  @State lightOpacity: number = 1;
  @State heaterScale: number = 1;
  @State heaterOpacity: number = 1;

  // 3D大棚旋转角度（用于预览）
  @State rotationY: number = 0.5;
  @State rotationX: number = 0.3;

  // 旋转动画定时器
  private rotationTimer: number = -1;

  // 设备参数
  @State curtainPower: number = 50;
  @State pumpPower: number = 70;
  @State pumpDuration: number = 15;
  @State fanSpeed: number = 1500;

  // 环境监测实时数据（正常值）
  @State lightIntensity: number = 984.7;
  @State soilMoisture: number = 76.2;
  @State npkN: number = 103;
  @State npkP: number = 42;
  @State npkK: number = 87;
  @State co2Concentration: number = 921.4;
  @State envTemperature: number = 19.6;
  @State envHumidity: number = 71.4;
  @State soilTemperature: number = 15.7;

  @State dashboardLoading: boolean = false;
  @State dashboardConnected: boolean = false;

  @State apiDevices: DashboardDeviceItem[] = [];
  @State latestMetrics: MetricsDayItem | null = null;

  private apiEnvTemperature: number = 19.6;
  private apiEnvHumidity: number = 71.4;
  private apiLightIntensity: number = 984.7;
  private apiCo2Concentration: number = 921.4;
  private apiSoilTemperature: number = 15.7;
  private apiSoilMoisture: number = 76.2;

  // 监测模式激活状态
  @State lightMonitoringActive: boolean = false;
  @State envTempMonitoringActive: boolean = false;
  @State envHumidityMonitoringActive: boolean = false;
  @State co2MonitoringActive: boolean = false;
  @State soilTempMonitoringActive: boolean = false;
  @State soilMoistureMonitoringActive: boolean = false;

  // 监测阶段状态 (0=未开始, 1=偏低, 2=正常, 3=偏高)
  @State lightMonitoringPhase: number = 0;
  @State envTempMonitoringPhase: number = 0;
  @State envHumidityMonitoringPhase: number = 0;
  @State co2MonitoringPhase: number = 0;
  @State soilTempMonitoringPhase: number = 0;
  @State soilMoistureMonitoringPhase: number = 0;

  // 土壤微量元素弹窗
  @State showNPKModal: boolean = false;

  // 其他环境参数弹窗
  @State showOtherEnvModal: boolean = false;

  // 适宜范围
  private lightMin: number = 800;
  private lightMax: number = 1000;
  private co2Min: number = 800;
  private co2Max: number = 1000;
  private soilTempMin: number = 13;
  private soilTempMax: number = 18;
  private soilMoistureMin: number = 70;
  private soilMoistureMax: number = 80;
  private envTempMin: number = 18;
  private envTempMax: number = 20;
  private envHumidityMin: number = 60;
  private envHumidityMax: number = 80;

  // 生长监测数据
  @State plantHeight: number = 25;
  @State leafCount: number = 8;
  @State growthDays: number = 15;

  // 在线时长（秒）
  @State curtainOnlineTime: number = 7320;
  @State pumpOnlineTime: number = 5430;
  @State fanOnlineTime: number = 0;
  @State lightOnlineTime: number = 0;
  @State heaterOnlineTime: number = 0;

  // 定时器ID
  private dataTimer: number = -1;
  private onlineTimeTimer: number = -1;

  // 页面进入时开启定时器
  aboutToAppear(): void {
    this.startDataRefresh();
    this.startRotationAnimation();
    this.fetchDashboardData();
  }

  // 页面离开时销毁定时器
  aboutToDisappear(): void {
    this.stopDataRefresh();
    if (this.rotationTimer !== -1) {
      clearInterval(this.rotationTimer);
    }
  }

  // 启动风扇旋转动画
  startRotationAnimation(): void {
    this.rotationTimer = setInterval(() => {
      if (this.isFanOn) {
        this.fanRotation = (this.fanRotation + 18) % 360;
      }
    }, 100);
  }

  // 启动数据定时刷新
  startDataRefresh(): void {
    // 防止重复创建定时器
    if (this.dataTimer !== -1) {
      return;
    }
    this.dataTimer = setInterval(() => {
      this.refreshEnvData();
    }, 5000); // 5秒间隔，避免过于频繁

    if (this.onlineTimeTimer !== -1) {
      return;
    }
    this.onlineTimeTimer = setInterval(() => {
      this.refreshOnlineTime();
    }, 1000);
  }

  // 停止数据刷新
  stopDataRefresh(): void {
    if (this.dataTimer !== -1) {
      clearInterval(this.dataTimer);
      this.dataTimer = -1;
    }
    if (this.onlineTimeTimer !== -1) {
      clearInterval(this.onlineTimeTimer);
      this.onlineTimeTimer = -1;
    }
  }

  async fetchDashboardData(): Promise<void> {
    this.dashboardLoading = true;
    try {
      const request = http.createHttp();
      const resp = await request.request(`${ApiConfig.BASE_URL}/analytics/dashboard`, {
        method: http.RequestMethod.GET,
        connectTimeout: 5000,
        readTimeout: 10000
      });
      request.destroy();

      if (resp.responseCode === 200 && resp.result) {
        const data: DashboardResponse = JSON.parse(resp.result as string) as DashboardResponse;
        if (data.sensor_summary) {
          const s = data.sensor_summary;
          this.apiEnvTemperature = s.temperature.current;
          this.apiEnvHumidity = s.humidity.current;
          this.apiLightIntensity = s.light.current;
          this.apiCo2Concentration = s.co2.current;
          this.apiSoilTemperature = s.soil_temp.current;
          this.apiSoilMoisture = s.soil_moisture.current;

          this.envTemperature = this.apiEnvTemperature;
          this.envHumidity = this.apiEnvHumidity;
          this.lightIntensity = this.apiLightIntensity;
          this.co2Concentration = this.apiCo2Concentration;
          this.soilTemperature = this.apiSoilTemperature;
          this.soilMoisture = this.apiSoilMoisture;

          this.dashboardConnected = true;
        }

        if (data.metrics_7day && data.metrics_7day.length > 0) {
          this.latestMetrics = data.metrics_7day[data.metrics_7day.length - 1];
        }

        if (data.devices && data.devices.length > 0) {
          this.apiDevices = data.devices;
          for (let i = 0; i < data.devices.length; i++) {
            const dev: DashboardDeviceItem = data.devices[i];
            const onlineSecs: number = dev.runtime_total_hrs * 3600;
            const devId: string = dev.device_id || '';
            if (devId.includes('curtain') || devId.includes('cur')) {
              this.curtainOnlineTime = onlineSecs;
            } else if (devId.includes('pump')) {
              this.pumpOnlineTime = onlineSecs;
            } else if (devId.includes('fan')) {
              this.fanOnlineTime = onlineSecs;
            } else if (devId.includes('light')) {
              this.lightOnlineTime = onlineSecs;
            } else if (devId.includes('heater') || devId.includes('heat')) {
              this.heaterOnlineTime = onlineSecs;
            }
          }
        }
      }
    } catch (e) {
      this.dashboardConnected = false;
    }
    this.dashboardLoading = false;
  }

  async sendDeviceCommand(name: string, turnOn: boolean): Promise<void> {
    const action: string = turnOn ? '打开' : '关闭';
    try {
      const request = http.createHttp();
      await request.request(`${ApiConfig.BASE_URL}/chat`, {
        method: http.RequestMethod.POST,
        header: { 'Content-Type': 'application/json' },
        extraData: JSON.stringify({ command: `${action}${name}` }),
        connectTimeout: 5000,
        readTimeout: 15000
      });
      request.destroy();
    } catch (e) {
      // 静默失败，设备状态已在本地更新
    }
  }

  // 环境数据动态变化刷新（新逻辑：只更新激活的监测参数）
  refreshEnvData(): void {
    this.updateMonitoringData();
    this.drawGreenhouse3D();
  }

  // 更新监测数据
  updateMonitoringData(): void {
    if (!this.lightMonitoringActive) {
      this.lightIntensity = this.apiLightIntensity;
    }
    if (!this.envTempMonitoringActive) {
      this.envTemperature = this.apiEnvTemperature;
    }
    if (!this.envHumidityMonitoringActive) {
      this.envHumidity = this.apiEnvHumidity;
    }
    if (!this.co2MonitoringActive) {
      this.co2Concentration = this.apiCo2Concentration;
    }
    if (!this.soilTempMonitoringActive) {
      this.soilTemperature = this.apiSoilTemperature;
    }
    if (!this.soilMoistureMonitoringActive) {
      this.soilMoisture = this.apiSoilMoisture;
    }
  }

  // 光照强度监测逻辑
  toggleLightMonitoring(): void {
    if (this.lightMonitoringActive) {
      this.lightMonitoringActive = false;
      this.lightMonitoringPhase = 0;
      this.lightIntensity = this.apiLightIntensity;
    } else {
      this.lightMonitoringActive = true;
      this.lightMonitoringPhase = 1;
      this.lightIntensity = 632.5;
    }
  }

  // 检查光照强度设备状态
  checkLightMonitoring(): void {
    if (!this.lightMonitoringActive) return;

    if (this.lightMonitoringPhase === 1) {
      // 偏低状态，等待补光灯打开
      if (this.isLightOn) {
        setTimeout(() => {
          if (this.isLightOn && this.lightMonitoringPhase === 1) {
            this.lightMonitoringPhase = 2;
            this.lightIntensity = this.apiLightIntensity;
          }
        }, 3000);
      }
    } else if (this.lightMonitoringPhase === 2) {
      // 正常状态，等待补光灯关闭
      if (!this.isLightOn && !this.isCurtainOn) {
        setTimeout(() => {
          if (!this.isLightOn && this.lightMonitoringPhase === 2) {
            this.lightMonitoringPhase = 3;
            this.lightIntensity = 1195.3;
          }
        }, 1000);
      }
      // 正常状态，等待遮光帘打开
      if (this.isCurtainOn) {
        setTimeout(() => {
          if (this.isCurtainOn && this.lightMonitoringPhase === 3) {
            this.lightMonitoringPhase = 2;
            this.lightIntensity = this.apiLightIntensity;
          }
        }, 3000);
      }
    } else if (this.lightMonitoringPhase === 3) {
      // 偏高状态，等待遮光帘打开
      if (this.isCurtainOn) {
        setTimeout(() => {
          if (this.isCurtainOn && this.lightMonitoringPhase === 3) {
            this.lightMonitoringPhase = 2;
            this.lightIntensity = this.apiLightIntensity;
          }
        }, 3000);
      }
    }
  }

  // 环境温度监测逻辑
  toggleEnvTempMonitoring(): void {
    if (this.envTempMonitoringActive) {
      this.envTempMonitoringActive = false;
      this.envTempMonitoringPhase = 0;
      this.envTemperature = this.apiEnvTemperature;
    } else {
      this.envTempMonitoringActive = true;
      this.envTempMonitoringPhase = 3;
      this.envTemperature = 27.8;
    }
  }

  // 检查环境温度设备状态
  checkEnvTempMonitoring(): void {
    if (!this.envTempMonitoringActive) return;

    if (this.envTempMonitoringPhase === 3) {
      // 偏高状态，等待遮光帘+水泵+风扇都打开
      if (this.isCurtainOn && this.isPumpOn && this.isFanOn) {
        setTimeout(() => {
          if (this.isCurtainOn && this.isPumpOn && this.isFanOn && this.envTempMonitoringPhase === 3) {
            this.envTempMonitoringPhase = 2;
            this.envTemperature = this.apiEnvTemperature;
          }
        }, 3000);
      }
    } else if (this.envTempMonitoringPhase === 2) {
      // 正常状态，等待遮光帘+水泵+风扇都关闭
      if (!this.isCurtainOn && !this.isPumpOn && !this.isFanOn && !this.isLightOn && !this.isHeaterOn) {
        setTimeout(() => {
          if (!this.isCurtainOn && !this.isPumpOn && !this.isFanOn && this.envTempMonitoringPhase === 2) {
            this.envTempMonitoringPhase = 1;
            this.envTemperature = 13.4;
          }
        }, 1000);
      }
      // 正常状态，等待补光灯+加热棒都打开
      if (this.isLightOn && this.isHeaterOn) {
        setTimeout(() => {
          if (this.isLightOn && this.isHeaterOn && this.envTempMonitoringPhase === 1) {
            this.envTempMonitoringPhase = 2;
            this.envTemperature = this.apiEnvTemperature;
          }
        }, 3000);
      }
    } else if (this.envTempMonitoringPhase === 1) {
      // 偏低状态，等待补光灯+加热棒都打开
      if (this.isLightOn && this.isHeaterOn) {
        setTimeout(() => {
          if (this.isLightOn && this.isHeaterOn && this.envTempMonitoringPhase === 1) {
            this.envTempMonitoringPhase = 2;
            this.envTemperature = this.apiEnvTemperature;
          }
        }, 3000);
      }
    }
  }

  // 环境湿度监测逻辑
  toggleEnvHumidityMonitoring(): void {
    if (this.envHumidityMonitoringActive) {
      this.envHumidityMonitoringActive = false;
      this.envHumidityMonitoringPhase = 0;
      this.envHumidity = this.apiEnvHumidity;
    } else {
      this.envHumidityMonitoringActive = true;
      this.envHumidityMonitoringPhase = 1;
      this.envHumidity = 53.7;
    }
  }

  // 检查环境湿度设备状态
  checkEnvHumidityMonitoring(): void {
    if (!this.envHumidityMonitoringActive) return;

    if (this.envHumidityMonitoringPhase === 1) {
      // 偏低状态，等待水泵打开
      if (this.isPumpOn) {
        setTimeout(() => {
          if (this.isPumpOn && this.envHumidityMonitoringPhase === 1) {
            this.envHumidityMonitoringPhase = 2;
            this.envHumidity = this.apiEnvHumidity;
          }
        }, 3000);
      }
    } else if (this.envHumidityMonitoringPhase === 2) {
      // 正常状态，等待水泵关闭
      if (!this.isPumpOn && !this.isFanOn) {
        setTimeout(() => {
          if (!this.isPumpOn && this.envHumidityMonitoringPhase === 2) {
            this.envHumidityMonitoringPhase = 3;
            this.envHumidity = 84.2;
          }
        }, 1000);
      }
      // 正常状态，等待风扇打开
      if (this.isFanOn) {
        setTimeout(() => {
          if (this.isFanOn && this.envHumidityMonitoringPhase === 3) {
            this.envHumidityMonitoringPhase = 2;
            this.envHumidity = this.apiEnvHumidity;
          }
        }, 3000);
      }
    } else if (this.envHumidityMonitoringPhase === 3) {
      // 偏高状态，等待风扇打开
      if (this.isFanOn) {
        setTimeout(() => {
          if (this.isFanOn && this.envHumidityMonitoringPhase === 3) {
            this.envHumidityMonitoringPhase = 2;
            this.envHumidity = this.apiEnvHumidity;
          }
        }, 3000);
      }
    }
  }

  // CO2浓度监测逻辑
  toggleCO2Monitoring(): void {
    if (this.co2MonitoringActive) {
      this.co2MonitoringActive = false;
      this.co2MonitoringPhase = 0;
      this.co2Concentration = this.apiCo2Concentration;
    } else {
      this.co2MonitoringActive = true;
      this.co2MonitoringPhase = 3;
      this.co2Concentration = 1132.1;
    }
  }

  // 检查CO2浓度设备状态
  checkCO2Monitoring(): void {
    if (!this.co2MonitoringActive) return;

    if (this.co2MonitoringPhase === 3) {
      // 偏高状态，等待风扇打开
      if (this.isFanOn) {
        setTimeout(() => {
          if (this.isFanOn && this.co2MonitoringPhase === 3) {
            this.co2MonitoringPhase = 2;
            this.co2Concentration = this.apiCo2Concentration;
          }
        }, 3000);
      }
    } else if (this.co2MonitoringPhase === 2) {
      // 正常状态，等待风扇关闭
      if (!this.isFanOn && !this.isPumpOn) {
        setTimeout(() => {
          if (!this.isFanOn && !this.isPumpOn && this.co2MonitoringPhase === 2) {
            this.co2MonitoringPhase = 1;
            this.co2Concentration = 679.2;
          }
        }, 1000);
      }
      // 正常状态，等待风扇+水泵都打开
      if (this.isFanOn && this.isPumpOn) {
        setTimeout(() => {
          if (this.isFanOn && this.isPumpOn && this.co2MonitoringPhase === 1) {
            this.co2MonitoringPhase = 2;
            this.co2Concentration = this.apiCo2Concentration;
          }
        }, 3000);
      }
    } else if (this.co2MonitoringPhase === 1) {
      // 偏低状态，等待风扇+水泵都打开
      if (this.isFanOn && this.isPumpOn) {
        setTimeout(() => {
          if (this.isFanOn && this.isPumpOn && this.co2MonitoringPhase === 1) {
            this.co2MonitoringPhase = 2;
            this.co2Concentration = this.apiCo2Concentration;
          }
        }, 3000);
      }
    }
  }

  // 土壤温度监测逻辑
  toggleSoilTempMonitoring(): void {
    if (this.soilTempMonitoringActive) {
      this.soilTempMonitoringActive = false;
      this.soilTempMonitoringPhase = 0;
      this.soilTemperature = this.apiSoilTemperature;
    } else {
      this.soilTempMonitoringActive = true;
      this.soilTempMonitoringPhase = 3;
      this.soilTemperature = 20.4;
    }
  }

  // 检查土壤温度设备状态
  checkSoilTempMonitoring(): void {
    if (!this.soilTempMonitoringActive) return;

    if (this.soilTempMonitoringPhase === 3) {
      // 偏高状态，等待遮光帘+水泵+风扇都打开
      if (this.isCurtainOn && this.isPumpOn && this.isFanOn) {
        setTimeout(() => {
          if (this.isCurtainOn && this.isPumpOn && this.isFanOn && this.soilTempMonitoringPhase === 3) {
            this.soilTempMonitoringPhase = 2;
            this.soilTemperature = this.apiSoilTemperature;
          }
        }, 3000);
      }
    } else if (this.soilTempMonitoringPhase === 2) {
      // 正常状态，等待遮光帘+水泵+风扇都关闭
      if (!this.isCurtainOn && !this.isPumpOn && !this.isFanOn && !this.isLightOn && !this.isHeaterOn) {
        setTimeout(() => {
          if (!this.isCurtainOn && !this.isPumpOn && !this.isFanOn && this.soilTempMonitoringPhase === 2) {
            this.soilTempMonitoringPhase = 1;
            this.soilTemperature = 9.3;
          }
        }, 1000);
      }
      // 正常状态，等待补光灯+加热棒都打开
      if (this.isLightOn && this.isHeaterOn) {
        setTimeout(() => {
          if (this.isLightOn && this.isHeaterOn && this.soilTempMonitoringPhase === 1) {
            this.soilTempMonitoringPhase = 2;
            this.soilTemperature = this.apiSoilTemperature;
          }
        }, 3000);
      }
    } else if (this.soilTempMonitoringPhase === 1) {
      // 偏低状态，等待补光灯+加热棒都打开
      if (this.isLightOn && this.isHeaterOn) {
        setTimeout(() => {
          if (this.isLightOn && this.isHeaterOn && this.soilTempMonitoringPhase === 1) {
            this.soilTempMonitoringPhase = 2;
            this.soilTemperature = this.apiSoilTemperature;
          }
        }, 3000);
      }
    }
  }

  // 土壤湿度监测逻辑
  toggleSoilMoistureMonitoring(): void {
    if (this.soilMoistureMonitoringActive) {
      this.soilMoistureMonitoringActive = false;
      this.soilMoistureMonitoringPhase = 0;
      this.soilMoisture = this.apiSoilMoisture;
    } else {
      this.soilMoistureMonitoringActive = true;
      this.soilMoistureMonitoringPhase = 1;
      this.soilMoisture = 61.2;
    }
  }

  // 检查土壤湿度设备状态
  checkSoilMoistureMonitoring(): void {
    if (!this.soilMoistureMonitoringActive) return;

    if (this.soilMoistureMonitoringPhase === 1) {
      // 偏低状态，等待水泵打开
      if (this.isPumpOn) {
        setTimeout(() => {
          if (this.isPumpOn && this.soilMoistureMonitoringPhase === 1) {
            this.soilMoistureMonitoringPhase = 2;
            this.soilMoisture = this.apiSoilMoisture;
          }
        }, 3000);
      }
    } else if (this.soilMoistureMonitoringPhase === 2) {
      // 正常状态，等待水泵关闭
      if (!this.isPumpOn && !this.isFanOn) {
        setTimeout(() => {
          if (!this.isPumpOn && this.soilMoistureMonitoringPhase === 2) {
            this.soilMoistureMonitoringPhase = 3;
            this.soilMoisture = 86.7;
          }
        }, 1000);
      }
      // 正常状态，等待风扇打开
      if (this.isFanOn) {
        setTimeout(() => {
          if (this.isFanOn && this.soilMoistureMonitoringPhase === 3) {
            this.soilMoistureMonitoringPhase = 2;
            this.soilMoisture = this.apiSoilMoisture;
          }
        }, 3000);
      }
    } else if (this.soilMoistureMonitoringPhase === 3) {
      // 偏高状态，等待风扇打开
      if (this.isFanOn) {
        setTimeout(() => {
          if (this.isFanOn && this.soilMoistureMonitoringPhase === 3) {
            this.soilMoistureMonitoringPhase = 2;
            this.soilMoisture = this.apiSoilMoisture;
          }
        }, 3000);
      }
    }
  }

  // 在线时长刷新
  refreshOnlineTime(): void {
    if (this.isCurtainOn) {
      this.curtainOnlineTime++;
    }
    if (this.isPumpOn) {
      this.pumpOnlineTime++;
    }
    if (this.isFanOn) {
      this.fanOnlineTime++;
    }
    if (this.isLightOn) {
      this.lightOnlineTime++;
    }
    if (this.isHeaterOn) {
      this.heaterOnlineTime++;
    }
  }

  // 格式化在线时长
  formatOnlineTime(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hours > 0) {
      return `${hours}小时${minutes}分`;
    }
    if (minutes > 0) {
      return `${minutes}分${secs}秒`;
    }
    return `${secs}秒`;
  }

  // 模拟操作状态
  @State isProcessingPump: boolean = false;

  // 按钮动画状态
  @State btnScale: number = 1;
  @State cardScale: number = 1;
  @State pumpBtnScale: number = 1;
  @State detailBtnScale: number = 1;
  @State markDoneBtnScale: number = 1;
  @State diagImageBtnScale: number = 1;

  private showToast(message: string): void {
    try {
      promptAction.showToast({ message: message });
    } catch (error) {
      console.error('Toast show failed: ' + JSON.stringify(error));
    }
  }

  // ================= 页面主视图 =================
  formatMetric(val: number, decimals: number): string {
    return val.toFixed(decimals);
  }

  build() {
    Stack({ alignContent: Alignment.Bottom }) {

      // 1. 底层主体结构
      Column() {
        this.Header()

        Scroll() {
          Column({ space: 24 }) {
            this.DigitalTwinSection()
            this.EnvironmentSection()
            this.DeviceControlSection()
            this.PlantGrowthSection()
            this.TodoAlarmsSection()

            // 底部留白，防遮挡
            Row().height(90)
          }
          .padding({ top: 16 })
        }
        .layoutWeight(1)
        .scrollBar(BarState.Off)
        .backgroundColor(ThemeColors.base)
        .align(Alignment.Top)
      }
      .width('100%')
      .height('100%')

      // 2. 悬浮通知中心 (绝对定位)
      if (this.showNotifications) {
        // 全屏透明遮罩，点击收起通知
        Column()
          .width('100%')
          .height('100%')
          .backgroundColor('rgba(0,0,0,0.1)')
          .zIndex(40)
          .onClick(() => { this.showNotifications = false; })

        this.NotificationCenter()
      }

      // 3. 环境详情弹窗
      if (this.showEnvDetailModal) {
        this.EnvDetailModal()
      }

      // 4. 设备详情弹窗
      if (this.showDeviceDetailModal) {
        this.DeviceDetailModal()
      }

      // 5. 作物详情弹窗
      if (this.showPlantDetailModal) {
        this.PlantDetailModal()
      }

      // 6. 阶段说明弹窗
      if (this.showStageDetailModal) {
        this.StageDetailModal()
      }

      // 7. 预警详情弹窗（修复"查看详情"失效）
      if (this.showWarningDetailModal) {
        this.WarningDetailModal()
      }

      // 8. 诊断图片弹窗
      if (this.showDiagnosisImage) {
        this.DiagnosisImageModal()
      }

      // 9. 土壤微量元素含量弹窗
      if (this.showNPKModal) {
        this.NPKModal()
      }

      // 其他环境参数弹窗
      if (this.showOtherEnvModal) {
        this.OtherEnvModal()
      }

      // 10. 大棚选择弹窗
      if (this.showGreenhouseSelectModal) {
        this.GreenhouseSelectModal()
      }

      // 11. 底部导航栏
      this.BottomNav()
    }
    .width('100%')
    .height('100%')
    .backgroundColor(ThemeColors.base)
  }

  // ================= 局部组件 Builder =================

  // 头部 Header
  @Builder Header() {
    Row() {
      // Logo 区域
      Row({ space: 8 }) {
        Row() { Text('A').fontColor('#fff').fontWeight(FontWeight.Bold) }
        .width(28).height(28).backgroundColor(ThemeColors.primary).borderRadius(6).justifyContent(FlexAlign.Center)
        Text('AGRI-SYNC').fontSize(18).fontWeight(900).fontColor(ThemeColors.primary)
      }

      // 铃铛通知
      Stack() {
        Button('🔔')
          .type(ButtonType.Circle)
          .backgroundColor(ThemeColors.card)
          .width(40).height(40)
          .fontColor(ThemeColors.textMain)
          .border({ width: 1, color: ThemeColors.borderLight })
          .onClick(() => { this.showNotifications = !this.showNotifications; })

        // 红点
        Circle({ width: 10, height: 10 })
          .fill(ThemeColors.danger)
          .border({ width: 2, color: ThemeColors.card })
          .position({ x: 26, y: 0 })
      }
    }
    .width('100%').height(60).padding({ left: 20, right: 20 })
    .backgroundColor('rgba(248, 247, 244, 0.9)').backdropBlur(20)
    .justifyContent(FlexAlign.SpaceBetween)
    .zIndex(30)
  }

  // 通知中心弹窗
  @Builder NotificationCenter() {
    Column() {
      Row() { Text('预警通知').fontColor('#fff').fontWeight(FontWeight.Bold).fontSize(14) }
      .width('100%').padding(16).border({ width: { bottom: 1 }, color: 'rgba(255,255,255,0.1)' })

      // 通知列表
      Scroll() {
        Column() {
          this.NotificationItem('🌾', '作物倒伏提醒', '有作物倒伏，尽快前去查看', '11:05', ThemeColors.warning, 0)
          this.NotificationItem('🔥', '温度过高预警', '大棚内温度已超过35℃，可能影响作物生长', '10:23', ThemeColors.danger, 1)
          this.NotificationItem('🏜️', '土壤干旱预警', '土壤含水量低于20%，需要及时浇水', '09:45', ThemeColors.warning, 2)
          this.NotificationItem('💧', '湿度异常预警', '空气湿度低于40%，可能影响作物授粉', '08:12', '#3b82f6', 3)
        }
      }.constraintSize({ maxHeight: 250 })

      Row() { Text('查看全部通知').fontColor('#9ca3af').fontSize(13) }
      .width('100%').padding(12).justifyContent(FlexAlign.Center).border({ width: { top: 1 }, color: 'rgba(255,255,255,0.1)' })
    }
    .width(280)
    .backgroundColor('rgba(26, 41, 34, 0.95)')
    .backdropBlur(20)
    .borderRadius(16)
    .border({ width: 1, color: 'rgba(255,255,255,0.1)' })
    .position({ x: '100%', y: 60 })
    .translate({ x: '-100%' })
    .offset({ x: -20 })
    .zIndex(50)
    .shadow({ radius: 30, color: 'rgba(0,0,0,0.2)', offsetY: 10 })
  }

  @Builder NotificationItem(icon: string, title: string, desc: string, time: string, color: string, index: number) {
    Row({ space: 12 }) {
      Row() { Text(icon).fontSize(16) }
      .width(32).height(32).backgroundColor(`${color}20`).borderRadius(16).justifyContent(FlexAlign.Center)

      Column({ space: 4 }) {
        Row() {
          Row({ space: 4 }) {
            Text(title).fontColor('#fff').fontSize(13).fontWeight(FontWeight.Medium)
            if (!this.notificationReadStatus[index]) {
              Circle({ width: 6, height: 6 }).fill(ThemeColors.danger)
            }
          }
          Text(time).fontColor('#6b7280').fontSize(11)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Text(desc).fontColor('#9ca3af').fontSize(11).lineHeight(16)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
    }
    .width('100%').padding(16).border({ width: { bottom: 1 }, color: 'rgba(255,255,255,0.05)' })
    .opacity(this.notificationReadStatus[index] ? 0.6 : 1)
    .onClick(() => {
      this.notificationReadStatus[index] = true;
      this.showToast('已标记为已读');
    })
  }

  // 1. 数字孪生面板 - 3D大棚模型
  @Builder DigitalTwinSection() {
    Column() {
      Stack({ alignContent: Alignment.TopEnd }) {
        Canvas(this.greenhouse3DContext)
          .width('100%')
          .height(180)
          .backgroundColor('#1a1a2e')
          .borderRadius(20)
          .onReady(() => {
            this.drawGreenhouse3D();
          })

        Column({ space: 8 }) {
          Row({ space: 4 }) {
            Circle({ width: 6, height: 6 }).fill('#4ade80')
            Text('SIM: ACTIVE').fontColor('#4ade80').fontSize(10).fontFamily('monospace')
          }.backgroundColor('rgba(0,0,0,0.5)').padding({ left: 8, right: 8, top: 4, bottom: 4 }).borderRadius(4).border({ width: 1, color: 'rgba(74, 222, 128, 0.3)' })

          Text('4号大棚 · 萝卜区').fontColor('#fff').fontSize(10).backgroundColor('rgba(0,0,0,0.5)').padding({ left: 8, right: 8, top: 4, bottom: 4 }).borderRadius(4).border({ width: 1, color: 'rgba(11, 89, 52, 0.3)' })
            .onClick(() => {
              this.showGreenhouseSelectModal = true;
            })
        }.position({ x: '100%', y: 16 }).translate({ x: '-100%' }).offset({ x: -16 }).alignItems(HorizontalAlign.End)

        Row() {
          Column({ space: 4 }) {
            Text('数字孪生环境').fontColor('#fff').fontSize(18).fontWeight(FontWeight.Bold).letterSpacing(1)
            Text('点击查看3D模型').fontColor('#4ade80').fontSize(11).fontFamily('monospace')
          }.alignItems(HorizontalAlign.Start)

          Blank()

          Button('🔍 全屏查看')
            .backgroundColor('rgba(11, 89, 52, 0.6)')
            .fontColor('#fff')
            .fontSize(11)
            .borderRadius(16)
            .padding({ left: 12, right: 12, top: 6, bottom: 6 })
            .onClick(() => {
              this.openGreenhouse3D();
            })
        }
        .width('100%')
        .padding(16)
        .position({ x: 0, y: '100%' })
        .translate({ y: '-100%' })
        .alignItems(VerticalAlign.Center)
      }
      .width('100%')
      .height(180)
      .shadow({ radius: 15, color: 'rgba(11, 89, 52, 0.3)' })
      .onClick(() => {
        this.openGreenhouse3D();
      })
    }.padding({ left: 16, right: 16 })
  }

  openGreenhouse3D(): void {
    router.pushUrl({
      url: 'pages/Greenhouse3DPage',
      params: {
        lightIntensity: this.lightIntensity,
        soilMoisture: this.soilMoisture,
        npkN: this.npkN,
        npkP: this.npkP,
        npkK: this.npkK,
        co2Concentration: this.co2Concentration,
        envTemperature: this.envTemperature,
        envHumidity: this.envHumidity,
        soilTemperature: this.soilTemperature
      }
    });
  }

  private greenhouse3DContext: CanvasRenderingContext2D = new CanvasRenderingContext2D(new RenderingContextSettings(true));

  // 3D投影函数
  project3D(x: number, y: number, z: number, centerX: number, centerY: number, scale: number): Point {
    const cosY = Math.cos(this.rotationY);
    const sinY = Math.sin(this.rotationY);
    const cosX = Math.cos(this.rotationX);
    const sinX = Math.sin(this.rotationX);

    const x1 = x * cosY - z * sinY;
    const z1 = x * sinY + z * cosY;
    const y1 = y * cosX - z1 * sinX;
    const z2 = y * sinX + z1 * cosX;

    const perspective = 400 / (400 + z2);
    return {
      x: centerX + x1 * scale * perspective,
      y: centerY - y1 * scale * perspective
    };
  }

  // 绘制3D大棚
  drawGreenhouse3D(): void {
    const ctx = this.greenhouse3DContext;
    const width = ctx.width;
    const height = ctx.height;
    const centerX = width / 2;
    const centerY = height / 2 + 20;
    const scale = Math.min(width, height) * 0.35;

    ctx.clearRect(0, 0, width, height);

    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, '#1a1a2e');
    gradient.addColorStop(1, '#16213e');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);

    const groundPoints: Point[] = [];
    for (let i = 0; i <= 10; i++) {
      const x = -1 + i * 0.2;
      groundPoints.push(this.project3D(x, -0.6, -0.8, centerX, centerY, scale));
    }
    for (let i = 10; i >= 0; i--) {
      const x = -1 + i * 0.2;
      groundPoints.push(this.project3D(x, -0.6, 0.8, centerX, centerY, scale));
    }
    ctx.beginPath();
    ctx.moveTo(groundPoints[0].x, groundPoints[0].y);
    for (let i = 1; i < groundPoints.length; i++) {
      ctx.lineTo(groundPoints[i].x, groundPoints[i].y);
    }
    ctx.closePath();
    ctx.fillStyle = 'rgba(139, 90, 43, 0.6)';
    ctx.fill();

    const archCount = 6;
    for (let i = 0; i < archCount; i++) {
      const z = -0.8 + i * 0.32;
      const archPoints: Point[] = [];

      for (let j = 0; j <= 12; j++) {
        const angle = Math.PI * j / 12;
        const x = Math.cos(angle) * 1;
        const y = Math.sin(angle) * 0.7 - 0.1;
        archPoints.push(this.project3D(x, y, z, centerX, centerY, scale));
      }

      ctx.beginPath();
      ctx.moveTo(archPoints[0].x, archPoints[0].y);
      for (let j = 1; j < archPoints.length; j++) {
        ctx.lineTo(archPoints[j].x, archPoints[j].y);
      }
      ctx.strokeStyle = 'rgba(192, 192, 192, 0.9)';
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    for (let i = 0; i <= 2; i++) {
      const x = -1 + i * 1;
      const railPoints: Point[] = [];
      for (let j = 0; j <= 12; j++) {
        const angle = Math.PI * j / 12;
        const railX = Math.cos(angle) * 1;
        const railY = Math.sin(angle) * 0.7 - 0.1;
        if (Math.abs(railX - x) < 0.1) {
          railPoints.push(this.project3D(x, railY, -0.8 + j * 0.13, centerX, centerY, scale));
        }
      }
      if (railPoints.length > 1) {
        ctx.beginPath();
        ctx.moveTo(railPoints[0].x, railPoints[0].y);
        for (let j = 1; j < railPoints.length; j++) {
          ctx.lineTo(railPoints[j].x, railPoints[j].y);
        }
        ctx.strokeStyle = 'rgba(192, 192, 192, 0.7)';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
    }

    const filmPoints: Point[] = [];
    for (let i = 0; i <= 12; i++) {
      const angle = Math.PI * i / 12;
      const x = Math.cos(angle) * 1;
      const y = Math.sin(angle) * 0.7 - 0.1;
      filmPoints.push(this.project3D(x, y, -0.8, centerX, centerY, scale));
    }
    for (let i = 12; i >= 0; i--) {
      const angle = Math.PI * i / 12;
      const x = Math.cos(angle) * 1;
      const y = Math.sin(angle) * 0.7 - 0.1;
      filmPoints.push(this.project3D(x, y, 0.8, centerX, centerY, scale));
    }
    ctx.beginPath();
    ctx.moveTo(filmPoints[0].x, filmPoints[0].y);
    for (let i = 1; i < filmPoints.length; i++) {
      ctx.lineTo(filmPoints[i].x, filmPoints[i].y);
    }
    ctx.closePath();
    ctx.fillStyle = 'rgba(100, 200, 255, 0.15)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(100, 200, 255, 0.3)';
    ctx.lineWidth = 1;
    ctx.stroke();

    this.drawInfoPanel(ctx, centerX - scale * 0.5, centerY - scale * 0.3, '☀️ 光照', `${this.lightIntensity} klx`, '#f59e0b');
    this.drawInfoPanel(ctx, centerX + scale * 0.2, centerY - scale * 0.3, '☁️ CO₂', `${this.co2Concentration} ppm`, '#14b8a6');
    this.drawInfoPanel(ctx, centerX - scale * 0.5, centerY + scale * 0.1, '💧 水分', `${this.soilMoisture}%`, '#3b82f6');
    this.drawInfoPanel(ctx, centerX + scale * 0.2, centerY + scale * 0.1, '🧪 NPK', `${this.npkN}/${this.npkP}/${this.npkK}`, '#a855f7');

    const plantRows = 3;
    for (let row = 0; row < plantRows; row++) {
      const z = -0.4 + row * 0.3;
      for (let col = 0; col < 4; col++) {
        const x = -0.6 + col * 0.4;
        const p = this.project3D(x, -0.55, z, centerX, centerY, scale);
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(34, 197, 94, 0.8)';
        ctx.fill();
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x, p.y - 8);
        ctx.strokeStyle = 'rgba(34, 197, 94, 0.6)';
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    }
  }

  // 绘制信息面板
  drawInfoPanel(ctx: CanvasRenderingContext2D, x: number, y: number, title: string, value: string, color: string): void {
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.beginPath();
    ctx.roundRect(x - 35, y - 12, 70, 35, 6);
    ctx.fill();

    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(x - 35, y - 12, 70, 35, 6);
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(title, x, y);

    ctx.fillStyle = color;
    ctx.font = 'bold 11px sans-serif';
    ctx.fillText(value, x, y + 14);
  }

  // 2. 核心环境监测
  @Builder EnvironmentSection() {
    Column({ space: 8 }) {
      Row() {
        Text('核心环境监测').fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain).layoutWeight(1)
        Button('其他')
          .fontSize(12)
          .height(28)
          .backgroundColor(ThemeColors.primaryLight)
          .fontColor(ThemeColors.primary)
          .onClick(() => {
            this.showOtherEnvModal = true;
          })
      }.width('100%').padding({ left: 4, right: 4 })

      // 第一行：环境温度、环境湿度
      Row({ space: 8 }) {
        this.EnvTempCard()
        this.EnvHumidityCard()
      }.width('100%')

      // 第二行：光照强度、CO₂浓度
      Row({ space: 8 }) {
        this.LightCard()
        this.CO2Card()
      }.width('100%')

      // 第三行：土壤温度、土壤湿度（分开）
      Row({ space: 8 }) {
        this.SoilTempCard()
        this.SoilMoistureCard()
      }.width('100%')

      // 第四行：土壤微量元素含量
      Row({ space: 8 }) {
        this.NPKCard()
      }.width('100%')
    }.padding({ left: 16, right: 16, bottom: 8 })
  }

  // 环境监测卡片动画状态
  @State envCardScale: number = 1;

  // 获取状态文本和颜色
  getStatusText(value: number, min: number, max: number): string {
    if (value < min) return '偏低';
    if (value > max) return '偏高';
    return '正常';
  }

  getStatusColor(value: number, min: number, max: number): string {
    if (value < min) return '#3b82f6';
    if (value > max) return '#ef4444';
    return ThemeColors.primary;
  }

  // 环境温度卡片
  @Builder EnvTempCard() {
    Column() {
      Row() {
        Text('环境温度').fontSize(12).fontColor(ThemeColors.textMuted).fontWeight(FontWeight.Medium)
        Row() { 
          Text(this.envTempMonitoringActive ? '🔍' : '🌡️').fontSize(12) 
        }
        .width(24)
        .height(24)
        .backgroundColor(this.envTempMonitoringActive ? '#0b593420' : '#ef444415')
        .borderRadius(12)
        .justifyContent(FlexAlign.Center)
        .onClick(() => {
          this.toggleEnvTempMonitoring();
        })
      }
      .width('100%')
      .justifyContent(FlexAlign.SpaceBetween)
      .margin({ bottom: 12 })

      Column({ space: 4 }) {
        Row() {
          Text(`${this.envTemperature}`)
            .fontSize(22)
            .fontWeight(FontWeight.Bold)
            .fontColor(ThemeColors.textMain)
          Text('°C')
            .fontSize(12)
            .fontColor(ThemeColors.textMuted)
            .margin({ left: 4, bottom: 4 })
        }
        .alignItems(VerticalAlign.Bottom)

        Text(`适宜: ${this.envTempMin}°C - ${this.envTempMax}°C`)
          .fontSize(10)
          .fontColor(ThemeColors.textMuted)
        
        Text(this.getStatusText(this.envTemperature, this.envTempMin, this.envTempMax))
          .fontSize(10)
          .fontColor(this.getStatusColor(this.envTemperature, this.envTempMin, this.envTempMax))
          .fontWeight(FontWeight.Bold)
          .margin({ top: 2 })
      }
      .alignItems(HorizontalAlign.Start)
    }
    .layoutWeight(1)
    .height(110)
    .backgroundColor(ThemeColors.card)
    .borderRadius(14)
    .padding(12)
    .border({ width: 1, color: this.envTempMonitoringActive ? ThemeColors.primary : ThemeColors.borderLight })
    .shadow({ radius: this.envTempMonitoringActive ? 10 : 8, color: this.envTempMonitoringActive ? 'rgba(11, 89, 52, 0.1)' : 'rgba(0,0,0,0.03)', offsetY: 2 })
  }

  // 环境湿度卡片
  @Builder EnvHumidityCard() {
    Column() {
      Row() {
        Text('环境湿度').fontSize(12).fontColor(ThemeColors.textMuted).fontWeight(FontWeight.Medium)
        Row() { 
          Text(this.envHumidityMonitoringActive ? '🔍' : '💧').fontSize(12) 
        }
        .width(24)
        .height(24)
        .backgroundColor(this.envHumidityMonitoringActive ? '#0b593420' : '#3b82f615')
        .borderRadius(12)
        .justifyContent(FlexAlign.Center)
        .onClick(() => {
          this.toggleEnvHumidityMonitoring();
        })
      }
      .width('100%')
      .justifyContent(FlexAlign.SpaceBetween)
      .margin({ bottom: 12 })

      Column({ space: 4 }) {
        Row() {
          Text(`${this.envHumidity}`)
            .fontSize(22)
            .fontWeight(FontWeight.Bold)
            .fontColor(ThemeColors.textMain)
          Text('%')
            .fontSize(12)
            .fontColor(ThemeColors.textMuted)
            .margin({ left: 4, bottom: 4 })
        }
        .alignItems(VerticalAlign.Bottom)

        Text(`适宜: ${this.envHumidityMin}% - ${this.envHumidityMax}%`)
          .fontSize(10)
          .fontColor(ThemeColors.textMuted)
        
        Text(this.getStatusText(this.envHumidity, this.envHumidityMin, this.envHumidityMax))
          .fontSize(10)
          .fontColor(this.getStatusColor(this.envHumidity, this.envHumidityMin, this.envHumidityMax))
          .fontWeight(FontWeight.Bold)
          .margin({ top: 2 })
      }
      .alignItems(HorizontalAlign.Start)
    }
    .layoutWeight(1)
    .height(110)
    .backgroundColor(ThemeColors.card)
    .borderRadius(14)
    .padding(12)
    .border({ width: 1, color: this.envHumidityMonitoringActive ? ThemeColors.primary : ThemeColors.borderLight })
    .shadow({ radius: this.envHumidityMonitoringActive ? 10 : 8, color: this.envHumidityMonitoringActive ? 'rgba(11, 89, 52, 0.1)' : 'rgba(0,0,0,0.03)', offsetY: 2 })
  }

  // 光照强度卡片（带监测激活按钮）
  @Builder LightCard() {
    Column() {
      Row() {
        Text('光照强度').fontSize(12).fontColor(ThemeColors.textMuted).fontWeight(FontWeight.Medium)
        Row() { 
          Text(this.lightMonitoringActive ? '🔍' : '☀️').fontSize(12) 
        }
        .width(24)
        .height(24)
        .backgroundColor(this.lightMonitoringActive ? '#0b593420' : '#f9731615')
        .borderRadius(12)
        .justifyContent(FlexAlign.Center)
        .onClick(() => {
          this.toggleLightMonitoring();
        })
      }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 12 })

      Column({ space: 4 }) {
        Row() {
          Text(`${this.lightIntensity}`).fontSize(22).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('Lux').fontSize(12).fontColor(ThemeColors.textMuted).margin({ left: 4, bottom: 4 })
        }.alignItems(VerticalAlign.Bottom)

        Text(`适宜: ${this.lightMin} - ${this.lightMax} Lux`)
          .fontSize(10)
          .fontColor(ThemeColors.textMuted)
        
        Text(this.getStatusText(this.lightIntensity, this.lightMin, this.lightMax))
          .fontSize(10)
          .fontColor(this.getStatusColor(this.lightIntensity, this.lightMin, this.lightMax))
          .fontWeight(FontWeight.Bold)
          .margin({ top: 2 })
      }.alignItems(HorizontalAlign.Start).width('100%')
    }
    .layoutWeight(1)
    .height(110)
    .backgroundColor(ThemeColors.card)
    .borderRadius(14)
    .padding(12)
    .border({ width: 1, color: this.lightMonitoringActive ? ThemeColors.primary : ThemeColors.borderLight })
    .shadow({ radius: this.lightMonitoringActive ? 10 : 8, color: this.lightMonitoringActive ? 'rgba(11, 89, 52, 0.1)' : 'rgba(0,0,0,0.03)', offsetY: 2 })
  }

  // 土壤温度卡片
  @Builder SoilTempCard() {
    Column() {
      Row() {
        Text('土壤温度').fontSize(12).fontColor(ThemeColors.textMuted).fontWeight(FontWeight.Medium)
        Row() { 
          Text(this.soilTempMonitoringActive ? '🔍' : '🌡️').fontSize(12) 
        }
        .width(24)
        .height(24)
        .backgroundColor(this.soilTempMonitoringActive ? '#0b593420' : '#22c55e15')
        .borderRadius(12)
        .justifyContent(FlexAlign.Center)
        .onClick(() => {
          this.toggleSoilTempMonitoring();
        })
      }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 12 })

      Column({ space: 4 }) {
        Row() {
          Text(`${this.soilTemperature}`).fontSize(22).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('°C').fontSize(12).fontColor(ThemeColors.textMuted).margin({ left: 4, bottom: 4 })
        }.alignItems(VerticalAlign.Bottom)

        Text(`适宜: ${this.soilTempMin}°C - ${this.soilTempMax}°C`)
          .fontSize(10)
          .fontColor(ThemeColors.textMuted)
        
        Text(this.getStatusText(this.soilTemperature, this.soilTempMin, this.soilTempMax))
          .fontSize(10)
          .fontColor(this.getStatusColor(this.soilTemperature, this.soilTempMin, this.soilTempMax))
          .fontWeight(FontWeight.Bold)
          .margin({ top: 2 })
      }.alignItems(HorizontalAlign.Start).width('100%')
    }
    .layoutWeight(1)
    .height(110)
    .backgroundColor(ThemeColors.card)
    .borderRadius(14)
    .padding(12)
    .border({ width: 1, color: this.soilTempMonitoringActive ? ThemeColors.primary : ThemeColors.borderLight })
    .shadow({ radius: this.soilTempMonitoringActive ? 10 : 8, color: this.soilTempMonitoringActive ? 'rgba(11, 89, 52, 0.1)' : 'rgba(0,0,0,0.03)', offsetY: 2 })
  }

  // 土壤湿度卡片
  @Builder SoilMoistureCard() {
    Column() {
      Row() {
        Text('土壤湿度').fontSize(12).fontColor(ThemeColors.textMuted).fontWeight(FontWeight.Medium)
        Row() { 
          Text(this.soilMoistureMonitoringActive ? '🔍' : '💧').fontSize(12) 
        }
        .width(24)
        .height(24)
        .backgroundColor(this.soilMoistureMonitoringActive ? '#0b593420' : '#3b82f615')
        .borderRadius(12)
        .justifyContent(FlexAlign.Center)
        .onClick(() => {
          this.toggleSoilMoistureMonitoring();
        })
      }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 12 })

      Column({ space: 4 }) {
        Row() {
          Text(`${this.soilMoisture}`).fontSize(22).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('%').fontSize(12).fontColor(ThemeColors.textMuted).margin({ left: 4, bottom: 4 })
        }.alignItems(VerticalAlign.Bottom)

        Text(`适宜: ${this.soilMoistureMin}% - ${this.soilMoistureMax}%`)
          .fontSize(10)
          .fontColor(ThemeColors.textMuted)
        
        Text(this.getStatusText(this.soilMoisture, this.soilMoistureMin, this.soilMoistureMax))
          .fontSize(10)
          .fontColor(this.getStatusColor(this.soilMoisture, this.soilMoistureMin, this.soilMoistureMax))
          .fontWeight(FontWeight.Bold)
          .margin({ top: 2 })
      }.alignItems(HorizontalAlign.Start).width('100%')
    }
    .layoutWeight(1)
    .height(110)
    .backgroundColor(ThemeColors.card)
    .borderRadius(14)
    .padding(12)
    .border({ width: 1, color: this.soilMoistureMonitoringActive ? ThemeColors.primary : ThemeColors.borderLight })
    .shadow({ radius: this.soilMoistureMonitoringActive ? 10 : 8, color: this.soilMoistureMonitoringActive ? 'rgba(11, 89, 52, 0.1)' : 'rgba(0,0,0,0.03)', offsetY: 2 })
  }

  @Builder NPKCard() {
    Column({ space: 6 }) {
      Row({ space: 4 }) {
        Text('土壤微量元素含量').fontSize(12).fontColor(ThemeColors.textMuted).fontWeight(FontWeight.Medium).layoutWeight(1)
        Row() { 
          Text('🧪').fontSize(12) 
        }
        .width(24)
        .height(24)
        .backgroundColor('#9333ea15')
        .borderRadius(12)
        .justifyContent(FlexAlign.Center)
        .onClick(() => {
          setTimeout(() => {
            this.showNPKModal = true;
          }, 5000);
        })
      }.width('100%').justifyContent(FlexAlign.SpaceBetween)

      Column({ space: 6 }) {
        this.NPKBarSmall('N(氮)', this.npkN, '#c084fc')
        this.NPKBarSmall('P(磷)', this.npkP, '#a855f7')
        this.NPKBarSmall('K(钾)', this.npkK, '#9333ea')
      }.width('100%')
    }
    .layoutWeight(1)
    .height(110)
    .backgroundColor(ThemeColors.card)
    .borderRadius(14)
    .padding(12)
    .border({ width: 1, color: ThemeColors.borderLight })
    .shadow({ radius: 8, color: 'rgba(0,0,0,0.03)', offsetY: 2 })
  }

  @Builder NPKBarSmall(label: string, value: number, color: string) {
    Row({ space: 6 }) {
      Text(label).fontSize(10).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMuted).width(36)
      Progress({ value: value, total: 100, type: ProgressType.Linear }).color(color).backgroundColor(ThemeColors.borderLight).layoutWeight(1)
      Text(`${value}mg/kg`).fontSize(9).fontColor(ThemeColors.textMuted).width(48)
    }.width('100%')
  }

  @Builder CO2Card() {
    Column() {
      Row() {
        Text('CO₂ 浓度').fontSize(12).fontColor(ThemeColors.textMuted).fontWeight(FontWeight.Medium)
        Row() { 
          Text(this.co2MonitoringActive ? '🔍' : '☁️').fontSize(12) 
        }
        .width(24)
        .height(24)
        .backgroundColor(this.co2MonitoringActive ? '#0b593420' : '#14b8a615')
        .borderRadius(12)
        .justifyContent(FlexAlign.Center)
        .onClick(() => {
          this.toggleCO2Monitoring();
        })
      }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 12 })

      Column({ space: 4 }) {
        Row() {
          Text(`${this.co2Concentration}`).fontSize(22).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('ppm').fontSize(12).fontColor(ThemeColors.textMuted).margin({ left: 4, bottom: 4 })
        }.alignItems(VerticalAlign.Bottom)

        Text(`适宜: ${this.co2Min} - ${this.co2Max} ppm`)
          .fontSize(10)
          .fontColor(ThemeColors.textMuted)
        
        Text(this.getStatusText(this.co2Concentration, this.co2Min, this.co2Max))
          .fontSize(10)
          .fontColor(this.getStatusColor(this.co2Concentration, this.co2Min, this.co2Max))
          .fontWeight(FontWeight.Bold)
          .margin({ top: 2 })
      }.alignItems(HorizontalAlign.Start).width('100%')
    }
    .layoutWeight(1)
    .height(110)
    .backgroundColor(ThemeColors.card)
    .borderRadius(14)
    .padding(12)
    .border({ width: 1, color: this.co2MonitoringActive ? ThemeColors.primary : ThemeColors.borderLight })
    .shadow({ radius: this.co2MonitoringActive ? 10 : 8, color: this.co2MonitoringActive ? 'rgba(11, 89, 52, 0.1)' : 'rgba(0,0,0,0.03)', offsetY: 2 })
  }

  // 3. 设备控制面板
  @Builder DeviceControlSection() {
    Column({ space: 12 }) {
      Row() {
        Text('设备快捷控制').fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
        Row({ space: 4 }) {
          Circle({ width: 6, height: 6 }).fill(ThemeColors.primary)
          Text(`${this.apiDevices.length}台在线`).fontSize(10).fontColor(ThemeColors.primary)
        }
      }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding({ left: 4, right: 4 })

      Scroll() {
        Row({ space: 12 }) {
          this.ControlCard('遮光帘', '🪟')
          this.ControlCard('水泵', '💧')
          this.ControlCard('风扇', '🌀')
          this.ControlCard('补光灯', '💡')
          this.ControlCard('加热棒', '🌡️')
        }.padding({ right: 16 })
      }
      .scrollable(ScrollDirection.Horizontal)
      .scrollBar(BarState.Off)
      .width('100%')
      .friction(0.6)
    }.padding({ left: 16, right: 16 })
  }

  // 获取设备动画状态
  getDeviceScale(name: string): number {
    if (name === '遮光帘') return this.curtainScale;
    if (name === '水泵') return this.pumpScale;
    if (name === '风扇') return this.fanScale;
    if (name === '补光灯') return this.lightScale;
    if (name === '加热棒') return this.heaterScale;
    return 1;
  }

  getDeviceOpacity(name: string): number {
    if (name === '遮光帘') return this.curtainOpacity;
    if (name === '水泵') return this.pumpOpacity;
    if (name === '风扇') return this.fanOpacity;
    if (name === '补光灯') return this.lightOpacity;
    if (name === '加热棒') return this.heaterOpacity;
    return 1;
  }

  getDeviceRotation(name: string): number {
    return name === '风扇' ? this.fanRotation : 0;
  }

  // 获取设备开关状态
  getDeviceIsOn(name: string): boolean {
    if (name === '遮光帘') return this.isCurtainOn;
    if (name === '水泵') return this.isPumpOn;
    if (name === '风扇') return this.isFanOn;
    if (name === '补光灯') return this.isLightOn;
    if (name === '加热棒') return this.isHeaterOn;
    return false;
  }

  // 设置设备开关状态
  setDeviceIsOn(name: string, value: boolean): void {
    if (name === '遮光帘') this.isCurtainOn = value;
    else if (name === '水泵') this.isPumpOn = value;
    else if (name === '风扇') this.isFanOn = value;
    else if (name === '补光灯') this.isLightOn = value;
    else if (name === '加热棒') this.isHeaterOn = value;
  }

  @Builder ControlCard(name: string, icon: string) {
    Column({ space: 10 }) {
      Stack() {
        Circle({ width: 44, height: 44 })
          .fill(this.getDeviceIsOn(name) ? 'rgba(11, 89, 52, 0.15)' : ThemeColors.base)

        Text(this.getDeviceIsOn(name) ? icon : '⏸️')
          .fontSize(22)
          .rotate({ angle: this.getDeviceIsOn(name) ? this.getDeviceRotation(name) : 0, centerX: '50%', centerY: '50%' })
          .opacity(this.getDeviceIsOn(name) ? 1 : 0.5)

        Circle({ width: 10, height: 10 })
          .fill(this.getDeviceIsOn(name) ? '#22c55e' : ThemeColors.textMuted)
          .border({ width: 2, color: '#fff' })
          .position({ x: 32, y: 2 })
      }

      Text(name)
        .fontSize(13)
        .fontWeight(FontWeight.Medium)
        .fontColor(this.getDeviceIsOn(name) ? ThemeColors.primary : ThemeColors.textMain)

      Text(this.getDeviceIsOn(name) ? '运行中' : '已停止')
        .fontSize(10)
        .fontWeight(FontWeight.Medium)
        .fontColor(this.getDeviceIsOn(name) ? '#22c55e' : ThemeColors.textMuted)
        .backgroundColor(this.getDeviceIsOn(name) ? 'rgba(34, 197, 94, 0.1)' : 'transparent')
        .padding({ left: 8, right: 8, top: 2, bottom: 2 })
        .borderRadius(10)

      Toggle({ type: ToggleType.Switch, isOn: this.getDeviceIsOn(name) })
        .selectedColor(ThemeColors.primary)
        .switchPointColor('#fff')
        .width(40).height(22)
        .onChange((newValue: boolean) => {
          animateTo({ duration: 150, curve: Curve.EaseInOut }, () => {
            if (name === '遮光帘') {
              this.curtainScale = 0.95;
              this.curtainOpacity = 0.8;
            } else if (name === '水泵') {
              this.pumpScale = 0.95;
              this.pumpOpacity = 0.8;
            } else if (name === '风扇') {
              this.fanScale = 0.95;
              this.fanOpacity = 0.8;
            } else if (name === '补光灯') {
              this.lightScale = 0.95;
              this.lightOpacity = 0.8;
            } else if (name === '加热棒') {
              this.heaterScale = 0.95;
              this.heaterOpacity = 0.8;
            }
          });

          setTimeout(() => {
            animateTo({ duration: 200, curve: Curve.EaseOut }, () => {
              if (name === '遮光帘') {
                this.curtainScale = 1;
                this.curtainOpacity = 1;
              } else if (name === '水泵') {
                this.pumpScale = 1;
                this.pumpOpacity = 1;
              } else if (name === '风扇') {
                this.fanScale = 1;
                this.fanOpacity = 1;
              } else if (name === '补光灯') {
                this.lightScale = 1;
                this.lightOpacity = 1;
              } else if (name === '加热棒') {
                this.heaterScale = 1;
                this.heaterOpacity = 1;
              }
            });
          }, 150);

          this.setDeviceIsOn(name, newValue);
          this.sendDeviceCommand(name, newValue);

          // 调用监测检查方法
          this.checkLightMonitoring();
          this.checkEnvTempMonitoring();
          this.checkEnvHumidityMonitoring();
          this.checkCO2Monitoring();
          this.checkSoilTempMonitoring();
          this.checkSoilMoistureMonitoring();
        })
    }
    .width(85)
    .height(130)
    .backgroundColor(ThemeColors.card)
    .borderRadius(16)
    .justifyContent(FlexAlign.Center)
    .border({ width: 1, color: this.getDeviceIsOn(name) ? 'rgba(11, 89, 52, 0.2)' : ThemeColors.borderLight })
    .shadow({ radius: this.getDeviceIsOn(name) ? 15 : 10, color: this.getDeviceIsOn(name) ? 'rgba(11, 89, 52, 0.08)' : 'rgba(0,0,0,0.03)', offsetY: this.getDeviceIsOn(name) ? 4 : 2 })
    .scale({ x: this.getDeviceScale(name), y: this.getDeviceScale(name) })
    .opacity(this.getDeviceOpacity(name))
    .onClick(() => {
      animateTo({ duration: 100, curve: Curve.EaseIn }, () => {
        if (name === '遮光帘') {
          this.curtainScale = 0.92;
        } else if (name === '水泵') {
          this.pumpScale = 0.92;
        } else if (name === '风扇') {
          this.fanScale = 0.92;
        } else if (name === '补光灯') {
          this.lightScale = 0.92;
        } else if (name === '加热棒') {
          this.heaterScale = 0.92;
        }
      });

      setTimeout(() => {
        animateTo({ duration: 200, curve: Curve.EaseOut }, () => {
          if (name === '遮光帘') {
            this.curtainScale = 1;
          } else if (name === '水泵') {
            this.pumpScale = 1;
          } else if (name === '风扇') {
            this.fanScale = 1;
          } else if (name === '补光灯') {
            this.lightScale = 1;
          } else if (name === '加热棒') {
            this.heaterScale = 1;
          }
        });
      }, 100);
    })
  }

  // 4. 植物生长监测
  @Builder PlantGrowthSection() {
    Column({ space: 12 }) {
      Row() {
        Text('植物生长监测').fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
        Text('详情 >').fontSize(10).fontColor(ThemeColors.textMuted)
      }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding({ left: 4, right: 4 })

      Scroll() {
        Row({ space: 12 }) {
          this.PlantCard('🌿', '白萝卜', '4号大棚 · A区', '生长期', ThemeColors.primary, 1) // 1代表第2个节点(生长期)
          this.PlantCard('🍅', '普罗旺斯番茄', '2号大棚 · B区', '开花期', '#f97316', 2) // 2代表第3个节点(开花期)
        }
      }.scrollable(ScrollDirection.Horizontal).scrollBar(BarState.Off)
    }.padding({ left: 16, right: 16 })
  }

  @Builder PlantCard(emoji: string, name: string, loc: string, status: string, color: string, activeIndex: number) {
    Column() {
      Row() {
        Row({ space: 8 }) {
          Row() { Text(emoji).fontSize(16) }.width(32).height(32).backgroundColor(`${color}15`).borderRadius(8).justifyContent(FlexAlign.Center)
          Column() {
            Text(name).fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
            Text(loc).fontSize(10).fontColor(ThemeColors.textMuted)
          }.alignItems(HorizontalAlign.Start)
        }
        Text(status).fontSize(10).fontWeight(FontWeight.Bold).fontColor(color).backgroundColor(`${color}15`).padding({ left: 8, right: 8, top: 4, bottom: 4 }).borderRadius(4)
      }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 16 })

      Stack({ alignContent: Alignment.Start }) {
        Row().width('100%').height(2).backgroundColor(ThemeColors.borderLight)
        Row().width(`${activeIndex * 25 + 10}%`).height(2).backgroundColor(color)

        Row() {
          this.StageDot('种植期', activeIndex >= 0, activeIndex === 0, color)
          this.StageDot('生长期', activeIndex >= 1, activeIndex === 1, color)
          this.StageDot('开花/高发', activeIndex >= 2, activeIndex === 2, color)
          this.StageDot('结果期', activeIndex >= 3, activeIndex === 3, color)
          this.StageDot('挂果期', activeIndex >= 4, activeIndex === 4, color)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween)
      }.width('100%')
    }
    .width(280).backgroundColor(ThemeColors.card).borderRadius(16).padding(16)
    .border({ width: 1, color: ThemeColors.borderLight }).shadow({ radius: 10, color: 'rgba(0,0,0,0.03)', offsetY: 2 })
    .onClick(() => {
      this.selectedPlant = name;
      this.showPlantDetailModal = true;
    })
  }

  @Builder StageDot(name: string, isPassed: boolean, isActive: boolean, color: string) {
    Column({ space: 6 }) {
      Circle({ width: 16, height: 16 })
        .fill(isActive ? color : (isPassed ? color : ThemeColors.borderLight))
        .border({ width: 3, color: '#fff' })
        .shadow(isActive ? { radius: 4, color: color, offsetX: 0, offsetY: 0 } : { radius: 0, color: 'transparent' })
        .onClick(() => {
          this.selectedStage = name;
          this.showStageDetailModal = true;
        })

      Text(name)
        .fontSize(9)
        .fontWeight(isActive ? FontWeight.Bold : FontWeight.Normal)
        .fontColor(isActive ? color : ThemeColors.textMuted)
    }.width(40)
  }

  // 5. 农事待办 (Alarms)
  @Builder TodoAlarmsSection() {
    Column({ space: 12 }) {
      Row() {
        Text('农事待办').fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
        Text(`${this.alarmCount}项异常报警`).fontSize(10).fontWeight(FontWeight.Bold).fontColor(ThemeColors.danger).backgroundColor('#fee2e2').padding({ left: 8, right: 8, top: 2, bottom: 2 }).borderRadius(10)
      }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding({ left: 4, right: 4 })

      Column({ space: 12 }) {
        // 卡片 1 (橘色警告)
        Column({ space: 12 }) {
          Row({ space: 12 }) {
            Row() { Text('💧').fontSize(16) }.width(32).height(32).backgroundColor('#fff7ed').borderRadius(16).justifyContent(FlexAlign.Center)
            Column({ space: 6 }) {
              Row() {
                Text('水分不足预警').fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
                Row({ space: 4 }) {
                  Text('10:42').fontSize(10).fontColor(ThemeColors.textMuted).fontFamily('monospace')
                  Text(this.isWarningExpanded ? '▲' : '▼').fontSize(10).fontColor(ThemeColors.textMuted)
                }
              }.width('100%').justifyContent(FlexAlign.SpaceBetween)

              if (this.isWarningExpanded) {
                Text('检测到 1区土壤含水量低至15%，低于萝卜生长期适宜阈值(30%)。').fontSize(11).fontColor(ThemeColors.textMuted).lineHeight(16)

                Row({ space: 8 }) {
                  Button(this.isProcessingPump ? '处理中...' : '智能开启水泵')
                    .fontSize(11).fontWeight(FontWeight.Medium).fontColor('#fff')
                    .backgroundColor(this.isProcessingPump ? ThemeColors.accent : ThemeColors.primary)
                    .height(28)
                    .scale({ x: this.pumpBtnScale, y: this.pumpBtnScale })
                    .onClick(() => {
                      animateTo({ duration: 100 }, () => { this.pumpBtnScale = 0.95; });
                      setTimeout(() => {
                        animateTo({ duration: 100 }, () => { this.pumpBtnScale = 1; });
                      }, 100);
                      this.isProcessingPump = true;
                      setTimeout(() => {
                        this.isProcessingPump = false;
                        this.isPumpOn = true;
                        promptAction.showToast({ message: '水泵已开启 ✓' });
                      }, 1000)
                    })
                  Button('查看详情').fontSize(11).fontColor(ThemeColors.textMain).backgroundColor(ThemeColors.base).border({ width: 1, color: ThemeColors.borderLight }).height(28)
                    .scale({ x: this.detailBtnScale, y: this.detailBtnScale })
                    .onClick(() => {
                      animateTo({ duration: 100 }, () => { this.detailBtnScale = 0.95; });
                      setTimeout(() => {
                        animateTo({ duration: 100 }, () => { this.detailBtnScale = 1; });
                      }, 100);
                      this.showWarningDetailModal = true;
                    })
                }.margin({ top: 4 })
              }
            }.layoutWeight(1).alignItems(HorizontalAlign.Start)
          }.width('100%').backgroundColor(ThemeColors.card).borderRadius(12).padding(12).borderWidth({ left: 4, top: 1, right: 1, bottom: 1 }).borderColor({ left: ThemeColors.warning, top: ThemeColors.borderLight, right: ThemeColors.borderLight, bottom: ThemeColors.borderLight }).shadow({ radius: 5, color: 'rgba(0,0,0,0.02)' })
        }
        .width('100%')
        .onClick(() => {
          animateTo({ duration: 300 }, () => {
            this.isWarningExpanded = !this.isWarningExpanded;
          });
        })

        // 卡片 2 (红色警告)
        Row({ space: 12 }) {
          Stack() {
            Row() { Text('📷').fontSize(16) }.width(32).height(32).backgroundColor('#fef2f2').borderRadius(16).justifyContent(FlexAlign.Center)
            Circle({ width: 10, height: 10 }).fill(ThemeColors.danger).border({ width: 2, color: '#fff' }).position({ x: 24, y: 0 })
          }
          Column({ space: 6 }) {
            Row() {
              Row({ space: 4 }) {
                Text('视觉分析报警').fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
                Text('高优').fontSize(8).fontColor(ThemeColors.danger).backgroundColor('#fee2e2').border({ width: 1, color: '#fecaca'}).padding({ left: 4, right: 4, top: 1, bottom: 1 }).borderRadius(4)
              }
              Row({ space: 4 }) {
                Text('08:15').fontSize(10).fontColor(ThemeColors.textMuted).fontFamily('monospace')
                Text(this.isDiagnosisExpanded ? '▲' : '▼').fontSize(10).fontColor(ThemeColors.textMuted)
              }
            }.width('100%').justifyContent(FlexAlign.SpaceBetween)

            if (this.isDiagnosisExpanded) {
              Text('AI视觉模型 (YOLOv11) 在2区发现疑似霜霉病斑点，置信度 89%。').fontSize(11).fontColor(ThemeColors.textMuted).lineHeight(16)

              Row({ space: 8 }) {
                Button('查看诊断图片').fontSize(11).fontWeight(FontWeight.Medium).fontColor(ThemeColors.danger).backgroundColor('#fff').border({ width: 1, color: '#fecaca' }).height(28)
                  .scale({ x: this.diagImageBtnScale, y: this.diagImageBtnScale })
                  .onClick(() => {
                    animateTo({ duration: 100 }, () => { this.diagImageBtnScale = 0.95; });
                    setTimeout(() => {
                      animateTo({ duration: 100 }, () => { this.diagImageBtnScale = 1; });
                    }, 100);
                    this.showDiagnosisImage = true;
                  })
                Button('标记完成').fontSize(11).fontColor(ThemeColors.textMain).backgroundColor(ThemeColors.base).border({ width: 1, color: ThemeColors.borderLight }).height(28)
                  .scale({ x: this.markDoneBtnScale, y: this.markDoneBtnScale })
                  .onClick(() => {
                    animateTo({ duration: 100 }, () => { this.markDoneBtnScale = 0.95; });
                    setTimeout(() => {
                      animateTo({ duration: 100 }, () => { this.markDoneBtnScale = 1; });
                    }, 100);
                    if (this.alarmCount > 0) {
                      this.alarmCount--;
                      this.showToast('已标记完成 ✓');
                    }
                  })
              }.margin({ top: 4 })
            }
          }.layoutWeight(1).alignItems(HorizontalAlign.Start)
        }.width('100%').backgroundColor(ThemeColors.card).borderRadius(12).padding(12).borderWidth({ left: 4, top: 1, right: 1, bottom: 1 }).borderColor({ left: ThemeColors.danger, top: ThemeColors.borderLight, right: ThemeColors.borderLight, bottom: ThemeColors.borderLight }).shadow({ radius: 5, color: 'rgba(0,0,0,0.02)' })
        .onClick(() => {
          animateTo({ duration: 300 }, () => {
            this.isDiagnosisExpanded = !this.isDiagnosisExpanded;
          });
        })
      }
    }.padding({ left: 16, right: 16 })
  }

  // 6. 底部导航栏
  // @Builder BottomNav() {
  //   Row() {
  //     this.NavItem('首页', '🏠', true)
  //     this.NavItem('控制', '🎛️', false)
  //
  //     // 中间的 AI 悬浮按钮
  //     Column() {
  //       Stack() {
  //         Circle({ width: 48, height: 48 }).fill(ThemeColors.primary)
  //         Text('🧠').fontSize(20)
  //       }
  //       .borderWidth(4).borderColor(ThemeColors.card).borderRadius(28)
  //       .shadow({ radius: 10, color: 'rgba(11, 89, 52, 0.4)', offsetY: 4 })
  //       Text('AI大脑').fontSize(10).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMuted).margin({ top: 4 })
  //     }
  //     .offset({ y: -20 })
  //
  //     this.NavItem('生命周期', '🌱', false)
  //     this.NavItem('设置', '⚙️', false)
  //   }
  //   .width('100%').height(64).backgroundColor('rgba(255, 255, 255, 0.95)').backdropBlur(20)
  //   .border({ width: { top: 1 }, color: ThemeColors.borderLight })
  //   .justifyContent(FlexAlign.SpaceAround).alignItems(VerticalAlign.Bottom).padding({ bottom: 8 })
  //   .zIndex(50)
  // }

  // 导航项动画状态
  @State navScale: number = 1;

  @Builder NavItem(title: string, emoji: string, isActive: boolean) {
    Column({ space: 4 }) {
      Text(emoji)
        .fontSize(isActive ? 26 : 24)
        .opacity(isActive ? 1 : 0.5)
        .scale({ x: isActive ? 1.1 : 1, y: isActive ? 1.1 : 1 })
        .animation({ duration: 250, curve: Curve.EaseInOut })

      Text(title)
        .fontSize(10)
        .fontWeight(isActive ? FontWeight.Bold : FontWeight.Medium)
        .fontColor(isActive ? ThemeColors.primary : ThemeColors.textMuted)
        .animation({ duration: 250, curve: Curve.EaseInOut })

      // 选中指示器
      if (isActive) {
        Row()
          .width(20)
          .height(3)
          .backgroundColor(ThemeColors.primary)
          .borderRadius(2)
          .animation({ duration: 250, curve: Curve.EaseOut })
      }
    }
    .padding({ bottom: 4 })
    .scale({ x: this.navScale, y: this.navScale })
    .onClick(() => {
      // 点击缩放动画
      animateTo({ duration: 100, curve: Curve.EaseIn }, () => {
        this.navScale = 0.9;
      });

      setTimeout(() => {
        animateTo({ duration: 200, curve: Curve.EaseOut }, () => {
          this.navScale = 1;
        });
      }, 100);

      this.selectedNav = title;

      // 页面切换动画提示
      if (title === 'AI协作') {
        this.showToast('AI大脑启动中...');
      } else {
        this.showToast(`已切换到${title}`);
      }
    })
  }

  @Builder BottomNav() {
    Row() {
      this.NavItem('首页', '🏠', this.selectedNav === '首页')
      this.NavItem('控制', '🎛️', this.selectedNav === '控制')

      Column() {
        Stack() {
          Circle({ width: 48, height: 48 }).fill(ThemeColors.primary)
            .scale({ x: this.aiPulseScale, y: this.aiPulseScale })
          Text('🧠').fontSize(20)
        }
        .borderWidth(4).borderColor(ThemeColors.card).borderRadius(28)
        .shadow({ radius: 10, color: 'rgba(11, 89, 52, 0.4)', offsetY: 4 })
        .onClick(() => {
          animateTo({ duration: 300 }, () => { this.aiPulseScale = 1.2; });
          setTimeout(() => {
            animateTo({ duration: 300 }, () => { this.aiPulseScale = 1; });
          }, 300);
          this.showToast('AI大脑启动中...');
        })
        Text('AI大脑').fontSize(10).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMuted).margin({ top: 4 })
      }
      .offset({ y: -20 })

      this.NavItem('生命周期', '🌱', this.selectedNav === '生命周期')
      this.NavItem('设置', '⚙️', this.selectedNav === '设置')
    }
    .width('100%').height(64).backgroundColor('rgba(255, 255, 255, 0.95)').backdropBlur(20)
    .border({ width: { top: 1 }, color: ThemeColors.borderLight })
    .justifyContent(FlexAlign.SpaceAround).alignItems(VerticalAlign.Bottom).padding({ bottom: 8 })
    .zIndex(50)
  }

  // ================= 弹窗组件 =================

  // 土壤微量元素含量弹窗
  @Builder NPKModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.5)').onClick(() => this.showNPKModal = false)
      Column({ space: 20 }) {
        Row() {
          Text('土壤微量元素含量').fontSize(18).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('✕').fontSize(18).fontColor(ThemeColors.textMuted).onClick(() => this.showNPKModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween)

        Column({ space: 12 }) {
          Row() {
            Text('当前含量：').fontSize(14).fontColor(ThemeColors.textMuted)
            Text(`氮 ${this.npkN}mg/kg`).fontSize(14).fontColor(ThemeColors.textMain).fontWeight(FontWeight.Bold)
          }
          Row() {
            Text('').fontSize(14).fontColor('transparent')
            Text(`磷 ${this.npkP}mg/kg`).fontSize(14).fontColor(ThemeColors.textMain).fontWeight(FontWeight.Bold)
          }
          Row() {
            Text('').fontSize(14).fontColor('transparent')
            Text(`钾 ${this.npkK}mg/kg`).fontSize(14).fontColor(ThemeColors.textMain).fontWeight(FontWeight.Bold)
          }
        }
        .width('100%')
        .padding(16)
        .backgroundColor(ThemeColors.primaryLight)
        .borderRadius(12)

        Column({ space: 8 }) {
          Text('健康微量元素含量范围：').fontSize(13).fontColor(ThemeColors.textMuted).fontWeight(FontWeight.Bold)
          Text('氮 140-225 mg/kg').fontSize(12).fontColor(ThemeColors.textMuted)
          Text('磷 57-100 mg/kg').fontSize(12).fontColor(ThemeColors.textMuted)
          Text('钾 106-150 mg/kg').fontSize(12).fontColor(ThemeColors.textMuted)
        }
        .width('100%')
        .padding(12)
        .backgroundColor('#f0f9ff')
        .borderRadius(12)

        Row() {
          Text('⚠️').fontSize(16)
          Text('警告：土壤中微量元素含量不宜生长').fontSize(13).fontColor(ThemeColors.danger).fontWeight(FontWeight.Bold)
        }.width('100%').justifyContent(FlexAlign.Center).padding(12).backgroundColor('#fef2f2').borderRadius(12)
      }
      .width('85%')
      .backgroundColor(ThemeColors.card)
      .borderRadius(20)
      .padding(24)
      .shadow({ radius: 30, color: 'rgba(0,0,0,0.2)' })
    }
    .width('100%')
    .height('100%')
    .zIndex(100)
  }

  // 其他环境参数弹窗
  @Builder OtherEnvModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.5)').onClick(() => this.showOtherEnvModal = false)

      Column() {
        Row() {
          Text('其他环境参数').fontSize(18).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('✕').fontSize(18).fontColor(ThemeColors.textMuted).onClick(() => this.showOtherEnvModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16)

        Scroll() {
          Column({ space: 12 }) {
            // 第一行：光辐射 + 日光积分
            Row({ space: 8 }) {
              this.OtherEnvCard('有效光辐射',
                this.latestMetrics ? this.formatMetric(this.latestMetrics.par_val_umol, 1) : '450',
                'μmol/m²·s', '微摩尔/平方米·秒')
              this.OtherEnvCard('日光积分',
                this.latestMetrics ? this.formatMetric(this.latestMetrics.dli_daily_mol, 1) : '20',
                'mol/m²·d', '摩尔/平方米·天')
            }.width('100%')

            // 第二行：有效积温 + 蒸气压亏损
            Row({ space: 8 }) {
              this.OtherEnvCard('有效积温',
                this.latestMetrics ? this.formatMetric(this.latestMetrics.current_accumulated_gdd_c, 0) : '1000',
                '°C·d', '℃·天')
              this.OtherEnvCard('蒸气压亏损',
                this.latestMetrics ? this.formatMetric(this.latestMetrics.vpd_val_kpa, 2) : '1.0',
                'kPa', '千帕')
            }.width('100%')

            // 第三行：碳汇速率 + 光利用率
            Row({ space: 8 }) {
              this.OtherEnvCard('碳汇速率',
                this.latestMetrics ? this.formatMetric(this.latestMetrics.carbon_sink_rate_g_hr, 2) : '22',
                'g C/hr', '克碳/小时')
              this.OtherEnvCard('光利用率评分',
                this.latestMetrics ? this.formatMetric(this.latestMetrics.lue_score_pct, 1) : '0.80',
                '%', '无量纲')
            }.width('100%')

            // 第四行：能效比 + 养分消耗
            Row({ space: 8 }) {
              this.OtherEnvCard('设备稳态能效比',
                this.latestMetrics ? this.formatMetric(this.latestMetrics.energy_optimization_index, 2) : '3.8',
                '', '无量纲')
              this.OtherEnvCardWithStatus('土壤养分消耗量',
                this.latestMetrics ? this.formatMetric(this.latestMetrics.nutrient_consumption_rate_mg, 0) : '156',
                'mg/kg', '毫克/千克', '正常')
            }.width('100%')
          }.padding(16)
        }.width('100%').layoutWeight(1).scrollBar(BarState.Auto)
      }.width('90%').height('80%').backgroundColor(ThemeColors.card).borderRadius(20)
    }.width('100%').height('100%').zIndex(100)
  }

  // 其他环境参数卡片
  @Builder OtherEnvCard(title: string, value: string, unit: string, description: string) {
    Column({ space: 8 }) {
      Text(title).fontSize(12).fontColor(ThemeColors.textMuted).width('100%')

      Row({ space: 4 }) {
        Text(value).fontSize(24).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
        if (unit) {
          Text(unit).fontSize(10).fontColor(ThemeColors.textMuted)
        }
      }.width('100%').alignItems(VerticalAlign.Bottom)

      if (description) {
        Text(description).fontSize(10).fontColor(ThemeColors.textMuted).width('100%')
      }
    }
    .width('100%')
    .padding(12)
    .backgroundColor(ThemeColors.card)
    .borderRadius(12)
    .borderWidth(1)
    .borderColor(ThemeColors.borderLight)
    .layoutWeight(1)
    .alignItems(HorizontalAlign.Start)
  }

  // 其他环境参数卡片（带状态标签）
  @Builder OtherEnvCardWithStatus(title: string, value: string, unit: string, description: string, status: string) {
    Column({ space: 8 }) {
      Text(title).fontSize(12).fontColor(ThemeColors.textMuted).width('100%')

      Row({ space: 4 }) {
        Text(value).fontSize(24).fontWeight(FontWeight.Bold).fontColor(ThemeColors.warning)
        if (unit) {
          Text(unit).fontSize(10).fontColor(ThemeColors.textMuted)
        }
      }.width('100%').alignItems(VerticalAlign.Bottom)

      if (description) {
        Text(description).fontSize(10).fontColor(ThemeColors.textMuted).width('100%')
      }

      Row() {
        Text(status)
          .fontSize(11)
          .fontColor('#ffffff')
          .backgroundColor(ThemeColors.warning)
          .padding({ left: 8, right: 8, top: 2, bottom: 2 })
          .borderRadius(4)
      }.width('100%').margin({ top: 4 })
    }
    .width('100%')
    .padding(12)
    .backgroundColor('#fff7ed')
    .borderRadius(12)
    .borderWidth(1)
    .borderColor('#fed7aa')
    .layoutWeight(1)
    .alignItems(HorizontalAlign.Start)
  }

  @Builder GreenhouseSelectModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => this.showGreenhouseSelectModal = false)
      Column() {
        Row() {
          Text('选择大棚').fontSize(16).fontWeight(FontWeight.Bold)
          Text('✕').fontSize(16).fontColor(ThemeColors.textMuted).onClick(() => this.showGreenhouseSelectModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16).borderWidth({ bottom: 1 }).borderColor(ThemeColors.borderLight)
        Column({ space: 12 }) {
          this.GreenhouseOption('4号大棚', '萝卜区', true)
          this.GreenhouseOption('3号大棚', '生菜区', false)
          this.GreenhouseOption('2号大棚', '番茄区', false)
          this.GreenhouseOption('1号大棚', '黄瓜区', false)
        }.padding(16)
      }.width('80%').backgroundColor(ThemeColors.card).borderRadius(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder GreenhouseOption(name: string, area: string, isSelected: boolean) {
    Row() {
      Row({ space: 12 }) {
        Text('🏡').fontSize(24)
        Column() { Text(name).fontSize(14).fontWeight(FontWeight.Medium); Text(area).fontSize(10).fontColor(ThemeColors.textMuted) }.alignItems(HorizontalAlign.Start)
      }
      if (isSelected) { Text('✓').fontSize(16).fontColor(ThemeColors.primary) }
    }.width('100%').padding(12).backgroundColor(isSelected ? ThemeColors.primaryLight : 'transparent').borderRadius(8)
    .onClick(() => {
      this.showToast(`已切换到${name}${area}`);
      this.showGreenhouseSelectModal = false;
    })
  }

  @Builder EnvDetailModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => this.showEnvDetailModal = false)
      Column() {
        Row() {
          Text(this.selectedEnvType + '详情').fontSize(16).fontWeight(FontWeight.Bold)
          Text('✕').fontSize(16).fontColor(ThemeColors.textMuted).onClick(() => this.showEnvDetailModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16).borderWidth({ bottom: 1 }).borderColor(ThemeColors.borderLight)
        Column({ space: 16 }) {
          Row() { Text('📈').fontSize(40); Text('历史趋势').fontSize(14).fontColor(ThemeColors.textMuted) }.alignItems(VerticalAlign.Center).width('100%').padding({ top: 20 })
          Column({ space: 8 }) {
            if (this.selectedEnvType === '光照强度') {
              Row() { Text('当前值').fontSize(12).fontColor(ThemeColors.textMuted); Text(`${this.lightIntensity} klx`).fontSize(18).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
              Row() { Text('适宜范围').fontSize(12).fontColor(ThemeColors.textMuted); Text('25-40 klx').fontSize(14) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
              Row() { Text('状态').fontSize(12).fontColor(ThemeColors.textMuted); Text(this.lightIntensity >= 25 && this.lightIntensity <= 40 ? '适宜' : '异常').fontSize(14).fontColor(this.lightIntensity >= 25 && this.lightIntensity <= 40 ? ThemeColors.primary : ThemeColors.danger).backgroundColor(this.lightIntensity >= 25 && this.lightIntensity <= 40 ? ThemeColors.primaryLight : '#fee2e2').padding({ left: 8, right: 8, top: 2, bottom: 2 }) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
            } else if (this.selectedEnvType === '土壤水分') {
              Row() { Text('当前值').fontSize(12).fontColor(ThemeColors.textMuted); Text(`${this.soilMoisture}%`).fontSize(18).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
              Row() { Text('适宜范围').fontSize(12).fontColor(ThemeColors.textMuted); Text('30-50%').fontSize(14) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
              Row() { Text('状态').fontSize(12).fontColor(ThemeColors.textMuted); Text(this.soilMoisture >= 30 && this.soilMoisture <= 50 ? '适宜' : '异常').fontSize(14).fontColor(this.soilMoisture >= 30 && this.soilMoisture <= 50 ? ThemeColors.primary : ThemeColors.danger).backgroundColor(this.soilMoisture >= 30 && this.soilMoisture <= 50 ? ThemeColors.primaryLight : '#fee2e2').padding({ left: 8, right: 8, top: 2, bottom: 2 }) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
            } else if (this.selectedEnvType === '氮磷钾含量') {
              Row() { Text('N含量').fontSize(12).fontColor(ThemeColors.textMuted); Text(`${this.npkN}%`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
              Row() { Text('P含量').fontSize(12).fontColor(ThemeColors.textMuted); Text(`${this.npkP}%`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
              Row() { Text('K含量').fontSize(12).fontColor(ThemeColors.textMuted); Text(`${this.npkK}%`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
            } else {
              Row() { Text('当前值').fontSize(12).fontColor(ThemeColors.textMuted); Text(`${this.co2Concentration} ppm`).fontSize(18).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
              Row() { Text('适宜范围').fontSize(12).fontColor(ThemeColors.textMuted); Text('400-1000 ppm').fontSize(14) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
              Row() { Text('状态').fontSize(12).fontColor(ThemeColors.textMuted); Text(this.co2Concentration >= 400 && this.co2Concentration <= 1000 ? '适宜' : '异常').fontSize(14).fontColor(this.co2Concentration >= 400 && this.co2Concentration <= 1000 ? ThemeColors.primary : ThemeColors.danger).backgroundColor(this.co2Concentration >= 400 && this.co2Concentration <= 1000 ? ThemeColors.primaryLight : '#fee2e2').padding({ left: 8, right: 8, top: 2, bottom: 2 }) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
            }
          }.width('100%').padding(16).backgroundColor(ThemeColors.base).borderRadius(8)
          Column({ space: 8 }) {
            Text('阈值设置').fontSize(12).fontColor(ThemeColors.textMuted).width('100%')
            Row() { Text('最小值').fontSize(12); TextInput({ placeholder: '25' }).layoutWeight(1).height(32) }.width('100%')
            Row() { Text('最大值').fontSize(12); TextInput({ placeholder: '40' }).layoutWeight(1).height(32) }.width('100%')
          }.width('100%').padding(16).backgroundColor(ThemeColors.base).borderRadius(8)
        }.padding(16)
        Button('保存设置').width('100%').backgroundColor(ThemeColors.primary).height(40).margin({ top: 16 })
          .onClick(() => { this.showToast('设置已保存'); this.showEnvDetailModal = false; })
      }.width('85%').backgroundColor(ThemeColors.card).borderRadius(16).padding(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder DeviceDetailModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => this.showDeviceDetailModal = false)
      Column() {
        Row() {
          Text(this.selectedDevice + '控制').fontSize(16).fontWeight(FontWeight.Bold)
          Text('✕').fontSize(16).fontColor(ThemeColors.textMuted).onClick(() => this.showDeviceDetailModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16).borderWidth({ bottom: 1 }).borderColor(ThemeColors.borderLight)
        Column({ space: 16 }) {
          Row() {
            Text('设备状态').fontSize(14)
            Toggle({ type: ToggleType.Switch, isOn: this.selectedDevice === '遮光帘' ? this.isCurtainOn : this.selectedDevice === '水泵' ? this.isPumpOn : this.isFanOn })
              .selectedColor(ThemeColors.primary)
              .onChange((isOn: boolean) => {
                if (this.selectedDevice === '遮光帘') this.isCurtainOn = isOn;
                else if (this.selectedDevice === '水泵') this.isPumpOn = isOn;
                else this.isFanOn = isOn;
                this.showToast(this.selectedDevice + (isOn ? '已开启' : '已关闭'));
              })
          }.width('100%').justifyContent(FlexAlign.SpaceBetween)
          if (this.selectedDevice === '遮光帘') {
            Column() { Text('遮光帘功率').fontSize(12).fontColor(ThemeColors.textMuted); Slider({ value: this.curtainPower, min: 0, max: 100, style: SliderStyle.OutSet }).selectedColor(ThemeColors.primary).onChange((v: number) => this.curtainPower = v); Row() { Text(`${this.curtainPower}%`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.End) }.width('100%').padding(12).backgroundColor(ThemeColors.base).borderRadius(8)
          }
          if (this.selectedDevice === '水泵') {
            Column() { Text('水泵功率').fontSize(12).fontColor(ThemeColors.textMuted); Slider({ value: this.pumpPower, min: 0, max: 100, style: SliderStyle.OutSet }).selectedColor(ThemeColors.primary).onChange((v: number) => this.pumpPower = v); Row() { Text(`${this.pumpPower}%`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.End) }.width('100%').padding(12).backgroundColor(ThemeColors.base).borderRadius(8).margin({ top: 8 })
            Column() { Text('运行时长(分钟)').fontSize(12).fontColor(ThemeColors.textMuted); Row() { Button('-').width(28).height(28).type(ButtonType.Circle).backgroundColor(ThemeColors.borderLight).onClick(() => { if (this.pumpDuration > 1) this.pumpDuration-- }); Text(`${this.pumpDuration}`).fontSize(16).fontWeight(FontWeight.Bold).width(40).textAlign(TextAlign.Center); Button('+').width(28).height(28).type(ButtonType.Circle).backgroundColor(ThemeColors.borderLight).onClick(() => { if (this.pumpDuration < 60) this.pumpDuration++ }) }.width('100%').justifyContent(FlexAlign.Center) }.width('100%').padding(12).backgroundColor(ThemeColors.base).borderRadius(8).margin({ top: 8 })
          }
          if (this.selectedDevice === '风扇') {
            Column() { Text('风扇转速').fontSize(12).fontColor(ThemeColors.textMuted); Slider({ value: this.fanSpeed, min: 500, max: 3000, step: 100, style: SliderStyle.OutSet }).selectedColor(ThemeColors.primary).onChange((v: number) => this.fanSpeed = v); Row() { Text(`${this.fanSpeed} RPM`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.End) }.width('100%').padding(12).backgroundColor(ThemeColors.base).borderRadius(8)
          }
          Row() {
            Row({ space: 4 }) { Circle({ width: 8, height: 8 }).fill(ThemeColors.accent); Text('在线').fontSize(12).fontColor(ThemeColors.accent) }
            Text(`已连接 ${this.selectedDevice === '遮光帘' ? this.formatOnlineTime(this.curtainOnlineTime) : this.selectedDevice === '水泵' ? this.formatOnlineTime(this.pumpOnlineTime) : this.formatOnlineTime(this.fanOnlineTime)}`).fontSize(10).fontColor(ThemeColors.textMuted)
          }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding({ top: 8 })
        }.padding(16)
        Button('保存设置').width('100%').backgroundColor(ThemeColors.primary).height(40).margin({ top: 16 })
          .onClick(() => { this.showToast('设置已保存'); this.showDeviceDetailModal = false; })
      }.width('85%').backgroundColor(ThemeColors.card).borderRadius(16).padding(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder PlantDetailModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => this.showPlantDetailModal = false)
      Column() {
        Row() {
          Text(this.selectedPlant === '白萝卜' ? '白萝卜详情' : '普罗旺斯番茄详情').fontSize(16).fontWeight(FontWeight.Bold)
          Text('✕').fontSize(16).fontColor(ThemeColors.textMuted).onClick(() => this.showPlantDetailModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16).borderWidth({ bottom: 1 }).borderColor(ThemeColors.borderLight)
        
        if (this.selectedPlant === '白萝卜') {
          this.WhiteRadishDetail()
        } else {
          this.TomatoDetail()
        }
      }.width('85%').backgroundColor(ThemeColors.card).borderRadius(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder WhiteRadishDetail() {
    Column({ space: 16 }) {
      Row({ space: 16 }) {
        Text('🌿').fontSize(40)
        Column() {
          Text('白萝卜').fontSize(18).fontWeight(FontWeight.Bold)
          Text('4号大棚·A区').fontSize(12).fontColor(ThemeColors.textMuted)
          Text('生长期').fontSize(12).fontColor(ThemeColors.primary).backgroundColor(ThemeColors.primaryLight).padding({ left: 8, right: 8, top: 2, bottom: 2 }).margin({ top: 4 })
        }.alignItems(HorizontalAlign.Start)
      }.width('100%')

      Column({ space: 8 }) {
        Text('生长数据').fontSize(12).fontColor(ThemeColors.textMuted).width('100%')
        Row() { Text('株高').fontSize(12); Text(`${this.plantHeight}cm`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Row() { Text('叶片数').fontSize(12); Text(`${this.leafCount}片`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Row() { Text('生长天数').fontSize(12); Text(`${this.growthDays}天`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Row() { Text('预计收获').fontSize(12); Text(`${Math.max(0, 45 - this.growthDays)}天后`).fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
      }.width('100%').padding(12).backgroundColor(ThemeColors.base).borderRadius(8)

      Column({ space: 8 }) {
        Text('环境数据').fontSize(12).fontColor(ThemeColors.textMuted).width('100%')
        Row() { Text('土壤水分').fontSize(12); Text(`${this.soilMoisture}%`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Row() { Text('环境温度').fontSize(12); Text(`${Math.round(22 + Math.random() * 6)}°C`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Row() { Text('光照强度').fontSize(12); Text(`${this.lightIntensity}klx`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
      }.width('100%').padding(12).backgroundColor(ThemeColors.base).borderRadius(8)

      Button('关闭').width('100%').backgroundColor(ThemeColors.primary).height(40)
        .onClick(() => this.showPlantDetailModal = false)
    }.padding(16)
  }

  @Builder TomatoDetail() {
    Column({ space: 16 }) {
      Row({ space: 16 }) {
        Text('🍅').fontSize(40)
        Column() {
          Text('普罗旺斯番茄').fontSize(18).fontWeight(FontWeight.Bold)
          Text('2号大棚·B区').fontSize(12).fontColor(ThemeColors.textMuted)
          Text('开花期').fontSize(12).fontColor('#f97316').backgroundColor('#fff7ed').padding({ left: 8, right: 8, top: 2, bottom: 2 }).margin({ top: 4 })
        }.alignItems(HorizontalAlign.Start)
      }.width('100%')

      Column({ space: 8 }) {
        Text('生长数据').fontSize(12).fontColor(ThemeColors.textMuted).width('100%')
        Row() { Text('株高').fontSize(12); Text(`${Math.round(100 + this.growthDays * 0.8)}cm`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Row() { Text('花序数').fontSize(12); Text(`${Math.min(8, 3 + Math.floor(this.growthDays / 15))}层`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Row() { Text('果实数').fontSize(12); Text(`${Math.min(20, Math.floor(this.growthDays / 3))}个`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Row() { Text('生长天数').fontSize(12); Text(`${this.growthDays + 30}天`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Row() { Text('预计收获').fontSize(12); Text(`${Math.max(0, 50 - this.growthDays - 30)}天后`).fontSize(14).fontWeight(FontWeight.Bold).fontColor('#f97316') }.width('100%').justifyContent(FlexAlign.SpaceBetween)
      }.width('100%').padding(12).backgroundColor(ThemeColors.base).borderRadius(8)
      Column({ space: 8 }) {
        Text('环境数据').fontSize(12).fontColor(ThemeColors.textMuted).width('100%')
        Row() { Text('土壤水分').fontSize(12); Text(`${this.soilMoisture}%`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Row() { Text('环境温度').fontSize(12); Text(`${Math.round(24 + Math.random() * 8)}°C`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Row() { Text('光照强度').fontSize(12); Text(`${this.lightIntensity}klx`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Row() { Text('CO₂浓度').fontSize(12); Text(`${this.co2Concentration}ppm`).fontSize(14).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
      }.width('100%').padding(12).backgroundColor(ThemeColors.base).borderRadius(8)

      Column({ space: 8 }) {
        Text('养护建议').fontSize(12).fontColor(ThemeColors.textMuted).width('100%')
        Row() {
          Row({ space: 4 }) { Text('🟢').fontSize(10); Text('授粉期').fontSize(11) }
          Text('建议人工辅助授粉').fontSize(11).fontColor(ThemeColors.textMuted)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Row() {
          Row({ space: 4 }) { Text('🟡').fontSize(10); Text('施肥').fontSize(11) }
          Text('追施磷钾肥').fontSize(11).fontColor(ThemeColors.textMuted)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        Row() {
          Row({ space: 4 }) { Text('🔴').fontSize(10); Text('病虫害').fontSize(11) }
          Text('注意防治霜霉病').fontSize(11).fontColor(ThemeColors.danger)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween)
      }.width('100%').padding(12).backgroundColor('#fff7ed').borderRadius(8)

      Button('关闭').width('100%').backgroundColor('#f97316').height(40)
        .onClick(() => this.showPlantDetailModal = false)
    }.padding(16)
  }

  @Builder StageDetailModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => this.showStageDetailModal = false)
      Column() {
        Row() {
          Text(this.selectedStage + '说明').fontSize(16).fontWeight(FontWeight.Bold)
          Text('✕').fontSize(16).fontColor(ThemeColors.textMuted).onClick(() => this.showStageDetailModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16).borderWidth({ bottom: 1 }).borderColor(ThemeColors.borderLight)
        Column({ space: 12 }) {
          if (this.selectedStage === '种植期') {
            Text('🌱 种植期').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
            Text('此阶段需要保持土壤湿润，适宜温度20-25°C。注意防治地下害虫。').fontSize(12).fontColor(ThemeColors.textMuted).lineHeight(18)
          } else if (this.selectedStage === '生长期') {
            Text('🌿 生长期').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
            Text('生长旺季，需要充足水分和养分。建议追施氮肥，保持土壤湿度60-70%。').fontSize(12).fontColor(ThemeColors.textMuted).lineHeight(18)
          } else if (this.selectedStage === '开花/高发') {
            Text('🌸 开花期').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
            Text('注意防治病虫害，适当增加磷钾肥。保持通风良好，避免积水。').fontSize(12).fontColor(ThemeColors.textMuted).lineHeight(18)
          } else if (this.selectedStage === '结果期') {
            Text('🥕 结果期').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
            Text('肉质根膨大期，需要充足水分但避免过度。适当控水可提高品质。').fontSize(12).fontColor(ThemeColors.textMuted).lineHeight(18)
          } else {
            Text('🍂 挂果期').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
            Text('准备收获期，注意及时采收。避免裂根，保持土壤适度干燥。').fontSize(12).fontColor(ThemeColors.textMuted).lineHeight(18)
          }
        }.padding(16)
        Button('我知道了').width('100%').backgroundColor(ThemeColors.primary).height(40).margin({ top: 16 })
          .onClick(() => this.showStageDetailModal = false)
      }.width('75%').backgroundColor(ThemeColors.card).borderRadius(16).padding(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder WarningDetailModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => this.showWarningDetailModal = false)
      Column() {
        Row() {
          Text('预警详情').fontSize(16).fontWeight(FontWeight.Bold)
          Text('✕').fontSize(16).fontColor(ThemeColors.textMuted).onClick(() => this.showWarningDetailModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16).borderWidth({ bottom: 1 }).borderColor(ThemeColors.borderLight)
        Column({ space: 16 }) {
          Row() { Text('💧').fontSize(32); Column() { Text('水分不足预警').fontSize(14).fontWeight(FontWeight.Bold); Text('10:42').fontSize(10).fontColor(ThemeColors.textMuted) }.alignItems(HorizontalAlign.Start) }.width('100%')
          Column({ space: 8 }) { Text('问题描述').fontSize(12).fontColor(ThemeColors.textMuted); Text('检测到 1区土壤含水量低至15%，低于萝卜生长期适宜阈值(30%)。').fontSize(12).lineHeight(16) }.width('100%').padding(12).backgroundColor('#fff7ed').borderRadius(8)
          Column({ space: 8 }) { Text('历史趋势').fontSize(12).fontColor(ThemeColors.textMuted); Row() { Row().layoutWeight(1).height(20).backgroundColor(ThemeColors.danger); Row().layoutWeight(1).height(30).backgroundColor(ThemeColors.warning); Row().layoutWeight(1).height(40).backgroundColor(ThemeColors.warning); Row().layoutWeight(1).height(50).backgroundColor(ThemeColors.borderLight) }.width('100%').alignItems(VerticalAlign.Bottom) }.width('100%').padding(12).backgroundColor(ThemeColors.base).borderRadius(8)
          Column({ space: 8 }) { Text('处理建议').fontSize(12).fontColor(ThemeColors.textMuted); Text('建议开启水泵灌溉15分钟，保持土壤含水量在30%-50%区间。').fontSize(12).lineHeight(16) }.width('100%').padding(12).backgroundColor(ThemeColors.primaryLight).borderRadius(8)
        }.padding(16)
        Button('关闭').width('100%').backgroundColor(ThemeColors.primary).height(40).margin({ top: 16 })
          .onClick(() => this.showWarningDetailModal = false)
      }.width('85%').backgroundColor(ThemeColors.card).borderRadius(16).padding(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder DiagnosisImageModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.6)').onClick(() => this.showDiagnosisImage = false)
      Column() {
        Row() {
          Text('诊断图片').fontSize(16).fontWeight(FontWeight.Bold)
          Text('✕').fontSize(16).fontColor('#fff').onClick(() => this.showDiagnosisImage = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16)
        Column() {
          Text('📷').fontSize(80)
          Text('[疑似霜霉病斑点图片]').fontSize(12).fontColor('#9ca3af')
          Text('AI置信度: 89%').fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.danger).margin({ top: 8 })
          Text('建议：及时喷施代森锰锌防治').fontSize(12).fontColor(ThemeColors.textMuted).margin({ top: 8 })
        }.width('80%').height(300).backgroundColor('#1f2937').borderRadius(16).justifyContent(FlexAlign.Center)
        Button('关闭').width('60%').backgroundColor(ThemeColors.card).fontColor('#fff').height(40).margin({ top: 20 })
          .onClick(() => this.showDiagnosisImage = false)
      }
    }.width('100%').height('100%').zIndex(100)
  }
}
