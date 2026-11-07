# 关键词自动回复

消息包含关键词时直接返回预设回复，不经过AI

| 项 | 值 |
| --- | --- |
| 包 id | `pack_keyword_reply` |
| 插件 id | `keyword_reply` |
| 版本 | 1.0.0 |
| 分类 | utility |
| 默认启用 | 否 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_keyword_reply/`） |
| 钩子 | validate_settings、on_ingest |
| 权限 | read_message |
| 设置项 | enabled、rules |
| 源码行数 | 47 |

## 安装

把整个 `pack_keyword_reply` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `keyword_reply`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`7e15f3a1a915d7a1…`），未做行为改动。
