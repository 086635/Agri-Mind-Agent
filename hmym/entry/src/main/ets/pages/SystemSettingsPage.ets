import { promptAction } from '@kit.ArkUI';
import { http } from '@kit.NetworkKit';
import { ApiConfig } from '../common/ApiConfig';

// ================= 修复1：使用 class 替代 const 对象，解决严格模式报错 =================
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
}

interface ActionItem {
  session_id: string;
  action: string;
  reason: string;
  status: string;
  skill: string;
  has_feedback: boolean;
  feedback: Record<string, string> | null;
  time: string;
}

interface FeedbackItem {
  session_id: string;
  feedback_type: string;
  reasoning: string;
  confidence: number;
  time: string;
}

interface ChatMessageItem {
  message_id: string;
  role: string;        // 'user' 或 'assistant'
  content: string;
  session_id: string;
  chat_mode: string;   // 'expert'农艺 / 'device'设备
  feedback: string | null;
  time: string;
}

interface ExperienceHistoryResponse {
  actions: ActionItem[];
  feedback_log: FeedbackItem[];
  chat_messages: ChatMessageItem[];
  total_actions: number;
  total_feedback: number;
  total_chat_messages: number;
}

// ================= 系统状态API相关接口 =================
interface ServiceStatusItem {
  name: string;
  service_name: string;
  service_display: string;
  port: number;
  latency_ms: number;
  status: string;
  status_color: string;
  last_sync: string;
}

interface UserProfileData {
  name: string;
  role: string;
  avatar_letter: string;
  last_login_time: string;
  last_login_device: string;
  experience_level: string;
  total_interactions: number;
  preferred_mode: string;
}

interface SystemStatusResponse {
  services: ServiceStatusItem[];
  user_profile: UserProfileData;
  health_percent: number;
  avg_latency_ms: number;
  online_count: number;
  total_services: number;
}

interface ApiLogicRecord {
  id: string;
  inputText: string;
  operationLogic: string;
  createTime: string;
}

// 调控设备信息
interface DeviceInfo {
  icon: string;
  name: string;
  color: string;
}

@Component
export struct SystemSettingsPage {
  // ================= 状态管理 =================
  // 用户信息（从API获取，替代硬编码）
  @State userName: string = '李技术';
  @State userRole: string = '管理员';
  @State userAvatar: string = '李';
  @State lastLoginInfo: string = '今天 08:30 • iPhone 14';
  @State userExperienceLevel: string = '';
  @State userTotalInteractions: number = 0;
  @State userPreferredMode: string = '';

  // 微服务状态（从API获取，替代硬编码）
  @State serviceStatuses: ServiceStatusItem[] = [];
  @State systemHealthPercent: number = 98;
  @State isRefreshing: boolean = false;

  // 操作逻辑记录（从API获取，替代本地OperationLogicStorage）
  @State apiOperationLogics: ApiLogicRecord[] = [];
  @State logicLoading: boolean = false;
  @State showOperationDetailModal: boolean = false;
  @State selectedApiLogic: ApiLogicRecord | null = null;

  // 经验历史
  @State experienceActions: ActionItem[] = [];
  @State experienceFeedbacks: FeedbackItem[] = [];
  @State chatMessages: ChatMessageItem[] = [];
  @State experienceLoading: boolean = false;
  @State experienceTab: string = 'actions';
  @State showExperienceDetailPage: boolean = false;

  // 操作逻辑列表页
  @State showOperationListPage: boolean = false;

  // ================= 页面主视图 =================
  build() {
    Stack({ alignContent: Alignment.Bottom }) {

      // 主体内容区
      Column() {
        this.Header()

        Scroll() {
          Column({ space: 16 }) {
            this.ProfileSection()
            this.SystemStatusSection()
            this.OperationLogicSection()
            this.ExperienceHistorySection()

          }
          .padding(16)
          .width('100%')
        }
        .layoutWeight(1)
        .scrollBar(BarState.Off)
        .padding({ bottom: 80 })
      }
      .width('100%')
      .height('100%')
      .backgroundColor(ThemeColors.background)

      // 操作逻辑详情弹窗
      if (this.showOperationDetailModal) {
        this.OperationDetailModal()
      }

      // 经验学习记录详情页（全屏）
      if (this.showExperienceDetailPage) {
        this.ExperienceDetailPage()
      }

      // 操作逻辑列表详情页（全屏）
      if (this.showOperationListPage) {
        this.OperationListPage()
      }

      // 底部导航栏
      //this.BottomNav()
    }
    .width('100%')
    .height('100%')
  }

  // ================= 局部组件 Builder =================

  aboutToAppear(): void {
    this.fetchSystemStatus();
    this.fetchOperationLogics();
    this.fetchExperienceHistory();
  }

  // ================= API获取方法 =================

