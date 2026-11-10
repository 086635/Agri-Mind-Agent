import { promptAction } from '@kit.ArkUI';
import { router } from '@kit.ArkUI';
import { http } from '@kit.NetworkKit';
import { ApiConfig } from '../common/ApiConfig';
import { photoAccessHelper } from '@kit.MediaLibraryKit';
import { fileIo } from '@kit.CoreFileKit';
import { util } from '@kit.ArkTS';

// ================= 主题颜色配置 (严格模式安全版) =================
class ThemeColors {
  static readonly base: string = '#f4f7f6';
  static readonly card: string = '#ffffff';
  static readonly primary: string = '#0b5934';
  static readonly primaryLight: string = '#e8f3ee';
  static readonly primaryDark: string = '#074025';
  static readonly textMain: string = '#1f2937';
  static readonly textMuted: string = '#6b7280';
  static readonly borderLight: string = '#f3f4f6';
  static readonly accent: string = '#10b981';
  static readonly danger: string = '#ef4444';
  static readonly warning: string = '#f59e0b';
}


interface DashboardActionItem {
  actor?: string;
  action?: string;
  reason?: string;
  status?: string;
  time?: string;
}

// ================= 上传结果数据 =================
interface UploadResult {
  annotated_url: string;
  report_filename: string;
  summary: string;
  stageAnalysis: string;
}

interface AnalysisSection {
  title: string;
  content: string;
}

interface ReportItem {
  filename: string;
  growth_stage?: string;
  stage_name?: string;
  timestamp?: string;
  created_at?: string;
  size?: number;
}

// ================= 数据接口与模拟数据 =================
interface HistoryRecord {
  id: string;
  stage: string;
  title: string;
  time: string;
  info: string;
  status: 'completed' | 'processing';
  crop: string;
  area: string;
  confidence: number;
  count: number;
  goodRate?: number;
  maturity?: number;
  description: string;
  emoji: string;
  pageRoute?: string;
}

interface YieldDetailItem {
  label: string;
  value: string;
}

const mockHistoryRecords: HistoryRecord[] = [
  { id: '1', stage: '选种期', title: '选种分析', time: '今天 10:00', info: '油菜花选种质量', status: 'completed', crop: '油菜花', area: '中双11号', confidence: 92, count: 1000, description: '一级种占比65%，二级种占比22%，三级种占比8%，等外种占比5%。整体质量良好，建议使用一级种播种。', emoji: '🌱' },
  { id: '2', stage: '生长期', title: '病虫害分析二', time: '今天 11:00', info: '病虫害', status: 'completed', crop: '油菜花', area: '薹花期', confidence: 88, count: 0, description: '菌核病零星发生，蚜虫早期危害，总体病虫害压力中度偏轻。需立即启动预防性措施。', emoji: '🐛' },
  { id: '3', stage: '生长期', title: '土壤环境分析二', time: '今天 11:15', info: '土壤环境', status: 'completed', crop: '油菜花', area: '黄褐土', confidence: 90, count: 0, description: '土壤酸化趋势明显、钾元素缺乏、结构板结、排水不畅。改良重点：调酸、补钾、增气、降渍。', emoji: '🌍' },
  { id: '4', stage: '生长期', title: '病虫害分析', time: '今天 11:30', info: 'A/B区域对比', status: 'completed', crop: '黄瓜', area: 'A/B区域', confidence: 91, count: 11, description: 'A区域发现潜叶蝇虫害+轻微叶斑病，B区域健康。已自动开启杀虫喷雾+通风杀菌。', emoji: '🐛', pageRoute: 'pages/PestAnalysisPage' },
  { id: '5', stage: '成熟期', title: '果实产出分析', time: '今天 14:20', info: 'A/B区域对比', status: 'completed', crop: '大豆', area: 'A/B区域', confidence: 88, count: 70, description: 'A区域低产风险，预估90kg/亩；B区域丰产预期，预估195kg/亩。建议对A区域启动高强度补肥。', emoji: '🫘', pageRoute: 'pages/FruitOutputAnalysisPage' },
  { id: '6', stage: '生长期', title: '土壤环境分析', time: '今天 15:45', info: 'A/B区域对比', status: 'completed', crop: '番茄', area: 'A/B区域', confidence: 95, count: 0, description: 'A区域土壤湿度12.7%严重缺水，B区域土壤湿度25.0%正常适宜。已开启A区域自动浇水阀。', emoji: '🌱', pageRoute: 'pages/SoilEnvironmentAnalysisPage' },
  { id: '7', stage: '成熟期', title: '植物倒伏分析', time: '今天 16:30', info: 'A/B区域对比', status: 'completed', crop: '玉米', area: 'A/B区域', confidence: 92, count: 0, description: 'A区域植株倒伏，倾斜角度42°；B区域植株正常直立。已开启植株扶正+补钾壮秆。', emoji: '🌾', pageRoute: 'pages/PlantLodgingAnalysisPage' },
  { id: '8', stage: '成熟期', title: '植物倒伏分析二', time: '今天 17:00', info: '植株倒伏风险评估', status: 'completed', crop: '油菜花', area: '角果发育期', confidence: 85, count: 0, description: '倒伏综合风险指数中等偏高。茎秆物理强度不足、根系发育受限、潜在病害威胁及不利天气概率四重叠加。', emoji: '🌾' },
  { id: '9', stage: '成熟期', title: '果实产出分析二', time: '今天 17:30', info: '果实产出评估', status: 'completed', crop: '油菜花', area: '中双11号', confidence: 87, count: 0, description: '实际亩产144.5公斤，属中等偏下水平。受倒伏、病害及养分失衡影响，产量损失约19%，品质指标不达标。', emoji: '🫘' }
];


@Component
export struct AgriSyncLifecyclePage {
  // ================= 状态管理 =================
  @State activeTab: string = 'seed'; // seed | growth | maturity

  // 上传结果状态
  @State seedUploadResult: UploadResult | null = null;
  @State growthUploadResult: UploadResult | null = null;
  @State maturityUploadResult: UploadResult | null = null;
  @State isUploading: boolean = false;

  // 阶段分析章节（从 Qwen 输出解析）
  @State seedAnalysisSections: AnalysisSection[] = [];
  @State growthAnalysisSections: AnalysisSection[] = [];
  @State maturityAnalysisSections: AnalysisSection[] = [];

  // 报告状态
  @State showReportsDialog: boolean = false;
  @State reportsList: ReportItem[] = [];
  @State reportDetail: string = '';
  @State showReportDetailDialog: boolean = false;

  // 弹窗状态
  @State selectedRecord: HistoryRecord | null = null;
  @State showSeedAnalysisModal: boolean = false;
  @State showPestAnalysisModal: boolean = false;
  @State showSoilAnalysisModal: boolean = false;
  @State showLodgingAnalysisModal: boolean = false;
  @State showFruitOutputAnalysisModal: boolean = false;

  // 产量预测状态
  @State showYieldPredictionModal: boolean = false;
  @State selectedYieldCrop: string = '';

  @State actionHistory: HistoryRecord[] = [];
  @State historyFromApi: boolean = false;
  @State filteredRecords: HistoryRecord[] = [];

  aboutToAppear(): void {
    this.fetchActionHistory();
  }

  async fetchActionHistory(): Promise<void> {
    try {
      const request = http.createHttp();
      const resp = await request.request(`${ApiConfig.BASE_URL}/analytics/dashboard`, {
        method: http.RequestMethod.GET,
        connectTimeout: 5000,
        readTimeout: 10000
      });
      request.destroy();

      if (resp.responseCode === 200 && resp.result) {
        const data: Record<string, Object> = JSON.parse(resp.result as string) as Record<string, Object>;
        const actions: DashboardActionItem[] = (data['recent_actions'] as DashboardActionItem[]) || [];
        if (actions.length > 0) {
          const mapped: HistoryRecord[] = [];
          for (let i = 0; i < actions.length; i++) {
            const a: DashboardActionItem = actions[i];
            const ctx: string = a.reason || '未知操作';
            const actType: string = a.action || 'CHAT';
            const isDevice: boolean = actType === 'VOICE_CMD';
            mapped.push({
              id: `api_${i}`,
              stage: isDevice ? '生长期' : '选种期',
              title: ctx.length > 12 ? ctx.substring(0, 12) + '...' : ctx,
              time: a.time ? this.formatActionTime(a.time) : '刚刚',
              info: isDevice ? '语音控制' : 'AI对话',
              status: 'completed' as 'completed',
              crop: isDevice ? '语音设备' : 'AI助手',
              area: actType,
              confidence: 90,
              count: 0,
              description: ctx,
              emoji: isDevice ? '🎤' : '💬'
            });
          }
          this.actionHistory = mapped;
          this.historyFromApi = true;
          this.filteredRecords = mapped;
        }
      }
    } catch (e) {
      this.historyFromApi = false;
      this.filteredRecords = this.getFilteredRecordsFallback();
    }
  }

  formatActionTime(isoStr: string): string {
    try {
      const d: Date = new Date(isoStr);
      const now: Date = new Date();
      const diffMs: number = now.getTime() - d.getTime();
      const diffMin: number = Math.floor(diffMs / 60000);
      if (diffMin < 1) return '刚刚';
      if (diffMin < 60) return `${diffMin}分钟前`;
      const diffHr: number = Math.floor(diffMin / 60);
      if (diffHr < 24) return `${diffHr}小时前`;
      return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    } catch (e) {
      return isoStr.substring(5, 16);
    }
  }

