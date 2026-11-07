# 鲸鱼娘情绪与精力

维护角色的心情、精力和压力，随时间恢复；只在消息发送成功后更新。/状态 可查看当前角色状态。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_emotion_state` |
| 插件 id | `emotion_state` |
| 版本 | 1.0.0 |
| 分类 | social |
| 默认启用 | 是 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_emotion_state/`） |
| 钩子 | on_ingest、on_pre_ai、on_sent |
| 权限 | read_message, send_message, store_data |
| 设置项 | autoUpdate、enabled、injectPrompt |
| 源码行数 | 58 |

## 安装

把整个 `pack_emotion_state` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `emotion_state`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`b1db729bd2c0daec…`），未做行为改动。
