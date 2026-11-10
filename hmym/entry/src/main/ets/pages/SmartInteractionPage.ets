import { promptAction, router } from '@kit.ArkUI';
import { http } from '@kit.NetworkKit';
import { photoAccessHelper } from '@kit.MediaLibraryKit';
import { fileIo } from '@kit.CoreFileKit';
import { OperationLogicStorage, OperationLogic } from '../common/OperationLogicStorage';
import { ApiConfig } from '../common/ApiConfig';

class ThemeColors {
  static readonly primary: string = '#0b5934';
  static readonly primaryLight: string = '#e8f3ee';
  static readonly primaryDark: string = '#074025';
  static readonly accent: string = '#10b981';
  static readonly dark: string = '#1e293b';
  static readonly surface: string = '#ffffff';
  static readonly background: string = '#f4f7f6';
  static readonly danger: string = '#ef4444';
  static readonly warning: string = '#f59e0b';
  static readonly textMain: string = '#1a2922';
  static readonly textMuted: string = '#6b7d73';
}

interface EmbedLog {
  title: string;
  desc?: string;
  status: string;
  time: string;
  type: 'success' | 'info' | 'warning';
}

interface ChatMessage {
  id: string;
  role: 'system' | 'ai' | 'user';
  content: string;
  time?: string;
  status?: 'pending' | 'executing' | 'completed' | 'failed';
  embedLog?: EmbedLog;
  hasPumpControl?: boolean;
  imageUrl?: string;
  sessionId?: string;
  feedback?: 'positive' | 'negative';
}

interface QuickCommand {
  text: string;
  isPrimary: boolean;
  isHighlighted: boolean;
}

interface ChatResponse {
  response?: string;
  message?: string;
  result?: string;
  data?: Record<string, Object>;
}

interface ChatRequestResult {
  text: string;
  sessionId: string;
}

interface ChatApiResponse {
  message?: string;
  response?: string;
  result?: string;
  session_id?: string;
}

// ================= 聊天记录API相关接口 =================
interface ApiChatMessageItem {
  id: string;
  role: string;
  content: string;
  sessionId: string | null;
  feedback: string | null;
  time: string;
}

interface ChatHistoryResponse {
  data: ApiChatMessageItem[];
  total: number;
}

interface AnalyzeHeader {
  status: string;
  latency_ms: number;
  device: string;
}

interface Detection {
  class_name: string;
  class: string;
  confidence: number;
  bbox: number[];
}

interface AnalyzedObject {
  id: number;
  class_name: string;
  confidence: number;
  bbox: number[];
  crop_url: string;
  rag_context: string;
  llm_analysis: string;
}

interface AnalyzeSummary {
  total_count: number;
  total_objects: number;
  is_healthy: boolean;
  healthy: number;
  unhealthy: number;
}

interface AnalyzeData {
  summary?: AnalyzeSummary;
  detections?: Detection[];
  analyzed_objects?: AnalyzedObject[];
  action_advice?: string;
}

interface AnalyzeResponse {
  header?: AnalyzeHeader;
  data?: AnalyzeData;
  report?: Record<string, Object>;
  annotated_url?: string;
  report_filename?: string;
}

interface PhotoSelectResult {
  photoUris: string[];
}

interface PredictionSignal {
  signal: string;
  analysis: string;
}

interface PredictionKnowledge {
  keyword: string;
  signals: PredictionSignal[];
  prediction: string;
  action: string;
}

interface ExperienceActionItem {
  device: string;
  action: string;
  value: number;
  unit: string;
}

interface ExperienceEnvSnapshot {
  temperature: number;
  humidity: number;
}

interface ExperienceExecutePayload {
  actions: ExperienceActionItem[];
  reasoning: string;
  env_snapshot: ExperienceEnvSnapshot;
}

const predictionKnowledgeBase: PredictionKnowledge[] = [
  {
    keyword: '温度升高',
    signals: [
      { signal: '微光谱变化', analysis: '叶片在感染初期（尚未显症）会反射特定的红外/紫外光谱' },
      { signal: '冠层温度异常', analysis: '局部区域温度轻微升高（真菌/细菌活动产热）' }
    ],
    prediction: '病害爆发预判',
    action: 'AI 预判 3-5 天后可能爆发菌核病，提前喷施保护性药剂'
  },
  {
    keyword: '叶片变化',
    signals: [
      { signal: '叶片角度微变', analysis: '在缺水初期，叶片会轻微下垂以减小蒸腾面积' },
      { signal: '生长速率放缓', analysis: '通过多期图像对比，预判生长拐点' }
    ],
    prediction: '水分胁迫预判',
    action: 'AI 预判未来 24 小时将进入水分胁迫，提前启动滴灌系统'
  },
  {
    keyword: '花蕾变化',
    signals: [
      { signal: '花蕾颜色变化', analysis: '花蕾颜色由浅变深，预示即将开放' },
      { signal: '花蕾体积增大', analysis: '花蕾体积明显增大，花瓣开始松散' }
    ],
    prediction: '盛花期预判',
    action: 'AI 预判 7 天后进入盛花期，提前调度无人机授粉团队，避免错过最佳窗口期'
  },
  {
    keyword: '土壤湿度下降',
    signals: [
      { signal: '土壤电导率变化', analysis: '土壤盐分浓度随水分蒸发而升高' },
      { signal: '根系活动减弱', analysis: '根系吸水能力下降，养分运输受阻' }
    ],
    prediction: '干旱预判',
    action: 'AI 预判 12 小时后将出现轻度干旱，建议提前进行滴灌补水'
  },
  {
    keyword: '虫害迹象',
    signals: [
      { signal: '叶片微小孔洞', analysis: '害虫取食造成的初期损伤' },
      { signal: '叶背虫卵附着', analysis: '害虫产卵繁殖的前兆' }
    ],
    prediction: '虫害爆发预判',
    action: 'AI 预判 5-7 天后可能爆发虫害，建议提前释放天敌昆虫或设置诱捕器'
  }
];

@Component
export struct SmartInteractionPage {
  @State inputText: string = '';
  @State isTyping: boolean = false;
  @State showVoiceOverlay: boolean = false;
  @State voiceText: string = '聆听中...';
  @State isApiConnected: boolean = false;
  @State lastApiLatency: number = 0;

  @State isPredictionMode: boolean = false;
  @State savedPredictions: PredictionKnowledge[] = [];
  @State showKnowledgeBaseModal: boolean = false;
  @State thinkingStep: number = 0;
  @State isThinking: boolean = false;

  // 聊天模式：0=专家农艺问答，1=设备调控
  @State chatMode: number = 0; // 0: 农艺专家, 1: 设备调控

  // 设备控制关键词（用于自动识别）
  deviceKeywords: string[] = ['打开', '关闭', '启动', '停止', '开启', '水泵', '风扇', '通风', '补光', '灯', '遮阳',
    '灌溉', '喷雾', '温控', '加热', '降温', '调高', '调低', '设备', '控制', 'pump', 'fan', 'light', 'on', 'off'];

  @State lightIntensity: number = 32.5;
  @State soilMoisture: number = 28;
  @State temperature: number = 24.5;
  @State connectionLatency: number = 23;
  @State onlineDeviceCount: number = 8;
  @State metricsContext: string = '';
  @State sensorUpdateTime: string = '';

  @State isRefreshing: boolean = false;
  @State refreshScale: number = 1;

  @State showConnectionModal: boolean = false;
  @State showHistoryModal: boolean = false;
  @State showEnvDetailModal: boolean = false;
  @State showImagePicker: boolean = false;
  @State selectedEnvType: string = '';
  @State envTimeRange: string = '今日';

  // 操作逻辑弹窗
  @State showOperationLogicModal: boolean = false;
  @State operationLogicInput: string = '';
  @State pendingInputText: string = '';

  @State quickCommands: QuickCommand[] = [
    { text: '打开水泵', isPrimary: true, isHighlighted: true },
    { text: '关闭风扇', isPrimary: false, isHighlighted: false },
    { text: '查询CO₂', isPrimary: false, isHighlighted: false },
    { text: '打开遮光帘', isPrimary: false, isHighlighted: false },
    { text: '设置灌溉', isPrimary: false, isHighlighted: true },
    { text: '病虫害分析', isPrimary: false, isHighlighted: false }
  ];

  @State lastContext: string = '';
  @State lastAction: string = '';
  @State annotatedImageUrl: string = '';
  @State reportFilename: string = '';

  private dataTimer: number = -1;
  private warningTimer: number = -1;
  private refreshCount: number = 0;
  private isFetchingMetrics: boolean = false; // 防止并发请求
  private scroller: Scroller = new Scroller();
  private httpRequest: http.HttpRequest | null = null;

  @State messages: ChatMessage[] = [];

  @State chatHistoryLoaded: boolean = false;
  @State showDeleteConfirm: boolean = false;
  @State showMoreMenu: boolean = false;
  @State pendingDeleteId: string = '';

  aboutToAppear(): void {
    this.fetchChatHistory();
    this.startDataRefresh();
    // 健康检查不阻塞UI，异步执行即可
    this.checkApiHealth();
  }

  aboutToDisappear(): void {
    this.stopDataRefresh();
    if (this.httpRequest) {
      this.httpRequest.destroy();
    }
  }

