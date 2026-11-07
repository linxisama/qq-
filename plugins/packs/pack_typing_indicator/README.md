# 正在输入提示

私聊（可选群聊）里让机器人像真人一样亮起「正在输入…」：从它决定要回话到消息发出之间，对方会看到正在输入。零 token：不改提示词、不注册工具、不调模型，只在对的时机补发状态包。（需要协议端支持 set_input_status；官方接口不支持，此模式下不生效。）

| 项 | 值 |
| --- | --- |
| 包 id | `pack_typing_indicator` |
| 插件 id | `typing_indicator` |
| 版本 | 1.0.0 |
| 分类 | utility |
| 默认启用 | 否 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_typing_indicator/`） |
| 钩子 | on_pre_ai |
| 权限 | read_message |
| 设置项 | cooldownSec、enabled、eventType、minDelayMs、privateOnly、showTyping |
| 源码行数 | 161 |

## 安装

把整个 `pack_typing_indicator` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `typing_indicator`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`9d44fd7ab6103e3d…`），未做行为改动。
