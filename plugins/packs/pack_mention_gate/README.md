# 点名闸门

给机器人加一道点名闸门：① 名单里的群只在被 @ 或戳一戳时才开口（其余消息不调模型）；② 精确到某个群的某个人（名单外的人照常回复）；③ 名单之外的群可以完全不受影响，也可以谁叫都不理。@ 按 QQ 号判定，重名不会误判。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_mention_gate` |
| 插件 id | `mention_gate` |
| 版本 | 1.0.0 |
| 分类 | message |
| 默认启用 | 是 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_mention_gate/`） |
| 钩子 | post_load、on_block、on_pre_ai |
| 权限 | read_message |
| 设置项 | enabled、group_ids、mode、prompt_note、user_rules |
| 源码行数 | 289 |

## 安装

把整个 `pack_mention_gate` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `mention_gate`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`249b9ed9018aa0ef…`），未做行为改动。
