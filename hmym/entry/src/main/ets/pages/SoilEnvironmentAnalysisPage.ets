import { router } from '@kit.ArkUI';
import { promptAction } from '@kit.ArkUI';
import { http } from '@kit.NetworkKit';
import { photoAccessHelper } from '@kit.MediaLibraryKit';
import { fileIo } from '@kit.CoreFileKit';
import { util } from '@kit.ArkTS';
import { ApiConfig } from '../common/ApiConfig';

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

@Entry
@Component
struct SoilEnvironmentAnalysisPage {
  @State analyzeLoading: boolean = false;
  @State analyzeResult: string = '';
  @State hasAnalyzed: boolean = false;
  @State selectedImageUri: string = '';
  @State annotatedImageUrl: string = '';
  @State detectionCount: number = 0;
  @State isHealthy: boolean = true;
  @State detections: string = '';
  @State actionAdvice: string = '';

  async pickAndAnalyze(): Promise<void> {
    try {
      const photoSelectOptions: photoAccessHelper.PhotoSelectOptions = {
        MIMEType: photoAccessHelper.PhotoViewMIMETypes.IMAGE_TYPE,
        maxSelectNumber: 1
      };
      const photoPicker = new photoAccessHelper.PhotoViewPicker();
      const photoSelectResult: photoAccessHelper.PhotoSelectResult = await photoPicker.select(photoSelectOptions);

      if (photoSelectResult.photoUris && photoSelectResult.photoUris.length > 0) {
        const sourceUri = photoSelectResult.photoUris[0];
        this.selectedImageUri = sourceUri;
        await this.uploadAndAnalyzeBase64(sourceUri);
      }
    } catch (e) {
      promptAction.showToast({ message: '选择图片失败' });
    }
  }

  async uploadAndAnalyzeBase64(sourceUri: string): Promise<void> {
    this.analyzeLoading = true;
    this.hasAnalyzed = true;
    try {
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

      const readFd = fileIo.openSync(destPath, fileIo.OpenMode.READ_ONLY);
      const readStat: fileIo.Stat = fileIo.statSync(destPath);
      const readSize: number = readStat.size;
      const buffer = new ArrayBuffer(readSize);
      fileIo.readSync(readFd.fd, buffer);
      fileIo.closeSync(readFd);

      const base64Helper = new util.Base64Helper();
      const encodedBuf: Uint8Array = new Uint8Array(buffer);
      const base64Str: string = base64Helper.encodeToStringSync(encodedBuf);

      const httpRequest = http.createHttp();
      const resp = await httpRequest.request(`${ApiConfig.BASE_URL}/upload/base64`, {
        method: http.RequestMethod.POST,
        header: { 'Content-Type': 'application/json' },
        extraData: JSON.stringify({
          image_base64: base64Str,
          filename: `soil_${Date.now()}.jpg`,
          growth_stage: 'growth'
        }),
        connectTimeout: 10000,
        readTimeout: 60000,
        expectDataType: http.HttpDataType.STRING
      });
      httpRequest.destroy();

      if (resp.responseCode === 200 && resp.result) {
        const data: Record<string, Object> = JSON.parse(resp.result as string) as Record<string, Object>;
        this.parseVisionResponse(data);
      } else if (resp.responseCode === 502 || resp.responseCode === 503) {
        this.analyzeResult = '视觉服务未启动。请运行: python vision_server.py (端口8004)';
      } else {
        this.analyzeResult = `请求失败 HTTP ${resp.responseCode}`;
      }
    } catch (e) {
      this.analyzeResult = '连接失败，请确认超级网关(9000)和视觉服务(8004)是否启动';
    } finally {
      this.analyzeLoading = false;
    }
  }

  async requestQuickAnalyze(): Promise<void> {
    this.analyzeLoading = true;
    this.hasAnalyzed = true;
    try {
      const request = http.createHttp();
      const resp = await request.request(`${ApiConfig.BASE_URL}/analyze/json`, {
        method: http.RequestMethod.POST,
        header: { 'Content-Type': 'application/json' },
        extraData: JSON.stringify({ analysis_type: 'soil', test_mode: true }),
        connectTimeout: 10000, readTimeout: 30000
      });
      request.destroy();
      if (resp.responseCode === 200 && resp.result) {
        const data: Record<string, Object> = JSON.parse(resp.result as string) as Record<string, Object>;
        this.parseVisionResponse(data);
      } else if (resp.responseCode === 502 || resp.responseCode === 503) {
        this.analyzeResult = '视觉服务未启动。请运行: python vision_server.py (端口8004)';
      } else {
        this.analyzeResult = `请求失败 HTTP ${resp.responseCode}`;
      }
    } catch (e) {
      this.analyzeResult = '连接失败，请确认超级网关(9000)和视觉服务(8004)是否启动';
    } finally {
      this.analyzeLoading = false;
    }
  }

