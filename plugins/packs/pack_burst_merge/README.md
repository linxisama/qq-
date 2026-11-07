# 连发合并

同一人在短时间内连续发消息时，等他发完再一起回复。被 @ 或被叫昵称时**不等待**、立刻回；其余情况对方静默 quietMs（默认 0.6 秒）就开口，最长不超过合并窗口 capMs。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_burst_merge` |
| 插件 id | `burst_merge` |
| 版本 | 1.0.0 |
| 分类 | rhythm |
| 默认启用 | 是 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_burst_merge/`） |
| 钩子 | on_pre_ai |
| 权限 | read_message |
| 设置项 | capMs、enabled、quietMs |
| 源码行数 | 65 |

## 安装

把整个 `pack_burst_merge` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `burst_merge`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`38ffd7a6b91be3d9…`），未做行为改动。