  // ================= 页面主视图 =================
  build() {
    Stack({ alignContent: Alignment.Bottom }) {

      Column() {
        this.Header()

        Scroll() {
          Column() {
            this.TopTabs()

            // 动态内容区
            Column() {
              if (this.activeTab === 'seed') {
                this.SeedContent()
              } else if (this.activeTab === 'growth') {
                this.GrowthContent()
              } else if (this.activeTab === 'maturity') {
                this.MaturityContent()
              }

              this.YieldPredictionSection()
              this.HistorySection()
            }
            .padding({ left: 16, right: 16, top: 16, bottom: 90 }) // 底部留白防遮挡
          }
        }
        .layoutWeight(1)
        .scrollBar(BarState.Off)
        .backgroundColor(ThemeColors.base)
        .align(Alignment.Top)
      }
      .width('100%')
      .height('100%')

      // 历史记录详情弹窗 (Modal)
      if (this.selectedRecord !== null) {
        this.RecordDetailModal()
      }

      // 选种分析详情弹窗
      if (this.showSeedAnalysisModal) {
        this.SeedAnalysisModal()
      }

      // 病虫害分析详情弹窗
      if (this.showPestAnalysisModal) {
        this.PestAnalysisModal()
      }

      // 土壤环境分析详情弹窗
      if (this.showSoilAnalysisModal) {
        this.SoilAnalysisModal()
      }

      // 植物倒伏分析详情弹窗
      if (this.showLodgingAnalysisModal) {
        this.PlantLodgingAnalysisModal()
      }

      // 果实产出分析详情弹窗
      if (this.showFruitOutputAnalysisModal) {
        this.FruitOutputAnalysisModal()
      }

      // 产量预测详情弹窗
      if (this.showYieldPredictionModal) {
        this.YieldPredictionDetailModal()
      }

      // 报告列表弹窗
      if (this.showReportsDialog) {
        this.ReportsListDialog()
      }

      // 报告详情弹窗
      if (this.showReportDetailDialog) {
        this.ReportDetailDialog()
      }
    }
    .width('100%')
    .height('100%')
    .backgroundColor(ThemeColors.base)
  }

  // ================= 图片选择与上传 =================
  async pickAndUploadImage(stage: string): Promise<void> {
    if (this.isUploading) {
      return;
    }

    try {
      const photoSelectOptions: photoAccessHelper.PhotoSelectOptions = {
        MIMEType: photoAccessHelper.PhotoViewMIMETypes.IMAGE_TYPE,
        maxSelectNumber: 1
      };

      const photoPicker = new photoAccessHelper.PhotoViewPicker();
      const photoSelectResult: photoAccessHelper.PhotoSelectResult = await photoPicker.select(photoSelectOptions);

      if (photoSelectResult.photoUris && photoSelectResult.photoUris.length > 0) {
        const sourceUri = photoSelectResult.photoUris[0];
        this.isUploading = true;
        promptAction.showToast({ message: '正在上传图片...' });

        // 直接使用 base64 方式上传（稳定可靠，不依赖 MultipartFormData）
        const uploadResult = await this.uploadImageBase64(sourceUri, stage);

        if (uploadResult) {
          // 存储上传结果
          if (stage === 'seed') {
            this.seedUploadResult = uploadResult;
          } else if (stage === 'growth') {
            this.growthUploadResult = uploadResult;
          } else {
            this.maturityUploadResult = uploadResult;
          }

          // 调用 /analyze/json 获取阶段分析
          await this.analyzeLifecycle(stage);
          promptAction.showToast({ message: '分析完成' });
        }

        this.isUploading = false;
      }
    } catch (error) {
      this.isUploading = false;
      promptAction.showToast({ message: '图片选择取消或失败' });
    }
  }

  // 读取图片文件并转为 base64，通过 JSON POST 上传
  async uploadImageBase64(sourceUri: string, growthStage: string): Promise<UploadResult | null> {
    try {
      // 1. 将图片从 file://media/ 复制到 cache 目录
      const context = getContext(this);
      const cacheDir = context.cacheDir;
      const fileName = `upload_${Date.now()}.jpg`;
      const destPath = `${cacheDir}/${fileName}`;

      const srcFd = fileIo.openSync(sourceUri, fileIo.OpenMode.READ_ONLY);
      const destFd = fileIo.openSync(destPath, fileIo.OpenMode.CREATE | fileIo.OpenMode.WRITE_ONLY | fileIo.OpenMode.TRUNC);
      try {
        const srcStat: fileIo.Stat = fileIo.statSync(sourceUri);
        const fileSize: number = srcStat.size;
        const buf = new ArrayBuffer(fileSize);
        fileIo.readSync(srcFd.fd, buf);
        fileIo.writeSync(destFd.fd, buf);
      } finally {
        fileIo.closeSync(srcFd);
        fileIo.closeSync(destFd);
      }

      // 2. 从 cache 目录读取文件内容
      const readFd = fileIo.openSync(destPath, fileIo.OpenMode.READ_ONLY);
      const readStat: fileIo.Stat = fileIo.statSync(destPath);
      const readSize: number = readStat.size;
      const buffer = new ArrayBuffer(readSize);
      fileIo.readSync(readFd.fd, buffer);
      fileIo.closeSync(readFd);

      // 3. 使用 util.Base64Helper 编码（ArkTS 严格模式安全）
      const base64Helper = new util.Base64Helper();
      const encodedBuf: Uint8Array = new Uint8Array(buffer);
      const base64Str: string = base64Helper.encodeToStringSync(encodedBuf);

      // 4. 通过 JSON POST 发送到 /upload/base64
      const httpRequest = http.createHttp();
      const response = await httpRequest.request(
        ApiConfig.BASE_URL + '/upload/base64',
        {
          method: http.RequestMethod.POST,
          header: { 'Content-Type': 'application/json' },
          extraData: JSON.stringify({
            image_base64: base64Str,
            filename: `upload_${growthStage}_${Date.now()}.jpg`,
            growth_stage: growthStage
          }),
          connectTimeout: 10000,
          readTimeout: 60000,
          expectDataType: http.HttpDataType.STRING
        }
      );
      httpRequest.destroy();

      if (response.responseCode === 200 && response.result) {
        const data: Record<string, Object> = JSON.parse(response.result as string) as Record<string, Object>;
        const stageAnalysis: string = (data['stage_analysis'] as string) || '';
        // 构建中文检测摘要
        const detections: Object[] = (data['detections'] as Object[]) || [];
        let summaryText: string = '';
        if (detections.length > 0) {
          const detParts: string[] = [];
          for (let i = 0; i < detections.length; i++) {
            const det: Record<string, Object> = detections[i] as Record<string, Object>;
            const cn: string = (det['class_name_cn'] as string) || (det['class_name'] as string) || '未知';
            const conf: number = (det['confidence'] as number) || 0;
            detParts.push(`${cn}(${(conf * 100).toFixed(0)}%)`);
          }
          summaryText = `检测到 ${detections.length} 个目标：${detParts.join('、')}`;
        } else {
          summaryText = '未检测到明确目标';
        }
        const actionAdvice: string = (data['summary'] as Record<string, Object>) ?
          ((data['summary'] as Record<string, Object>)['action_advice'] as string) || '' : '';
        if (actionAdvice) {
          summaryText = `${summaryText}\n${actionAdvice}`;
        }
        const uploadResult: UploadResult = {
          annotated_url: (data['annotated_url'] as string) || '',
          report_filename: (data['report_filename'] as string) || '',
          summary: summaryText,
          stageAnalysis: stageAnalysis
        } as UploadResult;

        // 解析阶段分析并存储
        const sections: AnalysisSection[] = this.parseAnalysisSections(stageAnalysis);
        if (growthStage === 'seed') {
          this.seedAnalysisSections = sections;
        } else if (growthStage === 'growth') {
          this.growthAnalysisSections = sections;
        } else {
          this.maturityAnalysisSections = sections;
        }

        return uploadResult;
      }
      return null;
    } catch (error) {
      promptAction.showToast({ message: '上传失败' });
      return null;
    }
  }

  async analyzeLifecycle(growthStage: string): Promise<void> {
    try {
      const httpRequest = http.createHttp();
      const response = await httpRequest.request(
        ApiConfig.BASE_URL + '/analyze/json',
        {
          method: http.RequestMethod.POST,
          header: { 'Content-Type': 'application/json' },
          extraData: JSON.stringify({
            analysis_type: 'lifecycle',
            growth_stage: growthStage,
            test_mode: false
          }),
          connectTimeout: 10000,
          readTimeout: 60000
        }
      );
      httpRequest.destroy();

      if (response.responseCode === 200 && response.result) {
        const data: Record<string, Object> = JSON.parse(response.result as string) as Record<string, Object>;
        // 更新对应阶段的 summary
        const newSummary: string = (data['summary'] as string) || (data['message'] as string) || '';
        if (newSummary) {
          if (growthStage === 'seed' && this.seedUploadResult) {
            this.seedUploadResult = { annotated_url: this.seedUploadResult.annotated_url, report_filename: this.seedUploadResult.report_filename, summary: newSummary } as UploadResult;
          } else if (growthStage === 'growth' && this.growthUploadResult) {
            this.growthUploadResult = { annotated_url: this.growthUploadResult.annotated_url, report_filename: this.growthUploadResult.report_filename, summary: newSummary } as UploadResult;
          } else if (growthStage === 'maturity' && this.maturityUploadResult) {
            this.maturityUploadResult = { annotated_url: this.maturityUploadResult.annotated_url, report_filename: this.maturityUploadResult.report_filename, summary: newSummary } as UploadResult;
          }
        }
      }
    } catch (error) {
      // 分析失败不影响上传结果显示
    }
  }

  clearUploadResult(stage: string): void {
    if (stage === 'seed') {
      this.seedUploadResult = null;
      this.seedAnalysisSections = [];
    } else if (stage === 'growth') {
      this.growthUploadResult = null;
      this.growthAnalysisSections = [];
    } else {
      this.maturityUploadResult = null;
      this.maturityAnalysisSections = [];
    }
  }

  parseAnalysisSections(analysis: string): AnalysisSection[] {
    if (!analysis) {
      return [] as AnalysisSection[];
    }
    const sections: AnalysisSection[] = [];
    const parts: string[] = analysis.split('##');
    for (let i = 1; i < parts.length; i++) {
      const part: string = parts[i].trim();
      if (!part) {
        continue;
      }
      const newlineIdx: number = part.indexOf('\n');
      let title: string = '';
      let content: string = '';
      if (newlineIdx > 0) {
        title = part.substring(0, newlineIdx).trim();
        content = part.substring(newlineIdx + 1).trim();
      } else {
        title = part.trim();
        content = '';
      }
      if (title) {
        sections.push({ title: title, content: content } as AnalysisSection);
      }
    }
    return sections;
  }

  getUploadResult(stage: string): UploadResult | null {
    if (stage === 'seed') {
      return this.seedUploadResult;
    } else if (stage === 'growth') {
      return this.growthUploadResult;
    } else {
      return this.maturityUploadResult;
    }
  }

