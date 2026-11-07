# 人设存档隔离

切换人设后分开对话历史与个人记忆，再切回来可继续原有存档；不会删除或搬走用户文件。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_archive_isolation` |
| 插件 id | `archive_isolation` |
| 版本 | 1.0.0 |
| 分类 | utility |
| 默认启用 | 是 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_archive_isolation/`） |
| 钩子 | （无钩子，仅提供设置项） |
| 权限 | store_data |
| 设置项 | enabled、protectKeys |
| 源码行数 | 23 |

## 安装

把整个 `pack_archive_isolation` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `archive_isolation`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`3cf2793fa79a20d0…`），未做行为改动。
