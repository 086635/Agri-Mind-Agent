# AGRI-SYNC 首页交互功能 Spec

## Why
用户需要实现 AGRI-SYNC 农业物联网应用的首页（`AgriSyncDashboardPage.ets`），包含完整的环境监测、设备控制、植物生长监测、农事待办和底部导航交互功能。

## What Changes
- 创建 AGRI-SYNC 首页完整交互功能
- 实现顶部信息栏（消息通知、区域切换、环境视图切换）
- 实现核心环境监测模块（光照/土壤/氮磷钾/CO₂卡片及详情弹窗）
- 实现设备快捷控制模块（遮光帘/水泵/风扇控制）
- 实现植物生长监测模块（作物卡片、生长进度、阶段说明）
- 实现农事待办模块（预警处理、视觉分析报警）
- 实现底部导航栏（5个页面切换、AI协作脉冲动画）

## Impact
- Affected specs: 农业智能控制页面
- Affected code: `d:\shiyan\hmym\entry\src\main\ets\pages\AgriSyncDashboardPage.ets`

## 技术栈
- ArkTS + ArkUI V1，API 12+，Stage 模型
- @State 管理核心状态，@Provide/@Consume 跨页面共享
- 响应式布局适配手机/折叠屏

---

## ADDED Requirements

### Requirement: 顶部信息栏交互

#### Scenario: 点击铃铛图标
- **WHEN** 用户点击右上角铃铛图标
- **THEN** 弹出消息通知列表，显示未读消息，已读/未读状态可切换

#### Scenario: 点击区域标题
- **WHEN** 用户点击 "4号大棚・萝卜区"
- **THEN** 弹出大棚/区域选择弹窗，切换后更新页面数据与标题

#### Scenario: 点击眼睛图标
- **WHEN** 用户点击数字孪生环境右侧眼睛图标
- **THEN** 切换环境可视化视图（全息监测 ↔ 数据列表）

---

### Requirement: 环境监测卡片交互

#### Scenario: 点击监测卡片
- **WHEN** 用户点击光照强度/土壤水分/氮磷钾含量/CO₂浓度卡片
- **THEN** 弹出详情弹窗，展示历史趋势曲线、数据对比与阈值设置

#### Scenario: 点击氮磷钾进度条
- **WHEN** 用户点击 N/P/K 进度条
- **THEN** 展开详细数值与施肥建议弹窗

#### Scenario: 点击CO₂柱状图
- **WHEN** 用户点击 CO₂ 浓度柱状图
- **THEN** 切换不同时间段数据视图（今日/本周/本月）

---

### Requirement: 设备快捷控制模块

#### Scenario: 点击设备卡片
- **WHEN** 用户点击遮光帘/水泵卡片区域
- **THEN** 展开设备详细控制页（功率、时长、状态等调节项）

#### Scenario: 点击设备状态文字
- **WHEN** 用户点击 "运行中" 文字
- **THEN** 切换设备启停状态，同步更新 UI 样式

#### Scenario: 风扇Toggle开关
- **WHEN** 用户点击风扇 Toggle 开关
- **THEN** 切换风扇启停状态，添加点击反馈动效

#### Scenario: 点击设备状态点
- **WHEN** 用户点击绿色在线状态点
- **THEN** 查看设备在线时长与连接信息

---

### Requirement: 植物生长监测模块

#### Scenario: 点击白萝卜卡片
- **WHEN** 用户点击白萝卜生长卡片
- **THEN** 进入作物详情页，展示生长周期、环境数据与农事记录

#### Scenario: 点击生长进度阶段
- **WHEN** 用户点击生长进度条的不同阶段（种植期/生长期/开花/高发）
- **THEN** 弹出阶段说明与养护建议

#### Scenario: 点击番茄卡片
- **WHEN** 用户点击右侧番茄卡片
- **THEN** 切换当前监测作物，更新页面所有相关数据

---

### Requirement: 农事待办模块

#### Scenario: 点击智能开启水泵按钮
- **WHEN** 用户点击 "智能开启水泵" 按钮
- **THEN** 触发水泵启动，按钮变为 "水泵启动中" 加载动画，完成后更新为 "已开启"

#### Scenario: 点击查看详情按钮
- **WHEN** 用户点击 "查看详情" 按钮
- **THEN** 进入预警详情页，展示数据曲线与处理记录

#### Scenario: 点击诊断图片按钮
- **WHEN** 用户点击 "查看诊断图片" 按钮
- **THEN** 弹出病害图片预览弹窗，支持放大查看

#### Scenario: 点击标记完成按钮
- **WHEN** 用户点击 "标记完成" 按钮
- **THEN** 将报警标记为已处理，从待办列表移除，同步更新 "2项异常报警" 计数

#### Scenario: 点击待办卡片
- **WHEN** 用户点击待办卡片任意区域
- **THEN** 展开/收起详细内容

---

### Requirement: 底部导航栏

#### Scenario: 点击导航项
- **WHEN** 用户点击底部导航项（首页/控制/AI协作/生命周期/设置）
- **THEN** 切换对应页面，当前页图标高亮并添加选中动效

#### Scenario: 点击AI协作图标
- **WHEN** 用户点击 AI 协作图标
- **THEN** 触发脉冲动画，突出核心功能入口

---

## REMOVED Requirements
无

---

## 技术实现要点
1. 使用 `Tabs` + `TabBar` 实现底部导航
2. 使用 `animateTo` 实现点击反馈和状态切换动效
3. 使用 `TextPicker` / `ActionSheet` 实现弹窗选择
4. 使用 `@Provide` 跨组件共享状态
5. 卡片点击区域 ≥48dp 保证可点击性
6. 响应式布局使用 `flexLayout` 和百分比宽度