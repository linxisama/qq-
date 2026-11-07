# 自动语音

按 explicit/text/voice/both 策略把回复朗读成语音并发送。默认 explicit 且关闭；群聊未点名不自动朗读；语音失败回文字并说明。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_voice_reply` |
| 插件 id | `voice_reply` |
| 版本 | 1.0.0 |
| 分类 | voice |
| 默认启用 | 否 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_voice_reply/`） |
| 钩子 | on_pre_ai、on_post_reply |
| 权限 | read_message, send_message |
| 设置项 | enabled、fallbackToText、groupRequiresName、maxChars、mode |
| 源码行数 | 101 |

## 安装

把整个 `pack_voice_reply` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `voice_reply`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`34001b3001122618…`），未做行为改动。
