# 对话完成判定

同一个人连着发消息时，别在人家话还没说完的时候插嘴。按内容判定：结尾悬着、落在连接词上、或者只有几个字 → 再多等一会儿；像一句问话、只是在喊人、说得比较长 → 照常回。（移植说明：JS 版靠宿主的唤醒倒计时仲裁，本项目只在当前一轮内延后等待，不会提前回复；多人同时说话时把说话人摘要告诉模型。）

| 项 | 值 |
| --- | --- |
| 包 id | `pack_turn_complete` |
| 插件 id | `turn_complete` |
| 版本 | 1.0.0 |
| 分类 | message |
| 默认启用 | 否 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_turn_complete/`） |
| 钩子 | on_pre_ai |
| 权限 | read_message |
| 设置项 | anchorOnly、capMs、contentJudge、enabled、maxDelayMs、quietMs、tellModel |
| 源码行数 | 308 |

## 安装

把整个 `pack_turn_complete` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `turn_complete`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`4357860f82ade866…`），未做行为改动。
