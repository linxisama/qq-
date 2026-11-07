# 打字速度

在句子之间插入打字延迟标记，模拟真人打字节奏。「媒体消息也分段」关掉时，带图片/表情的回复不再拆句 —— 否则媒体段与文字会被拆开成两条消息，看起来像机器人漏发了图。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_send_pacing` |
| 插件 id | `send_pacing` |
| 版本 | 1.0.0 |
| 分类 | rhythm |
| 默认启用 | 否 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_send_pacing/`） |
| 钩子 | on_post_reply |
| 权限 | send_message |
| 设置项 | baseMs、enabled、maxMs、maxMsPerChar、mediaPacing、minMs、minMsPerChar |
| 源码行数 | 119 |

## 安装

把整个 `pack_send_pacing` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `send_pacing`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`10ec4aed6627326a…`），未做行为改动。