  parseVisionResponse(data: Record<string, Object>): void {
    const dataObj = data['data'] as Record<string, Object>;
    if (dataObj) {
      const summary = dataObj['summary'] as Record<string, Object>;
      if (summary) {
        this.detectionCount = (summary['total_count'] as number) || (summary['total_objects'] as number) || 0;
        this.isHealthy = (summary['is_healthy'] as boolean) ?? true;
      }
      const detections = dataObj['detections'] as Array<Record<string, Object>>;
      if (detections && detections.length > 0) {
        const lines: string[] = [];
        for (const det of detections) {
          const className = (det['class_name'] as string) || (det['class'] as string) || '未知';
          const confidence = (det['confidence'] as number) || 0;
          lines.push(`${className}: ${(confidence * 100).toFixed(1)}%`);
        }
        this.detections = lines.join('\n');
      }
      this.actionAdvice = (dataObj['action_advice'] as string) || '';
    }

    const annotatedUrl = data['annotated_url'] as string;
    if (annotatedUrl) {
      this.annotatedImageUrl = `${ApiConfig.BASE_URL}${annotatedUrl}`;
    }

    let result = `📊 检测到 ${this.detectionCount} 个对象\n`;
    result += `健康状态: ${this.isHealthy ? '✅ 正常' : '⚠️ 需关注'}\n`;
    if (this.detections) {
      result += `\n检测结果:\n${this.detections}\n`;
    }
    if (this.actionAdvice) {
      result += `\n💡 建议: ${this.actionAdvice}`;
    }
    this.analyzeResult = result;
  }

  build() {
    Column() {
      Row() {
        Text('<').fontSize(24).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMuted)
          .onClick(() => router.back())
        Text('土壤环境分析').fontSize(20).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
        Row() {
          Circle({ width: 8, height: 8 }).fill(ThemeColors.danger)
          Text('异常').fontSize(12).fontColor(ThemeColors.danger).fontWeight(FontWeight.Medium)
        }
        .backgroundColor('rgba(239, 68, 68, 0.1)')
        .padding({ left: 12, right: 12, top: 6, bottom: 6 })
        .borderRadius(16)
        .borderWidth(1)
        .borderColor('rgba(239, 68, 68, 0.2)')
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 16, bottom: 16 })
      .backgroundColor('rgba(255, 255, 255, 0.95)')
      .backdropBlur(20)
      .borderWidth({ bottom: 1 })
      .borderColor(ThemeColors.borderLight)
      .justifyContent(FlexAlign.SpaceBetween)
      .zIndex(30)

