# MoviePilot-Plugins

MoviePilot 站点自动签到插件，支持 V1 和 V2 版本。

## 插件列表

### AutoCkeckin - 站点自动签到

自动签到 MoviePilot 中配置的所有 PT 站点。

**功能特性：**
- ✅ 支持 NexusPHP、Gazelle 等主流站点框架
- ✅ 自动检测签到页面（attendance.php 等）
- ✅ 支持排除特定站点（如需要验证码的站点）
- ✅ 签到结果通知推送
- ✅ Cron 定时执行（默认每天 8:00）
- ✅ API 手动触发
- ✅ 支持 MoviePilot V1 和 V2

## 安装方式

1. MoviePilot 后台 → 插件市场 → 添加插件仓库
2. 输入本仓库地址：`https://github.com/xl-jeeter/MoviePilot-Plugins`
3. 找到"站点自动签到"点击安装

## 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| 启用插件 | 开启/关闭自动签到 | 关闭 |
| 开启通知 | 签到完成后发送通知 | 开启 |
| 签到周期 | Cron 表达式 | `0 8 * * *`（每天8点） |
| 排除站点 | 逗号分隔的站点名称 | 空 |
| 立即运行一次 | 立即执行一次签到 | 关闭 |

## API

- `GET /api/v1/autockeckin/checkin?apikey=xxx` - 手动触发签到

## 注意事项

- 对于需要验证码的站点（如北洋园），建议添加到排除列表
- Cookie 失效时会跳过并通知
- 支持浏览器仿真模式（需在站点设置中开启）

## 开发者

- 作者：xl-jeeter
- GitHub：https://github.com/xl-jeeter