  // ================= 报告功能 =================
  async fetchReports(stage?: string): Promise<void> {
    try {
      const httpRequest = http.createHttp();
      const url: string = stage ?
        ApiConfig.BASE_URL + '/reports?growth_stage=' + stage :
        ApiConfig.BASE_URL + '/reports';
      const response = await httpRequest.request(
        url,
        {
          method: http.RequestMethod.GET,
          connectTimeout: 5000,
          readTimeout: 10000
        }
      );
      httpRequest.destroy();

      if (response.responseCode === 200 && response.result) {
        const data: Record<string, Object> = JSON.parse(response.result as string) as Record<string, Object>;
        if (Array.isArray(data)) {
          this.reportsList = data as ReportItem[];
        } else if (data['reports'] && Array.isArray(data['reports'])) {
          this.reportsList = data['reports'] as ReportItem[];
        } else {
          this.reportsList = [];
        }
      }
    } catch (error) {
      this.reportsList = [];
      promptAction.showToast({ message: '获取报告列表失败' });
    }
    this.showReportsDialog = true;
  }

  async fetchReportDetail(filename: string): Promise<void> {
    try {
      const httpRequest = http.createHttp();
      const response = await httpRequest.request(
        ApiConfig.BASE_URL + '/reports/' + filename,
        {
          method: http.RequestMethod.GET,
          connectTimeout: 5000,
          readTimeout: 10000
        }
      );
      httpRequest.destroy();

      if (response.responseCode === 200 && response.result) {
        const data: Record<string, Object> = JSON.parse(response.result as string) as Record<string, Object>;
        // 只提取 stage_analysis 内容
        const analysis: string = (data['stage_analysis'] as string) || '';
        if (analysis) {
          // 解析 ## 章节并渲染
          const sections: AnalysisSection[] = this.parseAnalysisSections(analysis);
          if (sections.length > 0) {
            // 用章节格式显示
            const parts: string[] = [];
            for (let i = 0; i < sections.length; i++) {
              parts.push(`【${sections[i].title}】\n${sections[i].content}`);
            }
            this.reportDetail = parts.join('\n\n');
          } else {
            this.reportDetail = analysis;
          }
        } else {
          this.reportDetail = '暂无分析内容';
        }
      } else {
        this.reportDetail = '无法加载报告内容';
      }
    } catch (error) {
      this.reportDetail = '加载报告失败';
    }
    this.showReportDetailDialog = true;
  }

  // ================= 局部组件 Builder =================

  @Builder Header() {
    Row() {
      Text('AI全生命周期').fontSize(18).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
      Row({ space: 6 }) {
        Circle({ width: 6, height: 6 }).fill(ThemeColors.accent)
        Text('视觉中心: 已连接').fontSize(10).fontColor(ThemeColors.primary).fontWeight(FontWeight.Medium)
      }
      .backgroundColor('rgba(16, 185, 129, 0.1)').padding({ left: 10, right: 10, top: 4, bottom: 4 })
      .borderRadius(12).borderWidth(1).borderColor('rgba(16, 185, 129, 0.2)')
    }
    .width('100%').padding(16).backgroundColor('rgba(255, 255, 255, 0.95)').backdropBlur(20)
    .borderWidth({ bottom: 1 }).borderColor(ThemeColors.borderLight)
    .justifyContent(FlexAlign.SpaceBetween).zIndex(30)
  }

  @Builder TopTabs() {
    Stack({ alignContent: Alignment.Center }) {
      // 背景连接线
      Row().width('80%').height(2).backgroundColor(ThemeColors.borderLight)
      // 激活进度线
      Row().width(this.activeTab === 'seed' ? '0%' : (this.activeTab === 'growth' ? '40%' : '80%'))
        .height(2).backgroundColor(ThemeColors.primary)
        .position({ x: '10%', y: 39 })
        .animation({ duration: 300, curve: Curve.EaseInOut })

      Row() {
        this.TabItem('seed', '🌱', '选种期')
        this.TabItem('growth', '🌿', '生长期')
        this.TabItem('maturity', '🍅', '成熟期')
      }.width('100%').justifyContent(FlexAlign.SpaceAround)
    }.width('100%').backgroundColor(ThemeColors.card).padding({ top: 20, bottom: 20 })
    .borderWidth({ bottom: 1 }).borderColor(ThemeColors.borderLight)
  }

  @Builder TabItem(id: string, emoji: string, title: string) {
    Column({ space: 6 }) {
      Row() { Text(emoji).fontSize(20) }
      .width(40).height(40).borderRadius(20)
      .backgroundColor(this.activeTab === id ? ThemeColors.primary : ThemeColors.card)
      .borderWidth(this.activeTab === id ? 4 : 2)
      .borderColor(this.activeTab === id ? ThemeColors.primaryLight : ThemeColors.borderLight)
      .justifyContent(FlexAlign.Center)
      Text(title)
        .fontSize(11).fontWeight(this.activeTab === id ? FontWeight.Bold : FontWeight.Medium)
        .fontColor(this.activeTab === id ? ThemeColors.primary : ThemeColors.textMuted)
    }.onClick(() => { this.activeTab = id; this.filteredRecords = this.getFilteredRecords(); })
  }

  // 1. 选种期内容
  @Builder SeedContent() {
    Column() {
      // 图片上传/展示区域
      if (this.seedUploadResult) {
        Stack({ alignContent: Alignment.TopEnd }) {
          Image(ApiConfig.BASE_URL + this.seedUploadResult.annotated_url)
            .width('100%').height(180).objectFit(ImageFit.Cover).borderRadius(12)
          Text('✕').fontSize(14).fontColor('#fff').width(28).height(28).backgroundColor('rgba(0,0,0,0.5)')
            .borderRadius(14).textAlign(TextAlign.Center).margin({ top: 8, right: 8 })
            .onClick(() => this.clearUploadResult('seed'))
        }.width('100%').margin({ bottom: 12 })

        // 检测摘要
        Column({ space: 6 }) {
          Text('检测摘要').fontSize(12).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
          Text(this.seedUploadResult.summary).fontSize(11).fontColor(ThemeColors.textMain).lineHeight(16)
        }.width('100%').padding(10).backgroundColor(ThemeColors.primaryLight).borderRadius(8).margin({ bottom: 12 })
      } else {
        Column() {
          if (this.isUploading && this.activeTab === 'seed') {
            LoadingProgress().width(32).height(32).color(ThemeColors.primary)
            Text('正在上传分析...').fontSize(12).fontColor(ThemeColors.textMuted).margin({ top: 8 })
          } else {
            Text('📷').fontSize(32)
            Text('点击选择图片').fontSize(12).fontColor(ThemeColors.textMuted).margin({ top: 8 })
          }
        }.width('100%').height(180).backgroundColor(ThemeColors.borderLight).borderRadius(12).justifyContent(FlexAlign.Center).margin({ bottom: 12 })
        .onClick(() => this.pickAndUploadImage('seed'))
      }

      Row() {
        Button('查看报告').fontSize(12).backgroundColor(ThemeColors.primaryLight).fontColor(ThemeColors.primary).height(36).layoutWeight(1)
          .onClick(() => this.fetchReports('seed'))
        Button('导出筛选报告').fontSize(12).backgroundColor(ThemeColors.primary).fontColor('#fff').height(36).layoutWeight(1).margin({ left: 8 })
          .onClick(() => {
            if (this.seedUploadResult) {
              this.showSeedAnalysisModal = true;
            } else {
              promptAction.showToast({ message: '请先上传图片' });
            }
          })
      }.width('100%')
    }.backgroundColor(ThemeColors.card).borderRadius(16).padding(16).borderWidth(1).borderColor(ThemeColors.borderLight)
  }


  // 2. 生长期内容
  @Builder GrowthContent() {
    Column() {
      // 图片上传/展示区域
      if (this.growthUploadResult) {
        Stack({ alignContent: Alignment.TopEnd }) {
          Image(ApiConfig.BASE_URL + this.growthUploadResult.annotated_url)
            .width('100%').height(180).objectFit(ImageFit.Cover).borderRadius(12)
          Text('✕').fontSize(14).fontColor('#fff').width(28).height(28).backgroundColor('rgba(0,0,0,0.5)')
            .borderRadius(14).textAlign(TextAlign.Center).margin({ top: 8, right: 8 })
            .onClick(() => this.clearUploadResult('growth'))
        }.width('100%').margin({ bottom: 12 })

        // 检测摘要
        Column({ space: 6 }) {
          Text('检测摘要').fontSize(12).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
          Text(this.growthUploadResult.summary).fontSize(11).fontColor(ThemeColors.textMain).lineHeight(16)
        }.width('100%').padding(10).backgroundColor(ThemeColors.primaryLight).borderRadius(8).margin({ bottom: 12 })
      } else {
        Column() {
          if (this.isUploading && this.activeTab === 'growth') {
            LoadingProgress().width(32).height(32).color(ThemeColors.primary)
            Text('正在上传分析...').fontSize(12).fontColor(ThemeColors.textMuted).margin({ top: 8 })
          } else {
            Text('📷').fontSize(32)
            Text('点击选择图片').fontSize(12).fontColor(ThemeColors.textMuted).margin({ top: 8 })
          }
        }.width('100%').height(180).backgroundColor(ThemeColors.borderLight).borderRadius(12).justifyContent(FlexAlign.Center).margin({ bottom: 12 })
        .onClick(() => this.pickAndUploadImage('growth'))
      }

      Row() {
        Button('查看报告').fontSize(12).backgroundColor(ThemeColors.primaryLight).fontColor(ThemeColors.primary).height(36).layoutWeight(1)
          .onClick(() => this.fetchReports('growth'))
        Button('导出生长报告').fontSize(12).backgroundColor(ThemeColors.primary).fontColor('#fff').height(36).layoutWeight(1).margin({ left: 8 })
          .onClick(() => {
            if (this.growthUploadResult) {
              promptAction.showToast({ message: '正在生成报告...' });
              setTimeout(() => { this.showPestAnalysisModal = true; }, 1000);
            } else {
              promptAction.showToast({ message: '请先上传图片' });
            }
          })
      }.width('100%')
    }.backgroundColor(ThemeColors.card).borderRadius(16).padding(16).borderWidth(1).borderColor(ThemeColors.borderLight)
  }