      Scroll() {
        Column({ space: 24 }) {
          Row({ space: 8 }) {
            Text('📷').fontSize(14)
            Text('拍照识别').fontSize(13).fontWeight(FontWeight.Bold)
            Blank()
            if (this.analyzeLoading) {
              LoadingProgress().width(16).height(16).color(ThemeColors.primary)
            } else {
              Text('点击选择图片').fontSize(10).fontColor('#9ca3af')
            }
          }
          .width('100%').padding(14).backgroundColor(ThemeColors.primaryLight).borderRadius(12)
          .onClick(() => { this.pickAndAnalyze(); })

          Row({ space: 8 }) {
            Text('⚡').fontSize(14)
            Text('快速分析').fontSize(13).fontWeight(FontWeight.Bold)
            Blank()
            if (this.analyzeLoading) {
              LoadingProgress().width(16).height(16).color(ThemeColors.primary)
            } else {
              Text('Mock数据').fontSize(10).fontColor('#9ca3af')
            }
          }
          .width('100%').padding(14).backgroundColor('#fef3c7').borderRadius(12)
          .onClick(() => { this.requestQuickAnalyze(); })

          if (this.selectedImageUri) {
            Image(this.selectedImageUri)
              .width('100%').height(200).objectFit(ImageFit.Cover).borderRadius(12)
          }

          if (this.annotatedImageUrl) {
            Column({ space: 8 }) {
              Text('标注结果').fontSize(11).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
              Image(this.annotatedImageUrl)
                .width('100%').height(200).objectFit(ImageFit.Cover).borderRadius(8)
            }
            .width('100%').padding(14).backgroundColor('#f0fdf4').borderRadius(12).borderWidth(1).borderColor('#bbf7d0')
          }

          if (this.hasAnalyzed) {
            Column({ space: 8 }) {
              Text('AI 分析结果').fontSize(11).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
              Text(this.analyzeResult).fontSize(11).fontColor('#374151').lineHeight(18)
            }
            .width('100%').padding(14).backgroundColor('#f0fdf4').borderRadius(12).borderWidth(1).borderColor('#bbf7d0')
          }

          Column({ space: 20 }) {
            Row() {
              Text('A区域数据').fontSize(20).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
              Text('异常').fontSize(14).fontColor(ThemeColors.danger).backgroundColor('rgba(239, 68, 68, 0.1)').padding({ left: 12, right: 12, top: 6, bottom: 6 }).borderRadius(8)
            }.width('100%').justifyContent(FlexAlign.SpaceBetween)

            Column({ space: 16 }) {
              this.ResultItem('土壤湿度状态', '严重缺水', ThemeColors.danger)
              this.ResultItem('当前土壤湿度', '12.7%', ThemeColors.danger)
              this.ResultItem('安全阈值', '20%~30%', ThemeColors.textMuted)
              this.ResultItem('土壤墒情等级', '干旱', ThemeColors.danger)
              this.ResultItem('预警状态', '异常', ThemeColors.danger)
              this.ResultItem('环境温度', '28℃', ThemeColors.textMain)
              this.ResultItem('环境湿度', '61%', ThemeColors.textMain)
              this.ResultItem('土壤温度', '23.5℃', ThemeColors.textMain)
              this.ResultItem('土壤氮含量', '85mg/kg', ThemeColors.warning)
              this.ResultItem('土壤磷含量', '22mg/kg', ThemeColors.warning)
              this.ResultItem('土壤钾含量', '110mg/kg', ThemeColors.textMain)
              this.ResultItem('光照强度', '662LUX', ThemeColors.textMain)
              this.ResultItem('CO₂浓度', '361PPM', ThemeColors.textMain)
              this.ResultItem('土壤电导率', '320uS/cm', ThemeColors.textMain)
              this.ResultItem('土壤盐分', '180uS/cm', ThemeColors.textMain)
              this.ResultItem('AI分析结论', '土壤水分远低于适宜区间', ThemeColors.danger)
              this.ResultItem('自动处理', '开启自动浇水阀', ThemeColors.primary)
            }
            .width('100%')
            .backgroundColor(ThemeColors.card)
            .borderRadius(16)
            .padding(24)
            .borderWidth(2)
            .borderColor('rgba(239, 68, 68, 0.3)')
          }
          .width('100%')
          .backgroundColor(ThemeColors.card)
          .borderRadius(20)
          .padding(24)
          .borderWidth(2)
          .borderColor('rgba(239, 68, 68, 0.4)')
          .shadow({ radius: 8, color: 'rgba(239, 68, 68, 0.1)', offsetX: 0, offsetY: 4 })

          Column({ space: 20 }) {
            Row() {
              Text('B区域数据').fontSize(20).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
              Text('安全').fontSize(14).fontColor(ThemeColors.accent).backgroundColor('rgba(16, 185, 129, 0.1)').padding({ left: 12, right: 12, top: 6, bottom: 6 }).borderRadius(8)
            }.width('100%').justifyContent(FlexAlign.SpaceBetween)

            Column({ space: 16 }) {
              this.ResultItem('土壤湿度状态', '正常适宜', ThemeColors.accent)
              this.ResultItem('当前土壤湿度', '25.0%', ThemeColors.accent)
              this.ResultItem('安全阈值', '20%~30%', ThemeColors.textMuted)
              this.ResultItem('土壤墒情等级', '适宜', ThemeColors.accent)
              this.ResultItem('预警状态', '安全', ThemeColors.accent)
              this.ResultItem('环境温度', '28℃', ThemeColors.textMain)
              this.ResultItem('环境湿度', '61%', ThemeColors.textMain)
              this.ResultItem('土壤温度', '23.6℃', ThemeColors.textMain)
              this.ResultItem('土壤氮含量', '90mg/kg', ThemeColors.accent)
              this.ResultItem('土壤磷含量', '25mg/kg', ThemeColors.accent)
              this.ResultItem('土壤钾含量', '120mg/kg', ThemeColors.accent)
              this.ResultItem('光照强度', '779LUX', ThemeColors.accent)
              this.ResultItem('CO₂浓度', '359PPM', ThemeColors.textMain)
              this.ResultItem('土壤电导率', '350uS/cm', ThemeColors.textMain)
              this.ResultItem('土壤盐分', '200uS/cm', ThemeColors.textMain)
              this.ResultItem('AI分析结论', '土壤湿度处于最优区间', ThemeColors.accent)
              this.ResultItem('自动处理', '无', ThemeColors.textMuted)
            }
            .width('100%')
            .backgroundColor(ThemeColors.card)
            .borderRadius(16)
            .padding(24)
            .borderWidth(2)
            .borderColor('rgba(16, 185, 129, 0.3)')
          }
          .width('100%')
          .backgroundColor(ThemeColors.card)
          .borderRadius(20)
          .padding(24)
          .borderWidth(2)
          .borderColor('rgba(16, 185, 129, 0.4)')
          .shadow({ radius: 8, color: 'rgba(16, 185, 129, 0.1)', offsetX: 0, offsetY: 4 })

          Column({ space: 20 }) {
            Text('核心对比数据').fontSize(20).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain).width('100%')

            Column({ space: 16 }) {
              this.CompareItem('土壤湿度', '12.7%', '25.0%')
              this.CompareItem('墒情等级', '干旱', '适宜')
              this.CompareItem('土壤氮含量', '85mg/kg', '90mg/kg')
              this.CompareItem('土壤磷含量', '22mg/kg', '25mg/kg')
              this.CompareItem('土壤钾含量', '110mg/kg', '120mg/kg')
              this.CompareItem('光照强度', '662LUX', '779LUX')
              this.CompareItem('预警状态', '异常', '安全')
            }
          }
          .width('100%')
          .backgroundColor(ThemeColors.card)
          .borderRadius(20)
          .padding(24)
          .borderWidth(2)
          .borderColor(ThemeColors.borderLight)
          .shadow({ radius: 8, color: 'rgba(0, 0, 0, 0.05)', offsetX: 0, offsetY: 4 })

          Column({ space: 20 }) {
            Row({ space: 10 }) {
              Text('💡').fontSize(20)
              Text('解决方案').fontSize(20).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
            }.width('100%')

            Column({ space: 16 }) {
              Row({ space: 14 }) {
                Row() { Text('1').fontSize(14).fontColor('#fff').fontWeight(FontWeight.Bold) }.width(28).height(28).backgroundColor(ThemeColors.danger).borderRadius(14).justifyContent(FlexAlign.Center)
                Column({ space: 6 }) {
                  Text('紧急补水措施').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
                  Text('立即开启自动浇水系统，将A区域土壤湿度提升至20%-30%的安全区间').fontSize(14).fontColor(ThemeColors.textMuted)
                }.alignItems(HorizontalAlign.Start).layoutWeight(1)
              }.width('100%')

              Row({ space: 14 }) {
                Row() { Text('2').fontSize(14).fontColor('#fff').fontWeight(FontWeight.Bold) }.width(28).height(28).backgroundColor(ThemeColors.warning).borderRadius(14).justifyContent(FlexAlign.Center)
                Column({ space: 6 }) {
                  Text('补充土壤养分').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
                  Text('A区域氮磷含量偏低，建议追施复合肥，改善土壤肥力状况').fontSize(14).fontColor(ThemeColors.textMuted)
                }.alignItems(HorizontalAlign.Start).layoutWeight(1)
              }.width('100%')

              Row({ space: 14 }) {
                Row() { Text('3').fontSize(14).fontColor('#fff').fontWeight(FontWeight.Bold) }.width(28).height(28).backgroundColor(ThemeColors.primary).borderRadius(14).justifyContent(FlexAlign.Center)
                Column({ space: 6 }) {
                  Text('优化灌溉策略').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
                  Text('建立定时定量灌溉机制，根据天气和作物生长阶段动态调整浇水量').fontSize(14).fontColor(ThemeColors.textMuted)
                }.alignItems(HorizontalAlign.Start).layoutWeight(1)
              }.width('100%')

              Row({ space: 14 }) {
                Row() { Text('4').fontSize(14).fontColor('#fff').fontWeight(FontWeight.Bold) }.width(28).height(28).backgroundColor(ThemeColors.accent).borderRadius(14).justifyContent(FlexAlign.Center)
                Column({ space: 6 }) {
                  Text('B区域持续监测').fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
                  Text('B区域土壤环境良好，保持现有管理，定期检测土壤指标变化').fontSize(14).fontColor(ThemeColors.textMuted)
                }.alignItems(HorizontalAlign.Start).layoutWeight(1)
              }.width('100%')
            }

            Row({ space: 16 }) {
              Button('一键执行方案')
                .layoutWeight(1)
                .backgroundColor(ThemeColors.primary)
                .fontColor('#fff')
                .height(52)
                .fontSize(16)
                .fontWeight(FontWeight.Bold)
                .borderRadius(12)
                .onClick(() => promptAction.showToast({ message: '方案已下发执行' }))
              Button('手动调整')
                .layoutWeight(1)
                .backgroundColor(ThemeColors.borderLight)
                .fontColor(ThemeColors.textMain)
                .height(52)
                .fontSize(16)
                .fontWeight(FontWeight.Bold)
                .borderRadius(12)
                .onClick(() => promptAction.showToast({ message: '进入手动调整模式' }))
            }
            .width('100%')
          }
          .width('100%')
          .backgroundColor(ThemeColors.card)
          .borderRadius(20)
          .padding(24)
          .borderWidth(2)
          .borderColor(ThemeColors.borderLight)
          .shadow({ radius: 8, color: 'rgba(0, 0, 0, 0.05)', offsetX: 0, offsetY: 4 })

          Row({ space: 16 }) {
            Button('导出报告')
              .layoutWeight(1)
              .backgroundColor(ThemeColors.primary)
              .fontColor('#fff')
              .height(52)
              .fontSize(16)
              .fontWeight(FontWeight.Bold)
              .borderRadius(12)
              .onClick(() => promptAction.showToast({ message: '报告已导出' }))
            Button('返回')
              .layoutWeight(1)
              .backgroundColor(ThemeColors.borderLight)
              .fontColor(ThemeColors.textMain)
              .height(52)
              .fontSize(16)
              .fontWeight(FontWeight.Bold)
              .borderRadius(12)
              .onClick(() => router.back())
          }
          .width('100%')
          .margin({ top: 8, bottom: 16 })
        }
        .padding(20)
      }
      .layoutWeight(1)
      .scrollBar(BarState.Off)
      .backgroundColor(ThemeColors.base)
    }
    .width('100%')
    .height('100%')
    .backgroundColor(ThemeColors.base)
  }

  @Builder ResultItem(label: string, value: string, color: string) {
    Row() {
      Text(label + '：').fontSize(16).fontColor(ThemeColors.textMuted)
      Text(value).fontSize(16).fontWeight(FontWeight.Medium).fontColor(color)
    }.width('100%').justifyContent(FlexAlign.Start).padding({ top: 8, bottom: 8 })
  }

  @Builder CompareItem(label: string, valueA: string, valueB: string) {
    Row() {
      Text(label).fontSize(16).fontColor(ThemeColors.textMain).width('28%')
      Row() {
        Text('A区域：').fontSize(14).fontColor(ThemeColors.textMuted)
        Text(valueA).fontSize(16).fontWeight(FontWeight.Bold).fontColor(this.getValueColor(valueA))
      }.layoutWeight(1)
      Row() {
        Text('B区域：').fontSize(14).fontColor(ThemeColors.textMuted)
        Text(valueB).fontSize(16).fontWeight(FontWeight.Bold).fontColor(this.getValueColor(valueB))
      }.layoutWeight(1)
    }.width('100%').padding({ top: 12, bottom: 12 }).borderWidth({ bottom: 1 }).borderColor(ThemeColors.borderLight)
  }

  getValueColor(value: string): string {
    const goodKeywords = ['适宜', '安全', '25.0%', '90mg', '25mg', '120mg', '779'];
    const badKeywords = ['干旱', '异常', '12.7%', '85mg', '22mg'];

    for (const keyword of goodKeywords) {
      if (value.includes(keyword)) return ThemeColors.accent;
    }
    for (const keyword of badKeywords) {
      if (value.includes(keyword)) return ThemeColors.danger;
    }
    return ThemeColors.textMain;
  }
}
