import { router } from '@kit.ArkUI';

interface Point3D {
  x: number;
  y: number;
  z: number;
}

interface Point2D {
  x: number;
  y: number;
}

interface SensorPosition {
  x: number;
  z: number;
}

@Entry
@Component
struct Greenhouse3DPage {
  @State rotationY: number = 0.4;
  @State rotationX: number = 0.35;
  @State zoom: number = 1;
  private lastTouchX: number = 0;
  private lastTouchY: number = 0;
  private lastPinchDistance: number = 0;
  private isDragging: boolean = false;
  private animationFrame: number = 0;

  private settings: RenderingContextSettings = new RenderingContextSettings(true);
  private context: CanvasRenderingContext2D = new CanvasRenderingContext2D(this.settings);
  private dataTimer: number = -1;

  aboutToAppear(): void {
    this.startAnimation();
  }

  aboutToDisappear(): void {
    if (this.dataTimer !== -1) {
      clearInterval(this.dataTimer);
    }
  }

  startAnimation(): void {
    this.dataTimer = setInterval(() => {
      this.animationFrame++;
      this.drawGreenhouse();
    }, 50);
  }

  build() {
    Column() {
      Row() {
        Button('← 返回')
          .backgroundColor('rgba(11, 89, 52, 0.8)')
          .fontColor('#fff')
          .borderRadius(20)
          .padding({ left: 16, right: 16, top: 8, bottom: 8 })
          .onClick(() => {
            router.back();
          })

        Blank()

        Row({ space: 8 }) {
          Button('-')
            .backgroundColor('rgba(100, 100, 100, 0.8)')
            .fontColor('#fff')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .borderRadius(15)
            .width(30)
            .height(30)
            .onClick(() => {
              this.zoom = Math.max(0.6, this.zoom - 0.1);
              this.drawGreenhouse();
            })

          Text(`${Math.round(this.zoom * 100)}%`)
            .fontColor('#fff')
            .fontSize(12)
            .width(45)
            .textAlign(TextAlign.Center)

          Button('+')
            .backgroundColor('rgba(100, 100, 100, 0.8)')
            .fontColor('#fff')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .borderRadius(15)
            .width(30)
            .height(30)
            .onClick(() => {
              this.zoom = Math.min(1.8, this.zoom + 0.1);
              this.drawGreenhouse();
            })
        }

        Blank()

        Column({ space: 2 }) {
          Text('文洛式玻璃温室').fontColor('#fff').fontSize(14).fontWeight(FontWeight.Bold)
          Text('拖拽旋转 · 按钮缩放').fontColor('rgba(255,255,255,0.6)').fontSize(10)
        }.alignItems(HorizontalAlign.End)
      }
      .width('100%')
      .padding({ left: 16, right: 16, top: 10, bottom: 10 })
      .backgroundColor('rgba(0,0,0,0.3)')

      Canvas(this.context)
        .width('100%')
        .layoutWeight(1)
        .backgroundColor('#87CEEB')
        .onReady(() => {
          this.drawGreenhouse();
        })
        .onMouse((event: MouseEvent) => {
          if (event.action === MouseAction.Press) {
            this.isDragging = true;
            this.lastTouchX = event.x;
            this.lastTouchY = event.y;
          } else if (event.action === MouseAction.Release) {
            this.isDragging = false;
          } else if (event.action === MouseAction.Move && this.isDragging) {
            const deltaX = event.x - this.lastTouchX;
            const deltaY = event.y - this.lastTouchY;
            this.rotationY += deltaX * 0.008;
            this.rotationX = Math.max(-0.3, Math.min(0.7, this.rotationX + deltaY * 0.005));
            this.lastTouchX = event.x;
            this.lastTouchY = event.y;
            this.drawGreenhouse();
          }
        })
        .onTouch((event: TouchEvent) => {
          if (event.type === TouchType.Down) {
            if (event.touches.length === 1) {
              this.isDragging = true;
              this.lastTouchX = event.touches[0].x;
              this.lastTouchY = event.touches[0].y;
            } else if (event.touches.length === 2) {
              this.lastPinchDistance = this.getPinchDistance(event.touches[0], event.touches[1]);
            }
          } else if (event.type === TouchType.Move) {
            if (event.touches.length === 1 && this.isDragging) {
              const deltaX = event.touches[0].x - this.lastTouchX;
              const deltaY = event.touches[0].y - this.lastTouchY;
              this.rotationY += deltaX * 0.008;
              this.rotationX = Math.max(-0.3, Math.min(0.7, this.rotationX + deltaY * 0.005));
              this.lastTouchX = event.touches[0].x;
              this.lastTouchY = event.touches[0].y;
              this.drawGreenhouse();
            } else if (event.touches.length === 2) {
              const currentDistance = this.getPinchDistance(event.touches[0], event.touches[1]);
              const deltaDistance = currentDistance - this.lastPinchDistance;
              this.zoom = Math.max(0.6, Math.min(1.8, this.zoom + deltaDistance * 0.003));
              this.lastPinchDistance = currentDistance;
              this.drawGreenhouse();
            }
          } else if (event.type === TouchType.Up) {
            this.isDragging = false;
          }
        })
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#1a1a2e')
  }

  getPinchDistance(touch1: TouchObject, touch2: TouchObject): number {
    const dx = touch1.x - touch2.x;
    const dy = touch1.y - touch2.y;
    return Math.sqrt(dx * dx + dy * dy);
  }

  project3D(x: number, y: number, z: number, centerX: number, centerY: number, scale: number): Point2D {
    const cosY = Math.cos(this.rotationY);
    const sinY = Math.sin(this.rotationY);
    const cosX = Math.cos(this.rotationX);
    const sinX = Math.sin(this.rotationX);

    const x1 = x * cosY - z * sinY;
    const z1 = x * sinY + z * cosY;
    const y1 = y * cosX - z1 * sinX;
    const z2 = y * sinX + z1 * cosX;

    const perspective = 600 / (600 + z2);
    return {
      x: centerX + x1 * scale * perspective * this.zoom,
      y: centerY - y1 * scale * perspective * this.zoom
    };
  }

  drawGreenhouse(): void {
    const ctx = this.context;
    const width = ctx.width;
    const height = ctx.height;
    const centerX = width / 2;
    const centerY = height / 2 + 20;
    const scale = Math.min(width, height) * 0.12;

    ctx.clearRect(0, 0, width, height);

    const skyGradient = ctx.createLinearGradient(0, 0, 0, height);
    skyGradient.addColorStop(0, '#4A90D9');
    skyGradient.addColorStop(0.5, '#87CEEB');
    skyGradient.addColorStop(1, '#B0E0E6');
    ctx.fillStyle = skyGradient;
    ctx.fillRect(0, 0, width, height);

    this.drawSun(ctx, width - 80, 60);
    this.drawClouds(ctx, width, height);

    this.drawGround(ctx, centerX, centerY, scale);

    this.drawFoundation(ctx, centerX, centerY, scale);

    this.drawMainFrame(ctx, centerX, centerY, scale);

    this.drawGlass(ctx, centerX, centerY, scale);

    this.drawExternalShade(ctx, centerX, centerY, scale);

    this.drawInternalShade(ctx, centerX, centerY, scale);

    this.drawPlantingTroughs(ctx, centerX, centerY, scale);

    this.drawCrops(ctx, centerX, centerY, scale);

    this.drawIrrigationPipes(ctx, centerX, centerY, scale);

    this.drawGrowLights(ctx, centerX, centerY, scale);

    this.drawSideLights(ctx, centerX, centerY, scale);

    this.drawRoofWindows(ctx, centerX, centerY, scale);

    this.drawCirculationFans(ctx, centerX, centerY, scale);

    this.drawWetPad(ctx, centerX, centerY, scale);

    this.drawExhaustFans(ctx, centerX, centerY, scale);

    this.drawControlCabinet(ctx, centerX, centerY, scale);

    this.drawSensors(ctx, centerX, centerY, scale);

    this.drawWeatherStation(ctx, centerX, centerY, scale);

    this.drawRailTrack(ctx, centerX, centerY, scale);
  }

  drawSun(ctx: CanvasRenderingContext2D, x: number, y: number): void {
    const glowGradient = ctx.createRadialGradient(x, y, 0, x, y, 100);
    glowGradient.addColorStop(0, 'rgba(255, 255, 200, 0.8)');
    glowGradient.addColorStop(0.3, 'rgba(255, 220, 100, 0.4)');
    glowGradient.addColorStop(1, 'rgba(255, 200, 50, 0)');
    ctx.fillStyle = glowGradient;
    ctx.beginPath();
    ctx.arc(x, y, 100, 0, Math.PI * 2);
    ctx.fill();

    ctx.beginPath();
    ctx.arc(x, y, 30, 0, Math.PI * 2);
    ctx.fillStyle = '#FFF8DC';
    ctx.fill();
  }

  drawClouds(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
    this.drawCloud(ctx, 100, 80, 40);
    this.drawCloud(ctx, width - 200, 100, 35);
    this.drawCloud(ctx, width / 2, 50, 30);
  }

  drawCloud(ctx: CanvasRenderingContext2D, x: number, y: number, size: number): void {
    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.arc(x + size * 0.8, y - size * 0.2, size * 0.7, 0, Math.PI * 2);
    ctx.arc(x + size * 1.5, y, size * 0.6, 0, Math.PI * 2);
    ctx.arc(x - size * 0.5, y + size * 0.1, size * 0.5, 0, Math.PI * 2);
    ctx.fill();
  }

  drawGround(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    const groundPoints: Point2D[] = [];
    for (let i = 0; i <= 20; i++) {
      const x = -12 + i * 1.2;
      groundPoints.push(this.project3D(x, -3, -8, centerX, centerY, scale));
    }
    for (let i = 20; i >= 0; i--) {
      const x = -12 + i * 1.2;
      groundPoints.push(this.project3D(x, -3, 8, centerX, centerY, scale));
    }
    ctx.beginPath();
    ctx.moveTo(groundPoints[0].x, groundPoints[0].y);
    for (let i = 1; i < groundPoints.length; i++) {
      ctx.lineTo(groundPoints[i].x, groundPoints[i].y);
    }
    ctx.closePath();
    const groundGradient = ctx.createLinearGradient(0, centerY - 50, 0, centerY + 100);
    groundGradient.addColorStop(0, '#7CB342');
    groundGradient.addColorStop(1, '#558B2F');
    ctx.fillStyle = groundGradient;
    ctx.fill();
  }

  drawFoundation(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    const foundationHeight = 0.5;
    const points = [
      this.project3D(-10, -3, -5, centerX, centerY, scale),
      this.project3D(10, -3, -5, centerX, centerY, scale),
      this.project3D(10, -3 + foundationHeight, -5, centerX, centerY, scale),
      this.project3D(-10, -3 + foundationHeight, -5, centerX, centerY, scale),
    ];
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i].x, points[i].y);
    }
    ctx.closePath();
    ctx.fillStyle = '#808080';
    ctx.fill();
    ctx.strokeStyle = '#606060';
    ctx.lineWidth = 1;
    ctx.stroke();

    const points2 = [
      this.project3D(10, -3, -5, centerX, centerY, scale),
      this.project3D(10, -3, 5, centerX, centerY, scale),
      this.project3D(10, -3 + foundationHeight, 5, centerX, centerY, scale),
      this.project3D(10, -3 + foundationHeight, -5, centerX, centerY, scale),
    ];
    ctx.beginPath();
    ctx.moveTo(points2[0].x, points2[0].y);
    for (let i = 1; i < points2.length; i++) {
      ctx.lineTo(points2[i].x, points2[i].y);
    }
    ctx.closePath();
    ctx.fillStyle = '#909090';
    ctx.fill();
    ctx.stroke();
  }

  drawMainFrame(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    ctx.strokeStyle = '#C0C0C0';
    ctx.lineWidth = 2;

    const archCount = 5;
    for (let i = 0; i < archCount; i++) {
      const z = -4 + i * 2;
      this.drawArchFrame(ctx, centerX, centerY, scale, z);
    }

    for (let i = 0; i <= 4; i++) {
      const x = -8 + i * 4;
      this.drawVerticalPost(ctx, centerX, centerY, scale, x, -4);
      this.drawVerticalPost(ctx, centerX, centerY, scale, x, 4);
    }

    ctx.lineWidth = 1.5;
    for (let z = -4; z <= 4; z += 2) {
      const y = -2.5;
      const p1 = this.project3D(-8, y, z, centerX, centerY, scale);
      const p2 = this.project3D(8, y, z, centerX, centerY, scale);
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    }

    for (let i = 0; i <= 4; i++) {
      const x = -8 + i * 4;
      for (let z = -4; z <= 4; z += 2) {
        const p1 = this.project3D(x, -2.5, z, centerX, centerY, scale);
        const p2 = this.project3D(x, 4, z, centerX, centerY, scale);
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();
      }
    }
  }

  drawArchFrame(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number, z: number): void {
    ctx.strokeStyle = '#C0C0C0';
    ctx.lineWidth = 2.5;

    const peakPoints: Point2D[] = [];
    for (let i = 0; i <= 4; i++) {
      const x = -8 + i * 4;
      const p = this.project3D(x, 4, z, centerX, centerY, scale);
      peakPoints.push(p);
    }
    ctx.beginPath();
    ctx.moveTo(peakPoints[0].x, peakPoints[0].y);
    for (let i = 1; i < peakPoints.length; i++) {
      ctx.lineTo(peakPoints[i].x, peakPoints[i].y);
    }
    ctx.stroke();

    for (let i = 0; i <= 4; i++) {
      const x = -8 + i * 4;
      const p1 = this.project3D(x, -2.5, z, centerX, centerY, scale);
      const p2 = this.project3D(x, 4, z, centerX, centerY, scale);
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    }

    for (let i = 0; i < 4; i++) {
      const x1 = -8 + i * 4;
      const x2 = -8 + (i + 1) * 4;
      const midX = (x1 + x2) / 2;
      const p1 = this.project3D(x1, 4, z, centerX, centerY, scale);
      const p2 = this.project3D(midX, 5.5, z, centerX, centerY, scale);
      const p3 = this.project3D(x2, 4, z, centerX, centerY, scale);
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.quadraticCurveTo(p2.x, p2.y, p3.x, p3.y);
      ctx.stroke();
    }
  }

  drawVerticalPost(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number, x: number, z: number): void {
    const p1 = this.project3D(x, -2.5, z, centerX, centerY, scale);
    const p2 = this.project3D(x, 4, z, centerX, centerY, scale);
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.stroke();
  }

  drawGlass(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    ctx.fillStyle = 'rgba(144, 238, 144, 0.25)';
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.lineWidth = 0.5;

    for (let i = 0; i < 4; i++) {
      const z1 = -4 + i * 2;
      const z2 = -4 + (i + 1) * 2;

      for (let j = 0; j < 4; j++) {
        const x1 = -8 + j * 4;
        const x2 = -8 + (j + 1) * 4;
        const midX = (x1 + x2) / 2;

        const points = [
          this.project3D(x1, 4, z1, centerX, centerY, scale),
          this.project3D(x2, 4, z1, centerX, centerY, scale),
          this.project3D(midX, 5.5, z1, centerX, centerY, scale),
        ];
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        ctx.lineTo(points[1].x, points[1].y);
        ctx.quadraticCurveTo(points[2].x, points[2].y, points[0].x, points[0].y);
        ctx.fill();
        ctx.stroke();
      }

      const sidePoints = [
        this.project3D(-8, -2.5, z1, centerX, centerY, scale),
        this.project3D(-8, 4, z1, centerX, centerY, scale),
        this.project3D(-8, 4, z2, centerX, centerY, scale),
        this.project3D(-8, -2.5, z2, centerX, centerY, scale),
      ];
      ctx.beginPath();
      ctx.moveTo(sidePoints[0].x, sidePoints[0].y);
      for (let k = 1; k < sidePoints.length; k++) {
        ctx.lineTo(sidePoints[k].x, sidePoints[k].y);
      }
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      const sidePoints2 = [
        this.project3D(8, -2.5, z1, centerX, centerY, scale),
        this.project3D(8, 4, z1, centerX, centerY, scale),
        this.project3D(8, 4, z2, centerX, centerY, scale),
        this.project3D(8, -2.5, z2, centerX, centerY, scale),
      ];
      ctx.beginPath();
      ctx.moveTo(sidePoints2[0].x, sidePoints2[0].y);
      for (let k = 1; k < sidePoints2.length; k++) {
        ctx.lineTo(sidePoints2[k].x, sidePoints2[k].y);
      }
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    }
  }

  drawExternalShade(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    ctx.fillStyle = 'rgba(30, 30, 30, 0.6)';
    ctx.strokeStyle = '#404040';
    ctx.lineWidth = 1;

    for (let i = 0; i < 4; i++) {
      const z1 = -4 + i * 2;
      const z2 = -4 + (i + 1) * 2;

      for (let j = 0; j < 4; j++) {
        const x1 = -8 + j * 4;
        const x2 = -8 + (j + 1) * 4;
        const midX = (x1 + x2) / 2;

        const points = [
          this.project3D(x1, 5.8, z1, centerX, centerY, scale),
          this.project3D(x2, 5.8, z1, centerX, centerY, scale),
          this.project3D(midX, 7, z1, centerX, centerY, scale),
        ];
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        ctx.lineTo(points[1].x, points[1].y);
        ctx.quadraticCurveTo(points[2].x, points[2].y, points[0].x, points[0].y);
        ctx.fill();
      }
    }

    ctx.strokeStyle = '#505050';
    ctx.lineWidth = 1.5;
    for (let z = -4; z <= 4; z += 2) {
      for (let j = 0; j < 4; j++) {
        const x1 = -8 + j * 4;
        const x2 = -8 + (j + 1) * 4;
        const midX = (x1 + x2) / 2;
        const p1 = this.project3D(x1, 5.8, z, centerX, centerY, scale);
        const p2 = this.project3D(midX, 7, z, centerX, centerY, scale);
        const p3 = this.project3D(x2, 5.8, z, centerX, centerY, scale);
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.quadraticCurveTo(p2.x, p2.y, p3.x, p3.y);
        ctx.stroke();
      }
    }
  }

  drawInternalShade(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    ctx.fillStyle = 'rgba(200, 200, 200, 0.4)';

    const shadeZ = [0, 2];
    for (const z of shadeZ) {
      const points = [
        this.project3D(-6, 3.5, z, centerX, centerY, scale),
        this.project3D(6, 3.5, z, centerX, centerY, scale),
        this.project3D(6, 3.5, z + 1.5, centerX, centerY, scale),
        this.project3D(-6, 3.5, z + 1.5, centerX, centerY, scale),
      ];
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
      }
      ctx.closePath();
      ctx.fill();
    }

    ctx.fillStyle = '#404040';
    const motorPos1 = this.project3D(-8, 3.8, -3, centerX, centerY, scale);
    ctx.beginPath();
    ctx.roundRect(motorPos1.x - 8, motorPos1.y - 5, 16, 10, 2);
    ctx.fill();
    ctx.fillStyle = '#202020';
    ctx.beginPath();
    ctx.roundRect(motorPos1.x - 5, motorPos1.y - 3, 10, 6, 1);
    ctx.fill();
  }

  drawPlantingTroughs(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    const troughPositions = [-3, 0, 3];

    for (const x of troughPositions) {
      const points = [
        this.project3D(x - 1.2, -2.5, -3, centerX, centerY, scale),
        this.project3D(x + 1.2, -2.5, -3, centerX, centerY, scale),
        this.project3D(x + 1.2, -2.5, 3, centerX, centerY, scale),
        this.project3D(x - 1.2, -2.5, 3, centerX, centerY, scale),
      ];
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
      }
      ctx.closePath();
      ctx.fillStyle = '#8B4513';
      ctx.fill();
      ctx.strokeStyle = '#5D3A1A';
      ctx.lineWidth = 1;
      ctx.stroke();

      const topPoints = [
        this.project3D(x - 1.2, -2.2, -3, centerX, centerY, scale),
        this.project3D(x + 1.2, -2.2, -3, centerX, centerY, scale),
        this.project3D(x + 1.2, -2.2, 3, centerX, centerY, scale),
        this.project3D(x - 1.2, -2.2, 3, centerX, centerY, scale),
      ];
      ctx.beginPath();
      ctx.moveTo(topPoints[0].x, topPoints[0].y);
      for (let i = 1; i < topPoints.length; i++) {
        ctx.lineTo(topPoints[i].x, topPoints[i].y);
      }
      ctx.closePath();
      ctx.fillStyle = '#3E2723';
      ctx.fill();
    }

    ctx.fillStyle = '#9E9E9E';
    for (const z of [-4, 4]) {
      const points = [
        this.project3D(-8, -2.5, z - 0.5, centerX, centerY, scale),
        this.project3D(8, -2.5, z - 0.5, centerX, centerY, scale),
        this.project3D(8, -2.5, z + 0.5, centerX, centerY, scale),
        this.project3D(-8, -2.5, z + 0.5, centerX, centerY, scale),
      ];
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
      }
      ctx.closePath();
      ctx.fill();
    }
  }

  drawCrops(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    const troughPositions = [-3, 0, 3];

    for (const troughX of troughPositions) {
      for (let row = 0; row < 8; row++) {
        const z = -2.5 + row * 0.7;
        for (let col = 0; col < 3; col++) {
          const x = troughX - 0.6 + col * 0.6;
          const p = this.project3D(x, -2, z, centerX, centerY, scale);

          const leafSize = 4 + Math.sin(this.animationFrame * 0.1 + row + col) * 1;

          ctx.fillStyle = '#2E7D32';
          ctx.beginPath();
          ctx.arc(p.x, p.y - leafSize, leafSize, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = '#4CAF50';
          ctx.beginPath();
          ctx.arc(p.x - 2, p.y - leafSize + 2, leafSize * 0.7, 0, Math.PI * 2);
          ctx.fill();
          ctx.beginPath();
          ctx.arc(p.x + 2, p.y - leafSize + 2, leafSize * 0.7, 0, Math.PI * 2);
          ctx.fill();

          ctx.strokeStyle = '#1B5E20';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(p.x, p.y - leafSize);
          ctx.stroke();
        }
      }
    }
  }

  drawIrrigationPipes(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 3;

    for (const z of [-3, 0, 3]) {
      const p1 = this.project3D(-7, 2, z, centerX, centerY, scale);
      const p2 = this.project3D(7, 2, z, centerX, centerY, scale);
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    }

    ctx.strokeStyle = '#333333';
    ctx.lineWidth = 1.5;
    const troughPositions = [-3, 0, 3];
    for (const x of troughPositions) {
      for (let z = -2; z <= 2; z += 1) {
        const p1 = this.project3D(x, 2, z, centerX, centerY, scale);
        const p2 = this.project3D(x, -1.5, z, centerX, centerY, scale);
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();
      }
    }
  }

  drawGrowLights(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    const troughPositions = [-3, 0, 3];

    for (const x of troughPositions) {
      for (let z = -2; z <= 2; z += 2) {
        const p1 = this.project3D(x - 0.5, 0.8, z, centerX, centerY, scale);
        const p2 = this.project3D(x + 0.5, 0.8, z, centerX, centerY, scale);

        ctx.fillStyle = '#FFFFFF';
        ctx.strokeStyle = '#E0E0E0';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.roundRect(p1.x, p1.y - 3, p2.x - p1.x, 6, 2);
        ctx.fill();
        ctx.stroke();

        const glowGradient = ctx.createRadialGradient(
          (p1.x + p2.x) / 2, p1.y + 10, 0,
          (p1.x + p2.x) / 2, p1.y + 10, 20
        );
        glowGradient.addColorStop(0, 'rgba(255, 200, 255, 0.4)');
        glowGradient.addColorStop(1, 'rgba(255, 200, 255, 0)');
        ctx.fillStyle = glowGradient;
        ctx.beginPath();
        ctx.arc((p1.x + p2.x) / 2, p1.y + 10, 20, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  drawSideLights(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    ctx.fillStyle = '#FFFFFF';
    ctx.strokeStyle = '#FFB6C1';
    ctx.lineWidth = 1;

    for (let i = 0; i < 4; i++) {
      const z = -3 + i * 2;
      const p = this.project3D(-7.8, 1, z, centerX, centerY, scale);
      ctx.beginPath();
      ctx.roundRect(p.x - 6, p.y - 6, 12, 12, 2);
      ctx.fill();
      ctx.stroke();

      const glowGradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 15);
      glowGradient.addColorStop(0, 'rgba(255, 200, 255, 0.3)');
      glowGradient.addColorStop(1, 'rgba(255, 200, 255, 0)');
      ctx.fillStyle = glowGradient;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 15, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  drawRoofWindows(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    ctx.fillStyle = 'rgba(200, 230, 255, 0.6)';
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 1;

    for (let i = 0; i < 3; i++) {
      const x = -6 + i * 4;
      const z = 0;

      const points = [
        this.project3D(x - 1, 5.2, z, centerX, centerY, scale),
        this.project3D(x + 1, 5.2, z, centerX, centerY, scale),
        this.project3D(x + 1, 5.8, z, centerX, centerY, scale),
        this.project3D(x - 1, 5.8, z, centerX, centerY, scale),
      ];
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let j = 1; j < points.length; j++) {
        ctx.lineTo(points[j].x, points[j].y);
      }
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = '#4CAF50';
      const actuator = this.project3D(x, 4.8, z, centerX, centerY, scale);
      ctx.beginPath();
      ctx.roundRect(actuator.x - 2, actuator.y - 4, 4, 8, 1);
      ctx.fill();
      ctx.fillStyle = 'rgba(200, 230, 255, 0.6)';
    }
  }

  drawCirculationFans(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    for (let i = 0; i < 3; i++) {
      const x = -4 + i * 4;
      const z = 0;
      const p = this.project3D(x, 3, z, centerX, centerY, scale);

      ctx.fillStyle = '#1a1a1a';
      ctx.beginPath();
      ctx.arc(p.x, p.y, 12, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = '#333333';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 12, 0, Math.PI * 2);
      ctx.stroke();

      const bladeAngle = this.animationFrame * 0.3 + i;
      ctx.strokeStyle = '#555555';
      ctx.lineWidth = 2;
      for (let b = 0; b < 4; b++) {
        const angle = bladeAngle + (b * Math.PI / 2);
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x + Math.cos(angle) * 8, p.y + Math.sin(angle) * 8);
        ctx.stroke();
      }
    }
  }

  drawWetPad(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    const points = [
      this.project3D(-8, -2.5, -3, centerX, centerY, scale),
      this.project3D(-8, 1, -3, centerX, centerY, scale),
      this.project3D(-8, 1, 3, centerX, centerY, scale),
      this.project3D(-8, -2.5, 3, centerX, centerY, scale),
    ];

    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i].x, points[i].y);
    }
    ctx.closePath();

    const gradient = ctx.createLinearGradient(points[0].x, points[0].y, points[2].x, points[2].y);
    gradient.addColorStop(0, '#5C6BC0');
    gradient.addColorStop(0.5, '#7986CB');
    gradient.addColorStop(1, '#5C6BC0');
    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.strokeStyle = '#3949AB';
    ctx.lineWidth = 1;
    for (let i = 0; i < 20; i++) {
      const y = points[0].y + (points[1].y - points[0].y) * (i / 20);
      ctx.beginPath();
      ctx.moveTo(points[0].x - 2, y);
      ctx.lineTo(points[2].x + 2, y);
      ctx.stroke();
    }
  }

  drawExhaustFans(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    for (let i = 0; i < 4; i++) {
      const z = -2.5 + i * 1.5;
      const p = this.project3D(8.3, 2, z, centerX, centerY, scale);

      ctx.fillStyle = '#FFC107';
      ctx.beginPath();
      ctx.arc(p.x, p.y, 15, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#1a1a1a';
      ctx.beginPath();
      ctx.arc(p.x, p.y, 12, 0, Math.PI * 2);
      ctx.fill();

      const bladeAngle = this.animationFrame * 0.4 + i * 0.5;
      ctx.strokeStyle = '#444444';
      ctx.lineWidth = 2;
      for (let b = 0; b < 6; b++) {
        const angle = bladeAngle + (b * Math.PI / 3);
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x + Math.cos(angle) * 10, p.y + Math.sin(angle) * 10);
        ctx.stroke();
      }
    }
  }

  drawControlCabinet(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    const baseP = this.project3D(7, -2.5, -3.5, centerX, centerY, scale);

    ctx.fillStyle = '#607D8B';
    ctx.beginPath();
    ctx.roundRect(baseP.x - 10, baseP.y - 50, 20, 50, 3);
    ctx.fill();

    ctx.strokeStyle = '#455A64';
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.fillStyle = '#263238';
    ctx.beginPath();
    ctx.roundRect(baseP.x - 8, baseP.y - 45, 16, 20, 2);
    ctx.fill();

    ctx.fillStyle = '#4CAF50';
    ctx.font = '8px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('25°C', baseP.x, baseP.y - 38);
    ctx.fillText('60%', baseP.x, baseP.y - 30);

    ctx.fillStyle = '#4CAF50';
    ctx.beginPath();
    ctx.arc(baseP.x - 5, baseP.y - 15, 3, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = '#FFC107';
    ctx.beginPath();
    ctx.arc(baseP.x + 5, baseP.y - 15, 3, 0, Math.PI * 2);
    ctx.fill();
  }

  drawSensors(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    const sensorPositions: SensorPosition[] = [
      { x: -4, z: -2 },
      { x: 0, z: 0 },
      { x: 4, z: 2 },
    ];

    for (const pos of sensorPositions) {
      const p = this.project3D(pos.x, -1, pos.z, centerX, centerY, scale);

      ctx.fillStyle = '#FFFFFF';
      ctx.beginPath();
      ctx.roundRect(p.x - 4, p.y - 6, 8, 12, 2);
      ctx.fill();

      ctx.strokeStyle = '#BDBDBD';
      ctx.lineWidth = 0.5;
      ctx.stroke();

      ctx.strokeStyle = '#9E9E9E';
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(p.x, p.y + 6);
      ctx.lineTo(p.x, p.y + 15);
      ctx.stroke();
    }
  }

  drawWeatherStation(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    const p = this.project3D(0, 7.5, 0, centerX, centerY, scale);

    ctx.strokeStyle = '#78909C';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
    ctx.lineTo(p.x, p.y + 20);
    ctx.stroke();

    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.arc(p.x, p.y - 5, 6, 0, Math.PI * 2);
    ctx.fill();

    const cupAngle = this.animationFrame * 0.2;
    ctx.strokeStyle = '#90A4AE';
    ctx.lineWidth = 1.5;
    for (let i = 0; i < 3; i++) {
      const angle = cupAngle + (i * Math.PI * 2 / 3);
      ctx.beginPath();
      ctx.moveTo(p.x, p.y - 5);
      ctx.lineTo(p.x + Math.cos(angle) * 8, p.y - 5 + Math.sin(angle) * 8);
      ctx.stroke();

      ctx.fillStyle = '#B0BEC5';
      ctx.beginPath();
      ctx.arc(p.x + Math.cos(angle) * 8, p.y - 5 + Math.sin(angle) * 8, 3, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.fillStyle = '#FFD54F';
    ctx.beginPath();
    ctx.arc(p.x + 10, p.y, 4, 0, Math.PI * 2);
    ctx.fill();
  }

  drawRailTrack(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, scale: number): void {
    ctx.strokeStyle = '#BDBDBD';
    ctx.lineWidth = 2;

    const p1 = this.project3D(-6, -2.5, 4.3, centerX, centerY, scale);
    const p2 = this.project3D(6, -2.5, 4.3, centerX, centerY, scale);
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.stroke();

    const p3 = this.project3D(-6, -2.5, 4.7, centerX, centerY, scale);
    const p4 = this.project3D(6, -2.5, 4.7, centerX, centerY, scale);
    ctx.beginPath();
    ctx.moveTo(p3.x, p3.y);
    ctx.lineTo(p4.x, p4.y);
    ctx.stroke();

    const cartX = -3 + Math.sin(this.animationFrame * 0.05) * 2;
    const cartP = this.project3D(cartX, -2.3, 4.5, centerX, centerY, scale);

    ctx.fillStyle = '#424242';
    ctx.beginPath();
    ctx.roundRect(cartP.x - 15, cartP.y - 8, 30, 8, 2);
    ctx.fill();

    ctx.fillStyle = '#F44336';
    ctx.beginPath();
    ctx.roundRect(cartP.x + 8, cartP.y - 12, 6, 8, 1);
    ctx.fill();

    ctx.fillStyle = '#616161';
    ctx.beginPath();
    ctx.arc(cartP.x - 10, cartP.y + 2, 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(cartP.x + 10, cartP.y + 2, 3, 0, Math.PI * 2);
    ctx.fill();
  }
}
