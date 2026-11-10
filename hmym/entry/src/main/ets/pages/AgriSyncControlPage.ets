import { promptAction } from '@kit.ArkUI';

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
  static readonly blue: string = '#3b82f6';
  static readonly cyan: string = '#06b6d4';
}

@Component
export struct AgriSyncControlPage {
  @State waterPower: number = 45;
  @State waterDuration: number = 15;
  @State waterThreshold: number = 30;
  @State pumpRunning: boolean = false;

  @State lightPower: number = 75;
  @State lightGroups: number = 4;
  @State curtainOpen: number = 30;
  @State isAutoLight: boolean = true;
  @State lightOn: boolean = false;
  @State lightOff: boolean = false;

  @State targetTemp: number = 25;
   @State tempOn: boolean = false;
  @State tempPriority: string = '暖气';
  @State tempThreshold: number = 2.0;

  @State targetHumidity: number = 60;
  @State humidityTolerance: number = 5;
  @State humidityMode: number = 0;
  @State humidifierOn: boolean = false;
  @State dehumidifierOn: boolean = false;

  @State ventMode: string = '自然通风';
  @State fanSpeed: number = 1000;
  @State ventDuration: number = 30;
  @State windowAngle: number = 45;
  @State ventOn: boolean = false;

  @State showPlantModal: boolean = false;
  @State showCropSelectModal: boolean = false;
  @State showWarningModal: boolean = false;
  @State showEnergyModal: boolean = false;
  @State timeTab: string = '本月';

  @State pumpBtnScale: number = 1;
  @State stepperMinusBtnScale: number = 1;
  @State stepperPlusBtnScale: number = 1;
  @State lightOnBtnScale: number = 1;
  @State lightOffBtnScale: number = 1;
  @State humidifierBtnScale: number = 1;
  @State dehumidifierBtnScale: number = 1;

  @State pumpRotation: number = 0;
  @State tempRotation: number = 0;
  @State ventRotation: number = 0;

  @State waterSaved: number = 0;
  @State carbonReduced: number = 0;
  @State energyScore: number = 0;
  @State animationStarted: boolean = false;

  aboutToAppear() {
    setTimeout(() => {
      this.animationStarted = true;
      this.animateValues();
      this.startRotationAnimations();
    }, 300);
  }

  private rotationTimer: number = -1;

  startRotationAnimations() {
    this.rotationTimer = setInterval(() => {
      if (this.pumpRunning) {
        this.pumpRotation = (this.pumpRotation + 30) % 360;
      }
      if (this.tempOn) {
        this.tempRotation = (this.tempRotation + 30) % 360;
      }
      if (this.ventOn) {
        this.ventRotation = (this.ventRotation + 18) % 360;
      }
    }, 250);
  }

  animateValues() {
    let waterTarget = 1240;
    let carbonTarget = 48.5;
    let scoreTarget = 92;
    let duration = 1500;
    let steps = 30;
    let interval = duration / steps;
    let stepWater = waterTarget / steps;
    let stepCarbon = carbonTarget / steps;
    let stepScore = scoreTarget / steps;
    let count = 0;

    let timer = setInterval(() => {
      count++;
      this.waterSaved = Math.round(stepWater * count);
      this.carbonReduced = Math.round(stepCarbon * count * 10) / 10;
      this.energyScore = Math.round(stepScore * count);
      if (count >= steps) {
        clearInterval(timer);
        this.waterSaved = waterTarget;
        this.carbonReduced = carbonTarget;
        this.energyScore = scoreTarget;
      }
    }, interval);
  }

  private showToast(message: string): void {
    try {
      promptAction.showToast({ message: message });
    } catch (error) {
      console.error('Toast show failed: ' + JSON.stringify(error));
    }
  }

  // 检查是否有任何设备在运行
  private isAnyDeviceRunning(): boolean {
    return this.pumpRunning || this.tempOn || this.ventOn || this.humidifierOn || this.dehumidifierOn;
  }

  build() {
    Stack({ alignContent: Alignment.Bottom }) {
      Column() {
        this.Header()

        Scroll() {
          Column({ space: 24 }) {
            this.WaterSystemSection()
            this.LightSystemSection()
            this.TempSystemSection()
            this.HumiditySystemSection()
            this.VentSystemSection()
            this.ProfileSection()
            this.EnergySection()

            Row().height(90)
          }
          .padding(16)
        }
        .layoutWeight(1)
        .scrollBar(BarState.Off)
        .backgroundColor(ThemeColors.base)
        .align(Alignment.Top)
      }
      .width('100%')
      .height('100%')

      if (this.showPlantModal) {
        this.AddPlantModal()
      }

      if (this.showCropSelectModal) {
        this.CropSelectModal()
      }

      if (this.showWarningModal) {
        this.WarningDetailModal()
      }

      if (this.showEnergyModal) {
        this.EnergyDetailModal()
      }
    }
    .width('100%')
    .height('100%')
    .backgroundColor(ThemeColors.base)
  }

  @Builder Header() {
    Row() {
      Text('<').fontSize(22).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMuted)
        .onClick(() => this.showToast('返回'))
      Text('智能控制').fontSize(18).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)

