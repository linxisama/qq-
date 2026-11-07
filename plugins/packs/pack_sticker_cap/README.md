# 表情包库上限

防止有人一直发表情包把库和磁盘撑爆：按数量上限做 LRU 淘汰、按磁盘配额清理、可屏蔽指定人的表情。只管理机器人实际收藏的表情库和索引，不删除外部目录或手动图库；收集由“偷表情包”插件完成，/表情容量 可查看用量。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_sticker_cap` |
| 插件 id | `sticker_cap` |
| 版本 | 1.0.0 |
| 分类 | media |
| 默认启用 | 否 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_sticker_cap/`） |
| 钩子 | on_ingest、tick |
| 权限 | read_message, send_message |
| 设置项 | blockedSenders、checkIntervalSec、dryRun、enabled、maxItems、maxSizeMb、stickerDir |
| 源码行数 | 240 |

## 安装

把整个 `pack_sticker_cap` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `sticker_cap`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`75dc90417b84de5a…`），未做行为改动。
