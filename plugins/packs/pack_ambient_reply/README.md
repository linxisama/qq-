# 群聊随机接话

监控群聊，在没人 @ 机器人时按概率偶尔自然接话（像群友一样参与聊天）。带冷却与每小时上限，避免刷屏；只对已监听群生效，不处理命令与通知。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_ambient_reply` |
| 插件 id | `ambient_reply` |
| 版本 | 1.0.0 |
| 分类 | social |
| 默认启用 | 是 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_ambient_reply/`） |
| 钩子 | wants_reply |
| 权限 | read_message |
| 设置项 | activeHours、boostQuestion、cooldownSec、enabled、groups、ignorePrefix、maxPerHour、minChars、percent |
| 源码行数 | 117 |

## 安装

把整个 `pack_ambient_reply` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `ambient_reply`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`62fdb9ee1e528cc4…`），未做行为改动。
