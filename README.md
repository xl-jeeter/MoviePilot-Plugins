# MoviePilot-Plugins

MoviePilot 自动签到插件

## 插件列表

### 站点自动签到 (AutoCkeckin)

自动签到 MoviePilot 中配置的所有 PT 站点。

**功能特性：**
- ✅ 支持 NexusPHP、Gazelle 等主流站点框架
- ✅ 自动检测签到页面（attendance.php 等）
- ✅ 支持排除特定站点（如需要验证码的站点）
- ✅ 签到结果通知推送
- ✅ Cron 定时执行
- ✅ API 手动触发

**安装方式：**
1. 在 MoviePilot 后台 -> 插件市场 -> 添加插件仓库
2. 输入本仓库地址：`https://github.com/xl-jeeter/MoviePilot-Plugins`
3. 找到"站点自动签到"插件，点击安装

**配置说明：**
| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| 启用插件 | 开启/关闭自动签到 | 关闭 |
| 开启通知 | 签到完成后发送通知 | 开启 |
| 签到周期 | Cron 表达式 | `0 8 * * *`（每天8点） |
| 排除站点 | 逗号分隔的站点名称 | 空 |

**API：**
- `GET /api/v1/autockeckin/checkin?apikey=xxx` - 手动触发签到

## 开发者

- 作者：xl-jeeter
- GitHub：https://github.com/xl-jeeter
