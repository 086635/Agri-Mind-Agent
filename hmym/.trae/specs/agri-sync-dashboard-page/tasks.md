# Tasks - AGRI-SYNC 首页交互功能实现

## 任务概述
实现 `AgriSyncDashboardPage.ets` 完整交互功能，包含6大模块：顶部信息栏、环境监测卡片、设备控制、植物生长监测、农事待办、底部导航栏。

---

## Task 1: 创建首页基础框架和状态管理
- [x] SubTask 1.1: 定义页面全局状态数据模型（监测数据、设备状态、作物信息、待办事项等）
- [x] SubTask 1.2: 创建页面基础布局结构和滚动容器
- [x] SubTask 1.3: 初始化 ThemeColors 主题样式类

## Task 2: 实现顶部信息栏组件
- [x] SubTask 2.1: 区域标题组件（"4号大棚・萝卜区"）
- [x] SubTask 2.2: 铃铛消息图标按钮
- [x] SubTask 2.3: 眼睛视图切换图标
- [x] SubTask 2.4: 消息通知弹窗组件
- [x] SubTask 2.5: 区域选择弹窗组件

## Task 3: 实现核心环境监测模块
- [x] SubTask 3.1: 光照强度监测卡片组件
- [x] SubTask 3.2: 土壤水分监测卡片组件
- [x] SubTask 3.3: 氮磷钾含量监测卡片组件（N/P/K进度条）
- [x] SubTask 3.4: CO₂浓度监测卡片组件（柱状图）
- [x] SubTask 3.5: 监测卡片详情弹窗组件（历史曲线、数据对比、阈值设置）

## Task 4: 实现设备快捷控制模块
- [x] SubTask 4.1: 遮光帘控制卡片组件
- [x] SubTask 4.2: 水泵控制卡片组件（启停状态切换）
- [x] SubTask 4.3: 风扇控制卡片组件（Toggle开关）
- [x] SubTask 4.4: 设备在线状态点组件
- [x] SubTask 4.5: 设备详细控制弹窗组件

## Task 5: 实现植物生长监测模块
- [x] SubTask 5.1: 白萝卜生长卡片组件
- [x] SubTask 5.2: 生长进度条组件（种植期/生长期/开花/高发阶段）
- [x] SubTask 5.3: 阶段说明弹窗组件
- [x] SubTask 5.4: 番茄卡片切换组件
- [x] SubTask 5.5: 作物详情页组件

## Task 6: 实现农事待办模块
- [x] SubTask 6.1: 水分不足预警卡片组件
- [x] SubTask 6.2: 智能开启水泵按钮（加载动画）
- [x] SubTask 6.3: 视觉分析报警卡片组件
- [x] SubTask 6.4: 诊断图片预览弹窗组件
- [x] SubTask 6.5: 标记完成功能（更新待办计数）
- [x] SubTask 6.6: 卡片展开/收起动效

## Task 7: 实现底部导航栏
- [x] SubTask 7.1: TabBar 导航组件（首页/控制/AI协作/生命周期/设置）
- [x] SubTask 7.2: 导航项图标和选中状态
- [x] SubTask 7.3: AI协作图标脉冲动画
- [x] SubTask 7.4: 页面切换逻辑

## Task 8: 添加交互动效和样式优化
- [x] SubTask 8.1: 按钮点击缩放反馈动效
- [x] SubTask 8.2: 状态切换过渡动效
- [x] SubTask 8.3: 弹窗入场/退场动效
- [x] SubTask 8.4: 响应式布局适配（手机/折叠屏）

## Task 9: 补充缺失交互逻辑
- [x] SubTask 9.1: StageDot 阶段点击触发弹窗
- [x] SubTask 9.2: CO₂ 卡片点击切换时间段（今日/本周/本月）
- [x] SubTask 9.3: 作物卡片点击进入详情页
- [x] SubTask 9.4: 监测卡片点击触发详情弹窗
- [x] SubTask 9.5: 区域选择弹窗调用
- [x] SubTask 9.6: 待办卡片展开/收起动效
- [x] SubTask 9.7: 诊断图片按钮触发弹窗

---

# Task Dependencies
- Task 2 依赖于 Task 1
- Task 3 依赖于 Task 1
- Task 4 依赖于 Task 1
- Task 5 依赖于 Task 1
- Task 6 依赖于 Task 1
- Task 7 依赖于 Task 1
- Task 8 依赖于 Task 3, 4, 5, 6, 7
- Task 9 依赖于 Task 3, 5, 6