  async checkApiHealth(): Promise<void> {
    try {
      const request = http.createHttp();
      const startTime = Date.now();

      const response = await request.request(`${ApiConfig.BASE_URL}/health`, {
        method: http.RequestMethod.GET,
        header: {
          'ngrok-skip-browser-warning': 'true',
          'User-Agent': 'AgriSync-App/1.0',
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        connectTimeout: 3000,
        readTimeout: 3000
      });

      this.lastApiLatency = Date.now() - startTime;
      this.isApiConnected = response.responseCode === 200;

      if (this.isApiConnected) {
        this.messages.push({
          id: Date.now().toString(),
          role: 'system',
          content: `API连接成功 · 延迟 ${this.lastApiLatency}ms`
        });
      } else {
        this.messages.push({
          id: Date.now().toString(),
          role: 'system',
          content: `API响应异常 (${response.responseCode}) · 使用离线模式`
        });
      }

      request.destroy();
    } catch (error) {
      this.isApiConnected = false;
      this.messages.push({
        id: Date.now().toString(),
        role: 'system',
        content: `API连接失败 · 使用离线模式`
      });
    }
  }

  // ================= 聊天记录数据库操作 =================

  async fetchChatHistory(): Promise<void> {
    try {
      const request = http.createHttp();
      const resp = await request.request(`${ApiConfig.BASE_URL}/chat/history`, {
        method: http.RequestMethod.GET,
        connectTimeout: 5000,
        readTimeout: 8000
      });
      request.destroy();

      if (resp.responseCode === 200 && resp.result) {
        const jsonResult = JSON.parse(resp.result as string) as Record<string, Object>;
        const data = jsonResult['data'] as ApiChatMessageItem[];
        if (data && data.length > 0) {
          const loaded: ChatMessage[] = [];
          for (const item of data) {
            loaded.push({
              id: item.id,
              role: item.role as 'system' | 'ai' | 'user',
              content: item.content,
              time: item.time,
              sessionId: item.sessionId || undefined,
              feedback: item.feedback as 'positive' | 'negative' | undefined
            });
          }
          this.messages = loaded;
          this.chatHistoryLoaded = true;
          this.scrollToBottom();
        } else {
          this.messages = [{
            id: 'welcome_sys', role: 'system', content: '10:05 AM · 系统初始化完成'
          }, {
            id: 'welcome_ai', role: 'ai', content: '您好！我是 Agri-Sync 智能大脑。目前监控系统运行平稳。您可以直接下达设备控制指令，或询问数据分析。'
          }];
          this.chatHistoryLoaded = true;
        }
      } else {
        this.setDefaultMessages();
      }
    } catch (e) {
      this.setDefaultMessages();
    }
  }

  setDefaultMessages(): void {
    this.messages = [
      { id: 'welcome_sys', role: 'system', content: '10:05 AM · 系统初始化完成' },
      { id: 'welcome_ai', role: 'ai', content: '您好！我是 Agri-Sync 智能大脑。目前监控系统运行平稳。您可以直接下达设备控制指令，或询问数据分析。' }
    ];
    this.chatHistoryLoaded = true;
  }

  async saveMessageToDB(role: string, content: string, sessionId?: string): Promise<string | null> {
    try {
      const request = http.createHttp();
      let bodyJson: string = '';
      if (sessionId) {
        bodyJson = JSON.stringify({ role: role, content: content, session_id: sessionId });
      } else {
        bodyJson = JSON.stringify({ role: role, content: content });
      }
      const resp = await request.request(`${ApiConfig.BASE_URL}/chat/messages`, {
        method: http.RequestMethod.POST,
        header: { 'Content-Type': 'application/json' },
        extraData: bodyJson,
        connectTimeout: 5000,
        readTimeout: 5000
      });
      request.destroy();

      if (resp.responseCode === 200 && resp.result) {
        const result = JSON.parse(resp.result as string) as Record<string, Object>;
        const data = result['data'] as Record<string, string>;
        return data ? data['id'] : null;
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  // 保存操作逻辑到数据库（同步到设置页操作逻辑存储库）
  async saveOperationLogicToAPI(inputText: string, operationLogic: string): Promise<void> {
    try {
      const request = http.createHttp();
      const resp = await request.request(`${ApiConfig.BASE_URL}/system/operation-logics`, {
        method: http.RequestMethod.POST,
        header: { 'Content-Type': 'application/json' },
        extraData: JSON.stringify({
          input_text: inputText,
          operation_logic: operationLogic
        }),
        connectTimeout: 5000,
        readTimeout: 5000
      });
      request.destroy();
    } catch (e) {
      // 静默失败，不影响主流程
    }

    // 同步到 silicon gateway /api/v1/experience/execute
    try {
      const request2 = http.createHttp();
      await request2.request(`${ApiConfig.BASE_URL}/api/v1/experience/execute`, {
        method: http.RequestMethod.POST,
        header: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true',
          'User-Agent': 'AgriSync-App/1.0'
        },
        extraData: JSON.stringify({
          actions: [{ device: 'general', action: 'operation_logic', value: 1.0, unit: 'pct' }] as ExperienceActionItem[],
          reasoning: operationLogic,
          env_snapshot: { temperature: this.temperature, humidity: this.soilMoisture } as ExperienceEnvSnapshot
        } as ExperienceExecutePayload),
        connectTimeout: 5000,
        readTimeout: 5000
      });
      request2.destroy();
    } catch (e) {
      // 静默失败，不影响主流程
    }
  }

  async deleteMessageFromDB(messageId: string): Promise<boolean> {
    try {
      const request = http.createHttp();
      const resp = await request.request(`${ApiConfig.BASE_URL}/chat/messages/${messageId}`, {
        method: http.RequestMethod.DELETE,
        connectTimeout: 5000,
        readTimeout: 5000
      });
      request.destroy();
      return resp.responseCode === 200;
    } catch (e) {
      return false;
    }
  }

  async clearAllChatHistory(): Promise<boolean> {
    try {
      const request = http.createHttp();
      const resp = await request.request(`${ApiConfig.BASE_URL}/chat/clear`, {
        method: http.RequestMethod.DELETE,
        connectTimeout: 5000,
        readTimeout: 5000
      });
      request.destroy();
      return resp.responseCode === 200;
    } catch (e) {
      return false;
    }
  }

  handleDeleteMessage(messageId: string): void {
    this.pendingDeleteId = messageId;
    this.showDeleteConfirm = true;
  }

  async confirmDelete(): Promise<void> {
    if (!this.pendingDeleteId) return;
    const success = await this.deleteMessageFromDB(this.pendingDeleteId);
    if (success) {
      this.messages = this.messages.filter((m: ChatMessage): boolean => m.id !== this.pendingDeleteId);
      promptAction.showToast({ message: '消息已删除' });
    } else {
      promptAction.showToast({ message: '删除失败，请重试' });
    }
    this.showDeleteConfirm = false;
    this.pendingDeleteId = '';
  }

  cancelDelete(): void {
    this.showDeleteConfirm = false;
    this.pendingDeleteId = '';
  }

  // 自动识别用户意图，切换到对应模式
  detectIntent(text: string): number {
    const lower = text.toLowerCase();
    for (const kw of this.deviceKeywords) {
      if (lower.includes(kw.toLowerCase())) {
        return 1; // 设备调控模式
      }
    }
    return 0; // 农艺专家模式
  }

  // 获取当前模式名称
  getModeName(): string {
    return this.chatMode === 0 ? '🌾 农艺专家' : '⚙️ 设备调控';
  }

  // 获取模式颜色
  getModeColor(): string {
    return this.chatMode === 0 ? '#0b5934' : '#2563eb';
  }

  async sendChatRequest(message: string): Promise<ChatRequestResult> {
    // 自动识别意图并切换模式
    const detectedMode = this.detectIntent(message);
    const previousMode = this.chatMode;
    if (detectedMode !== this.chatMode) {
      this.chatMode = detectedMode;
    }

    if (!this.isApiConnected) {
      let fallback: ChatRequestResult = { text: this.getOfflineResponse(message), sessionId: '' };
      return fallback;
    }

    try {
      const request = http.createHttp();
      const startTime = Date.now();

      // 根据模式构建不同的系统提示
      const modePrefix = this.chatMode === 1
        ? '[设备调控模式] 用户请求控制农业设备，请直接给出设备操作指令（JSON格式：{"target":"设备名","action":"on/off","reason":"原因"}）。'
        : '[农艺专家模式] 用户咨询农业生产知识，请以专业农艺师角度给出详细、准确的解答。';

      const response = await request.request(`${ApiConfig.BASE_URL}/chat`, {
        method: http.RequestMethod.POST,
        header: {
          'ngrok-skip-browser-warning': 'true',
          'User-Agent': 'AgriSync-App/1.0',
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        extraData: JSON.stringify({
          message: `${modePrefix}\n${message}`,
          context: this.lastContext,
          last_action: this.lastAction,
          chat_mode: this.chatMode === 1 ? 'device' : 'expert'
        }),
        connectTimeout: 10000,
        readTimeout: 30000
      });

      this.lastApiLatency = Date.now() - startTime;
      request.destroy();

      if (response.responseCode === 200 && response.result) {
        const apiResp: ChatApiResponse = JSON.parse(response.result as string) as ChatApiResponse;
        let result: ChatRequestResult = {
          text: apiResp.message || apiResp.response || apiResp.result || '收到指令，正在处理...',
          sessionId: apiResp.session_id || ''
        };
        return result;
      }

      let fallback: ChatRequestResult = { text: this.getOfflineResponse(message), sessionId: '' };
      return fallback;
    } catch (error) {
      let fallback: ChatRequestResult = { text: this.getOfflineResponse(message), sessionId: '' };
      return fallback;
    }
  }

  async requestCropAnalysis(message: string): Promise<ChatRequestResult> {
    if (!this.isApiConnected) {
      return { text: this.getOfflineResponse(message), sessionId: '' };
    }

    try {
      const request = http.createHttp();
      const startTime = Date.now();

      const response = await request.request(`${ApiConfig.BASE_URL}/api/v1/chat`, {
        method: http.RequestMethod.POST,
        header: {
          'ngrok-skip-browser-warning': 'true',
          'User-Agent': 'AgriSync-App/1.0',
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        extraData: JSON.stringify({
          message: message
        }),
        connectTimeout: 10000,
        readTimeout: 30000
      });

      this.lastApiLatency = Date.now() - startTime;
      request.destroy();

      if (response.responseCode === 200 && response.result) {
        const jsonResult = JSON.parse(response.result as string) as Record<string, Object>;
        const status = jsonResult['status'] as string;
        const threadId = jsonResult['thread_id'] as string;
        const data = jsonResult['data'] as Record<string, Object>;

        if (status === 'success' && data) {
          const answer = data['answer'] as string;
          return {
            text: answer || '作物分析完成，暂无详细结果',
            sessionId: threadId || ''
          };
        }
      }

      return { text: this.getOfflineResponse(message), sessionId: '' };
    } catch (error) {
      return { text: this.getOfflineResponse(message), sessionId: '' };
    }
  }

  async sendVoiceCommand(command: string): Promise<string> {
    if (!this.isApiConnected) {
      return this.getOfflineResponse(command);
    }

    try {
      const request = http.createHttp();

      const response = await request.request(`${ApiConfig.BASE_URL}/voice_cmd`, {
        method: http.RequestMethod.POST,
        header: {
          'ngrok-skip-browser-warning': 'true',
          'User-Agent': 'AgriSync-App/1.0',
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        extraData: JSON.stringify({
          command: command,
          timestamp: Date.now()
        }),
        connectTimeout: 10000,
        readTimeout: 30000
      });

      request.destroy();

      if (response.responseCode === 200 && response.result) {
        const result: ChatResponse = JSON.parse(response.result as string);
        return result.response || result.message || '语音指令已执行';
      }

      return this.getOfflineResponse(command);
    } catch (error) {
      return this.getOfflineResponse(command);
    }
  }

  async analyzeImage(imageUri: string): Promise<string> {
    if (!this.isApiConnected) {
      return '离线模式暂不支持图像分析';
    }

    try {
      const request = http.createHttp();

      const file = fileIo.openSync(imageUri, fileIo.OpenMode.READ_ONLY);
      const stat = fileIo.statSync(imageUri);
      const fileSize = stat.size;
      const buffer = new ArrayBuffer(fileSize);
      fileIo.readSync(file.fd, buffer);
      fileIo.closeSync(file);

      const response = await request.request(`${ApiConfig.BASE_URL}/analyze`, {
        method: http.RequestMethod.POST,
        header: {
          'ngrok-skip-browser-warning': 'true',
          'User-Agent': 'AgriSync-App/1.0',
          'Accept': 'application/json',
          'Content-Type': 'multipart/form-data'
        },
        extraData: {
          file: buffer
        },
        connectTimeout: 10000,
        readTimeout: 60000
      });

      request.destroy();

      if (response.responseCode === 200 && response.result) {
        const result: AnalyzeResponse = JSON.parse(response.result as string);

        // 存储 annotated_url 和 report_filename
        if (result.annotated_url) {
          this.annotatedImageUrl = result.annotated_url;
        }
        if (result.report_filename) {
          this.reportFilename = result.report_filename;
        }

        if (result.data) {
          const summary = result.data.summary;
          const detections = result.data.detections;
          const advice = result.data.action_advice;

          let analysisText = '📊 图像分析结果\n\n';

          if (summary) {
            const totalCount = summary.total_count || summary.total_objects || 0;
            analysisText += `检测到 ${totalCount} 个对象\n`;
            analysisText += `健康状态: ${summary.is_healthy ? '✅ 正常' : '⚠️ 需关注'}\n`;
            if (summary.healthy !== undefined && summary.unhealthy !== undefined) {
              analysisText += `健康: ${summary.healthy} | 异常: ${summary.unhealthy}\n`;
            }
            analysisText += '\n';
          }

          if (detections && detections.length > 0) {
            analysisText += '检测结果:\n';
            for (const det of detections) {
              const className = det.class_name || det.class || '未知';
              analysisText += `• ${className}: ${(det.confidence * 100).toFixed(1)}%\n`;
            }
            analysisText += '\n';
          }

          if (advice) {
            analysisText += `💡 建议: ${advice}\n`;
          }

          if (result.annotated_url) {
            analysisText += `\n🖼️ 标注图: ${result.annotated_url}`;
          }
          if (result.report_filename) {
            analysisText += `\n📄 报告: ${result.report_filename}`;
          }

          return analysisText;
        }
      }

      return '图像分析失败，请稍后重试';
    } catch (error) {
      return `图像分析出错`;
    }
  }

  getOfflineResponse(text: string): string {
    if ((text.includes('再') || text.includes('更') || text.includes('久')) && this.lastAction.includes('水泵')) {
      return '已为您延长灌溉时长。当前设置为 20 分钟。';
    }
    if (text.includes('水泵') || text.includes('打开水泵')) {
      return '已为您打开水泵。请调节各大棚的出水量：';
    }
    if (text.includes('CO2') || text.includes('二氧化碳')) {
      return `当前温室内的二氧化碳浓度为 ${Math.round(700 + Math.random() * 200)} ppm，处于适宜农作物生长的正常范围内。`;
    }
    if (text.includes('关') && text.includes('风扇')) {
      return '已为您关闭风扇。';
    }
    if (text.includes('光照') || text.includes('打开遮光帘')) {
      return '已为您打开遮光帘。';
    }
    if (text.includes('温度')) {
      return `当前温室温度为 ${this.temperature}°C，处于适宜范围（18-30°C）。`;
    }
    if (text.includes('分析') || text.includes('病虫害')) {
      return '正在进行病虫害分析...\n\n初步结果：未发现明显病虫害迹象。作物生长状态良好。';
    }
    if (text.includes('水分') || text.includes('湿度')) {
      return `当前土壤湿度为 ${this.soilMoisture}%，${this.soilMoisture < 30 ? '低于适宜范围，建议开启灌溉' : '处于适宜范围'}。`;
    }
    return '收到您的指令，正在处理中...';
  }

  async submitFeedback(sessionId: string, feedbackType: 'positive' | 'negative', comment: string): Promise<void> {
    try {
      const request = http.createHttp();
      await request.request(`${ApiConfig.BASE_URL}/feedback`, {
        method: http.RequestMethod.POST,
        header: {
          'Content-Type': 'application/json'
        },
        extraData: JSON.stringify({
          session_id: sessionId,
          feedback_type: feedbackType,
          comment: comment || (feedbackType === 'positive' ? '用户认为回答有用' : '用户认为回答不准确')
        }),
        connectTimeout: 5000,
        readTimeout: 5000
      });
      request.destroy();
    } catch (error) {
      console.error('Feedback submit failed: ' + JSON.stringify(error));
    }
  }

  markFeedback(msgId: string, feedbackType: 'positive' | 'negative'): void {
    let newMessages: ChatMessage[] = [];
    for (let i = 0; i < this.messages.length; i++) {
      let m: ChatMessage = this.messages[i];
      if (m.id === msgId) {
        let copied: ChatMessage = {
          id: m.id,
          role: m.role,
          content: m.content,
          time: m.time,
          status: m.status,
          embedLog: m.embedLog,
          hasPumpControl: m.hasPumpControl,
          imageUrl: m.imageUrl,
          sessionId: m.sessionId,
          feedback: feedbackType
        };
        newMessages.push(copied);
      } else {
        newMessages.push(m);
      }
    }
    this.messages = newMessages;
  }

  startDataRefresh(): void {
    // 防止重复创建定时器
    if (this.dataTimer !== -1) {
      return;
    }
    this.dataTimer = setInterval(() => {
      this.refreshData();
    }, 5000); // 5秒间隔，避免过于频繁
  }

  stopDataRefresh(): void {
    if (this.dataTimer !== -1) {
      clearInterval(this.dataTimer);
      this.dataTimer = -1;
    }
    if (this.warningTimer !== -1) {
      clearInterval(this.warningTimer);
      this.warningTimer = -1;
    }
  }

  refreshData(): void {
    this.refreshCount++;

    if (this.refreshCount % 10 === 1) {
      this.fetchMetricsData();
    }

    if (this.metricsContext === '') {
      this.lightIntensity = Math.round((this.lightIntensity + (Math.random() - 0.5) * 1) * 10) / 10;
      this.lightIntensity = Math.max(20, Math.min(45, this.lightIntensity));

      this.soilMoisture = Math.round(this.soilMoisture + (Math.random() - 0.5) * 2);
      this.soilMoisture = Math.max(15, Math.min(80, this.soilMoisture));

      this.temperature = Math.round((this.temperature + (Math.random() - 0.5) * 0.8) * 10) / 10;
      this.temperature = Math.max(18, Math.min(35, this.temperature));

      this.connectionLatency = Math.round(this.connectionLatency + (Math.random() - 0.5) * 5);
      this.connectionLatency = Math.max(10, Math.min(100, this.connectionLatency));
    }

    this.updateQuickCommandsHighlight();
  }

  async fetchMetricsData(): Promise<void> {
    // 防止并发请求：上一次请求未完成时不发起新请求
    if (this.isFetchingMetrics) {
      return;
    }
    this.isFetchingMetrics = true;
    try {
      const request = http.createHttp();
      const resp = await request.request(`${ApiConfig.BASE_URL}/analytics/metrics/latest`, {
        method: http.RequestMethod.GET,
        connectTimeout: 5000,
        readTimeout: 8000
      });
      request.destroy();

      if (resp.responseCode === 200 && resp.result) {
        const data: Record<string, Object> = JSON.parse(resp.result as string) as Record<string, Object>;
        const context: string = (data['context'] as string) || '';
        if (context && context.length > 0) {
          this.metricsContext = context;
          this.lastContext = context;
          this.sensorUpdateTime = this.formatTime(new Date());
        }

        // 优先读取结构化 sensor_data，无需正则解析
        const sensorData: Record<string, Object> | null = data['sensor_data'] as Record<string, Object> | null;
        if (sensorData) {
          this.temperature = (sensorData['temperature'] as number) || this.temperature;
          this.soilMoisture = (sensorData['soil_moisture'] as number) || this.soilMoisture;
          this.lightIntensity = (sensorData['light_intensity'] as number) || this.lightIntensity;
          this.onlineDeviceCount = (sensorData['online_devices'] as number) || this.onlineDeviceCount;
          this.connectionLatency = (sensorData['latency_ms'] as number) || this.connectionLatency;
        } else if (context && context.length > 0) {
          // 兜底：正则解析 context 文本
          const tempMatch: RegExpMatchArray | null = context.match(/温度(\d+\.?\d*)/);
          if (tempMatch && tempMatch[1]) {
            this.temperature = parseFloat(tempMatch[1]);
          }
          const lightMatch: RegExpMatchArray | null = context.match(/光照[^度]*?(\d+\.?\d*)/);
          if (lightMatch && lightMatch[1]) {
            this.lightIntensity = parseFloat(lightMatch[1]);
          }
          const soilMatch: RegExpMatchArray | null = context.match(/土壤[^度]*?(\d+\.?\d*)/);
          if (soilMatch && soilMatch[1]) {
            this.soilMoisture = parseFloat(soilMatch[1]);
          }
          const devMatch: RegExpMatchArray | null = context.match(/在线[^\d]*?(\d+)/);
          if (devMatch && devMatch[1]) {
            this.onlineDeviceCount = parseInt(devMatch[1]);
          }
          const latMatch: RegExpMatchArray | null = context.match(/延迟[^:：]*?(\d+)/);
          if (latMatch && latMatch[1]) {
            this.connectionLatency = parseInt(latMatch[1]);
          }
        }
      }
    } catch (e) {
      // Keep existing values when API fails
    } finally {
      this.isFetchingMetrics = false;
    }
  }

  updateQuickCommandsHighlight(): void {
    for (let i = 0; i < this.quickCommands.length; i++) {
      const cmd = this.quickCommands[i];
      if (cmd.text === '打开水泵' && this.soilMoisture < 30) {
        cmd.isHighlighted = true;
      } else if (cmd.text === '关闭风扇' && this.temperature < 22) {
        cmd.isHighlighted = true;
      } else {
        cmd.isHighlighted = false;
      }
    }
  }

  doRefresh(): void {
    this.isRefreshing = true;
    this.refreshScale = 0.9;
    setTimeout(() => {
      this.refreshData();
      this.checkApiHealth();
      this.isRefreshing = false;
      this.refreshScale = 1;
      promptAction.showToast({ message: '数据已刷新' });
    }, 800);
  }

  async sendMessage(text: string) {
    if (!text.trim()) return;

    // 第一步：自动识别意图，切换到对应模式
    const detectedMode = this.detectIntent(text);
    if (detectedMode !== this.chatMode) {
      this.chatMode = detectedMode;
    }

    // 第二步：设备调控模式 → 弹出操作逻辑填写框
    if (this.chatMode === 1) {
      this.pendingInputText = text;
      this.operationLogicInput = '';
      this.showOperationLogicModal = true;
      return; // 等用户填写操作逻辑后再发送
    }

    // 第三步：农艺专家模式 → 直接发送，不弹操作逻辑框
    await this.submitMessage(text, '');
  }

  async submitMessage(text: string, operationLogic: string) {
    const userMsgId = Date.now().toString();
    this.messages.push({
      id: userMsgId,
      role: 'user',
      content: text,
      time: this.formatTime(new Date())
    });
    this.inputText = '';
    this.scrollToBottom();

    // 保存用户消息到数据库
    this.saveMessageToDB('user', text);

    // 设备调控模式：保存操作逻辑到数据库（同步到设置页的操作逻辑存储库）
    if (this.chatMode === 1) {
      const finalLogic = operationLogic.trim() || `[待执行] ${text}`;
      this.saveOperationLogicToAPI(text, finalLogic);
    } else {
      // 农艺模式：仅本地记录（不存入操作逻辑库）
      if (operationLogic.trim()) {
        const logic: OperationLogic = {
          id: Date.now().toString(),
          inputText: text,
          operationLogic: operationLogic,
          createTime: this.formatTime(new Date())
        };
        await OperationLogicStorage.getInstance().addLogic(logic);
      }
    }

    this.lastContext = text;
    this.isTyping = true;
    this.scrollToBottom();

    let responseText: string;
    let sessionId: string = '';
    let predictionData: PredictionKnowledge | null = null;

    if (this.isPredictionMode) {
      this.isThinking = true;
      this.thinkingStep = 1;

      await this.delay(800);
      this.thinkingStep = 2;
      await this.delay(600);
      this.thinkingStep = 3;
      await this.delay(500);

      const prediction = this.analyzePredictionSignal(text);
      if (prediction) {
        responseText = this.formatPredictionResponse(prediction);
        predictionData = prediction;
        if (!this.savedPredictions.find(p => p.keyword === prediction.keyword)) {
          this.savedPredictions.push(prediction);
        }
      } else {
        responseText = this.generateDefaultPrediction(text);
      }
      this.isThinking = false;
    } else {
      // 农艺专家模式下，若消息包含作物相关关键词，路由到 silicon gateway
      const cropKeywords: string[] = ['生长', '分析', '作物', '植株', '长势'];
      const isCropQuery = this.chatMode === 0 && cropKeywords.some(kw => text.includes(kw));
      let result: ChatRequestResult;
      if (isCropQuery) {
        result = await this.requestCropAnalysis(text);
      } else {
        result = await this.sendChatRequest(text);
      }
      responseText = result.text;
      sessionId = result.sessionId;
    }
    this.isTyping = false;

    const aiMsgId = (Date.now() + 1).toString();
    let reply: ChatMessage = {
      id: aiMsgId,
      role: 'ai',
      content: responseText,
      time: this.formatTime(new Date()),
      sessionId: sessionId
    };

    if (this.isPredictionMode && predictionData) {
      reply.embedLog = {
        title: `🔮 ${predictionData.prediction}`,
        status: '已存入知识库',
        time: '刚刚',
        type: 'warning'
      };
    } else if (text.includes('水泵') || text.includes('打开水泵')) {
      reply.hasPumpControl = true;
      reply.embedLog = {
        title: '设备控制: 灌溉水泵 [ON]',
        status: '✓ 指令已下达',
        time: '刚刚',
        type: 'success'
      };
      this.lastAction = '水泵';
    } else if (text.includes('关') && text.includes('风扇')) {
      reply.embedLog = {
        title: '设备控制: 风扇 [OFF]',
        status: '✓ 已关闭',
        time: '刚刚',
        type: 'info'
      };
      this.lastAction = '风扇';
    } else if (text.includes('遮光帘')) {
      reply.embedLog = {
        title: '设备控制: 遮光帘 [ON]',
        status: '✓ 已开启',
        time: '刚刚',
        type: 'success'
      };
      this.lastAction = '遮光帘';
    }

    this.messages.push(reply);
    this.scrollToBottom();

    // 保存AI回复到数据库
    this.saveMessageToDB('ai', responseText, sessionId);
  }

  analyzePredictionSignal(text: string): PredictionKnowledge | null {
    const lowerText = text.toLowerCase();
    
    if (lowerText.includes('温度') && (lowerText.includes('升高') || lowerText.includes('高'))) {
      return predictionKnowledgeBase.find(p => p.keyword === '温度升高') || null;
    }
    if (lowerText.includes('叶片') && (lowerText.includes('变') || lowerText.includes('下垂') || lowerText.includes('微'))) {
      return predictionKnowledgeBase.find(p => p.keyword === '叶片变化') || null;
    }
    if (lowerText.includes('花蕾') && (lowerText.includes('颜色') || lowerText.includes('大小') || lowerText.includes('变'))) {
      return predictionKnowledgeBase.find(p => p.keyword === '花蕾变化') || null;
    }
    if (lowerText.includes('土壤') && (lowerText.includes('湿度') || lowerText.includes('干'))) {
      return predictionKnowledgeBase.find(p => p.keyword === '土壤湿度下降') || null;
    }
    if (lowerText.includes('虫') || lowerText.includes('孔洞') || lowerText.includes('卵')) {
      return predictionKnowledgeBase.find(p => p.keyword === '虫害迹象') || null;
    }
    
    return null;
  }

  formatPredictionResponse(prediction: PredictionKnowledge): string {
    let response = `📊 时序预测分析报告\n\n`;
    response += `🔍 检测信号：${prediction.keyword}\n\n`;
    response += `⚠️ 预警信号分析：\n`;
    
    for (const signal of prediction.signals) {
      response += `\n• ${signal.signal}\n  └ ${signal.analysis}\n`;
    }
    
    response += `\n📈 预判结果：${prediction.prediction}\n\n`;
    response += `✅ 预判动作：\n${prediction.action}\n\n`;
    response += `💾 此预测已保存至知识库，可用于后续参考。`;
    
    return response;
  }

  generateDefaultPrediction(text: string): string {
    return `📊 时序预测分析\n\n您输入的信号："${text}"\n\n正在分析中...\n\n目前知识库中暂无完全匹配的预判模型，但系统已记录此信号特征。\n\n建议：\n• 持续监测相关指标变化\n• 结合其他传感器数据进行综合判断\n• 如有异常趋势，及时人工干预\n\n您可以尝试输入更具体的信号描述，例如：\n• "大棚温度轻微升高"\n• "植物叶片微变"\n• "花蕾颜色、大小有变化"`;
  }

  async pickAndAnalyzeImage(): Promise<void> {
    try {
      const photoSelectOptions: photoAccessHelper.PhotoSelectOptions = {
        MIMEType: photoAccessHelper.PhotoViewMIMETypes.IMAGE_TYPE,
        maxSelectNumber: 1
      };

      const photoPicker = new photoAccessHelper.PhotoViewPicker();
      const photoSelectResult: photoAccessHelper.PhotoSelectResult = await photoPicker.select(photoSelectOptions);

      if (photoSelectResult.photoUris && photoSelectResult.photoUris.length > 0) {
        const imageUri = photoSelectResult.photoUris[0];

        this.messages.push({
          id: Date.now().toString(),
          role: 'user',
          content: '📷 上传了一张图片进行分析',
          time: this.formatTime(new Date()),
          imageUrl: imageUri
        });
        this.scrollToBottom();

        this.isTyping = true;
        const analysisResult = await this.analyzeImage(imageUri);
        this.isTyping = false;

        this.messages.push({
          id: (Date.now() + 1).toString(),
          role: 'ai',
          content: analysisResult,
          time: this.formatTime(new Date())
        });
        this.scrollToBottom();
      }
    } catch (error) {
      promptAction.showToast({ message: '选择图片失败' });
    }
  }

  formatTime(date: Date): string {
    const hours = date.getHours();
    const minutes = date.getMinutes();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;
    return `${displayHours}:${minutes.toString().padStart(2, '0')} ${ampm}`;
  }

  scrollToBottom() {
    setTimeout(() => {
      this.scroller.scrollEdge(Edge.Bottom);
    }, 100);
  }

  delay(ms: number): Promise<void> {
    return new Promise<void>((resolve) => {
      setTimeout(() => {
        resolve();
      }, ms);
    });
  }

  build() {
    Stack({ alignContent: Alignment.Top }) {
      Column() {
        this.Header()
        this.SensorContext()
        this.ChatMessages()
        this.InputArea()
        Row().height(64).width('100%')
      }
      .width('100%')
      .height('100%')

      if (this.showVoiceOverlay) {
        this.VoiceOverlay()
      }
      this.MoreMenuPanel()
      if (this.showConnectionModal) {
        this.ConnectionModal()
      }
      if (this.showHistoryModal) {
        this.HistoryModal()
      }
      if (this.showEnvDetailModal) {
        this.EnvDetailModal()
      }
      if (this.showKnowledgeBaseModal) {
        this.KnowledgeBaseModal()
      }
      if (this.showOperationLogicModal) {
        this.OperationLogicModal()
      }
    }
    .width('100%')
    .height('100%')
  }

  @Builder ChatMessages() {
    Stack({ alignContent: Alignment.Top }) {
      Scroll(this.scroller) {
        Column({ space: 20 }) {
          // 顶部工具栏：清空记录 + 刷新
          if (this.chatHistoryLoaded && this.messages.length > 2) {
            Row() {
              Text(`共 ${this.messages.length} 条记录`).fontSize(10).fontColor('#9ca3af')
              Blank()
              Text('🗑️ 清空记录').fontSize(11).fontColor(ThemeColors.danger)
                .padding({ left: 10, right: 10, top: 4, bottom: 4 })
                .backgroundColor('rgba(239,68,68,0.06)')
                .borderRadius(12)
                .onClick(() => {
                  promptAction.showDialog({
                    title: '确认清空',
                    message: '确定要清空所有聊天记录吗？此操作不可恢复。',
                    buttons: [
                      { text: '取消', color: '#000000' },
                      { text: '清空', color: ThemeColors.danger }
                    ]
                  }).then(async (data) => {
                    if (data.index === 1) {
                      const success = await this.clearAllChatHistory();
                      if (success) {
                        this.setDefaultMessages();
                        promptAction.showToast({ message: '聊天记录已清空' });
                      } else {
                        promptAction.showToast({ message: '清空失败，请重试' });
                      }
                    }
                  });
                })
            }.width('100%').padding({ left: 8, right: 8 }).margin({ bottom: 4 })
          }

          ForEach(this.messages, (msg: ChatMessage) => {
            // 非系统消息支持长按删除
            if (msg.role === 'system') {
              this.SystemMessage(msg)
            } else if (msg.role === 'user') {
              this.UserMessageWithDelete(msg)
            } else {
              this.AiMessageWithDelete(msg)
            }
          }, (msg: ChatMessage) => msg.id)

          if (this.isTyping) {
            this.TypingIndicator()
          }

          Row().height(20)
        }
        .padding(16)
        .width('100%')
      }
      .width('100%')
      .layoutWeight(1)
      .scrollBar(BarState.Off)
      .backgroundColor(ThemeColors.background)
      .align(Alignment.Top)

      // 删除确认弹窗
      if (this.showDeleteConfirm) {
        this.DeleteConfirmDialog()
      }
    }
    .width('100%')
    .layoutWeight(1)
  }

  @Builder UserMessageWithDelete(msg: ChatMessage) {
    Row() {
      Column({ space: 4 }) {
        if (msg.imageUrl) {
          Image(msg.imageUrl)
            .width(150)
            .height(150)
            .objectFit(ImageFit.Cover)
            .borderRadius(8)
        }
        Text(msg.content)
          .fontSize(13)
          .fontColor(ThemeColors.surface)
          .backgroundColor(ThemeColors.primary)
          .padding(12)
          .borderRadius({ topLeft: 16, topRight: 16, bottomLeft: 16, bottomRight: 4 })
          .constraintSize({ maxWidth: '75%' })
        if (msg.time) {
          Text(msg.time).fontSize(9).fontColor('#9ca3af')
        }
      }
    }.width('100%').justifyContent(FlexAlign.End).alignItems(VerticalAlign.Bottom)
  }

  @Builder AiMessageWithDelete(msg: ChatMessage) {
    Row({ space: 8 }) {
      Stack() {
        Circle({ width: 32, height: 32 }).fill(ThemeColors.primary)
        Text('AI').fontSize(10).fontColor(ThemeColors.surface).fontWeight(FontWeight.Bold)
      }.alignSelf(ItemAlign.End)

      Column({ space: 8 }) {
        Text(msg.content).fontSize(13).fontColor('#374151').lineHeight(20).wordBreak(WordBreak.BREAK_ALL)

        if (msg.embedLog) {
          this.EmbedLogCard(msg.embedLog)
        }

        if (msg.hasPumpControl) {
          this.PumpControlPanel()
        }

        if (msg.sessionId) {
          Row({ space: 12 }) {
            Row({ space: 4 }) {
              Text('👍').fontSize(14)
                .opacity(msg.feedback === 'positive' ? 1 : 0.5)
              Text('有用').fontSize(10).fontColor(msg.feedback === 'positive' ? ThemeColors.accent : '#9ca3af')
            }
            .padding({ left: 8, right: 8, top: 4, bottom: 4 })
            .backgroundColor(msg.feedback === 'positive' ? '#dcfce7' : '#f3f4f6')
            .borderRadius(12)
            .onClick(() => {
              if (msg.feedback) return;
              this.markFeedback(msg.id, 'positive');
              this.submitFeedback(msg.sessionId!, 'positive', '');
              promptAction.showToast({ message: '感谢反馈，已记录' });
            })

            Row({ space: 4 }) {
              Text('👎').fontSize(14)
                .opacity(msg.feedback === 'negative' ? 1 : 0.5)
              Text('没用').fontSize(10).fontColor(msg.feedback === 'negative' ? ThemeColors.danger : '#9ca3af')
            }
            .padding({ left: 8, right: 8, top: 4, bottom: 4 })
            .backgroundColor(msg.feedback === 'negative' ? '#fef2f2' : '#f3f4f6')
            .borderRadius(12)
            .onClick(() => {
              if (msg.feedback) return;
              this.markFeedback(msg.id, 'negative');
              this.submitFeedback(msg.sessionId!, 'negative', '');
              promptAction.showToast({ message: '感谢反馈！我们会在经验库中记录' });
            })
          }
          .margin({ top: 2 })
        }

        if (msg.time) {
          Text(msg.time).fontSize(9).fontColor('#9ca3af').margin({ top: 4 })
        }
      }
      .alignItems(HorizontalAlign.Start)
      .backgroundColor(ThemeColors.surface)
      .padding(12)
      .borderRadius({ topLeft: 16, topRight: 16, bottomRight: 16, bottomLeft: 4 })
      .constraintSize({ maxWidth: '80%' })
    }
  }

  @Builder DeleteConfirmDialog() {
    Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.5)').onClick(() => {
      this.cancelDelete();
    })
    Column({ space: 16 }) {
      Text('确认删除').fontSize(16).fontWeight(FontWeight.Bold).fontColor('#1f2937')
      Text('确定要删除这条消息吗？').fontSize(13).fontColor('#6b7280')
      Row({ space: 12 }) {
        Button('取消')
          .layoutWeight(1)
          .backgroundColor('#f3f4f6')
          .fontColor('#4b5563')
          .height(40)
          .onClick(() => { this.cancelDelete(); })
        Button('删除')
          .layoutWeight(1)
          .backgroundColor(ThemeColors.danger)
          .fontColor('#ffffff')
          .height(40)
          .onClick(() => { this.confirmDelete(); })
      }.width('100%')
    }
    .width('80%')
    .padding(24)
    .backgroundColor(ThemeColors.surface)
    .borderRadius(16)
    .zIndex(200)
  }

  @Builder SystemMessage(msg: ChatMessage) {
    Row() {
      Text(msg.content).fontSize(10).fontColor('#6b7280').backgroundColor('rgba(229, 231, 235, 0.5)').padding({ left: 12, right: 12, top: 4, bottom: 4 }).borderRadius(16)
    }.width('100%').justifyContent(FlexAlign.Center)
  }

  @Builder UserMessage(msg: ChatMessage) {
    Row() {
      Column({ space: 4 }) {
        if (msg.imageUrl) {
          Image(msg.imageUrl)
            .width(150)
            .height(150)
            .objectFit(ImageFit.Cover)
            .borderRadius(8)
        }
        Text(msg.content)
          .fontSize(13)
          .fontColor(ThemeColors.surface)
          .backgroundColor(ThemeColors.primary)
          .padding(12)
          .borderRadius({ topLeft: 16, topRight: 16, bottomLeft: 16, bottomRight: 4 })
          .constraintSize({ maxWidth: '75%' })
        if (msg.time) {
          Text(msg.time).fontSize(9).fontColor('#9ca3af')
        }
      }
    }.width('100%').justifyContent(FlexAlign.End).alignItems(VerticalAlign.Bottom)
  }

  @Builder AiMessage(msg: ChatMessage) {
    Row({ space: 8 }) {
      Stack() {
        Circle({ width: 32, height: 32 }).fill(ThemeColors.primary)
        Text('AI').fontSize(10).fontColor(ThemeColors.surface).fontWeight(FontWeight.Bold)
      }.alignSelf(ItemAlign.End)

      Column({ space: 8 }) {
        Text(msg.content).fontSize(13).fontColor('#374151').lineHeight(20)

        if (msg.embedLog) {
          this.EmbedLogCard(msg.embedLog)
        }

        if (msg.hasPumpControl) {
          this.PumpControlPanel()
        }

        if (msg.sessionId) {
          Row({ space: 12 }) {
            Row({ space: 4 }) {
              Text('👍').fontSize(14)
                .opacity(msg.feedback === 'positive' ? 1 : 0.5)
              Text('有用').fontSize(10).fontColor(msg.feedback === 'positive' ? ThemeColors.accent : '#9ca3af')
            }
            .padding({ left: 8, right: 8, top: 4, bottom: 4 })
            .backgroundColor(msg.feedback === 'positive' ? '#dcfce7' : '#f3f4f6')
            .borderRadius(12)
            .onClick(() => {
              if (msg.feedback) return;
              this.markFeedback(msg.id, 'positive');
              this.submitFeedback(msg.sessionId!, 'positive', '');
              promptAction.showToast({ message: '感谢反馈，已记录' });
            })

            Row({ space: 4 }) {
              Text('👎').fontSize(14)
                .opacity(msg.feedback === 'negative' ? 1 : 0.5)
              Text('没用').fontSize(10).fontColor(msg.feedback === 'negative' ? ThemeColors.danger : '#9ca3af')
            }
            .padding({ left: 8, right: 8, top: 4, bottom: 4 })
            .backgroundColor(msg.feedback === 'negative' ? '#fef2f2' : '#f3f4f6')
            .borderRadius(12)
            .onClick(() => {
              if (msg.feedback) return;
              this.markFeedback(msg.id, 'negative');
              this.submitFeedback(msg.sessionId!, 'negative', '');
              promptAction.showToast({ message: '感谢反馈！我们会在经验库中记录' });
            })
          }
          .margin({ top: 2 })
        }

        if (msg.time) {
          Text(msg.time).fontSize(9).fontColor('#9ca3af').margin({ top: 4 })
        }
      }
      .alignItems(HorizontalAlign.Start)
      .backgroundColor(ThemeColors.surface)
      .padding(12)
      .borderRadius({ topLeft: 16, topRight: 16, bottomRight: 16, bottomLeft: 4 })
      .constraintSize({ maxWidth: '80%' })
      .shadow({ radius: 2, color: 'rgba(0,0,0,0.02)', offsetY: 1 })
    }.width('100%').alignItems(VerticalAlign.Bottom)
  }

  @Builder EmbedLogCard(log: EmbedLog) {
    Row({ space: 8 }) {
      Circle({ width: 24, height: 24 }).fill(log.type === 'success' ? '#eff6ff' : log.type === 'warning' ? '#fef3c7' : '#f3f4f6')
      Column() {
        Text(log.title).fontSize(11).fontWeight(FontWeight.Bold).fontColor('#1f2937')
        Row() {
          Text(log.status).fontSize(10).fontColor(log.type === 'success' ? ThemeColors.accent : log.type === 'warning' ? ThemeColors.warning : '#6b7280')
          Text(log.time).fontSize(10).fontColor('#6b7280')
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ top: 4 })
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
    }.padding(10).backgroundColor('#f9fafb').borderRadius(8).border({ width: 1, color: '#f3f4f6' }).width('100%')
  }

  @Builder PumpControlPanel() {
    Column({ space: 12 }) {
      this.PumpSlider('大棚1', 50)
      this.PumpSlider('大棚2', 40)
      this.PumpSlider('大棚3', 60)
    }.padding(12).backgroundColor('#f9fafb').borderRadius(8).border({ width: 1, color: '#f3f4f6' }).width('100%')
  }

  @Builder PumpSlider(name: string, value: number) {
    Column({ space: 4 }) {
      Row() {
        Text(name).fontSize(12).fontWeight(FontWeight.Medium)
        Text(`${value}%`).fontSize(12).fontWeight(FontWeight.Medium).fontColor(ThemeColors.primary)
      }.width('100%').justifyContent(FlexAlign.SpaceBetween)
      Slider({ value: value, min: 0, max: 100, style: SliderStyle.OutSet })
        .selectedColor(ThemeColors.primary)
        .blockColor(ThemeColors.surface)
        .trackColor('#e5e7eb')
    }.width('100%')
  }

  @Builder TypingIndicator() {
    Row({ space: 8 }) {
      Stack() { Circle({ width: 32, height: 32 }).fill(ThemeColors.primary) }.alignSelf(ItemAlign.End)
      
      if (this.isThinking && this.isPredictionMode) {
        Column({ space: 6 }) {
          Row({ space: 6 }) {
            Text('🔮').fontSize(12)
            Text(this.thinkingStep === 1 ? '正在分析信号特征...' : 
                 this.thinkingStep === 2 ? '匹配预警模型...' : 
                 '生成预判结论...').fontSize(12).fontColor('#6b7280')
          }
          Row({ space: 4 }) {
            Circle({ width: 6, height: 6 }).fill(this.thinkingStep >= 1 ? ThemeColors.warning : '#d1d5db')
            Circle({ width: 6, height: 6 }).fill(this.thinkingStep >= 2 ? ThemeColors.warning : '#d1d5db')
            Circle({ width: 6, height: 6 }).fill(this.thinkingStep >= 3 ? ThemeColors.warning : '#d1d5db')
          }
        }
        .backgroundColor('#fffbeb').padding(14).borderRadius({ topLeft: 16, topRight: 16, bottomRight: 16, bottomLeft: 4 })
        .borderWidth(1).borderColor('#fef3c7')
      } else {
        Row({ space: 4 }) {
          Circle({ width: 6, height: 6 }).fill('#d1d5db')
          Circle({ width: 6, height: 6 }).fill('#d1d5db')
          Circle({ width: 6, height: 6 }).fill('#d1d5db')
        }
        .backgroundColor(ThemeColors.surface).padding(14).borderRadius({ topLeft: 16, topRight: 16, bottomRight: 16, bottomLeft: 4 })
      }
    }.width('100%').alignItems(VerticalAlign.Bottom)
  }

  @Builder Header() {
    Column({ space: 8 }) {
      // 模式切换栏
      Row({ space: 0 }) {
        Text('🌾 农艺专家')
          .fontSize(12)
          .fontWeight(this.chatMode === 0 ? FontWeight.Bold : FontWeight.Normal)
          .fontColor(this.chatMode === 0 ? '#ffffff' : '#6b7280')
          .padding({ left: 16, right: 16, top: 6, bottom: 6 })
          .backgroundColor(this.chatMode === 0 ? '#0b5934' : 'transparent')
          .borderRadius({ topLeft: 16, bottomLeft: 16 })
          .onClick(() => { this.chatMode = 0; })

        Text('⚙️ 设备调控')
          .fontSize(12)
          .fontWeight(this.chatMode === 1 ? FontWeight.Bold : FontWeight.Normal)
          .fontColor(this.chatMode === 1 ? '#ffffff' : '#6b7280')
          .padding({ left: 16, right: 16, top: 6, bottom: 6 })
          .backgroundColor(this.chatMode === 1 ? '#2563eb' : 'transparent')
          .borderRadius({ topRight: 16, bottomRight: 16 })
          .onClick(() => { this.chatMode = 1; })
      }
      .width('auto')
      .border({ width: 1, color: '#e5e7eb', radius: 16 })

      // 标题行
      Row() {
        Text(`智能交互 · ${this.getModeName()}`).fontSize(18).fontWeight(FontWeight.Bold).fontColor('#1f2937')
        Blank()
        if (this.isPredictionMode) {
          Row({ space: 4 }) {
            Text('📚').fontSize(12)
            Text(`${this.savedPredictions.length}`).fontSize(10).fontColor('#fff').fontWeight(FontWeight.Bold)
          }
          .backgroundColor(ThemeColors.warning)
          .padding({ left: 8, right: 8, top: 4, bottom: 4 })
          .borderRadius(12)
          .onClick(() => { this.showKnowledgeBaseModal = true; })
        }
        Row({ space: 6 }) {
          Circle({ width: 6, height: 6 }).fill(this.isApiConnected ? ThemeColors.accent : ThemeColors.danger)
          Text(this.isApiConnected ? '大脑已连接' : '离线模式').fontSize(10).fontColor(this.isApiConnected ? ThemeColors.primary : ThemeColors.danger).fontWeight(FontWeight.Medium)
        }
        .backgroundColor(this.isApiConnected ? ThemeColors.primaryLight : '#fef2f2').padding({ left: 10, right: 10, top: 4, bottom: 4 }).borderRadius(12)
        .onClick(() => { this.showConnectionModal = true; })
      }
      .width('100%').justifyContent(FlexAlign.SpaceBetween)
    }
    .width('100%').padding(16).backgroundColor('rgba(255, 255, 255, 0.9)').backdropBlur(20)
  }

  @Builder SensorContext() {
    Row() {
      Row({ space: 16 }) {
        Row({ space: 4 }) {
          Text('☀️').fontSize(12)
          Text(`${this.lightIntensity}k`).fontSize(12).fontColor('#4b5563')
        }
        .onClick(() => { this.selectedEnvType = '光照'; this.showEnvDetailModal = true; })

        Row({ space: 4 }) {
          Text('💧').fontSize(12)
          Text(`${this.soilMoisture}%`).fontSize(12).fontColor(this.soilMoisture < 30 ? ThemeColors.danger : '#4b5563')
        }
        .onClick(() => { this.selectedEnvType = '水分'; this.showEnvDetailModal = true; })

        Row({ space: 4 }) {
          Text('🌡️').fontSize(12)
          Text(`${this.temperature}°C`).fontSize(12).fontColor('#4b5563')
        }
        .onClick(() => { this.selectedEnvType = '温度'; this.showEnvDetailModal = true; })
      }
      Text('刷新')
        .fontSize(10)
        .fontColor(ThemeColors.primary)
        .decoration({ type: TextDecorationType.Underline })
        .scale({ x: this.refreshScale, y: this.refreshScale })
        .onClick(() => { this.doRefresh(); })
    }
    .width('100%').padding({ left: 16, right: 16, top: 8, bottom: 8 })
    .backgroundColor('#f8faf9').border({ width: { bottom: 1 }, color: '#f3f4f6' })
    .justifyContent(FlexAlign.SpaceBetween)
  }

  @Builder ConnectionModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => this.showConnectionModal = false)
      Column() {
        Row() {
          Text('连接详情').fontSize(16).fontWeight(FontWeight.Bold)
          Text('✕').fontSize(16).fontColor('#6b7280').onClick(() => this.showConnectionModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16).borderWidth({ bottom: 1 }).borderColor('#e5e7eb')

        Column({ space: 12 }) {
          Row() { Text('API状态'); Text(this.isApiConnected ? '已连接' : '离线').fontColor(this.isApiConnected ? ThemeColors.accent : ThemeColors.danger) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
          Row() { Text('API延迟'); Text(`${this.lastApiLatency}ms`).fontColor(ThemeColors.primary) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
          Row() { Text('API地址'); Text(ApiConfig.BASE_URL).fontSize(10).fontColor('#6b7280') }.width('100%').justifyContent(FlexAlign.SpaceBetween)
          Row() { Text('在线设备'); Text(`${this.onlineDeviceCount}台`).fontColor(ThemeColors.primary) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        }.padding(16)

        Button('重新连接')
          .width('100%')
          .backgroundColor(ThemeColors.primary)
          .height(40)
          .onClick(async () => {
            await this.checkApiHealth();
            this.showConnectionModal = false;
          })
        Button('关闭').width('100%').backgroundColor('#f3f4f6').height(40).fontColor('#4b5563').margin({ top: 8 })
          .onClick(() => { this.showConnectionModal = false; })
      }.width('80%').backgroundColor(ThemeColors.surface).borderRadius(16).padding(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder EnvDetailModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => this.showEnvDetailModal = false)
      Column() {
        Row() {
          Text(`${this.selectedEnvType}历史趋势`).fontSize(16).fontWeight(FontWeight.Bold)
          Text('✕').fontSize(16).fontColor('#6b7280').onClick(() => this.showEnvDetailModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16).borderWidth({ bottom: 1 }).borderColor('#e5e7eb')

        Column({ space: 8 }) {
          Row() { Text('当前值').fontSize(12).fontColor('#6b7280'); Text(this.selectedEnvType === '光照' ? `${this.lightIntensity}klx` : this.selectedEnvType === '水分' ? `${this.soilMoisture}%` : `${this.temperature}°C`).fontSize(20).fontWeight(FontWeight.Bold) }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        }.padding(16).backgroundColor('#f9fafb').borderRadius(8)

        Row({ space: 8 }) {
          Text('时间段：').fontSize(12)
          Text(this.envTimeRange).fontSize(12).fontColor(ThemeColors.primary)
        }.width('100%').margin({ top: 8 })

        Row({ space: 8 }) {
          Button('今日').fontSize(11).fontColor(this.envTimeRange === '今日' ? '#fff' : ThemeColors.primary).backgroundColor(this.envTimeRange === '今日' ? ThemeColors.primary : '#e5e7eb').height(28)
            .onClick(() => { this.envTimeRange = '今日'; })
          Button('本周').fontSize(11).fontColor(this.envTimeRange === '本周' ? '#fff' : ThemeColors.primary).backgroundColor(this.envTimeRange === '本周' ? ThemeColors.primary : '#e5e7eb').height(28)
            .onClick(() => { this.envTimeRange = '本周'; })
          Button('本月').fontSize(11).fontColor(this.envTimeRange === '本月' ? '#fff' : ThemeColors.primary).backgroundColor(this.envTimeRange === '本月' ? ThemeColors.primary : '#e5e7eb').height(28)
            .onClick(() => { this.envTimeRange = '本月'; })
        }.width('100%').margin({ top: 8 })

        Button('关闭').width('100%').backgroundColor(ThemeColors.primary).height(40).margin({ top: 16 })
          .onClick(() => { this.showEnvDetailModal = false; })
      }.width('85%').backgroundColor(ThemeColors.surface).borderRadius(16).padding(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder KnowledgeBaseModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => this.showKnowledgeBaseModal = false)
      Column() {
        Row() {
          Row({ space: 8 }) {
            Text('📚').fontSize(18)
            Text('时序预测知识库').fontSize(16).fontWeight(FontWeight.Bold)
          }
          Text('✕').fontSize(16).fontColor('#6b7280').onClick(() => this.showKnowledgeBaseModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16).borderWidth({ bottom: 1 }).borderColor('#e5e7eb')

        Scroll() {
          Column({ space: 12 }) {
            if (this.savedPredictions.length === 0) {
              Column() {
                Text('📭').fontSize(40).margin({ bottom: 12 })
                Text('知识库暂无记录').fontSize(14).fontColor('#6b7280')
                Text('在时序预测模式下进行预判分析后，记录将自动保存到这里').fontSize(11).fontColor('#9ca3af').textAlign(TextAlign.Center).margin({ top: 8 })
              }.width('100%').padding(32)
            } else {
              ForEach(this.savedPredictions, (prediction: PredictionKnowledge, index: number) => {
                Column({ space: 8 }) {
                  Row({ space: 8 }) {
                    Text('🔮').fontSize(14)
                    Text(prediction.prediction).fontSize(13).fontWeight(FontWeight.Bold).fontColor('#1f2937')
                  }.width('100%')
                  
                  Row({ space: 4 }) {
                    Text('信号：').fontSize(10).fontColor('#6b7280')
                    Text(prediction.keyword).fontSize(10).fontColor(ThemeColors.warning).fontWeight(FontWeight.Medium)
                  }
                  
                  Column({ space: 4 }) {
                    ForEach(prediction.signals, (signal: PredictionSignal) => {
                      Row({ space: 4 }) {
                        Text('•').fontSize(10).fontColor('#9ca3af')
                        Text(signal.signal).fontSize(10).fontColor('#4b5563')
                      }
                    })
                  }.width('100%').padding({ left: 8 })
                  
                  Row() {
                    Text('预判动作：').fontSize(10).fontColor('#6b7280')
                    Text(prediction.action.length > 30 ? prediction.action.substring(0, 30) + '...' : prediction.action).fontSize(10).fontColor(ThemeColors.accent)
                  }.width('100%')
                }
                .width('100%')
                .backgroundColor('#f9fafb')
                .padding(12)
                .borderRadius(12)
                .borderWidth(1)
                .borderColor('#e5e7eb')
              })
            }
          }.padding(16)
        }.width('100%').layoutWeight(1)

        Button('关闭').width('100%').backgroundColor(ThemeColors.primary).height(40).margin({ top: 12 })
          .onClick(() => { this.showKnowledgeBaseModal = false; })
      }.width('85%').height('70%').backgroundColor(ThemeColors.surface).borderRadius(16).padding(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder OperationLogicModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.5)').onClick(() => {
        this.showOperationLogicModal = false;
      })

      Column({ space: 20 }) {
        Row() {
          Text('操作逻辑').fontSize(18).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('✕').fontSize(18).fontColor(ThemeColors.textMuted).onClick(() => {
            this.showOperationLogicModal = false;
          })
        }.width('100%').justifyContent(FlexAlign.SpaceBetween)

        Column({ space: 12 }) {
          Text('输入内容：').fontSize(14).fontColor(ThemeColors.textMuted)
          Text(this.pendingInputText).fontSize(14).fontColor(ThemeColors.textMain).fontWeight(FontWeight.Bold)
            .width('100%')
            .padding(12)
            .backgroundColor(ThemeColors.primaryLight)
            .borderRadius(8)
        }.width('100%')

        Column({ space: 12 }) {
          Text('操作逻辑：').fontSize(14).fontColor(ThemeColors.textMuted)
          TextArea({ placeholder: '请输入操作逻辑...', controller: new TextAreaController() })
            .width('100%')
            .height(120)
            .backgroundColor('#f9fafb')
            .borderRadius(8)
            .borderWidth(1)
            .borderColor('#e5e7eb')
            .onChange((value: string) => {
              this.operationLogicInput = value;
            })
        }.width('100%')

        Row({ space: 12 }) {
          Button('取消')
            .layoutWeight(1)
            .backgroundColor('#f3f4f6')
            .fontColor('#6b7280')
            .height(44)
            .onClick(() => {
              this.showOperationLogicModal = false;
            })

          Button('提交')
            .layoutWeight(1)
            .backgroundColor(ThemeColors.primary)
            .fontColor('#ffffff')
            .height(44)
            .onClick(() => {
              this.showOperationLogicModal = false;
              this.submitMessage(this.pendingInputText, this.operationLogicInput);
            })
        }.width('100%')
      }
      .width('85%')
      .backgroundColor(ThemeColors.surface)
      .borderRadius(20)
      .padding(24)
    }
    .width('100%')
    .height('100%')
    .zIndex(100)
  }

  @Builder HistoryModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => this.showHistoryModal = false)
      Column() {
        Row() {
          Text('历史对话').fontSize(16).fontWeight(FontWeight.Bold)
          Text('✕').fontSize(16).fontColor('#6b7280').onClick(() => this.showHistoryModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16).borderWidth({ bottom: 1 }).borderColor('#e5e7eb')

        Column({ space: 12 }) {
          Text('暂无更多历史记录').fontSize(14).fontColor('#9ca3af')
        }.padding(32).width('100%')

        Button('关闭').width('100%').backgroundColor(ThemeColors.primary).height(40)
          .onClick(() => { this.showHistoryModal = false; })
      }.width('85%').backgroundColor(ThemeColors.surface).borderRadius(16).padding(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder InputArea() {
    Column() {
      Scroll() {
        Row({ space: 8 }) {
          ForEach(this.quickCommands, (cmd: QuickCommand) => {
            this.Chip(cmd.text, cmd.isPrimary, cmd.isHighlighted)
          })
          this.Chip('+', false, false)
        }.padding({ left: 16, right: 16, top: 10, bottom: 10 })
      }.scrollable(ScrollDirection.Horizontal).scrollBar(BarState.Off)
      .border({ width: { bottom: 1 }, color: '#f9fafb' })

      // 输入框区域 - 仿微信风格：相机 | 输入框 | 语音 | 加号
      Row({ space: 8 }) {
        // 左侧相机按钮（圆形图标）
        Text('📷')
          .fontSize(22)
          .width(36)
          .height(36)
          .borderRadius(18)
          .backgroundColor('#f0f0f0')
          .textAlign(TextAlign.Center)
          .onClick(() => { this.pickAndAnalyzeImage(); })

        // 中间输入框 + 右侧按钮
        Row({ space: 8 }) {
          TextArea({
            placeholder: this.chatMode === 1 ? '输入设备控制指令...' : (this.isPredictionMode ? '输入信号预判分析...' : '咨询农艺问题...'),
            text: this.inputText
          })
            .onChange((value: string) => { this.inputText = value; })
            .backgroundColor('transparent')
            .fontSize(14)
            .fontColor('#1f2937')
            .placeholderColor('#9ca3af')
            .placeholderFont({ size: 13 })
            .layoutWeight(1)
            .height(40)
            .padding({ left: 4, right: 4, top: 6, bottom: 6 })

          if (this.inputText.trim()) {
            Text('发送')
              .fontSize(13)
              .fontWeight(FontWeight.Bold)
              .fontColor('#ffffff')
              .padding({ left: 14, right: 14, top: 7, bottom: 7 })
              .backgroundColor(ThemeColors.primary)
              .borderRadius(18)
              .onClick(() => {
                if (this.inputText.trim()) {
                  this.sendMessage(this.inputText);
                }
              })
          } else {
            // 无文字时显示语音 + 加号
            Row({ space: 10 }) {
              Text('🔊')
                .fontSize(20)
                .width(34)
                .height(34)
                .borderRadius(17)
                .backgroundColor('#f0f0f0')
                .textAlign(TextAlign.Center)
                .onClick(() => { this.showVoiceOverlay = true; setTimeout(() => { this.voiceText = "把温度调低一点"; }, 1500); })

              Text('+')
                .fontSize(22)
                .fontWeight(FontWeight.Medium)
                .fontColor('#333')
                .width(34)
                .height(34)
                .borderRadius(17)
                .backgroundColor('#f0f0f0')
                .textAlign(TextAlign.Center)
                .onClick(() => { this.showMoreMenu = true; })
            }
          }
        }
        .layoutWeight(1)
        .backgroundColor('#ffffff')
        .borderRadius(24)
        .border({ width: 1, color: '#e2e8f0' })
        .padding({ left: 12, right: 10, top: 4, bottom: 4 })
      }
      .width('100%').padding({ left: 12, right: 12, top: 8, bottom: 8 }).backgroundColor('#f8faf9')
    }.width('100%').backgroundColor(ThemeColors.surface)
  }

  // 加号菜单弹窗 - 仿微信底部弹出面板（2×2网格）
  @Builder MoreMenuPanel() {
    if (this.showMoreMenu) {
      Column() {
        Blank()

        // 底部菜单面板
        Column({ space: 28 }) {
          // 拖动条
          Row().width(36).height(4).backgroundColor('#d1d5db').borderRadius(2)

          // 功能按钮 - 2×2 网格
          Row({ space: 0 }) {
            Column({ space: 12 }) {
              this.MoreMenuItem('📷', '相册', '#10b981')
            }
            .layoutWeight(1)
            .alignItems(HorizontalAlign.Center)

            Column({ space: 12 }) {
              this.MoreMenuItem('📎', '文件', '#6b7280')
            }
            .layoutWeight(1)
            .alignItems(HorizontalAlign.Center)
          }
          .width('100%')

          Row({ space: 0 }) {
            Column({ space: 12 }) {
              this.MoreMenuItem('📞', '打电话', '#3b82f6')
            }
            .layoutWeight(1)
            .alignItems(HorizontalAlign.Center)

            Column({ space: 12 }) {
              this.MoreMenuItem('🔮', '时序预测', this.isPredictionMode ? '#f59e0b' : '#8b5cf6')
            }
            .layoutWeight(1)
            .alignItems(HorizontalAlign.Center)
          }
          .width('100%')
        }
        .width('100%')
        .padding({ left: 24, right: 24, top: 24, bottom: 48 })
        .backgroundColor('#ffffff')
        .borderRadius({ topLeft: 20, topRight: 20 })
      }
      .width('100%').height('100%')
      .backgroundColor('rgba(0,0,0,0.45)')
      .onClick(() => { this.showMoreMenu = false; })
    }
  }

  @Builder MoreMenuItem(icon: string, label: string, color: string) {
    Column({ space: 8 }) {
      Text(icon)
        .fontSize(30)
        .width(64)
        .height(64)
        .borderRadius(18)
        .backgroundColor(`${color}15`)
        .textAlign(TextAlign.Center)
      Text(label)
        .fontSize(11)
        .fontColor('#4b5563')
        .onClick(() => {
          this.showMoreMenu = false;
          if (label === '相册') {
            this.pickAndAnalyzeImage();
          } else if (label === '打电话') {
            promptAction.showToast({ message: '通话功能开发中' });
          } else if (label === '文件') {
            promptAction.showToast({ message: '文件上传功能开发中' });
          } else if (label === '时序预测') {
            this.isPredictionMode = !this.isPredictionMode;
            if (this.isPredictionMode) {
              this.messages.push({
                id: Date.now().toString(),
                role: 'system',
                content: '🔮 已进入时序预测模式 · 输入信号进行预判分析'
              });
              this.messages.push({
                id: (Date.now() + 1).toString(),
                role: 'ai',
                content: '时序预测模式已激活。请输入您观察到的微小信号变化，例如：\n• 大棚温度轻微升高\n• 植物叶片微变\n• 花蕾颜色、大小有变化\n\n我将分析预警信号并给出预判动作。'
              });
            } else {
              this.messages.push({
                id: Date.now().toString(),
                role: 'system',
                content: '已退出时序预测模式'
              });
            }
            this.scrollToBottom();
          }
        })
    }
  }

  @Builder Chip(text: string, isPrimary: boolean = false, isHighlighted: boolean = false) {
    Text(text)
      .fontSize(11)
      .fontWeight(FontWeight.Medium)
      .fontColor(isHighlighted ? '#fff' : (isPrimary ? ThemeColors.primary : '#4b5563'))
      .backgroundColor(isHighlighted ? ThemeColors.accent : ThemeColors.surface)
      .padding({ left: 12, right: 12, top: 6, bottom: 6 })
      .borderRadius(16)
      .border({ width: 1, color: isHighlighted ? ThemeColors.accent : (isPrimary ? 'rgba(11, 89, 52, 0.2)' : '#e5e7eb') })
      .onClick(() => {
        if (text === '+') {
          promptAction.showToast({ message: '自定义指令功能开发中' });
        } else {
          this.sendMessage(text);
        }
      })
  }

  @Builder VoiceOverlay() {
    Stack({ alignContent: Alignment.Bottom }) {
      Column()
        .width('100%')
        .height('100%')
        .backgroundColor('rgba(15, 23, 42, 0.6)')
        .onClick(() => { this.showVoiceOverlay = false; })

      Column() {
        Row().width(48).height(6).backgroundColor('#e5e7eb').borderRadius(3).margin({ bottom: 24 })

        Text('正在聆听您的指令...').fontSize(14).fontColor('#6b7280').fontWeight(FontWeight.Medium).margin({ bottom: 32 })

        Text(`"${this.voiceText}"`)
          .fontSize(20).fontWeight(FontWeight.Bold)
          .fontColor(this.voiceText === '聆听中...' ? '#9ca3af' : '#1f2937')
          .margin({ bottom: 40 }).textAlign(TextAlign.Center).constraintSize({ minHeight: 30 })

        Stack() {
          Circle({ width: 90, height: 90 }).fill('rgba(11, 89, 52, 0.1)')
          Button('结束')
            .fontColor(ThemeColors.surface).fontSize(12).fontWeight(FontWeight.Bold)
            .width(80).height(80)
            .type(ButtonType.Circle)
            .backgroundColor(ThemeColors.primary)
            .shadow({ radius: 20, color: 'rgba(16, 185, 129, 0.3)', offsetY: 10 })
            .onClick(async () => {
              this.showVoiceOverlay = false;
              if (this.voiceText !== '聆听中...') {
                const response = await this.sendVoiceCommand(this.voiceText);
                this.messages.push({
                  id: Date.now().toString(),
                  role: 'user',
                  content: this.voiceText,
                  time: this.formatTime(new Date())
                });
                this.messages.push({
                  id: (Date.now() + 1).toString(),
                  role: 'ai',
                  content: response,
                  time: this.formatTime(new Date())
                });
                this.scrollToBottom();
              }
              this.voiceText = '聆听中...';
            })
        }.margin({ bottom: 32 })

        Row({ space: 8 }) {
          Text('您可以试着说：').fontSize(11).fontColor('#9ca3af')
          Text('开启灌溉').fontSize(11).fontColor('#4b5563').backgroundColor('#f3f4f6').padding({ left: 8, right: 8, top: 2, bottom: 2 }).borderRadius(4)
          Text('降低温度').fontSize(11).fontColor('#4b5563').backgroundColor('#f3f4f6').padding({ left: 8, right: 8, top: 2, bottom: 2 }).borderRadius(4)
        }
      }
      .width('100%')
      .backgroundColor(ThemeColors.surface)
      .borderRadius({ topLeft: 24, topRight: 24 })
      .padding({ top: 16, bottom: 48, left: 24, right: 24 })
      .animation({ duration: 300, curve: Curve.EaseOut })
    }
    .width('100%')
    .height('100%')
    .zIndex(60)
  }
}
