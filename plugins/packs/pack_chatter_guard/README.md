# 水聊免回

连着发表情包、或者一直说水话的时候，机器人就不接了（连模型都不叫醒，0 token）。只认三类明确的水：纯表情/图片、命中水词表（哈哈、草、6、。。。、笑死…）、同一个字重复或全是标点。**不用「字数太少」当判据**——那会误伤「在吗」「谢谢」「几点」。中间插一句正常话就重新计数。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_chatter_guard` |
| 插件 id | `chatter_guard` |
| 版本 | 1.0.0 |
| 分类 | message |
| 默认启用 | 否 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_chatter_guard/`） |
| 钩子 | on_block |
| 权限 | read_message |
| 设置项 | alwaysReplyWhenAtMe、enabled、exemptKeyword、fillerWords、skipFiller、skipMedia、threshold、windowSec |
| 源码行数 | 215 |

## 安装

把整个 `pack_chatter_guard` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `chatter_guard`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`57c52db22a351644…`），未做行为改动。
