# 提前收尾（省 token）

移植自 JS 插件 early-finish。已交付完毕、没有遗留动作的这一轮，不再为可选的锦上添花动作多花一次模型调用：跳过“该不该接话”的判定调用和“让 AI 选表情”的选择调用。有工具失败、结尾是“我去看看”这类预告、或预告要交图却没交时，一律按正常流程走。不碰提示词、不改人设、不拦发言；“试运行”只记日志不真的省。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_early_finish` |
| 插件 id | `early_finish` |
| 版本 | 1.0.0 |
| 分类 | utility |
| 默认启用 | 否 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_early_finish/`） |
| 钩子 | on_sent |
| 权限 | send_message |
| 设置项 | dryRun、enabled、skipAiReaction、skipJudge、windowSec |
| 源码行数 | 174 |

## 安装

把整个 `pack_early_finish` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `early_finish`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`ed26b118798537b1…`），未做行为改动。