  async fetchSystemStatus(): Promise<void> {
    try {
      const request = http.createHttp();
      const resp = await request.request(`${ApiConfig.BASE_URL}/system/status`, {
        method: http.RequestMethod.GET,
        connectTimeout: 5000,
        readTimeout: 8000
      });
      request.destroy();

      if (resp.responseCode === 200 && resp.result) {
        const jsonResult = JSON.parse(resp.result as string) as Record<string, Object>;
        const data = jsonResult['data'] as SystemStatusResponse;
        if (data) {
          this.serviceStatuses = data.services || [];
          this.systemHealthPercent = data.health_percent || 98;
          if (data.user_profile) {
            this.userName = data.user_profile.name;
            this.userRole = data.user_profile.role;
            this.userAvatar = data.user_profile.avatar_letter;
            this.lastLoginInfo = `${data.user_profile.last_login_time} • ${data.user_profile.last_login_device}`;
            this.userExperienceLevel = data.user_profile.experience_level || '';
            this.userTotalInteractions = data.user_profile.total_interactions || 0;
            this.userPreferredMode = data.user_profile.preferred_mode || '';
          }
        }
      }
    } catch (e) {
      // 保持默认值
    }
  }

  async fetchOperationLogics(): Promise<void> {
    this.logicLoading = true;
    try {
      const request = http.createHttp();
      const resp = await request.request(`${ApiConfig.BASE_URL}/system/operation-logics`, {
        method: http.RequestMethod.GET,
        connectTimeout: 5000,
        readTimeout: 8000
      });
      request.destroy();

      if (resp.responseCode === 200 && resp.result) {
        const jsonResult = JSON.parse(resp.result as string) as Record<string, Object>;
        const dataList = jsonResult['data'] as ApiLogicRecord[];
        if (dataList) {
          this.apiOperationLogics = dataList;
        }
      }
    } catch (e) {
      this.apiOperationLogics = [];
    }
    this.logicLoading = false;
  }

