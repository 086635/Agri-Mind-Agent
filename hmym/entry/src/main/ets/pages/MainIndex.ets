import { promptAction } from '@kit.ArkUI';

// 导入你的 5 个子页面组件 (确保路径和你的文件名一致)
import { AgriSyncDashboardPage } from './AgriSyncDashboardPage'; // 确保文件名和大小写完全一致
import { AgriSyncControlPage } from './AgriSyncControlPage';
// ...其他3个
import { SmartInteractionPage } from './SmartInteractionPage';
import { AgriSyncLifecyclePage } from './AgriSyncLifecyclePage';
import { SystemSettingsPage } from './SystemSettingsPage';

// 提取统一定义的主题色，用于底部导航栏
class ThemeColors {
  static readonly primary: string = '#0b5934';
  static readonly surface: string = '#ffffff';
  static readonly textMuted: string = '#6b7280';
  static readonly borderLight: string = '#f3f4f6';
}

@Entry
@Component
struct MainIndex {
  // ================= 全局状态管理 =================
  // 0:首页, 1:控制, 2:AI协作, 3:生命周期, 4:设置
  @State currentIndex: number = 0;

  // ================= 页面主视图 =================
  build() {
    Stack({ alignContent: Alignment.Bottom }) {

      // 1. 动态页面渲染区
      Column() {
        if (this.currentIndex === 0) {
          AgriSyncDashboardPage()
        } else if (this.currentIndex === 1) {
          AgriSyncControlPage()
        } else if (this.currentIndex === 2) {
          SmartInteractionPage()
        } else if (this.currentIndex === 3) {
          AgriSyncLifecyclePage()
        } else if (this.currentIndex === 4) {
          SystemSettingsPage()
        }
      }
      .width('100%')
      .height('100%')
      .backgroundColor('#f4f7f6')

      // 2. 统一的全局底部导航栏
      this.UnifiedBottomNav()

    }
    .width('100%')
    .height('100%')
  }

  // ================= 全局组件 Builder =================

  @Builder UnifiedBottomNav() {
    Row() {
      this.NavItem('首页', '🏠', 0)
      this.NavItem('控制', '🎛️', 1)

      // 中间按钮 (AI协作) — 与其他图标齐平
      Column() {
        Stack({ alignContent: Alignment.Center }) {
          Circle({ width: 48, height: 48 }).fill(ThemeColors.primary)
            .shadow({ radius: 8, color: 'rgba(11, 89, 52, 0.3)', offsetY: 2 })
          Text('🧠').fontSize(20)
        }
        .width(48)
        .height(48)

        Text('AI协作')
          .fontSize(10)
          .fontWeight(FontWeight.Bold)
          .fontColor(this.currentIndex === 2 ? ThemeColors.primary : ThemeColors.textMuted)
          .margin({ top: 2 })
      }
      .height(64)
      .justifyContent(FlexAlign.End)
      .padding({ bottom: 6 })
      .onClick(() => {
        this.currentIndex = 2; // 切换到 AI 页面
      })

      this.NavItem('生命周期', '🌱', 3)
      this.NavItem('设置', '⚙️', 4)
    }
    .width('100%')
    .height(64)
    .backgroundColor('rgba(255, 255, 255, 0.95)')
    .backdropBlur(20)
    .borderWidth({ top: 1 })
    .borderColor(ThemeColors.borderLight)
    .justifyContent(FlexAlign.SpaceAround)
    .alignItems(VerticalAlign.Bottom)
    .padding({ bottom: 8 })
    .zIndex(999) // 确保在所有子页面的最上层
  }

  @Builder NavItem(title: string, emoji: string, targetIndex: number) {
    Column({ space: 4 }) {
      Text(emoji)
        .fontSize(24)
        .opacity(this.currentIndex === targetIndex ? 1 : 0.5) // 未选中时图标变半透明
      Text(title)
        .fontSize(10)
        .fontWeight(this.currentIndex === targetIndex ? FontWeight.Bold : FontWeight.Medium)
        .fontColor(this.currentIndex === targetIndex ? ThemeColors.primary : ThemeColors.textMuted)
    }
    .padding({ bottom: 4 })
    .onClick(() => {
      this.currentIndex = targetIndex; // 切换页面状态
    })
  }
}