      // 在线状态指示器
      Row({ space: 6 }) {
        Circle({ width: 8, height: 8 }).fill(this.isAnyDeviceRunning() ? ThemeColors.accent : ThemeColors.textMuted)
          .animation({ duration: 300, curve: Curve.EaseInOut })
        Text('在线').fontSize(12).fontColor(this.isAnyDeviceRunning() ? ThemeColors.accent : ThemeColors.textMuted)
          .animation({ duration: 300, curve: Curve.EaseInOut })
      }
    }
    .width('100%').padding(16).backgroundColor('rgba(255, 255, 255, 0.95)').backdropBlur(20)
    .borderWidth({ bottom: 1 }).borderColor(ThemeColors.borderLight)
    .justifyContent(FlexAlign.SpaceBetween).zIndex(30)
  }

  @Builder SectionTitle(icon: string, title: string) {
    Row({ space: 8 }) {
      Text(icon).fontSize(16)
      Text(title).fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.textMain)
    }.width('100%').margin({ bottom: 12 })
  }

  @Builder StepperControl(icon: string, title: string, subtitle: string, getVal: () => number, unit: string, step: number, onAdjust: (d: number) => void) {
    Row() {
      Row({ space: 12 }) {
        Row() { Text(icon).fontSize(14) }.width(32).height(32).backgroundColor(ThemeColors.base).borderRadius(16).justifyContent(FlexAlign.Center)
        Column({ space: 2 }) {
          Text(title).fontSize(14).fontWeight(FontWeight.Medium).fontColor(ThemeColors.textMain)
          Text(subtitle).fontSize(10).fontColor(ThemeColors.textMuted)
        }.alignItems(HorizontalAlign.Start)
      }
      Row({ space: 8 }) {
        Button('-').width(28).height(28).type(ButtonType.Circle).backgroundColor(ThemeColors.borderLight).fontColor(ThemeColors.textMuted)
          .scale({ x: this.stepperMinusBtnScale, y: this.stepperMinusBtnScale })
          .animation({ duration: 100 })
          .onClick(() => {
            animateTo({ duration: 100 }, () => { this.stepperMinusBtnScale = 0.95; });
            setTimeout(() => { animateTo({ duration: 100 }, () => { this.stepperMinusBtnScale = 1; }); }, 100);
            onAdjust(-step);
          })
        Text(`${getVal()}`).fontSize(14).fontWeight(FontWeight.Bold).width(30).textAlign(TextAlign.Center)
        Button('+').width(28).height(28).type(ButtonType.Circle).backgroundColor(ThemeColors.borderLight).fontColor(ThemeColors.textMuted)
          .scale({ x: this.stepperPlusBtnScale, y: this.stepperPlusBtnScale })
          .animation({ duration: 100 })
          .onClick(() => {
            animateTo({ duration: 100 }, () => { this.stepperPlusBtnScale = 0.95; });
            setTimeout(() => { animateTo({ duration: 100 }, () => { this.stepperPlusBtnScale = 1; }); }, 100);
            onAdjust(step);
          })
        Text(unit).fontSize(12).fontColor(ThemeColors.textMuted)
      }
    }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding({ top: 16 }).borderWidth({ top: 1 }).borderColor(ThemeColors.borderLight)
  }

  @Builder ScaleButton(text: string, isActive: boolean, scaleState: number, onClick: () => void) {
    Button(text).width('100%').height(44)
      .backgroundColor(isActive ? ThemeColors.primary : ThemeColors.borderLight)
      .fontColor(isActive ? '#fff' : ThemeColors.textMain)
      .fontWeight(FontWeight.Bold)
      .scale({ x: scaleState, y: scaleState })
      .shadow(isActive ? {
        radius: 8,
        color: 'rgba(11, 89, 52, 0.4)',
        offsetY: 4
      } : { radius: 0 })
      .animation({ duration: 200, curve: Curve.EaseInOut })
      .onClick(() => {
        animateTo({ duration: 100 }, () => {
          this.pumpBtnScale = 0.95;
          this.lightOnBtnScale = 0.95;
          this.lightOffBtnScale = 0.95;
          this.humidifierBtnScale = 0.95;
          this.dehumidifierBtnScale = 0.95;
        });
        setTimeout(() => {
          animateTo({ duration: 100 }, () => {
            this.pumpBtnScale = 1;
            this.lightOnBtnScale = 1;
            this.lightOffBtnScale = 1;
            this.humidifierBtnScale = 1;
            this.dehumidifierBtnScale = 1;
          });
        }, 100);
        onClick();
      })
  }

  @Builder WaterSystemSection() {
    Column() {
      this.SectionTitle('💧', '灌溉系统')
      Column() {
        Row() {
          Row({ space: 12 }) {
            Row() { Text('🌊').fontSize(16) }.width(40).height(40).backgroundColor('#eff6ff').borderRadius(20).justifyContent(FlexAlign.Center)
            Column({ space: 2 }) { Text('水泵功率').fontSize(14).fontWeight(FontWeight.Medium); Text('控制区域水压与流量').fontSize(10).fontColor(ThemeColors.textMuted) }.alignItems(HorizontalAlign.Start)
          }
          Row() { Text(`${this.waterPower}`).fontSize(20).fontWeight(FontWeight.Bold).fontColor(ThemeColors.blue); Text('%').fontSize(12).fontColor(ThemeColors.textMuted).margin({ left: 2, top: 4 }) }
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 12 })

        Slider({
          value: this.waterPower,
          min: 0,
          max: 100,
          step: 1,
          style: SliderStyle.OutSet
        })
          .selectedColor(ThemeColors.blue)
          .onChange((value: number, mode: SliderChangeMode) => {
            this.waterPower = Math.round(value);
            if (mode === SliderChangeMode.End || mode === SliderChangeMode.Moving) {
              this.showToast(`水泵功率已保存: ${Math.round(value)}%`);
            }
          })

        this.StepperControl('⏱️', '灌溉时长设置', '', () => this.waterDuration, '分钟', 5, (d) => this.waterDuration = Math.max(1, Math.min(60, this.waterDuration + d)))
        this.StepperControl('🏜️', '土壤湿度阈值', '', () => this.waterThreshold, '%', 1, (d) => this.waterThreshold = Math.max(0, Math.min(100, this.waterThreshold + d)))

        Row() {
          Row({ space: 12 }) {
            // 状态图标 - 运行时显示绿色旋转动画效果
            Row() {
              Text(this.pumpRunning ? '💧' : '⏸️')
                .fontSize(16)
                .rotate({ angle: this.pumpRunning ? this.pumpRotation : 0 })
            }
            .width(36)
            .height(36)
            .backgroundColor(this.pumpRunning ? '#f0fdf4' : '#f3f4f6')
            .borderRadius(18)
            .justifyContent(FlexAlign.Center)
            .shadow(this.pumpRunning ? {
              radius: 6,
              color: 'rgba(16, 185, 129, 0.3)',
              offsetY: 2
            } : { radius: 0 })

            Column({ space: 2 }) {
              Text('水泵运行状态').fontSize(14).fontWeight(FontWeight.Medium)
              Text(this.pumpRunning ? '设备正常工作' : '设备已暂停')
                .fontSize(10)
                .fontColor(ThemeColors.textMuted)
            }
            .alignItems(HorizontalAlign.Start)
          }

          // 状态指示器
          Row({ space: 8 }) {
            Stack({ alignContent: Alignment.Center }) {
              Circle({ width: 10, height: 10 })
                .fill(this.pumpRunning ? ThemeColors.accent : ThemeColors.textMuted)
                .animation({ duration: 300, curve: Curve.EaseInOut })

              Circle({ width: 10, height: 10 })
                .fill('rgba(16, 185, 129, 0.4)')
                .scale({ x: 1.5, y: 1.5 })
                .visibility(this.pumpRunning ? Visibility.Visible : Visibility.Hidden)
                .animation({ duration: 1000, curve: Curve.EaseOut, iterations: -1 })
            }
            .alignContent(Alignment.Center)
            .width(16)
            .height(16)

            Text(this.pumpRunning ? '运行中' : '已停止')
              .fontSize(13)
              .fontWeight(this.pumpRunning ? FontWeight.Bold : FontWeight.Medium)
              .fontColor(this.pumpRunning ? ThemeColors.accent : ThemeColors.textMuted)
              .animation({ duration: 300, curve: Curve.EaseInOut })
          }
        }
        .width('100%')
        .justifyContent(FlexAlign.SpaceBetween)
        .padding({ top: 16, bottom: 12 })
        .borderWidth({ top: 1 })
        .borderColor(ThemeColors.borderLight)

        Row() {
          Row({ space: 12 }) {
            Text('控制开关').fontSize(14).fontWeight(FontWeight.Medium)
          }
          Toggle({ type: ToggleType.Switch, isOn: this.pumpRunning })
            .selectedColor(ThemeColors.primary)
            .onChange((isOn: boolean) => {
              this.pumpRunning = isOn;
              this.showToast(isOn ? '水泵已开启' : '水泵已停止');
            })
        }
        .width('100%')
        .justifyContent(FlexAlign.SpaceBetween)
        .padding({ top: 12, bottom: 12 })

        this.ScaleButton(this.pumpRunning ? '关闭水泵' : '开启水泵', this.pumpRunning, this.pumpBtnScale, () => {
          this.pumpRunning = !this.pumpRunning;
          this.showToast(this.pumpRunning ? '水泵已开启' : '水泵已停止');
        })
      }.backgroundColor(ThemeColors.card).borderRadius(16).padding(16).borderWidth(1).borderColor(ThemeColors.borderLight).shadow({ radius: 5, color: 'rgba(0,0,0,0.02)' })
    }
  }

  @Builder LightSystemSection() {
    Column() {
      this.SectionTitle('☀️', '光照系统')
      Column() {
        Row() {
          Row({ space: 12 }) {
            Row() { Text('💡').fontSize(16) }.width(40).height(40).backgroundColor('#fef3c7').borderRadius(20).justifyContent(FlexAlign.Center)
            Column({ space: 2 }) { Text('单组灯功率').fontSize(14).fontWeight(FontWeight.Medium); Text('调节补光灯亮度').fontSize(10).fontColor(ThemeColors.textMuted) }.alignItems(HorizontalAlign.Start)
          }
          Row() { Text(`${this.lightPower}`).fontSize(20).fontWeight(FontWeight.Bold).fontColor(ThemeColors.warning); Text('%').fontSize(12).fontColor(ThemeColors.textMuted).margin({ left: 2, top: 4 }) }
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 12 })

        Slider({
          value: this.lightPower,
          min: 0,
          max: 100,
          step: 1,
          style: SliderStyle.OutSet
        })
          .selectedColor('#8b5cf6')
          .enabled(!this.isAutoLight)
          .opacity(this.isAutoLight ? 0.5 : 1)
          .onChange((value: number, mode: SliderChangeMode) => {
            this.lightPower = Math.round(value);
            if (!this.isAutoLight && (mode === SliderChangeMode.End || mode === SliderChangeMode.Moving)) {
              this.showToast(`单组灯功率已保存: ${Math.round(value)}%`);
            }
          })

        this.StepperControl('🔢', '开灯组数', '', () => this.lightGroups, '', 1, (d) => this.lightGroups = Math.max(1, Math.min(20, this.lightGroups + d)))

        Column() {
          Row() {
            Row({ space: 12 }) {
              Row() { Text('🪟').fontSize(14) }.width(32).height(32).backgroundColor('#fff7ed').borderRadius(16).justifyContent(FlexAlign.Center)
              Column({ space: 2 }) { Text('遮光帘开合度').fontSize(14).fontWeight(FontWeight.Medium); Text('调节光照透光度').fontSize(10).fontColor(ThemeColors.textMuted) }.alignItems(HorizontalAlign.Start)
            }
            Text(`${this.curtainOpen}%`).fontSize(18).fontWeight(FontWeight.Bold).fontColor(ThemeColors.warning)
          }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 8 })
          Slider({
            value: this.curtainOpen,
            min: 0,
            max: 100,
            step: 1,
            style: SliderStyle.OutSet
          }).selectedColor(ThemeColors.warning).onChange((value: number) => this.curtainOpen = Math.round(value))
        }.width('100%').padding({ top: 16 }).borderWidth({ top: 1 }).borderColor(ThemeColors.borderLight)

        Row() {
          Row({ space: 12 }) {
            Row() { Text('🤖').fontSize(14) }.width(32).height(32).backgroundColor('#eff6ff').borderRadius(16).justifyContent(FlexAlign.Center)
            Text('光强自动补偿').fontSize(14).fontWeight(FontWeight.Medium)
          }
          Toggle({ type: ToggleType.Switch, isOn: this.isAutoLight }).selectedColor(ThemeColors.primary).onChange((isOn: boolean) => {
            this.isAutoLight = isOn;
            this.showToast(isOn ? '光强自动补偿已启用' : '光强自动补偿已禁用');
          })
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding({ top: 16, bottom: 12 }).borderWidth({ top: 1 }).borderColor(ThemeColors.borderLight)

        Row({ space: 12 }) {
          Button('开启光照')
            .layoutWeight(1)
            .height(44)
            .backgroundColor(this.lightOn ? ThemeColors.primary : ThemeColors.borderLight)
            .fontColor(this.lightOn ? '#fff' : ThemeColors.textMain)
            .fontWeight(FontWeight.Bold)
            .scale({ x: this.lightOnBtnScale, y: this.lightOnBtnScale })
            .shadow(this.lightOn ? {
              radius: 8,
              color: 'rgba(11, 89, 52, 0.4)',
              offsetY: 4
            } : { radius: 0 })
            .animation({ duration: 200, curve: Curve.EaseInOut })
            .onClick(() => {
              animateTo({ duration: 100 }, () => { this.lightOnBtnScale = 0.95; });
              setTimeout(() => {
                animateTo({ duration: 100 }, () => { this.lightOnBtnScale = 1; });
              }, 100);
              this.lightOn = true;
              this.lightOff = false;
              this.showToast('光照已开启');
            })
          Button('关闭光照')
            .layoutWeight(1)
            .height(44)
            .backgroundColor(this.lightOff ? ThemeColors.danger : ThemeColors.borderLight)
            .fontColor(this.lightOff ? '#fff' : ThemeColors.textMain)
            .fontWeight(FontWeight.Bold)
            .scale({ x: this.lightOffBtnScale, y: this.lightOffBtnScale })
            .shadow(this.lightOff ? {
              radius: 8,
              color: 'rgba(239, 68, 68, 0.4)',
              offsetY: 4
            } : { radius: 0 })
            .animation({ duration: 200, curve: Curve.EaseInOut })
            .onClick(() => {
              animateTo({ duration: 100 }, () => { this.lightOffBtnScale = 0.95; });
              setTimeout(() => {
                animateTo({ duration: 100 }, () => { this.lightOffBtnScale = 1; });
              }, 100);
              this.lightOff = true;
              this.lightOn = false;
              this.showToast('光照已关闭');
            })
        }.width('100%')
      }.backgroundColor(ThemeColors.card).borderRadius(16).padding(16).borderWidth(1).borderColor(ThemeColors.borderLight)
    }
  }

  @Builder TempSystemSection() {
    Column() {
      this.SectionTitle('🌡️', '温度调节')
      Column() {
        Row() {
          Row({ space: 12 }) {
            // 状态图标
            Row() {
              Text(this.tempOn ? '🌡️' : '⏸️')
                .fontSize(16)
                .rotate({ angle: this.tempOn ? this.tempRotation : 0 })
            }
            .width(36)
            .height(36)
            .backgroundColor(this.tempOn ? '#f0fdf4' : '#f3f4f6')
            .borderRadius(18)
            .justifyContent(FlexAlign.Center)
            .shadow(this.tempOn ? {
              radius: 6,
              color: 'rgba(16, 185, 129, 0.3)',
              offsetY: 2
            } : { radius: 0 })

            Column({ space: 2 }) {
              Text('温度控制系统').fontSize(14).fontWeight(FontWeight.Medium)
              Text(this.tempOn ? '设备正常工作' : '设备已暂停')
                .fontSize(10)
                .fontColor(ThemeColors.textMuted)
            }
            .alignItems(HorizontalAlign.Start)
          }

          // 状态指示器
          Row({ space: 8 }) {
            Stack({ alignContent: Alignment.Center }) {
              Circle({ width: 10, height: 10 })
                .fill(this.tempOn ? ThemeColors.accent : ThemeColors.textMuted)
                .animation({ duration: 300, curve: Curve.EaseInOut })

              Circle({ width: 10, height: 10 })
                .fill('rgba(16, 185, 129, 0.4)')
                .scale({ x: 1.5, y: 1.5 })
                .visibility(this.tempOn ? Visibility.Visible : Visibility.Hidden)
                .animation({ duration: 1000, curve: Curve.EaseOut, iterations: -1 })
            }
            .alignContent(Alignment.Center)
            .width(16)
            .height(16)

            Text(this.tempOn ? '运行中' : '已停止')
              .fontSize(13)
              .fontWeight(this.tempOn ? FontWeight.Bold : FontWeight.Medium)
              .fontColor(this.tempOn ? ThemeColors.accent : ThemeColors.textMuted)
              .animation({ duration: 300, curve: Curve.EaseInOut })
          }
        }
        .width('100%')
        .justifyContent(FlexAlign.SpaceBetween)
        .padding({ bottom: 12 })
        .borderWidth({ bottom: 1 })
        .borderColor(ThemeColors.borderLight)

        Row() {
          Row({ space: 12 }) {
            Text('控制开关').fontSize(14).fontWeight(FontWeight.Medium)
          }
          Toggle({ type: ToggleType.Switch, isOn: this.tempOn })
            .selectedColor(ThemeColors.primary)
            .onChange((isOn: boolean) => {
              this.tempOn = isOn;
              this.showToast(isOn ? '温度控制已开启' : '温度控制已停止');
            })
        }
        .width('100%')
        .justifyContent(FlexAlign.SpaceBetween)
        .padding({ top: 12, bottom: 12 })

        Row() {
          Row({ space: 12 }) {
            Row() { Text('🔥').fontSize(16) }.width(40).height(40).backgroundColor('#ffedd5').borderRadius(20).justifyContent(FlexAlign.Center)
            Column({ space: 2 }) { Text('目标温度').fontSize(14).fontWeight(FontWeight.Medium); Text('设定理想环境温度').fontSize(10).fontColor(ThemeColors.textMuted) }.alignItems(HorizontalAlign.Start)
          }
          Row() { Text(`${this.targetTemp.toFixed(1)}`).fontSize(20).fontWeight(FontWeight.Bold).fontColor('#ea580c'); Text('°C').fontSize(12).fontColor(ThemeColors.textMuted).margin({ left: 2, top: 4 }) }
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 12 })
        Slider({
          value: this.targetTemp,
          min: 10,
          max: 40,
          step: 0.5,
          style: SliderStyle.OutSet
        }).selectedColor('#ea580c').onChange((value: number) => this.targetTemp = value)

        Column() {
          Text('设备优先级').fontSize(12).fontColor(ThemeColors.textMuted).margin({ bottom: 8 }).width('100%')
          Row({ space: 8 }) {
            this.PriorityBtn('暖气')
            this.PriorityBtn('湿帘')
          }.width('100%')
        }.padding({ top: 16 }).borderWidth({ top: 1 }).borderColor(ThemeColors.borderLight)

        this.StepperControl('🛡️', '温差保护阈值', '', () => this.tempThreshold, '°C', 0.5, (d) => this.tempThreshold = Math.max(1, Math.min(10, parseFloat((this.tempThreshold + d).toFixed(1)))))
      }.backgroundColor(ThemeColors.card).borderRadius(16).padding(16).borderWidth(1).borderColor(ThemeColors.borderLight)
    }
  }

  @Builder PriorityBtn(title: string) {
    Button(`优先${title}`)
      .layoutWeight(1).height(36).fontSize(12).fontWeight(FontWeight.Bold)
      .backgroundColor(this.tempPriority === title ? 'rgba(11, 89, 52, 0.05)' : 'transparent')
      .fontColor(this.tempPriority === title ? ThemeColors.primary : ThemeColors.textMain)
      .borderWidth(2).borderColor(this.tempPriority === title ? ThemeColors.primary : ThemeColors.borderLight)
      .onClick(() => {
        this.tempPriority = title;
        this.showToast(`已选择优先${title}`);
      })
  }

  @Builder HumiditySystemSection() {
    Column() {
      this.SectionTitle('💦', '湿度调节')
      Column() {
        Row() {
          Row({ space: 12 }) {
            Row() { Text('💧').fontSize(16) }.width(40).height(40).backgroundColor('#cffafe').borderRadius(20).justifyContent(FlexAlign.Center)
            Column({ space: 2 }) { Text('湿度目标值').fontSize(14).fontWeight(FontWeight.Medium); Text('设定理想环境湿度').fontSize(10).fontColor(ThemeColors.textMuted) }.alignItems(HorizontalAlign.Start)
          }
          Row() { Text(`${this.targetHumidity}`).fontSize(20).fontWeight(FontWeight.Bold).fontColor(ThemeColors.cyan); Text('%').fontSize(12).fontColor(ThemeColors.textMuted).margin({ left: 2, top: 4 }) }
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 12 })
        Slider({
          value: this.targetHumidity,
          min: 30,
          max: 90,
          step: 1,
          style: SliderStyle.OutSet
        }).selectedColor(ThemeColors.cyan).onChange((value: number) => this.targetHumidity = Math.round(value))

        this.StepperControl('⚖️', '湿度容忍度', '', () => this.humidityTolerance, '%', 1, (d) => this.humidityTolerance = Math.max(1, Math.min(20, this.humidityTolerance + d)))

        Column() {
          Text('湿度调节模式').fontSize(12).fontColor(ThemeColors.textMuted).margin({ bottom: 8 }).width('100%')
          Select([{ value: '智能平衡模式' }, { value: '精准加湿模式' }, { value: '高效除湿模式' }])
            .selected(this.humidityMode)
            .value(this.humidityMode === 0 ? '智能平衡模式' : this.humidityMode === 1 ? '精准加湿模式' : '高效除湿模式')
            .font({ size: 14 }).fontColor(ThemeColors.textMain)
            .width('100%').height(40).backgroundColor(ThemeColors.base).borderRadius(8)
            .onSelect((index: number) => {
              this.humidityMode = index;
              this.showToast(index === 0 ? '智能平衡模式' : index === 1 ? '精准加湿模式' : '高效除湿模式');
            })
        }.padding({ top: 16 }).borderWidth({ top: 1 }).borderColor(ThemeColors.borderLight)

        Row({ space: 12 }) {
          Button('开启加湿')
            .layoutWeight(1)
            .height(44)
            .backgroundColor(this.humidifierOn ? ThemeColors.primary : ThemeColors.borderLight)
            .fontColor(this.humidifierOn ? '#fff' : ThemeColors.textMain)
            .fontWeight(FontWeight.Bold)
            .scale({ x: this.humidifierBtnScale, y: this.humidifierBtnScale })
            .shadow(this.humidifierOn ? {
              radius: 8,
              color: 'rgba(11, 89, 52, 0.4)',
              offsetY: 4
            } : { radius: 0 })
            .animation({ duration: 200, curve: Curve.EaseInOut })
            .onClick(() => {
              animateTo({ duration: 100 }, () => { this.humidifierBtnScale = 0.95; });
              setTimeout(() => {
                animateTo({ duration: 100 }, () => { this.humidifierBtnScale = 1; });
              }, 100);
              this.humidifierOn = true;
              this.dehumidifierOn = false;
              this.showToast('加湿功能已开启');
            })
          Button('开启除湿')
            .layoutWeight(1)
            .height(44)
            .backgroundColor(this.dehumidifierOn ? ThemeColors.danger : ThemeColors.borderLight)
            .fontColor(this.dehumidifierOn ? '#fff' : ThemeColors.textMain)
            .fontWeight(FontWeight.Bold)
            .scale({ x: this.dehumidifierBtnScale, y: this.dehumidifierBtnScale })
            .shadow(this.dehumidifierOn ? {
              radius: 8,
              color: 'rgba(239, 68, 68, 0.4)',
              offsetY: 4
            } : { radius: 0 })
            .animation({ duration: 200, curve: Curve.EaseInOut })
            .onClick(() => {
              animateTo({ duration: 100 }, () => { this.dehumidifierBtnScale = 0.95; });
              setTimeout(() => {
                animateTo({ duration: 100 }, () => { this.dehumidifierBtnScale = 1; });
              }, 100);
              this.dehumidifierOn = true;
              this.humidifierOn = false;
              this.showToast('除湿功能已开启');
            })
        }.width('100%').margin({ top: 16 })
      }.backgroundColor(ThemeColors.card).borderRadius(16).padding(16).borderWidth(1).borderColor(ThemeColors.borderLight)
    }
  }

  @Builder VentSystemSection() {
    Column() {
      this.SectionTitle('🌀', '通风系统')
      Column() {
        Column() {
          Text('通风模式').fontSize(12).fontColor(ThemeColors.textMuted).margin({ bottom: 8 }).width('100%')
          Row({ space: 8 }) {
            this.VentModeBtn('自然通风')
            this.VentModeBtn('强制通风')
            this.VentModeBtn('混合通风')
          }.width('100%')
        }.padding({ bottom: 16 }).borderWidth({ bottom: 1 }).borderColor(ThemeColors.borderLight)

        Row() {
          Row({ space: 12 }) {
            // 状态图标
            Row() {
              Text(this.ventOn ? '🌀' : '⏸️')
                .fontSize(16)
                .rotate({ angle: this.ventOn ? this.ventRotation : 0 })
            }
            .width(36)
            .height(36)
            .backgroundColor(this.ventOn ? '#f0fdf4' : '#f3f4f6')
            .borderRadius(18)
            .justifyContent(FlexAlign.Center)
            .shadow(this.ventOn ? {
              radius: 6,
              color: 'rgba(16, 185, 129, 0.3)',
              offsetY: 2
            } : { radius: 0 })

            Column({ space: 2 }) {
              Text('通风系统').fontSize(14).fontWeight(FontWeight.Medium)
              Text(this.ventOn ? '设备正常工作' : '设备已暂停')
                .fontSize(10)
                .fontColor(ThemeColors.textMuted)
            }
            .alignItems(HorizontalAlign.Start)
          }

          // 状态指示器
          Row({ space: 8 }) {
            Stack({ alignContent: Alignment.Center }) {
              Circle({ width: 10, height: 10 })
                .fill(this.ventOn ? ThemeColors.accent : ThemeColors.textMuted)
                .animation({ duration: 300, curve: Curve.EaseInOut })

              Circle({ width: 10, height: 10 })
                .fill('rgba(16, 185, 129, 0.4)')
                .scale({ x: 1.5, y: 1.5 })
                .visibility(this.ventOn ? Visibility.Visible : Visibility.Hidden)
                .animation({ duration: 1000, curve: Curve.EaseOut, iterations: -1 })
            }
            .alignContent(Alignment.Center)
            .width(16)
            .height(16)

            Text(this.ventOn ? '运行中' : '已停止')
              .fontSize(13)
              .fontWeight(this.ventOn ? FontWeight.Bold : FontWeight.Medium)
              .fontColor(this.ventOn ? ThemeColors.accent : ThemeColors.textMuted)
              .animation({ duration: 300, curve: Curve.EaseInOut })
          }
        }
        .width('100%')
        .justifyContent(FlexAlign.SpaceBetween)
        .padding({ top: 16, bottom: 12 })
        .borderWidth({ top: 1 })
        .borderColor(ThemeColors.borderLight)

        Row() {
          Row({ space: 12 }) {
            Text('控制开关').fontSize(14).fontWeight(FontWeight.Medium)
          }
          Toggle({ type: ToggleType.Switch, isOn: this.ventOn })
            .selectedColor(ThemeColors.primary)
            .onChange((isOn: boolean) => {
              this.ventOn = isOn;
              this.showToast(isOn ? '通风已开启' : '通风已停止');
            })
        }
        .width('100%')
        .justifyContent(FlexAlign.SpaceBetween)
        .padding({ top: 12, bottom: 12 })

        Column() {
          Row() {
            Row({ space: 12 }) {
              Row() { Text('💨').fontSize(14) }.width(32).height(32).backgroundColor(ThemeColors.base).borderRadius(16).justifyContent(FlexAlign.Center)
              Column({ space: 2 }) { Text('风扇转速').fontSize(14).fontWeight(FontWeight.Medium); Text('调节通风扇速度').fontSize(10).fontColor(ThemeColors.textMuted) }.alignItems(HorizontalAlign.Start)
            }
            Text(`${this.fanSpeed} RPM`).fontSize(14).fontWeight(FontWeight.Bold)
          }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 8, top: 16 })
          Slider({
            value: this.fanSpeed,
            min: 500,
            max: 3000,
            step: 100,
            style: SliderStyle.OutSet
          }).selectedColor('#64748b').onChange((value: number) => this.fanSpeed = Math.round(value))
        }.width('100%')

        this.StepperControl('⏱️', '通风时长设置', '', () => this.ventDuration, '分钟', 5, (d) => this.ventDuration = Math.max(10, Math.min(120, this.ventDuration + d)))

        Column() {
          Row() {
            Row({ space: 12 }) {
              Row() { Text('📐').fontSize(14) }.width(32).height(32).backgroundColor('#fffbeb').borderRadius(16).justifyContent(FlexAlign.Center)
              Text('窗户开合角度').fontSize(14).fontWeight(FontWeight.Medium)
            }
            Text(`${this.windowAngle}°`).fontSize(16).fontWeight(FontWeight.Bold).fontColor(ThemeColors.warning)
          }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 8 })
          Slider({
            value: this.windowAngle,
            min: 0,
            max: 90,
            step: 1,
            style: SliderStyle.OutSet
          }).selectedColor(ThemeColors.warning).onChange((value: number) => this.windowAngle = Math.round(value))
        }.width('100%').padding({ top: 16 }).borderWidth({ top: 1 }).borderColor(ThemeColors.borderLight)

      }.backgroundColor(ThemeColors.card).borderRadius(16).padding(16).borderWidth(1).borderColor(ThemeColors.borderLight)
    }
  }

  @Builder VentModeBtn(title: string) {
    Button(title).layoutWeight(1).height(32).fontSize(11).fontWeight(FontWeight.Bold)
      .backgroundColor(this.ventMode === title ? 'rgba(11, 89, 52, 0.05)' : 'transparent')
      .fontColor(this.ventMode === title ? ThemeColors.primary : ThemeColors.textMain)
      .borderWidth(2).borderColor(this.ventMode === title ? ThemeColors.primary : ThemeColors.borderLight)
      .onClick(() => {
        this.ventMode = title;
        this.showToast(`已选择${title}`);
      })
  }

  @Builder ProfileSection() {
    Column() {
      Row() {
        this.SectionTitle('📋', '预警阈值与档案')
        Button('+').width(28).height(28).type(ButtonType.Circle).backgroundColor(ThemeColors.primaryLight).fontColor(ThemeColors.primary)
          .onClick(() => { this.showPlantModal = true })
          .offset({ y: -6 })
      }.width('100%').justifyContent(FlexAlign.SpaceBetween)

      Column() {
        Row() {
          Row({ space: 8 }) {
            Text('🥕').fontSize(20)
            Column() {
              Row({ space: 4 }) {
                Text('白萝卜').fontSize(14).fontWeight(FontWeight.Bold)
                  .onClick(() => this.showCropSelectModal = true)
                Text('当前应用').fontSize(10).fontColor(ThemeColors.primary).backgroundColor(ThemeColors.primaryLight).padding({ left: 4, right: 4, top: 2, bottom: 2 }).borderRadius(4)
              }
            }.alignItems(HorizontalAlign.Start)
          }
          Text('编辑 >').fontSize(10).fontColor(ThemeColors.textMuted)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 12 })

        Row() {
          Text('含水量监控').fontSize(11).fontColor(ThemeColors.textMuted)
          Text('当前：28% / 适宜：30%-40%').fontSize(11).fontColor(ThemeColors.textMain)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 8 })

        Row() {
          Row().layoutWeight(3).height(8).backgroundColor('#fee2e2').borderRadius({ topLeft: 4, bottomLeft: 4 })
          Row().layoutWeight(1).height(8).backgroundColor('#fef3c7')
          Row().layoutWeight(1).height(8).backgroundColor('rgba(11, 89, 52, 0.2)')
          Row().layoutWeight(2).height(8).backgroundColor('#fef3c7')
          Row().layoutWeight(3).height(8).backgroundColor('#fee2e2').borderRadius({ topRight: 4, bottomRight: 4 })
        }.width('100%')

        Text('⚠️ 水分偏低 2%，已触发预警规则，建议开启水泵')
          .fontSize(10).fontColor(ThemeColors.danger).backgroundColor('#fef2f2')
          .width('100%').padding(6).borderRadius(4).margin({ top: 8 })
          .onClick(() => this.showWarningModal = true)
      }.backgroundColor(ThemeColors.card).borderRadius(12).padding(16).borderWidth({ left: 4, top: 1, right: 1, bottom: 1 }).borderColor({ left: ThemeColors.primary, top: ThemeColors.borderLight, right: ThemeColors.borderLight, bottom: ThemeColors.borderLight }).shadow({ radius: 5, color: 'rgba(0,0,0,0.02)' }).margin({ bottom: 12 })

      this.SimplePlantCard('🥬', '奶油生菜', '💧 60-70%', '☀️弱光')
      this.SimplePlantCard('🍅', '樱桃番茄', '💧 45-55%', '☀️强光')

    }
  }

  @Builder SimplePlantCard(emoji: string, name: string, water: string, light: string) {
    Row() {
      Row({ space: 12 }) {
        Row() { Text(emoji).fontSize(16) }.width(32).height(32).backgroundColor('#f0fdf4').borderRadius(8).justifyContent(FlexAlign.Center)
        Column({ space: 4 }) {
          Text(name).fontSize(14).fontWeight(FontWeight.Medium)
          Row({ space: 8 }) { Text(water).fontSize(10).fontColor(ThemeColors.textMuted); Text(light).fontSize(10).fontColor(ThemeColors.textMuted) }
        }.alignItems(HorizontalAlign.Start)
      }
      Row({ space: 4 }) {
        Button('✎').width(28).height(28).type(ButtonType.Circle).backgroundColor(ThemeColors.base)
          .onClick(() => this.showToast('编辑功能'))
        Button('🗑️').width(28).height(28).type(ButtonType.Circle).backgroundColor('#fef2f2')
          .onClick(() => this.showToast('删除功能'))
      }
    }.width('100%').backgroundColor(ThemeColors.card).padding(12).borderRadius(12).borderWidth(1).borderColor(ThemeColors.borderLight).margin({ bottom: 8 })
  }

  @Builder EnergySection() {
    Column() {
      Row() {
        this.SectionTitle('⚡', '节能优化')
        Row() {
          Text('本周').fontSize(10).padding(4).fontColor(this.timeTab === '本周' ? ThemeColors.primary : ThemeColors.textMuted).backgroundColor(this.timeTab === '本周' ? ThemeColors.card : 'transparent').borderRadius(4).onClick(() => this.timeTab = '本周')
          Text('本月').fontSize(10).padding(4).fontColor(this.timeTab === '本月' ? ThemeColors.primary : ThemeColors.textMuted).backgroundColor(this.timeTab === '本月' ? ThemeColors.card : 'transparent').borderRadius(4).onClick(() => this.timeTab = '本月')
          Text('本年').fontSize(10).padding(4).fontColor(this.timeTab === '本年' ? ThemeColors.primary : ThemeColors.textMuted).backgroundColor(this.timeTab === '本年' ? ThemeColors.card : 'transparent').borderRadius(4).onClick(() => this.timeTab = '本年')
        }.backgroundColor('#e5e7eb').padding(2).borderRadius(6).offset({ y: -6 })
      }.width('100%').justifyContent(FlexAlign.SpaceBetween)

      Row({ space: 12 }) {
        Column({ space: 4 }) {
          Row({ space: 4 }) { Text('💧').fontSize(12); Text('累计节水').fontSize(12).fontWeight(FontWeight.Bold).fontColor(ThemeColors.blue) }
          Row() { Text(`${this.waterSaved.toLocaleString()}`).fontSize(24).fontWeight(FontWeight.Bold); Text('L').fontSize(10).fontColor(ThemeColors.textMuted).margin({ left: 2, bottom: 4 }) }.alignItems(VerticalAlign.Bottom)
        }.layoutWeight(1).backgroundColor('#eff6ff').padding(12).borderRadius(12).borderWidth(1).borderColor('#dbeafe').alignItems(HorizontalAlign.Start)

        Column({ space: 4 }) {
          Row({ space: 4 }) { Text('🌱').fontSize(12); Text('减少碳排').fontSize(12).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary) }
          Row() { Text(`${this.carbonReduced}`).fontSize(24).fontWeight(FontWeight.Bold); Text('kg').fontSize(10).fontColor(ThemeColors.textMuted).margin({ left: 2, bottom: 4 }) }.alignItems(VerticalAlign.Bottom)
          Text('相当于种植 2 棵树').fontSize(9).fontColor(ThemeColors.primary).backgroundColor(ThemeColors.primaryLight).padding(2).borderRadius(4)
        }.layoutWeight(1).backgroundColor('#f0fdf4').padding(12).borderRadius(12).borderWidth(1).borderColor('#dcfce7').alignItems(HorizontalAlign.Start)
      }.width('100%').margin({ bottom: 12 })

      Row() {
        Column({ space: 4 }) {
          Text('系统综合能效').fontSize(14).fontWeight(FontWeight.Bold)
          Text('智能算法优化运行策略').fontSize(11).fontColor(ThemeColors.textMuted)
          Text('A 级 卓越能效').fontSize(10).fontColor('#16a34a').backgroundColor('#dcfce7').padding({ left: 8, right: 8, top: 4, bottom: 4 }).borderRadius(4).margin({ top: 4 })
        }.alignItems(HorizontalAlign.Start)

        Stack() {
          Progress({ value: this.animationStarted ? this.energyScore : 0, total: 100, type: ProgressType.Ring }).width(64).height(64).color(ThemeColors.accent).style({ strokeWidth: 6 }).backgroundColor(ThemeColors.borderLight)
          Column() { Text(`${this.energyScore}`).fontSize(20).fontWeight(FontWeight.Bold); Text('分').fontSize(10).fontColor(ThemeColors.textMuted) }
        }
        .onClick(() => this.showEnergyModal = true)
      }.width('100%').backgroundColor(ThemeColors.card).padding(16).borderRadius(12).borderWidth(1).borderColor(ThemeColors.borderLight).justifyContent(FlexAlign.SpaceBetween)

    }
  }

  @Builder AddPlantModal() {
    Stack({ alignContent: Alignment.Bottom }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => this.showPlantModal = false)

      Column() {
        Row() {
          Text('添加植物档案').fontSize(16).fontWeight(FontWeight.Bold)
          Text('✕').fontSize(16).fontColor(ThemeColors.textMuted).onClick(() => this.showPlantModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16).borderWidth({ bottom: 1 }).borderColor(ThemeColors.borderLight)

        Column({ space: 16 }) {
          Column({ space: 6 }) {
            Text('作物名称').fontSize(12).fontColor(ThemeColors.textMuted)
            TextInput({ placeholder: '例如：秋葵' }).height(40).backgroundColor(ThemeColors.card).borderWidth(1).borderColor(ThemeColors.borderLight)
          }.alignItems(HorizontalAlign.Start).width('100%')

          Row({ space: 12 }) {
            Column({ space: 6 }) { Text('适宜水分 (Min %)').fontSize(12).fontColor(ThemeColors.textMuted); TextInput({ placeholder: '40' }).height(40).backgroundColor(ThemeColors.card).borderWidth(1).borderColor(ThemeColors.borderLight) }.layoutWeight(1).alignItems(HorizontalAlign.Start)
            Column({ space: 6 }) { Text('适宜水分 (Max %)').fontSize(12).fontColor(ThemeColors.textMuted); TextInput({ placeholder: '60' }).height(40).backgroundColor(ThemeColors.card).borderWidth(1).borderColor(ThemeColors.borderLight) }.layoutWeight(1).alignItems(HorizontalAlign.Start)
          }.width('100%')

          Column({ space: 6 }) {
            Text('光照需求').fontSize(12).fontColor(ThemeColors.textMuted)
            Select([{ value: '强光照 (全日照)' }, { value: '中等光照 (半日照)' }, { value: '弱光照 (耐阴)' }]).selected(0).value('强光照 (全日照)').width('100%').height(40).backgroundColor(ThemeColors.card).borderWidth(1).borderColor(ThemeColors.borderLight)
          }.alignItems(HorizontalAlign.Start).width('100%')

          Button('保存档案').width('100%').backgroundColor(ThemeColors.primary).height(44).margin({ top: 16 })
            .onClick(() => {
              this.showToast('档案已保存');
              this.showPlantModal = false;
            })
        }.padding(20).width('100%')
      }
      .width('100%').backgroundColor(ThemeColors.card).borderRadius({ topLeft: 24, topRight: 24 })
      .animation({ duration: 300, curve: Curve.EaseOut })
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder CropSelectModal() {
    Stack({ alignContent: Alignment.Bottom }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => this.showCropSelectModal = false)

      Column() {
        Row() {
          Text('选择作物').fontSize(16).fontWeight(FontWeight.Bold)
          Text('✕').fontSize(16).fontColor(ThemeColors.textMuted).onClick(() => this.showCropSelectModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding(16).borderWidth({ bottom: 1 }).borderColor(ThemeColors.borderLight)

        Column({ space: 12 }) {
          this.CropOption('🥕', '白萝卜', true)
          this.CropOption('🥬', '奶油生菜', false)
          this.CropOption('🍅', '樱桃番茄', false)
          this.CropOption('🌶️', '青椒', false)
          this.CropOption('🥒', '黄瓜', false)
        }.padding(16).width('100%')
      }
      .width('100%').backgroundColor(ThemeColors.card).borderRadius({ topLeft: 24, topRight: 24 })
      .animation({ duration: 300, curve: Curve.EaseOut })
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder CropOption(emoji: string, name: string, isSelected: boolean) {
    Row() {
      Row({ space: 12 }) {
        Text(emoji).fontSize(24)
        Text(name).fontSize(16).fontWeight(FontWeight.Medium)
      }
      if (isSelected) {
        Text('✓').fontSize(16).fontColor(ThemeColors.primary)
      }
    }
    .width('100%')
    .justifyContent(FlexAlign.SpaceBetween)
    .padding(12)
    .backgroundColor(isSelected ? ThemeColors.primaryLight : 'transparent')
    .borderRadius(8)
    .onClick(() => {
      this.showToast(`已选择${name}`);
      this.showCropSelectModal = false;
    })
  }

  @Builder WarningDetailModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => this.showWarningModal = false)

      Column() {
        Text('⚠️').fontSize(40).margin({ bottom: 12 })
        Text('水分预警详情').fontSize(18).fontWeight(FontWeight.Bold).margin({ bottom: 8 })
        Text('当前土壤含水量为 28%，低于适宜范围 30%-40%。建议及时开启水泵进行灌溉。').fontSize(14).fontColor(ThemeColors.textMuted).textAlign(TextAlign.Center).margin({ bottom: 20 })

        Row({ space: 12 }) {
          Button('确认').layoutWeight(1).height(40).backgroundColor(ThemeColors.borderLight).fontColor(ThemeColors.textMain)
            .onClick(() => {
              this.showToast('已确认预警');
              this.showWarningModal = false;
            })
          Button('立即开启水泵').layoutWeight(1).height(40).backgroundColor(ThemeColors.primary).fontColor('#fff')
            .onClick(() => {
              this.pumpRunning = true;
              this.showToast('水泵已开启');
              this.showWarningModal = false;
            })
        }.width('100%')
      }
      .width('80%').backgroundColor(ThemeColors.card).padding(24).borderRadius(16)
      .animation({ duration: 250, curve: Curve.EaseOut })
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder EnergyDetailModal() {
    Stack({ alignContent: Alignment.Center }) {
      Column().width('100%').height('100%').backgroundColor('rgba(0,0,0,0.4)').onClick(() => this.showEnergyModal = false)

      Column() {
        Row() {
          Text('能效详情').fontSize(18).fontWeight(FontWeight.Bold)
          Text('✕').fontSize(16).fontColor(ThemeColors.textMuted).onClick(() => this.showEnergyModal = false)
        }.width('100%').justifyContent(FlexAlign.SpaceBetween).margin({ bottom: 20 })

        Column({ space: 16 }) {
          Row() {
            Text('灌溉效率').fontSize(14).fontColor(ThemeColors.textMuted)
            Text('95%').fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.accent)
          }.width('100%').justifyContent(FlexAlign.SpaceBetween)

          Row() {
            Text('光照效率').fontSize(14).fontColor(ThemeColors.textMuted)
            Text('88%').fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.accent)
          }.width('100%').justifyContent(FlexAlign.SpaceBetween)

          Row() {
            Text('温控效率').fontSize(14).fontColor(ThemeColors.textMuted)
            Text('92%').fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.accent)
          }.width('100%').justifyContent(FlexAlign.SpaceBetween)

          Row() {
            Text('通风效率').fontSize(14).fontColor(ThemeColors.textMuted)
            Text('90%').fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.accent)
          }.width('100%').justifyContent(FlexAlign.SpaceBetween)

          Row() {
            Text('综合评分').fontSize(14).fontColor(ThemeColors.textMuted)
            Text('A 级').fontSize(14).fontWeight(FontWeight.Bold).fontColor(ThemeColors.primary)
          }.width('100%').justifyContent(FlexAlign.SpaceBetween)
        }
        .width('100%')
        .padding(16)
        .backgroundColor(ThemeColors.base)
        .borderRadius(12)
        .margin({ bottom: 16 })

        Button('关闭').width('100%').backgroundColor(ThemeColors.primary).height(40)
          .onClick(() => this.showEnergyModal = false)
      }
      .width('85%').backgroundColor(ThemeColors.card).padding(24).borderRadius(16)
      .animation({ duration: 250, curve: Curve.EaseOut })
    }.width('100%').height('100%').zIndex(100)
  }

  @Builder NavItem(title: string, emoji: string, isActive: boolean) {
    Column({ space: 4 }) {
      Text(emoji).fontSize(24).opacity(isActive ? 1 : 0.5)
      Text(title).fontSize(10).fontWeight(isActive ? FontWeight.Bold : FontWeight.Medium).fontColor(isActive ? ThemeColors.primary : ThemeColors.textMuted)
    }.padding({ bottom: 4 })
  }
}
