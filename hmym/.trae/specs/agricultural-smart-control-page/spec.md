# 智能控制页面交互增强 Spec

## Why
用户反馈需要增强交互体验：1) +/- 按钮点击时需要更明确的反馈动画；2) 通风系统需要添加总开关功能

## What Changes
- 优化 StepperControl 组件，添加点击反馈动效
- 在通风系统模块添加通风开关 Toggle 组件

## Impact
- Affected specs: 农业智能控制页面
- Affected code: `d:\shiyan\hmym\entry\src\main\ets\pages\AgriSyncControlPage.ets`

## ADDED Requirements
### Requirement: StepperControl 按钮点击反馈动效
系统 SHALL 提供 +/- 按钮点击时的缩放反馈动效

#### Scenario: 加减按钮点击
- **WHEN** 用户点击 "+" 或 "-" 按钮
- **THEN** 按钮产生缩放动效（0.95 -> 1），数值实时更新

### Requirement: 通风系统开关控制
系统 SHALL 提供通风系统的总开关 Toggle 控制

#### Scenario: 通风开关切换
- **WHEN** 用户点击通风 Toggle 开关
- **THEN** 开关状态切换，文字和圆点颜色同步更新，触发 Toast 提示

## 技术实现
- 使用 animateTo 实现按钮缩放动效
- 添加 @State ventOn: boolean 状态变量控制通风开关
