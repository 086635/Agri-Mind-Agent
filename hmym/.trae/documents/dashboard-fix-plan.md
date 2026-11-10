# 农业智能首页报错修复计划

## 报错分析

| 错误 | 原因 | 修复方案 |
|------|------|----------|
| `primaryLight` 不存在 | ThemeColors 类缺少该属性 | 添加 `static readonly primaryLight: string = '#e8f3ee';` |
| `HorizontalAlign` 赋给 `VerticalAlign` | 类型不匹配 | 修正为 `VerticalAlign.Start` |
| Function may throw exceptions | promptAction 可能抛异常 | try-catch 包裹 |

## 修复步骤

1. 在 ThemeColors 类中添加 primaryLight 属性
2. 修正 HorizontalAlign -> VerticalAlign
3. 确保 Toast 显示有异常处理
