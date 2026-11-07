# 上下文插话判定

用一次极短的模型调用判断「这条消息值不值得主动接话」。⚠️ 机制差异：原版在调模型之前判定，判「不接」= 0 token；本项目只能在 AI 调用前（同步钩子）里用独立事件循环发判定请求，判「不接」是拦住回复，**省不下已经花掉的 token**。判定失败默认按「不接」处理（与原版一致，保守侧）。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_context_chime` |
| 插件 id | `context_chime` |
| 版本 | 1.0.0 |
| 分类 | message |
| 默认启用 | 否 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_context_chime/`） |
| 钩子 | on_pre_ai、on_pre_ai_async |
| 权限 | read_message |
| 设置项 | allowPrivate、blockOnJudgeFailure、blockOnTimeout、confidenceThreshold、cooldownSec、dailyCallLimit、denyGroups、enabled、judgeModel、judgeProbability、maxTokens、minChars、onlyGroups、promptExtra、timeoutMs、windowSize |
| 源码行数 | 487 |

## 安装

把整个 `pack_context_chime` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `context_chime`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`78e3ba2e4e6a9ba9…`），未做行为改动。
