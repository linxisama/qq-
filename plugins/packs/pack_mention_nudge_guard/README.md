# 重复艾特忽略

同一人短时间内多次@时，提示机器人冷静应对

| 项 | 值 |
| --- | --- |
| 包 id | `pack_mention_nudge_guard` |
| 插件 id | `mention_nudge_guard` |
| 版本 | 1.0.0 |
| 分类 | rhythm |
| 默认启用 | 是 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_mention_nudge_guard/`） |
| 钩子 | on_pre_ai |
| 权限 | read_message |
| 设置项 | enabled、maxMentions、windowSec |
| 源码行数 | 59 |

## 安装

把整个 `pack_mention_nudge_guard` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `mention_nudge_guard`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`50b7067b39aff873…`），未做行为改动。