  // 3. 成熟期内容
  @Builder MaturityContent() {
    Column() {
      // 图片上传/展示区域
      if (this.maturityUploadResult) {
        Stack({ alignContent: Alignment.TopEnd }) {
          Image(ApiConfig.BASE_URL + this.maturityUploadResult.annotated_url)
            .width('100%').height(180).objectFit(ImageFit.Cover).borderRadius(12)
          Text('✕').fontSize(14).fontColor('#fff').width(28).height(28).backgroundColor('rgba(0,0,0,0.5)')
            .borderRadius(14).textAlign(TextAlign.Center).margin({ top: 8, right: 8 })
            .onClick(() => this.clearUploadResult('maturity'))
        }.width('100%').margin({ bottom: 12 })

        // 检测摘要
        Column({ space: 6 }) {
          Text('检测摘要').fontSize(12).fontWeight(FontWeight.Bold).fontColor(ThemeColors.warning)
          Text(this.maturityUploadResult.summary).fontSize(11).fontColor(ThemeColors.textMain).lineHeight(16)
        }.width('100%').padding(10).backgroundColor('#fef3c7').borderRadius(8).margin({ bottom: 12 })
      } else {
        Column() {
          if (this.isUploading && this.activeTab === 'maturity') {
            LoadingProgress().width(32).height(32).color(ThemeColors.warning)
            Text('正在上传分析...').fontSize(12).fontColor(ThemeColors.textMuted).margin({ top: 8 })
          } else {
            Text('📷').fontSize(32)
            Text('点击选择图片').fontSize(12).fontColor(ThemeColors.textMuted).margin({ top: 8 })
          }
        }.width('100%').height(180).backgroundColor(ThemeColors.borderLight).borderRadius(12).justifyContent(FlexAlign.Center).margin({ bottom: 12 })
        .onClick(() => this.pickAndUploadImage('maturity'))
      }

      Row() {
        Button('查看报告').fontSize(12).backgroundColor('#fef3c7').fontColor(ThemeColors.warning).height(36).layoutWeight(1)
          .onClick(() => this.fetchReports('maturity'))
        Button('导出采收报告').fontSize(12).backgroundColor(ThemeColors.warning).fontColor('#fff').height(36).layoutWeight(1).margin({ left: 8 })
          .onClick(() => {
            if (this.maturityUploadResult) {
              promptAction.showToast({ message: '正在生成报告...' });
              setTimeout(() => { this.showFruitOutputAnalysisModal = true; }, 1000);
            } else {
              promptAction.showToast({ message: '请先上传图片' });
            }
          })
      }.width('100%')
    }.backgroundColor(ThemeColors.card).borderRadius(16).padding(16).borderWidth(1).borderColor(ThemeColors.borderLight)
  }

  getFilteredRecords(): HistoryRecord[] {
    if (this.historyFromApi && this.actionHistory.length > 0) {
      return this.actionHistory;
    }
    return this.getFilteredRecordsFallback();
  }

  getFilteredRecordsFallback(): HistoryRecord[] {
    if (this.activeTab === 'seed') {
      return mockHistoryRecords.filter(r => r.stage === '选种期');
    } else if (this.activeTab === 'growth') {
      return mockHistoryRecords.filter(r => r.stage === '生长期');
    } else if (this.activeTab === 'maturity') {
      return mockHistoryRecords.filter(r => r.stage === '成熟期');
    }
    return [];
  }