  async deleteApiLogic(logicId: string): Promise<boolean> {
    try {
      const request = http.createHttp();
      const resp = await request.request(`${ApiConfig.BASE_URL}/system/operation-logics/${logicId}`, {
        method: http.RequestMethod.DELETE,
        connectTimeout: 5000,
        readTimeout: 8000
      });
      request.destroy();

      if (resp.responseCode === 200) {
        this.apiOperationLogics = this.apiOperationLogics.filter((item: ApiLogicRecord): boolean => item.id !== logicId);
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  }

  // 从操作逻辑文本中提取调控设备
  extractDevices(logicText: string): DeviceInfo[] {
    const allDevices: DeviceInfo[] = [
      { icon: '🌀', name: '通风扇', color: '#3b82f6' },
      { icon: '💧', name: '水泵', color: '#06b6d4' },
      { icon: '💡', name: '补光灯', color: '#f59e0b' },
      { icon: '🌡️', name: '温控器', color: '#ef4444' },
      { icon: '💨', name: '喷雾器', color: '#8b5cf6' },
      { icon: '☀️', name: '遮阳帘', color: '#f97316' }
    ];
    const found: DeviceInfo[] = [];
    for (const device of allDevices) {
      if (logicText.toLowerCase().includes(device.name.toLowerCase()) ||
        logicText.includes('fan') || logicText.includes('pump') ||
        logicText.includes('light') || logicText.includes('temp')) {
        // 避免重复添加
        if (!found.find((d: DeviceInfo): boolean => d.name === device.name)) {
          if ((device.name === '通风扇' && (logicText.includes('fan') || logicText.includes('通风'))) ||
            (device.name === '水泵' && (logicText.includes('pump') || logicText.includes('灌溉') || logicText.includes('水'))) ||
            (device.name === '补光灯' && (logicText.includes('light') || logicText.includes('光照') || logicText.includes('灯'))) ||
            (device.name === '温控器' && (logicText.includes('temp') || logicText.includes('温度'))) ||
            (device.name === '喷雾器' && (logicText.includes('spray') || logicText.includes('喷雾'))) ||
            (device.name === '遮阳帘' && (logicText.includes('shade') || logicText.includes('遮阳')))) {
            found.push(device);
          }
        }
      }
    }
    return found.length > 0 ? found : [{ icon: '⚙️', name: '智能调控', color: '#6b7280' }];
  }

  async fetchExperienceHistory(): Promise<void> {
    this.experienceLoading = true;
    try {
      const request = http.createHttp();
      const resp = await request.request(`${ApiConfig.BASE_URL}/experience/history`, {
        method: http.RequestMethod.GET,
        connectTimeout: 5000,
        readTimeout: 8000
      });
      request.destroy();

      if (resp.responseCode === 200 && resp.result) {
        const jsonResult: Record<string, Object> = JSON.parse(resp.result as string) as Record<string, Object>;
        const innerData: Record<string, Object> = jsonResult['data'] as Record<string, Object>;
        if (innerData) {
          this.experienceActions = (innerData['actions'] as ActionItem[]) || [];
          this.experienceFeedbacks = (innerData['feedback_log'] as FeedbackItem[]) || [];
          this.chatMessages = (innerData['chat_messages'] as ChatMessageItem[]) || [];
        } else {
          this.experienceActions = [];
          this.experienceFeedbacks = [];
          this.chatMessages = [];
        }
      }
    } catch (e) {
      this.experienceActions = [];
      this.experienceFeedbacks = [];
      this.chatMessages = [];
    }
    this.experienceLoading = false;
  }

  @Builder Header() {
    Row() {
      Text('系统设置')
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1f2937')

      // 系统正常 Badge
      Row({ space: 6 }) {
        Circle({ width: 6, height: 6 }).fill(ThemeColors.accent)
        Text('系统正常')
          .fontSize(10)
          .fontColor(ThemeColors.primary)
          .fontWeight(FontWeight.Medium)
      }
      .backgroundColor(ThemeColors.primaryLight)
      .padding({ left: 10, right: 10, top: 4, bottom: 4 })
      .borderRadius(12)
      .borderWidth(1)
      .borderColor(ThemeColors.primaryLight)
    }
    .width('100%')
    .padding(16)
    .backgroundColor('rgba(255, 255, 255, 0.9)')
    .backdropBlur(20)
    .justifyContent(FlexAlign.SpaceBetween)
  }

  @Builder ProfileSection() {
    Column() {
      Row({ space: 16 }) {
        Stack() {
          Circle({ width: 56, height: 56 }).fill(ThemeColors.primaryLight)
          Text(this.userAvatar).fontSize(20).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
        }.borderWidth(2).borderColor(ThemeColors.surface).borderRadius(28)

        Column({ space: 4 }) {
          Row({ space: 8 }) {
            Text(this.userName).fontSize(16).fontWeight(FontWeight.Bold).fontColor('#1f2937')
            Text(this.userRole)
              .fontSize(9)
              .fontColor(ThemeColors.primary)
              .backgroundColor(ThemeColors.primaryLight)
              .padding({ left: 6, right: 6, top: 2, bottom: 2 })
              .borderRadius(4)
          }
          Text(`上次登录: ${this.lastLoginInfo}`).fontSize(11).fontColor('#6b7280')
        }.alignItems(HorizontalAlign.Start)
      }.width('100%').margin({ bottom: 16 })

      Row() {
        this.RoleButton('管理员', '李技术', '李')
        this.RoleButton('技术员', '张工', '张')
        this.RoleButton('观察员', '王监', '王')
      }
      .width('100%')
      .backgroundColor('#f9fafb')
      .padding(4)
      .borderRadius(12)
      .margin({ bottom: 16 })

      // 用户画像信息（从API获取）
      if (this.userExperienceLevel || this.userTotalInteractions > 0 || this.userPreferredMode) {
        Column({ space: 8 }) {
          Row() {
            Text('用户画像').fontSize(12).fontWeight(FontWeight.Bold).fontColor('#374151')
          }.width('100%')

          Row({ space: 8 }) {
            if (this.userExperienceLevel) {
              Column({ space: 4 }) {
                Text('经验等级').fontSize(10).fontColor('#6b7280')
                Text(this.userExperienceLevel).fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              }.layoutWeight(1).padding(8).backgroundColor('#f0fdf4').borderRadius(8).alignItems(HorizontalAlign.Center)
            }
            if (this.userTotalInteractions > 0) {
              Column({ space: 4 }) {
                Text('交互次数').fontSize(10).fontColor('#6b7280')
                Text(`${this.userTotalInteractions}`).fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              }.layoutWeight(1).padding(8).backgroundColor('#f0fdf4').borderRadius(8).alignItems(HorizontalAlign.Center)
            }
            if (this.userPreferredMode) {
              Column({ space: 4 }) {
                Text('偏好模式').fontSize(10).fontColor('#6b7280')
                Text(this.userPreferredMode).fontSize(13).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
              }.layoutWeight(1).padding(8).backgroundColor('#f0fdf4').borderRadius(8).alignItems(HorizontalAlign.Center)
            }
          }.width('100%')
        }
        .width('100%')
        .padding(12)
        .backgroundColor('#f9fafb')
        .borderRadius(12)
        .margin({ bottom: 16 })
      }

      Button('退出登录')
        .width('100%')
        .backgroundColor('rgba(239, 68, 68, 0.05)')
        .fontColor(ThemeColors.danger)
        .fontSize(13)
        .fontWeight(FontWeight.Bold)
        .onClick(() => {
          promptAction.showDialog({
            title: '退出登录',
            message: '确定要退出当前账号吗？',
            buttons: [
              { text: '取消', color: '#000000' },
              { text: '退出', color: ThemeColors.danger }
            ]
          }).then(data => {
            if (data.index === 1) {
              promptAction.showToast({ message: '已退出登录' });
            }
          })
        })
    }
    .width('100%')
    .padding(16)
    .backgroundColor(ThemeColors.surface)
    .borderRadius(16)
  }

  @Builder RoleButton(role: string, name: string, avatar: string) {
    Text(role)
      .layoutWeight(1)
      .textAlign(TextAlign.Center)
      .padding({ top: 6, bottom: 6 })
      .fontSize(12)
      .fontWeight(this.userRole === role ? FontWeight.Bold : FontWeight.Medium)
      .fontColor(this.userRole === role ? ThemeColors.primary : '#6b7280')
      .backgroundColor(this.userRole === role ? ThemeColors.surface : 'transparent')
      .borderRadius(8)
      .onClick(() => {
        this.userRole = role;
        this.userName = name;
        this.userAvatar = avatar;
        promptAction.showToast({ message: `已切换为${role}角色` });
      })
  }

  @Builder SystemStatusSection() {
    Column() {
      Row({ space: 8 }) {
        Row().width(24).height(24).backgroundColor(ThemeColors.primaryLight).borderRadius(4)
        Text('微服务系统状态').fontSize(13).fontWeight(FontWeight.Bold)
      }.width('100%').margin({ bottom: 12 })

      // 动态渲染从API获取的服务状态卡片
      if (this.serviceStatuses.length > 0) {
        Flex({ wrap: FlexWrap.Wrap, justifyContent: FlexAlign.SpaceBetween }) {
          ForEach(this.serviceStatuses, (svc: ServiceStatusItem) => {
            this.ApiServiceCard(svc)
          })
        }.width('100%')
      } else {
        Column() {
          Text('暂无服务数据').fontSize(12).fontColor('#9ca3af')
        }.width('100%').padding(16).backgroundColor('#f9fafb').borderRadius(12)
      }

      Column({ space: 4 }) {
        Row() {
          Text('系统整体健康度').fontSize(10).fontColor('#6b7280')
          Text(`${this.systemHealthPercent}%`).fontSize(12).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ top: 12 })

        Progress({ value: this.systemHealthPercent, total: 100, type: ProgressType.Linear })
          .color(ThemeColors.accent)
          .backgroundColor('#f3f4f6')
          .width('100%')
      }.width('100%')

      Button(this.isRefreshing ? '刷新中...' : '刷新状态')
        .width('100%')
        .backgroundColor('#f9fafb')
        .fontColor('#4b5563')
        .fontSize(11)
        .margin({ top: 12 })
        .onClick(() => {
          this.isRefreshing = true;
          this.fetchSystemStatus().then(() => {
            this.isRefreshing = false;
            promptAction.showToast({ message: '系统状态已刷新' });
          })
        })
    }
    .width('100%')
    .padding(16)
    .backgroundColor(ThemeColors.surface)
    .borderRadius(16)
  }

  @Builder ApiServiceCard(svc: ServiceStatusItem) {
    Column() {
      Row() {
        Text(svc.name || svc.service_name || svc.service_display).fontSize(11).fontWeight(FontWeight.Bold).fontColor('#374151')
        Row({ space: 4 }) {
          Circle({ width: 6, height: 6 }).fill(svc.status_color === '#10b981' ? ThemeColors.accent : ThemeColors.warning)
          Text(`${svc.latency_ms}ms`).fontSize(9).fontColor(svc.status_color).fontWeight(FontWeight.Medium)
        }
      }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 8 })

      Text(`端口: ${svc.port}`).fontSize(10).fontColor('#6b7280').margin({ bottom: 4 })
      Text(`同步: ${svc.last_sync}`).fontSize(9).fontColor('#9ca3af')
    }
    .width('48%')
    .backgroundColor(svc.status === 'offline' ? '#fff7ed' : '#f9fafb')
    .padding(12)
    .borderRadius(12)
    .margin({ bottom: 8 })
  }

  @Builder OperationLogicSection() {
    // 微信风格收起卡片
    Row() {
      Row({ space: 10 }) {
        Text('📝').fontSize(20)
        Column({ space: 2 }) {
          Text('操作逻辑存储库').fontSize(14).fontWeight(FontWeight.Bold).fontColor('#1f2937')
          if (!this.logicLoading) {
            Text(`${this.apiOperationLogics.length}条记录`)
              .fontSize(11).fontColor('#9ca3af')
          } else {
            Text('加载中...').fontSize(11).fontColor('#9ca3af')
          }
        }.alignItems(HorizontalAlign.Start)
      }
      Blank()
      Text('>').fontSize(16).fontColor('#c4c4c4')
    }
    .width('100%')
    .padding(16)
    .backgroundColor(ThemeColors.surface)
    .borderRadius(12)
    .onClick(() => {
      this.showOperationListPage = true;
      this.fetchOperationLogics();
    })
  }

  @Builder OperationListPage() {
    // 全屏详情页（操作逻辑列表）
    Stack({ alignContent: Alignment.Top }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => {
        this.showOperationListPage = false;
      })

      Column({ space: 0 }) {
        // 导航栏
        Row() {
          Text('< 返回').fontSize(15).fontColor(ThemeColors.primary).fontWeight(FontWeight.Medium)
            .onClick(() => { this.showOperationListPage = false; })
          Blank()
          Text('操作逻辑存储库').fontSize(17).fontWeight(FontWeight.Bold).fontColor('#1f2937')
          Blank()
          Text('🔄').fontSize(16).fontColor(ThemeColors.primary)
            .onClick(() => { this.fetchOperationLogics(); })
        }.width('100%').padding({ left: 16, right: 16, top: 12, bottom: 12 })
        .backgroundColor(ThemeColors.surface)
        .borderRadius({ topLeft: 16, topRight: 16 })

        // 内容区
        Scroll() {
          if (this.logicLoading) {
            Column() {
              LoadingProgress().width(36).height(36).margin({ bottom: 8 })
              Text('加载中...').fontSize(12).fontColor('#9ca3af')
            }.width('100%').padding(48)
          } else if (this.apiOperationLogics.length === 0) {
            Column() {
              Text('📭').fontSize(48).margin({ bottom: 16 })
              Text('暂无操作逻辑记录').fontSize(15).fontColor('#6b7280')
              Text('在智能交互页面输入内容并提交操作逻辑后，记录将显示在这里')
                .fontSize(12).fontColor('#9ca3af').textAlign(TextAlign.Center).margin({ top: 8 })
            }.width('100%').padding(48)
          } else {
            Column({ space: 10 }) {
              ForEach(this.apiOperationLogics, (logic: ApiLogicRecord) => {
                this.LogicDetailCard(logic)
              })
            }.width('100%').padding(12)
          }
        }
        .width('100%')
        .layoutWeight(1)
        .backgroundColor('#f5f5f5')
      }
      .width('90%')
      .height('80%')
      .backgroundColor(ThemeColors.surface)
      .borderRadius({ topLeft: 20, topRight: 20, bottomLeft: 0, bottomRight: 0 })
      .zIndex(200)
    }
    .width('100%')
    .height('100%')
  }

  @Builder LogicDetailCard(logic: ApiLogicRecord) {
    Column({ space: 10 }) {
      // 标题行 + 删除按钮
      Row() {
        Text('📝').fontSize(15)
        Text(logic.inputText.length > 30 ? logic.inputText.substring(0, 30) + '...' : logic.inputText)
          .fontSize(13).fontWeight(FontWeight.Bold).fontColor('#1f2937').layoutWeight(1).maxLines(2)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
        Text('🗑️').fontSize(16).fontColor('#d1d5db')
          .onClick(() => {
            promptAction.showDialog({
              title: '删除确认',
              message: '确定要删除这条操作逻辑记录吗？',
              buttons: [
                { text: '取消', color: '#000000' },
                { text: '删除', color: ThemeColors.danger }
              ]
            }).then(async (data) => {
              if (data.index === 1) {
                const success = await this.deleteApiLogic(logic.id);
                if (success) {
                  promptAction.showToast({ message: '已删除' });
                } else {
                  promptAction.showToast({ message: '删除失败' });
                }
              }
            });
          })
      }.width('100%')

      // 具体调控设备（从操作逻辑中提取）
      Column({ space: 6 }) {
        Text('🔧 调控设备：').fontSize(11).fontColor('#0b5934').fontWeight(FontWeight.Bold)
        Row({ space: 8 }) {
          ForEach(this.extractDevices(logic.operationLogic), (device: DeviceInfo) => {
            Row({ space: 4 }) {
              Text(device.icon).fontSize(13)
              Text(device.name).fontSize(11).fontColor('#374151')
            }
            .padding({ left: 8, right: 8, top: 3, bottom: 3 })
            .backgroundColor('#dcfce7')
            .borderRadius(12)
          })
        }
      }
      .width('100%')
      .padding(10)
      .backgroundColor('#f0fdf4')
      .borderRadius(8)

      // 操作逻辑内容
      Column({ space: 6 }) {
        Text('操作逻辑：').fontSize(11).fontColor('#6b7280').fontWeight(FontWeight.Bold)
        Text(logic.operationLogic || '无')
          .fontSize(12).fontColor('#374151').lineHeight(18)
      }
      .width('100%')
      .padding(10)
      .backgroundColor('#f9fafb')
      .borderRadius(8)

      // 时间
      Text(`创建时间：${logic.createTime}`).fontSize(10).fontColor('#9ca3af')
    }
    .width('100%')
    .backgroundColor('#ffffff')
    .padding(14)
    .borderRadius(12)
    .onClick(() => {
      this.selectedApiLogic = logic;
      this.showOperationDetailModal = true;
    })
  }

  @Builder OperationDetailModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.5)').onClick(() => {
        this.showOperationDetailModal = false;
      })

      Column({ space: 20 }) {
        Row() {
          Text('操作逻辑详情').fontSize(18).fontWeight(FontWeight.Bold).fontColor('#1f2937')
          Text('✕').fontSize(18).fontColor('#6b7280').onClick(() => {
            this.showOperationDetailModal = false;
          })
        }.width('100%').justifyContent(FlexAlign.SpaceBetween)

        if (this.selectedApiLogic) {
          Column({ space: 16 }) {
            Column({ space: 8 }) {
              Text('输入内容：').fontSize(14).fontColor('#6b7280').fontWeight(FontWeight.Bold)
              Text(this.selectedApiLogic.inputText)
                .fontSize(14)
                .fontColor('#1f2937')
                .width('100%')
                .padding(12)
                .backgroundColor(ThemeColors.primaryLight)
                .borderRadius(8)
            }.width('100%')

            // 具体调控设备
            Column({ space: 8 }) {
              Text('🔧 调控设备：').fontSize(14).fontColor('#0b5934').fontWeight(FontWeight.Bold)
              Flex({ wrap: FlexWrap.Wrap }) {
                ForEach(this.extractDevices(this.selectedApiLogic.operationLogic), (device: DeviceInfo) => {
                  Row({ space: 6 }) {
                    Text(device.icon).fontSize(16)
                    Text(device.name).fontSize(13).fontColor('#374151')
                  }
                  .padding({ left: 12, right: 12, top: 5, bottom: 5 })
                  .backgroundColor('#dcfce7')
                  .borderRadius(14)
                })
              }.width('100%')
            }.width('100%')

            Column({ space: 8 }) {
              Text('操作逻辑：').fontSize(14).fontColor('#6b7280').fontWeight(FontWeight.Bold)
              Text(this.selectedApiLogic.operationLogic || '无')
                .fontSize(14)
                .fontColor('#1f2937')
                .width('100%')
                .padding(12)
                .backgroundColor('#f9fafb')
                .borderRadius(8)
                .borderWidth(1)
                .borderColor('#e5e7eb')
            }.width('100%')

            Row({ space: 4 }) {
              Text('创建时间：').fontSize(12).fontColor('#9ca3af')
              Text(this.selectedApiLogic.createTime).fontSize(12).fontColor('#9ca3af')
            }.width('100%')
          }.width('100%')
        }

        Row({ space: 12 }) {
          Button('删除')
            .layoutWeight(1)
            .backgroundColor('rgba(239, 68, 68, 0.1)')
            .fontColor(ThemeColors.danger)
            .height(44)
            .onClick(() => {
              if (this.selectedApiLogic) {
                promptAction.showDialog({
                  title: '删除确认',
                  message: '确定要删除这条操作逻辑记录吗？',
                  buttons: [
                    { text: '取消', color: '#000000' },
                    { text: '删除', color: ThemeColors.danger }
                  ]
                }).then(async (data) => {
                  if (data.index === 1) {
                    const success = await this.deleteApiLogic(this.selectedApiLogic!.id);
                    if (success) {
                      this.showOperationDetailModal = false;
                      promptAction.showToast({ message: '已删除' });
                    }
                  }
                });
              }
            })

          Button('关闭')
            .layoutWeight(1)
            .backgroundColor(ThemeColors.primary)
            .fontColor('#ffffff')
            .height(44)
            .onClick(() => {
              this.showOperationDetailModal = false;
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

  @Builder ExperienceHistorySection() {
    // 微信风格收起卡片
    Row() {
      Row({ space: 10 }) {
        Text('📖').fontSize(20)
        Column({ space: 2 }) {
          Text('经验学习记录').fontSize(14).fontWeight(FontWeight.Bold).fontColor('#1f2937')
          if (!this.experienceLoading) {
            Text(`${this.experienceActions.length}条操作 · ${this.experienceFeedbacks.length}条反馈`)
              .fontSize(11).fontColor('#9ca3af')
          } else {
            Text('加载中...').fontSize(11).fontColor('#9ca3af')
          }
        }.alignItems(HorizontalAlign.Start)
      }
      Blank()
      Text('>').fontSize(16).fontColor('#c4c4c4')
    }
    .width('100%')
    .padding(16)
    .backgroundColor(ThemeColors.surface)
    .borderRadius(12)
    .onClick(() => {
      this.showExperienceDetailPage = true;
      this.fetchExperienceHistory();
    })
  }

  @Builder ExperienceDetailPage() {
    // 全屏详情页（模拟新页面）
    Stack({ alignContent: Alignment.Top }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => {
        this.showExperienceDetailPage = false;
      })

      Column({ space: 0 }) {
        // 导航栏
        Row() {
          Text('< 返回').fontSize(15).fontColor(ThemeColors.primary).fontWeight(FontWeight.Medium)
            .onClick(() => { this.showExperienceDetailPage = false; })
          Blank()
          Text('经验学习记录').fontSize(17).fontWeight(FontWeight.Bold).fontColor('#1f2937')
          Blank()
          Text('🔄').fontSize(16).fontColor(ThemeColors.primary)
            .onClick(() => { this.fetchExperienceHistory(); })
        }.width('100%').padding({ left: 16, right: 16, top: 12, bottom: 12 })
        .backgroundColor(ThemeColors.surface)
        .borderRadius({ topLeft: 16, topRight: 16 })

        // Tab切换（三栏：操作历史 / 聊天记录 / 用户反馈）
        Row({ space: 0 }) {
          Column() {
            Text('操作历史').fontSize(12).fontWeight(this.experienceTab === 'actions' ? FontWeight.Bold : FontWeight.Normal)
              .fontColor(this.experienceTab === 'actions' ? ThemeColors.primary : '#6b7280')
              .padding({ top: 10, bottom: 10 })
            if (this.experienceTab === 'actions') {
              Row().width(40).height(3).backgroundColor(ThemeColors.primary).borderRadius(2).margin({ top: -3 })
            }
          }.layoutWeight(1).alignItems(HorizontalAlign.Center)
          .onClick(() => { this.experienceTab = 'actions'; })

          Column() {
            Text('聊天记录').fontSize(12).fontWeight(this.experienceTab === 'chat' ? FontWeight.Bold : FontWeight.Normal)
              .fontColor(this.experienceTab === 'chat' ? ThemeColors.primary : '#6b7280')
              .padding({ top: 10, bottom: 10 })
            if (this.experienceTab === 'chat') {
              Row().width(40).height(3).backgroundColor(ThemeColors.primary).borderRadius(2).margin({ top: -3 })
            }
          }.layoutWeight(1).alignItems(HorizontalAlign.Center)
          .onClick(() => { this.experienceTab = 'chat'; })

          Column() {
            Text('用户反馈').fontSize(12).fontWeight(this.experienceTab === 'feedbacks' ? FontWeight.Bold : FontWeight.Normal)
              .fontColor(this.experienceTab === 'feedbacks' ? ThemeColors.primary : '#6b7280')
              .padding({ top: 10, bottom: 10 })
            if (this.experienceTab === 'feedbacks') {
              Row().width(40).height(3).backgroundColor(ThemeColors.primary).borderRadius(2).margin({ top: -3 })
            }
          }.layoutWeight(1).alignItems(HorizontalAlign.Center)
          .onClick(() => { this.experienceTab = 'feedbacks'; })
        }
        .width('100%')
        .backgroundColor(ThemeColors.surface)

        // 内容区
        Scroll() {
          if (this.experienceLoading) {
            Column() {
              LoadingProgress().width(36).height(36).margin({ bottom: 8 })
              Text('加载中...').fontSize(12).fontColor('#9ca3af')
            }.width('100%').padding(48)
          } else if (this.experienceTab === 'actions') {
            if (this.experienceActions.length === 0) {
              this.EmptyState('暂无操作历史', '在智能交互页面发送消息后，每次操作将自动记录')
            } else {
              Column({ space: 8 }) {
                ForEach(this.experienceActions, (action: ActionItem) => {
                  this.ActionCard(action)
                })
              }.width('100%').padding(12)
            }
          } else if (this.experienceTab === 'chat') {
            if (this.chatMessages.length === 0) {
              this.EmptyState('暂无聊天记录', '在AI协作界面发送的消息将同步显示在这里')
            } else {
              Column({ space: 8 }) {
                ForEach(this.chatMessages, (msg: ChatMessageItem) => {
                  this.ChatMessageCard(msg)
                })
              }.width('100%').padding(12)
            }
          } else {
            if (this.experienceFeedbacks.length === 0) {
              this.EmptyState('暂无用户反馈', '用户点击 👍 或 👎 后，反馈记录将显示在这里')
            } else {
              Column({ space: 8 }) {
                ForEach(this.experienceFeedbacks, (fb: FeedbackItem) => {
                  this.FeedbackCard(fb)
                })
              }.width('100%').padding(12)
            }
          }
        }
        .width('100%')
        .layoutWeight(1)
        .backgroundColor('#f5f5f5')
      }
      .width('90%')
      .height('80%')
      .backgroundColor(ThemeColors.surface)
      .borderRadius({ topLeft: 20, topRight: 20, bottomLeft: 0, bottomRight: 0 })
      .zIndex(200)
    }
    .width('100%')
    .height('100%')
  }

  @Builder ActionCard(action: ActionItem) {
    Column({ space: 6 }) {
      Row() {
        Text(action.action === 'CHAT' ? '💬' : '🎤').fontSize(15)
        Text(action.reason || '未知指令')
          .fontSize(13).fontWeight(FontWeight.Bold).fontColor('#1f2937').layoutWeight(1).maxLines(2).textOverflow({ overflow: TextOverflow.Ellipsis })
      }.width('100%')

      Row({ space: 8 }) {
        Text(action.skill === 'device_control_skill' ? '设备控制' : '智能问答')
          .fontSize(10).fontColor(ThemeColors.surface)
          .backgroundColor(action.skill === 'device_control_skill' ? ThemeColors.accent : ThemeColors.primary)
          .padding({ left: 8, right: 8, top: 3, bottom: 3 }).borderRadius(8)
        Text(`状态: ${action.status === 'executed' ? '已执行' : '待执行'}`)
          .fontSize(10).fontColor(ThemeColors.accent)
      }

      Row({ space: 8 }) {
        Text(`会话: ${action.session_id ? action.session_id.substring(0, 18) : ''}`)
          .fontSize(9).fontColor('#9ca3af')
        Text(action.time ? action.time.substring(5, 16) : '')
          .fontSize(9).fontColor('#9ca3af')
      }.width('100%')

      if (action.has_feedback && action.feedback) {
        Row({ space: 4 }) {
          Text(((action.feedback['type'] || '') === 'positive') ? '👍 好评' : '👎 差评')
            .fontSize(10).fontWeight(FontWeight.Medium)
            .fontColor(((action.feedback['type'] || '') === 'positive') ? ThemeColors.accent : ThemeColors.danger)
          Text((action.feedback['comment'] || '') as string)
            .fontSize(10).fontColor('#6b7280').maxLines(1).layoutWeight(1)
        }
      }
    }
    .width('100%')
    .backgroundColor('#ffffff')
    .padding(12)
    .borderRadius(12)
  }

  @Builder FeedbackCard(fb: FeedbackItem) {
    Row({ space: 10 }) {
      Text(fb.feedback_type === 'positive' ? '👍' : '👎').fontSize(22)
      Column({ space: 4 }) {
        Text(fb.reasoning || (fb.feedback_type === 'positive' ? '用户好评' : '用户差评'))
          .fontSize(13).fontColor('#1f2937').maxLines(2).textOverflow({ overflow: TextOverflow.Ellipsis })
        Row({ space: 10 }) {
          Text(`置信度 ${(fb.confidence * 100).toFixed(0)}%`).fontSize(10).fontColor(ThemeColors.accent)
          Text(fb.time ? fb.time.substring(5, 16) : '').fontSize(10).fontColor('#9ca3af')
        }
      }.alignItems(HorizontalAlign.Start).layoutWeight(1)
    }
    .width('100%')
    .backgroundColor(fb.feedback_type === 'positive' ? '#f0fdf4' : '#fef2f2')
    .padding(12)
    .borderRadius(12)
    .borderWidth(1)
    .borderColor(fb.feedback_type === 'positive' ? '#bbf7d0' : '#fecaca')
  }

  @Builder ChatMessageCard(msg: ChatMessageItem) {
    Column({ space: 6 }) {
      // 第一行：角色图标 + 模式标签 + 内容
      Row({ space: 8 }) {
        // 角色标识
        Text(msg.role === 'user' ? '👤' : '🤖').fontSize(15)

        // 模式标签（核心：区分农艺/设备）
        Text(msg.chat_mode === 'device' ? '⚙️ 设备调控' : '🌾 农艺专家')
          .fontSize(10)
          .fontColor('#ffffff')
          .backgroundColor(msg.chat_mode === 'device' ? '#3b82f6' : '#10b981')
          .padding({ left: 8, right: 8, top: 3, bottom: 3 })
          .borderRadius(8)

        // 内容预览
        Text(msg.content || '')
          .fontSize(13)
          .fontColor('#1f2937')
          .fontWeight(FontWeight.Medium)
          .layoutWeight(1)
          .maxLines(2)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
      }.width('100%')

      // 第二行：时间 + 反馈
      Row({ space: 8 }) {
        Text(msg.time ? msg.time.substring(5, 16) : '')
          .fontSize(9).fontColor('#9ca3af')

        if (msg.feedback) {
          Text(msg.feedback === 'positive' ? '👍 有用' : '👎 无用')
            .fontSize(10).fontColor(msg.feedback === 'positive' ? ThemeColors.accent : ThemeColors.danger)
        }
      }.width('100%').justifyContent(FlexAlign.SpaceBetween)
    }
    .width('100%')
    .backgroundColor(msg.role === 'user' ? '#f0fdf4' : '#f8fafc')
    .padding(12)
    .borderRadius(12)
    .borderWidth(1)
    .borderColor(msg.role === 'user' ? '#bbf7d0' : '#e2e8f0')
  }

  @Builder ExperienceTabButton(label: string, tab: string) {
    Text(label).fontSize(11).fontWeight(this.experienceTab === tab ? FontWeight.Bold : FontWeight.Normal)
      .fontColor(this.experienceTab === tab ? ThemeColors.primary : '#9ca3af')
      .padding({ left: 12, right: 12, top: 6, bottom: 6 })
      .backgroundColor(this.experienceTab === tab ? ThemeColors.primaryLight : '#f3f4f6')
      .borderRadius(16)
      .onClick(() => { this.experienceTab = tab; })
  }

  @Builder EmptyState(title: string, desc: string) {
    Column() {
      Text('📭').fontSize(32).margin({ bottom: 8 })
      Text(title).fontSize(13).fontColor('#6b7280')
      Text(desc).fontSize(10).fontColor('#9ca3af').textAlign(TextAlign.Center).margin({ top: 4 })
    }.width('100%').padding(24)
  }

  // @Builder BottomNav() {
  //   Row() {
  //     this.NavItem('首页', 'ic_home')
  //     this.NavItem('控制', 'ic_control')
  //
  //     Column() {
  //       Stack() {
  //         Circle({ width: 48, height: 48 }).fill(ThemeColors.primary)
  //       }
  //       .borderWidth(4).borderColor(ThemeColors.surface).borderRadius(28)
  //       .shadow({ radius: 10, color: 'rgba(16, 185, 129, 0.4)', offsetY: 4 })
  //       Text('AI协作').fontSize(10).fontWeight(FontWeight.Bold).fontColor('#9ca3af').margin({ top: 4 })
  //     }
  //     .offset({ y: -20 })
  //
  //     this.NavItem('生命周期', 'ic_lifecycle')
  //     this.NavItem('设置', 'ic_settings', true)
  //   }
  //   .width('100%')
  //   .height(64)
  //   .backgroundColor(ThemeColors.surface)
  //   .justifyContent(FlexAlign.SpaceAround)
  //   .shadow({ radius: 10, color: 'rgba(0,0,0,0.02)', offsetY: -4 })
  // }

  @Builder NavItem(title: string, icon: string, isActive: boolean = false) {
    Column({ space: 4 }) {
      Row().width(24).height(24).backgroundColor(isActive ? ThemeColors.primary : '#9ca3af').borderRadius(4)
      Text(title)
        .fontSize(10)
        .fontWeight(isActive ? FontWeight.Bold : FontWeight.Medium)
        .fontColor(isActive ? ThemeColors.primary : '#9ca3af')
    }
  }
}