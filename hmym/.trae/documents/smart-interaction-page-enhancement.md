# Agri-Sync 智能交互页面增强计划

## 问题诊断

用户需要全面增强 `SmartInteractionPage.ets` 智能交互页面的功能，当前页面存在以下不足：

### 现有问题
1. 顶部状态区数据静态，无自动刷新
2. 连接状态无交互，点击无弹窗
3. 刷新功能无动画和反馈
4. 环境数值无点击弹窗
5. 消息类型单一，无状态反馈
6. 快捷指令数量少
7. 无上下文理解和主动预警
8. 无历史记录下拉加载
9. 输入框无智能联想

---

## 增强功能清单

### 1. 顶部状态与数据区
- [ ] 环境数据自动刷新（光照/水分/温度每2.5秒波动）
- [ ] "大脑已连接"点击弹出详情弹窗（延迟/设备在线数/日志入口）
- [ ] "刷新"按钮添加加载动画和Toast提示
- [ ] 环境数值点击弹出历史趋势弹窗（支持今日/本周/本月切换）

### 2. 对话消息区增强
- [ ] 消息添加时间戳显示
- [ ] AI消息支持富文本（加粗关键数据）
- [ ] 设备控制指令添加状态标签（待执行/正在执行/已完成/失败）
- [ ] 新消息到达时自动滚动到底部
- [ ] 用户消息支持长按菜单（复制/删除）
- [ ] 历史记录下拉加载

### 3. 快捷指令区扩展
- [ ] 新增更多快捷指令按钮
- [ ] 根据环境数据智能高亮推荐指令
- [ ] 添加自定义指令"+"按钮
- [ ] 按钮点击缩放动效

### 4. 输入区增强
- [ ] 发送前检查空输入
- [ ] 发送成功自动清空输入框
- [ ] 发送失败显示重试提示
- [ ] 快捷短语智能联想

### 5. 设备联动与智能逻辑
- [ ] 上下文记忆（理解"再开久一点"等模糊指令）
- [ ] 主动预警推送（温度/水分异常时自动消息）
- [ ] 设备控制结果自动回调消息

### 6. 页面体验优化
- [ ] 页面加载骨架屏
- [ ] 无对话时显示引导文案
- [ ] 网络断开离线提示

---

## 实现步骤

### Step 1: 基础状态增强
- 添加环境数据状态变量
- 添加定时刷新逻辑
- 添加连接详情弹窗

### Step 2: 数据刷新与交互
- 实现数据自动刷新函数
- 实现刷新按钮加载动画
- 实现数值点击历史弹窗

### Step 3: 消息组件增强
- 扩展消息类型结构
- 添加状态标签渲染
- 添加时间显示
- 添加自动滚动逻辑

### Step 4: 快捷指令扩展
- 扩展指令集
- 实现智能推荐逻辑
- 添加自定义指令功能

### 5. 智能预警与上下文
- 添加环境阈值检测
- 实现自动预警推送
- 添加上下文记忆变量

### 6. 体验优化
- 添加骨架屏/空状态
- 添加网络状态检测

---

## 关键代码结构

```typescript
// 1. 状态变量
@State lightIntensity: number = 28.5;
@State soilMoisture: number = 42;
@State temperature: number = 25;
@State messages: ChatMessage[] = [...];
@State isRefreshing: boolean = false;
@State showConnectionModal: boolean = false;
@State showHistoryModal: boolean = false;

// 2. 定时刷新
aboutToAppear(): void {
  setInterval(() => this.refreshData(), 2500);
}

// 3. 消息结构
interface ChatMessage {
  id: string;
  role: 'system' | 'ai' | 'user';
  content: string;
  time?: string;
  status?: 'pending' | 'executing' | 'completed' | 'failed';
  embedLog?: EmbedLog;
  hasPumpControl?: boolean;
}
```

---

## 预期效果

1. 顶部数据每2.5秒自动波动刷新
2. 点击连接状态弹出详情弹窗
3. 刷新按钮有加载动画
4. 快捷指令更丰富，有智能推荐
5. 消息有执行状态标签
6. 支持历史记录下拉加载
7. 环境异常时自动推送预警
8. 页面体验更流畅

---

## 文件位置
- 修改文件：`d:\shiyan\hmym\entry\src\main\ets\pages\SmartInteractionPage.ets`
- 依赖文件：`d:\shiyan\hmym\entry\src\main\ets\pages\AgriSyncDashboardPage.ets`（数据共享）