  // 产量预测区域
  @Builder YieldPredictionSection() {
    Column() {
      Row({ space: 6 }) { 
        Text('📈').fontSize(14); 
        Text('产量预测').fontSize(11).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMuted) 
      }.width('100%').margin({ top: 24, bottom: 12 })

      Scroll() {
        Row({ space: 12 }) {
          this.YieldPredictionCard('🍅', '番茄', '预计产量', '2,850', 'kg/亩', '+12.5%', true)
          this.YieldPredictionCard('🥒', '黄瓜', '预计产量', '3,200', 'kg/亩', '+8.3%', true)
          this.YieldPredictionCard('🌽', '玉米', '预计产量', '650', 'kg/亩', '-5.2%', false)
          this.YieldPredictionCard('🥬', '白菜', '预计产量', '4,500', 'kg/亩', '+15.8%', true)
          this.YieldPredictionCard('🌶️', '辣椒', '预计产量', '1,800', 'kg/亩', '+6.7%', true)
        }
      }.scrollable(ScrollDirection.Horizontal).scrollBar(BarState.Off).width('100%')
    }
  }

  // 产量预测卡片
  @Builder YieldPredictionCard(emoji: string, cropName: string, label: string, value: string, unit: string, change: string, isPositive: boolean) {
    Column({ space: 8 }) {
      Row() { 
        Text(emoji).fontSize(24) 
      }.width(48).height(48).backgroundColor(ThemeColors.primaryLight).borderRadius(12).justifyContent(FlexAlign.Center)

      Text(cropName).fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)

      Text(label).fontSize(10).fontColor(ThemeColors.textMuted)

      Row({ space: 4 }) {
        Text(value).fontSize(18).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
        Text(unit).fontSize(9).fontColor(ThemeColors.textMuted)
      }

      Row({ space: 4 }) {
        Text(isPositive ? '↑' : '↓').fontSize(10).fontColor(isPositive ? ThemeColors.accent : ThemeColors.danger)
        Text(change).fontSize(10).fontColor(isPositive ? ThemeColors.accent : ThemeColors.danger)
      }
      .backgroundColor(isPositive ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)')
      .padding({ left: 6, right: 6, top: 2, bottom: 2 })
      .borderRadius(8)
    }
    .width(120)
    .backgroundColor(ThemeColors.card)
    .borderRadius(16)
    .padding(12)
    .borderWidth(1)
    .borderColor(ThemeColors.borderLight)
    .shadow({ radius: 5, color: 'rgba(0,0,0,0.02)' })
    .onClick(() => {
      this.selectedYieldCrop = cropName;
      this.showYieldPredictionModal = true;
    })
  }

  // 产量预测详情弹窗
  @Builder YieldPredictionDetailModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.5)').onClick(() => {
        this.showYieldPredictionModal = false;
        this.selectedYieldCrop = '';
      })

      Column() {
        Row() {
          Text('产量预测详情').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('✕').fontSize(18).fontColor(ThemeColors.textMuted).onClick(() => {
            this.showYieldPredictionModal = false;
            this.selectedYieldCrop = '';
          })
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16)

        Scroll() {
          Column({ space: 16 }) {
            if (this.selectedYieldCrop === '番茄') {
              this.YieldDetailContent('🍅', '番茄', '2,850 kg/亩', '+12.5%', true,
                '当前处于开花结果期，生长状态良好。预计亩产2,850公斤，较去年增长12.5%。',
                [
                  { label: '种植面积', value: '15亩' } as YieldDetailItem,
                  { label: '种植密度', value: '2,800株/亩' } as YieldDetailItem,
                  { label: '生长阶段', value: '开花结果期' } as YieldDetailItem,
                  { label: '预计收获时间', value: '45天后' } as YieldDetailItem,
                  { label: '单果均重', value: '180g' } as YieldDetailItem,
                  { label: '果实数量', value: '15,833个/亩' } as YieldDetailItem,
                  { label: '优质果率', value: '85%' } as YieldDetailItem,
                  { label: '市场价格', value: '3.5元/kg' } as YieldDetailItem,
                  { label: '预计产值', value: '9,975元/亩' } as YieldDetailItem,
                  { label: '成本投入', value: '3,200元/亩' } as YieldDetailItem,
                  { label: '预计利润', value: '6,775元/亩' } as YieldDetailItem
                ])
            } else if (this.selectedYieldCrop === '黄瓜') {
              this.YieldDetailContent('🥒', '黄瓜', '3,200 kg/亩', '+8.3%', true,
                '处于盛果期，植株健壮，产量稳定。预计亩产3,200公斤，较去年增长8.3%。',
                [
                  { label: '种植面积', value: '20亩' } as YieldDetailItem,
                  { label: '种植密度', value: '3,000株/亩' } as YieldDetailItem,
                  { label: '生长阶段', value: '盛果期' } as YieldDetailItem,
                  { label: '预计收获时间', value: '30天后' } as YieldDetailItem,
                  { label: '单瓜均重', value: '150g' } as YieldDetailItem,
                  { label: '果实数量', value: '21,333个/亩' } as YieldDetailItem,
                  { label: '优质瓜率', value: '90%' } as YieldDetailItem,
                  { label: '市场价格', value: '2.8元/kg' } as YieldDetailItem,
                  { label: '预计产值', value: '8,960元/亩' } as YieldDetailItem,
                  { label: '成本投入', value: '2,800元/亩' } as YieldDetailItem,
                  { label: '预计利润', value: '6,160元/亩' } as YieldDetailItem
                ])
            } else if (this.selectedYieldCrop === '玉米') {
              this.YieldDetailContent('🌽', '玉米', '650 kg/亩', '-5.2%', false,
                '受前期干旱影响，生长受到一定抑制。预计亩产650公斤，较去年下降5.2%。',
                [
                  { label: '种植面积', value: '50亩' } as YieldDetailItem,
                  { label: '种植密度', value: '4,500株/亩' } as YieldDetailItem,
                  { label: '生长阶段', value: '灌浆期' } as YieldDetailItem,
                  { label: '预计收获时间', value: '60天后' } as YieldDetailItem,
                  { label: '穗粒数', value: '580粒/穗' } as YieldDetailItem,
                  { label: '千粒重', value: '320g' } as YieldDetailItem,
                  { label: '出籽率', value: '88%' } as YieldDetailItem,
                  { label: '市场价格', value: '2.2元/kg' } as YieldDetailItem,
                  { label: '预计产值', value: '1,430元/亩' } as YieldDetailItem,
                  { label: '成本投入', value: '850元/亩' } as YieldDetailItem,
                  { label: '预计利润', value: '580元/亩' } as YieldDetailItem
                ])
            } else if (this.selectedYieldCrop === '白菜') {
              this.YieldDetailContent('🥬', '白菜', '4,500 kg/亩', '+15.8%', true,
                '生长旺盛，叶片肥厚，品质优良。预计亩产4,500公斤，较去年增长15.8%。',
                [
                  { label: '种植面积', value: '10亩' } as YieldDetailItem,
                  { label: '种植密度', value: '3,500株/亩' } as YieldDetailItem,
                  { label: '生长阶段', value: '结球期' } as YieldDetailItem,
                  { label: '预计收获时间', value: '25天后' } as YieldDetailItem,
                  { label: '单株均重', value: '1.3kg' } as YieldDetailItem,
                  { label: '结球紧实度', value: '92%' } as YieldDetailItem,
                  { label: '优质菜率', value: '88%' } as YieldDetailItem,
                  { label: '市场价格', value: '1.5元/kg' } as YieldDetailItem,
                  { label: '预计产值', value: '6,750元/亩' } as YieldDetailItem,
                  { label: '成本投入', value: '1,800元/亩' } as YieldDetailItem,
                  { label: '预计利润', value: '4,950元/亩' } as YieldDetailItem
                ])
            } else if (this.selectedYieldCrop === '辣椒') {
              this.YieldDetailContent('🌶️', '辣椒', '1,800 kg/亩', '+6.7%', true,
                '开花坐果正常，病虫害防控到位。预计亩产1,800公斤，较去年增长6.7%。',
                [
                  { label: '种植面积', value: '12亩' } as YieldDetailItem,
                  { label: '种植密度', value: '2,500株/亩' } as YieldDetailItem,
                  { label: '生长阶段', value: '结果期' } as YieldDetailItem,
                  { label: '预计收获时间', value: '40天后' } as YieldDetailItem,
                  { label: '单果均重', value: '25g' } as YieldDetailItem,
                  { label: '果实数量', value: '72,000个/亩' } as YieldDetailItem,
                  { label: '优质椒率', value: '82%' } as YieldDetailItem,
                  { label: '市场价格', value: '4.5元/kg' } as YieldDetailItem,
                  { label: '预计产值', value: '8,100元/亩' } as YieldDetailItem,
                  { label: '成本投入', value: '3,500元/亩' } as YieldDetailItem,
                  { label: '预计利润', value: '4,600元/亩' } as YieldDetailItem
                ])
            }
          }.padding({ left: 16, right: 16, bottom: 16 })
        }.layoutWeight(1).scrollBar(BarState.Auto)
      }
      .width('85%')
      .constraintSize({ maxHeight: '80%' })
      .backgroundColor(ThemeColors.card)
      .borderRadius(20)
    }
    .width('100%')
    .height('100%')
  }

  // 产量详情内容
  @Builder YieldDetailContent(emoji: string, cropName: string, yieldValue: string, change: string, isPositive: boolean, 
    description: string, details: YieldDetailItem[]) {
    Column({ space: 12 }) {
      Row({ space: 12 }) {
        Row() { Text(emoji).fontSize(32) }.width(64).height(64).backgroundColor(ThemeColors.primaryLight).borderRadius(16).justifyContent(FlexAlign.Center)
        Column({ space: 4 }) {
          Text(cropName).fontSize(18).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Row({ space: 4 }) {
            Text(isPositive ? '↑' : '↓').fontSize(12).fontColor(isPositive ? ThemeColors.accent : ThemeColors.danger)
            Text(change).fontSize(12).fontColor(isPositive ? ThemeColors.accent : ThemeColors.danger)
          }
        }.alignItems(HorizontalAlign.Start).layoutWeight(1)
      }.width('100%')

      Row() {
        Text('预计产量').fontSize(11).fontColor(ThemeColors.textMuted)
        Text(yieldValue).fontSize(20).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary).layoutWeight(1).textAlign(TextAlign.End)
      }.width('100%').padding(12).backgroundColor(ThemeColors.primaryLight).borderRadius(12)

      Text(description).fontSize(12).fontColor(ThemeColors.textMuted).lineHeight(18)

      Column({ space: 8 }) {
        ForEach(details, (item: YieldDetailItem) => {
          Row() {
            Text(item.label).fontSize(12).fontColor(ThemeColors.textMuted)
            Text(item.value).fontSize(12).fontWeight(FontWeight.Medium).fontColor(ThemeColors.textMain).layoutWeight(1).textAlign(TextAlign.End)
          }.width('100%').padding({ top: 8, bottom: 8 }).borderWidth({ bottom: 1 }).borderColor(ThemeColors.borderLight)
        })
      }.width('100%').backgroundColor(ThemeColors.card).borderRadius(12).padding({ left: 12, right: 12 })
    }
  }

  // 4. 历史记录列表
  @Builder HistorySection() {
    Column() {
      Row({ space: 6 }) {
        Text('📊').fontSize(14)
        Text('近期分析记录').fontSize(11).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMuted)
        Blank()
        if (this.historyFromApi) {
          Text('API数据').fontSize(8).fontColor('#ffffff').backgroundColor(ThemeColors.accent).padding({ left: 6, right: 6, top: 2, bottom: 2 }).borderRadius(8)
        } else {
          Text('离线模式').fontSize(8).fontColor('#ffffff').backgroundColor('#9ca3af').padding({ left: 6, right: 6, top: 2, bottom: 2 }).borderRadius(8)
        }
        Text('🔄').fontSize(12)
      }.width('100%').margin({ top: 24, bottom: 12 })
      .onClick(() => { this.fetchActionHistory(); })

      ForEach(this.filteredRecords, (record: HistoryRecord) => {
        Row({ space: 12 }) {
          Row() { Text(record.emoji).fontSize(28) }.width(56).height(56).backgroundColor(ThemeColors.borderLight).borderRadius(12).justifyContent(FlexAlign.Center)
          Column({ space: 6 }) {
            Row({ space: 6 }) {
              Text(record.stage).fontSize(9).fontColor(record.stage === '选种期' ? ThemeColors.primary : (record.stage==='成熟期'? ThemeColors.warning : '#64748b')).backgroundColor(ThemeColors.borderLight).padding({ left: 6, right: 6, top: 2, bottom: 2 }).borderRadius(4).fontWeight(FontWeight.Bold)
              Text(record.title).fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain).layoutWeight(1).maxLines(1).textOverflow({ overflow: TextOverflow.Ellipsis })
            }.width('100%')
            Text(`${record.time} • ${record.info}`).fontSize(10).fontColor(ThemeColors.textMuted).fontFamily('monospace')
          }.layoutWeight(1).alignItems(HorizontalAlign.Start)
          Text('>').fontSize(14).fontColor(ThemeColors.textMuted)
        }
        .width('100%').backgroundColor(ThemeColors.card).padding(12).borderRadius(16).borderWidth(1).borderColor(ThemeColors.borderLight).margin({ bottom: 12 }).shadow({ radius: 5, color: 'rgba(0,0,0,0.02)' })
        .onClick(() => {
          if (record.title === '选种分析') {
            this.showSeedAnalysisModal = true;
          } else if (record.title === '病虫害分析二') {
            this.showPestAnalysisModal = true;
          } else if (record.title === '土壤环境分析二') {
            this.showSoilAnalysisModal = true;
          } else if (record.title === '植物倒伏分析二') {
            this.showLodgingAnalysisModal = true;
          } else if (record.title === '果实产出分析二') {
            this.showFruitOutputAnalysisModal = true;
          } else if (record.pageRoute) {
            router.pushUrl({ url: record.pageRoute });
          } else {
            this.selectedRecord = record;
          }
        })
      })
    }
  }

  // 5. 详情弹窗 Modal
  @Builder RecordDetailModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.5)').onClick(() => this.selectedRecord = null)

      if (this.selectedRecord) {
        Column() {
          // 顶部图片占位与标题
          Stack({ alignContent: Alignment.BottomStart }) {
            Row().width('100%').height(120).backgroundColor(ThemeColors.primary) // 使用主色做占位背景
            Column({ space: 6 }) {
              Row({ space: 8 }) {
                Text(this.selectedRecord.stage).fontSize(10).fontColor('#fff').borderWidth(1).borderColor('#fff').padding({ left: 8, right: 8, top: 2, bottom: 2 }).borderRadius(12)
                Text(this.selectedRecord.status === 'completed' ? '已完成' : '处理中').fontSize(10).fontColor(ThemeColors.accent).backgroundColor('rgba(255,255,255,0.9)').padding({ left: 8, right: 8, top: 2, bottom: 2 }).borderRadius(12)
              }
              Text(this.selectedRecord.title).fontSize(14).fontWeight(FontWeight.Bold).fontColor('#fff')
            }.padding(16).alignItems(HorizontalAlign.Start)
          }.width('100%')

          Column({ space: 16 }) {
            // 三格数据
            Row({ space: 8 }) {
              Column({ space: 4 }) { Text('作物类型').fontSize(10).fontColor(ThemeColors.textMuted); Text(this.selectedRecord.crop).fontSize(14).fontWeight(FontWeight.Bold) }.layoutWeight(1).backgroundColor(ThemeColors.borderLight).padding(10).borderRadius(12)
              Column({ space: 4 }) { Text('区域位置').fontSize(10).fontColor(ThemeColors.textMuted); Text(this.selectedRecord.area).fontSize(12).fontWeight(FontWeight.Bold).maxLines(1) }.layoutWeight(1).backgroundColor(ThemeColors.borderLight).padding(10).borderRadius(12)
              Column({ space: 4 }) { Text('分析时间').fontSize(10).fontColor(ThemeColors.textMuted); Text(this.selectedRecord.time.split(' ')[0]).fontSize(12).fontWeight(FontWeight.Bold) }.layoutWeight(1).backgroundColor(ThemeColors.borderLight).padding(10).borderRadius(12)
            }.width('100%')

            if (this.selectedRecord.status === 'completed') {
              Row({ space: 8 }) {
                Column({ space: 4 }) { Text('置信度').fontSize(10).fontColor(ThemeColors.primary); Text(`${this.selectedRecord.confidence}%`).fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary) }.layoutWeight(1).backgroundColor(ThemeColors.primaryLight).padding(10).borderRadius(12)
                Column({ space: 4 }) { Text('检测数量').fontSize(10).fontColor(ThemeColors.primary); Text(`${this.selectedRecord.count}`).fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary) }.layoutWeight(1).backgroundColor(ThemeColors.primaryLight).padding(10).borderRadius(12)
                Column({ space: 4 }) { Text('核心指标').fontSize(10).fontColor(ThemeColors.primary); Text(`${this.selectedRecord.goodRate || this.selectedRecord.maturity || '--'}%`).fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary) }.layoutWeight(1).backgroundColor(ThemeColors.primaryLight).padding(10).borderRadius(12)
              }.width('100%')
            } else {
              Row({ space: 12 }) {
                LoadingProgress().width(24).height(24).color(ThemeColors.warning)
                Column() { Text('正在分析中').fontSize(12).fontWeight(FontWeight.Bold).fontColor(ThemeColors.warning); Text('预计还需2分钟完成').fontSize(10).fontColor(ThemeColors.textMuted) }.alignItems(HorizontalAlign.Start)
              }.width('100%').backgroundColor('#fffbeb').padding(12).borderRadius(12).borderWidth(1).borderColor('#fef3c7')
            }

            Column({ space: 8 }) {
              Text('分析结果').fontSize(10).fontColor(ThemeColors.textMuted)
              Text(this.selectedRecord.description).fontSize(12).fontColor(ThemeColors.textMain).lineHeight(18)
            }.width('100%').backgroundColor(ThemeColors.borderLight).padding(12).borderRadius(12).alignItems(HorizontalAlign.Start)

            Row({ space: 12 }) {
              Button('关闭').layoutWeight(1).backgroundColor(ThemeColors.borderLight).fontColor(ThemeColors.textMain).height(40).onClick(() => this.selectedRecord = null)
              if (this.selectedRecord.status === 'completed') {
                Button('导出报告').layoutWeight(1).backgroundColor(ThemeColors.primary).fontColor('#fff').height(40).onClick(() => { promptAction.showToast({ message: `已导出: ${this.selectedRecord?.title}` }); this.selectedRecord = null; })
              }
            }.width('100%').margin({ top: 8 })

          }.padding(16).width('100%')
        }
        .width('90%').backgroundColor(ThemeColors.card).borderRadius(16).clip(true)
        .animation({ duration: 250, curve: Curve.EaseOut })
      }
    }.width('100%').height('100%').zIndex(100)
  }

  // 6. 底部导航栏
  // @Builder BottomNav() {
  //   Row() {
  //     this.NavItem('首页', '🏠', false)
  //     this.NavItem('控制', '🎛️', false)
  //     Column() {
  //       Stack() { Circle({ width: 48, height: 48 }).fill('#4b5563'); Text('🧠').fontSize(20) }
  //       .borderWidth(4).borderColor(ThemeColors.card).borderRadius(28)
  //       .shadow({ radius: 10, color: 'rgba(0, 0, 0, 0.1)', offsetY: 4 })
  //       Text('AI协作').fontSize(10).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMuted).margin({ top: 4 })
  //     }.offset({ y: -20 })
  //     // 生命周期激活
  //     this.NavItem('生命周期', '🌱', true)
  //     this.NavItem('设置', '⚙️', false)
  //   }
  //   .width('100%').height(64).backgroundColor('rgba(255, 255, 255, 0.95)').backdropBlur(20)
  //   .borderWidth({ top: 1 }).borderColor(ThemeColors.borderLight)
  //   .justifyContent(FlexAlign.SpaceAround).alignItems(VerticalAlign.Bottom).padding({ bottom: 8 })
  //   .zIndex(50)
  // }

  @Builder SeedAnalysisModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.5)').onClick(() => this.showSeedAnalysisModal = false)

      Column() {
        Row() {
          Text('选种质量分析').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('✕').fontSize(18).fontColor(ThemeColors.textMuted).onClick(() => this.showSeedAnalysisModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16)

        Scroll() {
          Column({ space: 12 }) {
            if (this.seedAnalysisSections.length === 0) {
              Column() {
                Text('暂无分析数据').fontSize(14).fontColor(ThemeColors.textMuted)
                Text('请先上传种子图片进行分析').fontSize(12).fontColor(ThemeColors.textMuted).margin({ top: 8 })
              }.width('100%').padding(30).alignItems(HorizontalAlign.Center)
            }
            ForEach(this.seedAnalysisSections, (section: AnalysisSection) => {
              Column({ space: 6 }) {
                Text(section.title).fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
                Text(section.content).fontSize(11).fontColor(ThemeColors.textMain).lineHeight(18)
              }.width('100%').padding(10).backgroundColor(ThemeColors.primaryLight).borderRadius(8)
            }, (section: AnalysisSection, index: number) => `${section.title}_${index}`)
          }.padding(16)
        }.width('100%').layoutWeight(1).scrollBar(BarState.Auto)

        Button('关闭').width('100%').height(40).backgroundColor(ThemeColors.primary).fontColor('#fff').margin({ top: 8, bottom: 16 }).onClick(() => this.showSeedAnalysisModal = false)
      }.width('90%').height('85%').backgroundColor(ThemeColors.card).borderRadius(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder PestAnalysisModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.5)').onClick(() => this.showPestAnalysisModal = false)

      Column() {
        Row() {
          Text('生长期分析').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('✕').fontSize(18).fontColor(ThemeColors.textMuted).onClick(() => this.showPestAnalysisModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16)

        Scroll() {
          Column({ space: 12 }) {
            if (this.growthAnalysisSections.length === 0) {
              Column() {
                Text('暂无分析数据').fontSize(14).fontColor(ThemeColors.textMuted)
                Text('请先上传生长期图片进行分析').fontSize(12).fontColor(ThemeColors.textMuted).margin({ top: 8 })
              }.width('100%').padding(30).alignItems(HorizontalAlign.Center)
            }
            ForEach(this.growthAnalysisSections, (section: AnalysisSection) => {
              Column({ space: 6 }) {
                Text(section.title).fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
                Text(section.content).fontSize(11).fontColor(ThemeColors.textMain).lineHeight(18)
              }.width('100%').padding(10).backgroundColor(ThemeColors.primaryLight).borderRadius(8)
            }, (section: AnalysisSection, index: number) => `${section.title}_${index}`)
          }.padding(16)
        }.width('100%').layoutWeight(1).scrollBar(BarState.Auto)

        Button('关闭').width('100%').height(40).backgroundColor(ThemeColors.primary).fontColor('#fff').margin({ top: 8, bottom: 16 }).onClick(() => this.showPestAnalysisModal = false)
      }.width('90%').height('85%').backgroundColor(ThemeColors.card).borderRadius(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder SoilAnalysisModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.5)').onClick(() => this.showSoilAnalysisModal = false)

      Column() {
        Row() {
          Text('土壤环境分析').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('✕').fontSize(18).fontColor(ThemeColors.textMuted).onClick(() => this.showSoilAnalysisModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16)

        Scroll() {
          Column({ space: 12 }) {
            Column({ space: 8 }) {
              Text('报告摘要').fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              Text('本报告模拟对长江中下游地区某典型油菜轮作田（前茬：水稻）的土壤进行了系统分析。核心结论是：土壤潜在肥力基础尚可，但存在酸化趋势明显、钾元素缺乏、结构板结、排水不畅等关键限制因素，是制约油菜高产优质的主要环境瓶颈。改良重点在于"调酸、补钾、增气、降渍"。').fontSize(11).fontColor(ThemeColors.textMain).lineHeight(16)
            }.width('100%').padding(10).backgroundColor(ThemeColors.primaryLight).borderRadius(8)

            Column({ space: 8 }) {
              Text('1. 土壤基本情况概览').fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              Column({ space: 4 }) {
                Text('采样深度：0-20 cm（耕作层）').fontSize(10).fontColor(ThemeColors.textMain)
                Text('前茬作物：单季稻').fontSize(10).fontColor(ThemeColors.textMain)
                Text('土壤类型：黄褐土（黏性较强）').fontSize(10).fontColor(ThemeColors.textMain)
                Text('采样时田间水分：湿润（水稻收获后，自然落干状态）').fontSize(10).fontColor(ThemeColors.textMain)
              }.width('100%').padding(10).backgroundColor(ThemeColors.borderLight).borderRadius(8)
            }.width('100%')

            Column({ space: 8 }) {
              Text('2. 核心指标检测与等级评价').fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              Column({ space: 6 }) {
                Column({ space: 4 }) {
                  Text('物理性质').fontSize(11).fontWeight(FontWeight.Bold).fontColor(ThemeColors.accent)
                  Text('土壤质地：黏壤土（中等偏黏）- 保水保肥力强，但通气透水性差').fontSize(10).fontColor(ThemeColors.textMuted)
                  Text('容重：1.45 g/cm³（偏紧实）- 理想值应<1.3 g/cm³，土壤板结').fontSize(10).fontColor(ThemeColors.textMuted)
                  Text('田间持水量：32%（较高）- 易导致渍害，与菌核病高发相关').fontSize(10).fontColor(ThemeColors.textMuted)
                }.width('100%').padding(8).backgroundColor('#d1fae5').borderRadius(6)
                Column({ space: 4 }) {
                  Text('化学性质').fontSize(11).fontWeight(FontWeight.Bold).fontColor(ThemeColors.warning)
                  Text('pH值：5.3（偏酸）- 核心限制因子，抑制根系生长').fontSize(10).fontColor(ThemeColors.textMuted)
                  Text('有机质：18.5 g/kg（中等）- 对高产目标仍有提升空间').fontSize(10).fontColor(ThemeColors.textMuted)
                  Text('碱解氮：125 mg/kg（中等偏上）- 水稻茬残留氮较多').fontSize(10).fontColor(ThemeColors.textMuted)
                  Text('有效磷：20.5 mg/kg（中等）- 酸性条件下磷易被固定').fontSize(10).fontColor(ThemeColors.textMuted)
                  Text('速效钾：85 mg/kg（缺乏）- 关键限制因子，油菜是喜钾作物').fontSize(10).fontColor(ThemeColors.danger)
                  Text('有效硼：0.35 mg/kg（潜在缺乏）- 临界值为0.5 mg/kg').fontSize(10).fontColor(ThemeColors.warning)
                }.width('100%').padding(8).backgroundColor('#fef3c7').borderRadius(6)
                Column({ space: 4 }) {
                  Text('生物性质').fontSize(11).fontWeight(FontWeight.Bold).fontColor('#6b7280')
                  Text('微生物活性：中等 - 受土壤板结和酸度影响，活性受到抑制').fontSize(10).fontColor(ThemeColors.textMuted)
                }.width('100%').padding(8).backgroundColor(ThemeColors.borderLight).borderRadius(6)
              }.width('100%').padding(10).backgroundColor(ThemeColors.borderLight).borderRadius(8)
            }.width('100%')

            Column({ space: 8 }) {
              Text('3. 关键限制因子与风险分析').fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              Column({ space: 6 }) {
                Text('酸害与养分失衡风险：pH值5.3是当前最严峻问题。酸度加剧钾、钙、镁淋失，固持磷和钼，可能活化有毒铝离子。').fontSize(10).fontColor(ThemeColors.textMain)
                Text('渍害与病害诱发风险：黏重质地和高容重导致排水不畅，是诱发菌核病、霜霉病的主要环境诱因。').fontSize(10).fontColor(ThemeColors.textMain)
                Text('结构性障碍风险：板结土壤限制油菜根系伸展，影响对深层水分和养分吸收。').fontSize(10).fontColor(ThemeColors.textMain)
                Text('中微量元素缺乏风险：钾、硼缺乏症状极可能在花期后集中显现。').fontSize(10).fontColor(ThemeColors.textMain)
              }.width('100%').padding(10).backgroundColor('#fee2e2').borderRadius(8)
            }.width('100%')

            Column({ space: 8 }) {
              Text('4. 综合改良与施肥管理建议').fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              Text('总体原则：以"降酸、增钾、改土、防渍"为中心').fontSize(10).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
              Column({ space: 6 }) {
                Text('紧急矫治措施：每亩施用生石灰50-75公斤调酸补钙；重施钾肥（硫酸钾15-20公斤/亩）和硼肥（硼砂0.5-1.0公斤/亩）。').fontSize(10).fontColor(ThemeColors.textMain)
                Text('长期改良策略：连续2-3季增施有机肥1-2吨/亩；每2-3年深松或深耕25-30cm；开深沟30-40cm完善排灌系统。').fontSize(10).fontColor(ThemeColors.textMain)
                Text('基肥方案：复合肥30-40公斤/亩 + 全部有机肥 + 全部硼肥 + 石灰/调理剂。').fontSize(10).fontColor(ThemeColors.textMain)
                Text('追肥方案：苗肥尿素3-5公斤/亩；薹肥尿素5-8公斤+氯化钾5-8公斤/亩；叶面喷施磷酸二氢钾+硼砂溶液。').fontSize(10).fontColor(ThemeColors.textMain)
              }.width('100%').padding(10).backgroundColor(ThemeColors.borderLight).borderRadius(8)
            }.width('100%')

            Column({ space: 8 }) {
              Text('5. 结论').fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              Text('本模拟田块土壤属于典型的"酸性、黏重、缺钾、易渍"类型，是制约油菜生产的常见障碍土壤。改良重点必须从调节土壤化学环境（调酸）和改善物理结构（降渍）入手，并大幅提高钾、硼的供应水平。通过上述综合措施，有望从根本上改善根系生长环境，系统性地提升油菜的抗逆性和产量潜力。建议在下一季种植前进行土壤复查，重点跟踪pH值和速效钾的变化情况。').fontSize(11).fontColor(ThemeColors.textMain).lineHeight(16)
            }.width('100%').padding(10).backgroundColor(ThemeColors.primaryLight).borderRadius(8)

            Button('关闭').width('100%').height(40).backgroundColor(ThemeColors.primary).fontColor('#fff').margin({ top: 8 }).onClick(() => this.showSoilAnalysisModal = false)
          }.padding(16)
        }.width('100%').layoutWeight(1).scrollBar(BarState.Auto)
      }.width('90%').height('85%').backgroundColor(ThemeColors.card).borderRadius(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder PlantLodgingAnalysisModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.5)').onClick(() => this.showLodgingAnalysisModal = false)

      Column() {
        Row() {
          Text('植物倒伏分析').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('✕').fontSize(18).fontColor(ThemeColors.textMuted).onClick(() => this.showLodgingAnalysisModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16)

        Scroll() {
          Column({ space: 12 }) {
            Column({ space: 8 }) {
              Text('核心结论').fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              Text('基于对模拟田块（品种：中双11号，生育期：角果发育期）的植株性状与田间环境综合分析，当前倒伏综合风险指数评定为中等偏高。风险主要源于茎秆物理强度不足、根系发育受限、潜在病害威胁及不利天气概率的四重叠加。若遇连续降雨伴大风天气，局部（特别是高密度区域）发生点片倒伏的风险显著。').fontSize(11).fontColor(ThemeColors.textMain).lineHeight(16)
            }.width('100%').padding(10).backgroundColor(ThemeColors.primaryLight).borderRadius(8)

            Column({ space: 8 }) {
              Text('1. 倒伏风险评估：指标测定与模拟数据').fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              Column({ space: 6 }) {
                Column({ space: 4 }) {
                  Text('植株形态').fontSize(11).fontWeight(FontWeight.Bold).fontColor(ThemeColors.accent)
                  Row() { Text('株高').fontSize(10).layoutWeight(1); Text('165-180 cm').fontSize(10).width(60); Text('中风险').fontSize(10).fontColor(ThemeColors.warning).width(50) }.width('100%')
                  Text('株高偏高，重心上移，但非决定性因素。').fontSize(9).fontColor(ThemeColors.textMuted)
                  Row() { Text('茎秆基部直径').fontSize(10).layoutWeight(1); Text('5.8 mm').fontSize(10).width(60); Text('高风险').fontSize(10).fontColor(ThemeColors.danger).width(50) }.width('100%').margin({ top: 4 })
                  Text('抗折力关键指标。理想值应>6.5mm。当前茎秆细弱，机械强度不足，是倒伏的核心内因。').fontSize(9).fontColor(ThemeColors.textMuted)
                  Row() { Text('茎秆壁厚').fontSize(10).layoutWeight(1); Text('较薄').fontSize(10).width(60); Text('高风险').fontSize(10).fontColor(ThemeColors.danger).width(50) }.width('100%').margin({ top: 4 })
                  Text('与钾、硅元素吸收不足有关，抗压与抗弯能力差。').fontSize(9).fontColor(ThemeColors.textMuted)
                  Row() { Text('节间长度').fontSize(10).layoutWeight(1); Text('下部较长').fontSize(10).width(60); Text('中风险').fontSize(10).fontColor(ThemeColors.warning).width(50) }.width('100%').margin({ top: 4 })
                  Text('基部节间过长（>8cm），降低了植株稳定性。').fontSize(9).fontColor(ThemeColors.textMuted)
                }.width('100%').padding(8).backgroundColor('#d1fae5').borderRadius(6)
                Column({ space: 4 }) {
                  Text('根系结构').fontSize(11).fontWeight(FontWeight.Bold).fontColor(ThemeColors.warning)
                  Row() { Text('根颈粗度').fontSize(10).layoutWeight(1); Text('约12 mm').fontSize(10).width(60); Text('高风险').fontSize(10).fontColor(ThemeColors.danger).width(50) }.width('100%')
                  Text('根系"锚定"能力弱。与土壤板结、耕作层浅有关。').fontSize(9).fontColor(ThemeColors.textMuted)
                  Row() { Text('根系分布').fontSize(10).layoutWeight(1); Text('浅层').fontSize(10).width(60); Text('高风险').fontSize(10).fontColor(ThemeColors.danger).width(50) }.width('100%').margin({ top: 4 })
                  Text('主根短，侧根少，多分布于0-15cm。根群浅，固持土壤能力差，遇风雨易整体松动。').fontSize(9).fontColor(ThemeColors.textMuted)
                }.width('100%').padding(8).backgroundColor('#fef3c7').borderRadius(6)
                Column({ space: 4 }) {
                  Text('群体结构').fontSize(11).fontWeight(FontWeight.Bold).fontColor('#6b7280')
                  Row() { Text('种植密度').fontSize(10).layoutWeight(1); Text('2.8万株/亩').fontSize(10).width(60); Text('低风险').fontSize(10).fontColor(ThemeColors.accent).width(50) }.width('100%')
                  Text('密度合理，通风透光尚可。').fontSize(9).fontColor(ThemeColors.textMuted)
                  Row() { Text('田间透光率').fontSize(10).layoutWeight(1); Text('<30%').fontSize(10).width(60); Text('中风险').fontSize(10).fontColor(ThemeColors.warning).width(50) }.width('100%').margin({ top: 4 })
                  Text('中下部荫蔽，促使茎秆徒长、组织柔嫩，并加重菌核病风险。').fontSize(9).fontColor(ThemeColors.textMuted)
                }.width('100%').padding(8).backgroundColor(ThemeColors.borderLight).borderRadius(6)
                Column({ space: 4 }) {
                  Text('外部诱因').fontSize(11).fontWeight(FontWeight.Bold).fontColor(ThemeColors.danger)
                  Row() { Text('土壤状况').fontSize(10).layoutWeight(1); Text('板结渍水').fontSize(10).width(60); Text('高风险').fontSize(10).fontColor(ThemeColors.danger).width(50) }.width('100%')
                  Text('根系下扎困难，且湿软土壤提供的支撑力弱。').fontSize(9).fontColor(ThemeColors.textMuted)
                  Row() { Text('病害风险').fontSize(10).layoutWeight(1); Text('侵染率5%').fontSize(10).width(60); Text('极高风险').fontSize(10).fontColor(ThemeColors.danger).width(50) }.width('100%').margin({ top: 4 })
                  Text('菌核病直接破坏茎秆维管束，造成"烂秆"，遇风必倒。').fontSize(9).fontColor(ThemeColors.textMuted)
                  Row() { Text('天气预测').fontSize(10).layoutWeight(1); Text('降雨大风').fontSize(10).width(60); Text('动态高风险').fontSize(10).fontColor(ThemeColors.danger).width(50) }.width('100%').margin({ top: 4 })
                  Text('角果期有连续降雨及大风概率，是触发倒伏的直接外力。').fontSize(9).fontColor(ThemeColors.textMuted)
                }.width('100%').padding(8).backgroundColor('#fee2e2').borderRadius(6)
              }.width('100%').padding(10).backgroundColor(ThemeColors.borderLight).borderRadius(8)
            }.width('100%')

            Column({ space: 8 }) {
              Text('2. 倒伏类型与主导机制分析').fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              Column({ space: 6 }) {
                Column({ space: 4 }) {
                  Text('根倒伏（主要潜在类型）').fontSize(11).fontWeight(FontWeight.Bold).fontColor(ThemeColors.danger)
                  Text('机制：由于土壤过湿松软、根系分布浅，植株整体抗倾覆能力差，在风雨作用下，根茎结合处发生倾斜或平铺。').fontSize(10).fontColor(ThemeColors.textMuted)
                  Text('关联因素：与前期"土壤环境分析"中排水不畅、结构板结的结论直接相关，是"土壤-根系"系统问题的直接体现。').fontSize(10).fontColor(ThemeColors.textMuted)
                }.width('100%').padding(8).backgroundColor('#fee2e2').borderRadius(6)
                Column({ space: 4 }) {
                  Text('茎折倒伏（关键风险类型）').fontSize(11).fontWeight(FontWeight.Bold).fontColor(ThemeColors.warning)
                  Text('机制：在茎秆基部（距地面20-40cm）因机械强度不足而发生弯折或断裂。').fontSize(10).fontColor(ThemeColors.textMuted)
                  Text('关联因素：茎秆纤细、壁薄是基础；若菌核病病斑在茎秆基部形成，将成为最薄弱的"断裂点"，极大增加茎折概率。这与"病虫害分析"中菌核病高风险预警形成致命关联。').fontSize(10).fontColor(ThemeColors.textMuted)
                }.width('100%').padding(8).backgroundColor('#fef3c7').borderRadius(6)
              }.width('100%').padding(10).backgroundColor(ThemeColors.borderLight).borderRadius(8)
            }.width('100%')

            Column({ space: 8 }) {
              Text('3. 综合致倒因子链').fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              Text('根本原因（土壤板结、酸化、缺钾）→ 导致（根系发育不良、茎秆纤维素合成不足）→ 叠加（田间荫蔽、茎秆徒长细弱）→ 诱发（病害侵染，形成脆弱点）→ 触发（风雨外力）→ 最终结果（根倒或茎折）。').fontSize(11).fontColor(ThemeColors.textMain).lineHeight(16)
            }.width('100%').padding(10).backgroundColor(ThemeColors.borderLight).borderRadius(8)

            Column({ space: 8 }) {
              Text('4. 抗倒伏管理优化建议').fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              Column({ space: 6 }) {
                Column({ space: 4 }) {
                  Text('A. 前期预防（适用于下季规划）').fontSize(11).fontWeight(FontWeight.Bold).fontColor(ThemeColors.accent)
                  Text('品种选择：选用株高适中（<160cm）、茎秆粗壮、根系发达的抗倒品种。').fontSize(10).fontColor(ThemeColors.textMuted)
                  Text('深翻改土：实施深耕打破犁底层，结合增施有机肥和石灰，从根本上改善土壤物理结构，促根系下扎。').fontSize(10).fontColor(ThemeColors.textMuted)
                  Text('科学施肥：重视钾、硅、硼肥的施用。钾肥增强茎秆韧性，硅肥能沉积于细胞壁，显著提高茎秆机械强度。').fontSize(10).fontColor(ThemeColors.textMuted)
                }.width('100%').padding(8).backgroundColor('#d1fae5').borderRadius(6)
                Column({ space: 4 }) {
                  Text('B. 当期应急调控（针对当前模拟田块）').fontSize(11).fontWeight(FontWeight.Bold).fontColor(ThemeColors.warning)
                  Text('化学调控：对于仍有营养生长的田块，可立即叶面喷施磷酸二氢钾（0.3%）+ 矮壮素类调节剂。此举并非降低株高，而是促进茎秆增粗、壁厚，缩短节间，但需严格按说明使用，避免药害。').fontSize(10).fontColor(ThemeColors.textMuted)
                  Text('病害防控：坚决执行菌核病防治方案。保护茎秆免受侵染，是防止"病理性茎折"的最后防线。').fontSize(10).fontColor(ThemeColors.textMuted)
                  Text('开沟降渍：再次清理加深"三沟"，确保土壤湿度处于下限，增加土壤紧实度和根系抓地力。').fontSize(10).fontColor(ThemeColors.textMuted)
                  Text('捆绑扶正：对于已开始倾斜或密度过大的点片区域，可采用人工竹竿拉绳分区隔离或简单捆绑，增强群体互相支撑。').fontSize(10).fontColor(ThemeColors.textMuted)
                }.width('100%').padding(8).backgroundColor('#fef3c7').borderRadius(6)
                Column({ space: 4 }) {
                  Text('C. 收获期减损预案').fontSize(11).fontWeight(FontWeight.Bold).fontColor('#6b7280')
                  Text('适时收获：密切关注天气，在完熟期、雨季前集中抢收。').fontSize(10).fontColor(ThemeColors.textMuted)
                  Text('调整机收参数：若使用联合收割机，对倒伏油菜需调整割台高度和拨禾轮速度，逆向收割或增加捡拾装置，减少损失。').fontSize(10).fontColor(ThemeColors.textMuted)
                }.width('100%').padding(8).backgroundColor(ThemeColors.borderLight).borderRadius(6)
              }.width('100%').padding(10).backgroundColor(ThemeColors.borderLight).borderRadius(8)
            }.width('100%')

            Column({ space: 8 }) {
              Text('5. 风险评估总结').fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              Text('本模拟田块的倒伏风险是多因素系统性失衡的结果，已非单一措施所能解决。当前最直接且不可控的风险，来源于菌核病在茎秆基部的侵染。即使风雨外力不大，病害也可能导致点片倒伏。').fontSize(11).fontColor(ThemeColors.textMain).lineHeight(16)
              Column({ space: 4 }) {
                Text('核心建议优先级：').fontSize(10).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
                Text('立即执行：强化菌核病防治（药剂保护茎秆），并彻底开沟排水。').fontSize(10).fontColor(ThemeColors.textMain)
                Text('下季必需：实施土壤改良（调酸、深耕、增有机肥）和增施钾肥，从根源上培育壮根强秆。').fontSize(10).fontColor(ThemeColors.textMain)
                Text('长期规划：优化品种布局，建立基于抗倒品种和健康土壤的可持续生产体系。').fontSize(10).fontColor(ThemeColors.textMain)
              }.width('100%').padding(8).backgroundColor(ThemeColors.primaryLight).borderRadius(6)
            }.width('100%').padding(10).backgroundColor(ThemeColors.primaryLight).borderRadius(8)

            Button('关闭').width('100%').height(40).backgroundColor(ThemeColors.primary).fontColor('#fff').margin({ top: 8 }).onClick(() => this.showLodgingAnalysisModal = false)
          }.padding(16)
        }.width('100%').layoutWeight(1).scrollBar(BarState.Auto)
      }.width('90%').height('85%').backgroundColor(ThemeColors.card).borderRadius(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder FruitOutputAnalysisModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.5)').onClick(() => this.showFruitOutputAnalysisModal = false)

      Column() {
        Row() {
          Text('采收期分析').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('✕').fontSize(18).fontColor(ThemeColors.textMuted).onClick(() => this.showFruitOutputAnalysisModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16)

        Scroll() {
          Column({ space: 12 }) {
            if (this.maturityAnalysisSections.length === 0) {
              Column() {
                Text('暂无分析数据').fontSize(14).fontColor(ThemeColors.textMuted)
                Text('请先上传采收期图片进行分析').fontSize(12).fontColor(ThemeColors.textMuted).margin({ top: 8 })
              }.width('100%').padding(30).alignItems(HorizontalAlign.Center)
            }
            ForEach(this.maturityAnalysisSections, (section: AnalysisSection) => {
              Column({ space: 6 }) {
                Text(section.title).fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
                Text(section.content).fontSize(11).fontColor(ThemeColors.textMain).lineHeight(18)
              }.width('100%').padding(10).backgroundColor(ThemeColors.primaryLight).borderRadius(8)
            }, (section: AnalysisSection, index: number) => `${section.title}_${index}`)
          }.padding(16)
        }.width('100%').layoutWeight(1).scrollBar(BarState.Auto)

        Button('关闭').width('100%').height(40).backgroundColor(ThemeColors.primary).fontColor('#fff').margin({ top: 8, bottom: 16 }).onClick(() => this.showFruitOutputAnalysisModal = false)
      }.width('90%').height('85%').backgroundColor(ThemeColors.card).borderRadius(16)
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder NavItem(title: string, emoji: string, isActive: boolean) {
    Column({ space: 4 }) {
      Text(emoji).fontSize(24).opacity(isActive ? 1 : 0.5)
      Text(title).fontSize(10).fontWeight(isActive ? FontWeight.Bold : FontWeight.Medium).fontColor(isActive ? ThemeColors.primary : ThemeColors.textMuted)
    }.padding({ bottom: 4 })
  }

  // 报告列表弹窗
  @Builder ReportsListDialog() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.5)').onClick(() => { this.showReportsDialog = false; })

      Column() {
        Row() {
          Text('分析报告').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('✕').fontSize(18).fontColor(ThemeColors.textMuted).onClick(() => { this.showReportsDialog = false; })
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16)

        if (this.reportsList.length === 0) {
          Column() {
            Text('暂无报告').fontSize(14).fontColor(ThemeColors.textMuted).margin({ top: 12 })
            Text('请先上传图片进行分析').fontSize(12).fontColor(ThemeColors.textMuted).margin({ top: 8 })
          }.width('100%').height(200).justifyContent(FlexAlign.Center)
        } else {
          Scroll() {
            Column({ space: 8 }) {
              ForEach(this.reportsList, (report: ReportItem) => {
                Row({ space: 12 }) {
                  Column({ space: 4 }) {
                    Text(report.stage_name || report.filename).fontSize(13).fontWeight(FontWeight.Medium).fontColor(ThemeColors.textMain).maxLines(1).textOverflow({ overflow: TextOverflow.Ellipsis })
                    if (report.timestamp) {
                      Text(report.timestamp.substring(0, 19).replace('T', ' ')).fontSize(10).fontColor(ThemeColors.textMuted)
                    }
                  }.layoutWeight(1).alignItems(HorizontalAlign.Start)
                  Text('查看').fontSize(12).fontColor(ThemeColors.primary).fontWeight(FontWeight.Bold)
                }.width('100%').padding(12).backgroundColor(ThemeColors.borderLight).borderRadius(12)
                .onClick(() => { this.showReportsDialog = false; this.fetchReportDetail(report.filename); })
              })
            }.padding({ left: 16, right: 16, bottom: 16 })
          }.layoutWeight(1).scrollBar(BarState.Auto)
        }

        Button('关闭').width('90%').height(40).backgroundColor(ThemeColors.borderLight).fontColor(ThemeColors.textMain).margin({ top: 12, bottom: 16 })
          .onClick(() => { this.showReportsDialog = false; })
      }.width('85%').constraintSize({ maxHeight: '70%' }).backgroundColor(ThemeColors.card).borderRadius(16)
    }.width('100%').height('100%').zIndex(100)
  }

  // 报告详情弹窗
  @Builder ReportDetailDialog() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.5)').onClick(() => { this.showReportDetailDialog = false; })

      Column() {
        Row() {
          Text('报告详情').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
          Text('✕').fontSize(18).fontColor(ThemeColors.textMuted).onClick(() => { this.showReportDetailDialog = false; })
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16)

        Scroll() {
          Text(this.reportDetail).fontSize(12).fontColor(ThemeColors.textMain).lineHeight(20).padding(16)
        }.layoutWeight(1).scrollBar(BarState.Auto)

        Button('关闭').width('90%').height(40).backgroundColor(ThemeColors.primary).fontColor('#fff').margin({ top: 12, bottom: 16 })
          .onClick(() => { this.showReportDetailDialog = false; })
      }.width('90%').constraintSize({ maxHeight: '80%' }).backgroundColor(ThemeColors.card).borderRadius(16)
    }.width('100%').height('100%').zIndex(100)
  }
}
