# @群友（按名字）

让机器人用名字 @ 群友：它在正文里写「@泡影之梦 你说得对」时，这里把名字认领成真正的 QQ @ 提醒（对方会收到红点），而不是一串没人看得到的普通字符。支持一次 @ 多人。认不出名字就按原样发送，绝不猜——猜错会 @ 到无关的人。（降级说明：群成员名单靠观察最近说过话的人累积，没说过话的人认不出来。）

| 项 | 值 |
| --- | --- |
| 包 id | `pack_at_mention` |
| 插件 id | `at_mention` |
| 版本 | 1.0.0 |
| 分类 | message |
| 默认启用 | 否 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_at_mention/`） |
| 钩子 | on_ingest、on_block、on_pre_ai、on_post_reply |
| 权限 | read_message, send_message |
| 设置项 | allowPartialMatch、debug、enabled、maxMentions |
| 源码行数 | 105 |

## 安装

把整个 `pack_at_mention` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `at_mention`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`14e0528c6428074a…`），未做行为改动。
