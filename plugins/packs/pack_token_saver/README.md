# Token 节流

移植自社区插件 token-saver，并按本项目的真机数据加强：① 历史滑窗裁剪，更早的内容压成一行摘要（只截取原文，不生成新内容）；② 截断历史里过长的单条内容（转发摘要/图片描述/网页正文这类每轮都要重发的长文本）；③ 删掉内容完全重复的轮次；④ 整段对话超过字数上限时从最早的轮次开始删（system 与当前这轮永不删除）。实测单轮 prompt 平均 1897 token、输出只有 25 token，所以这里省的每一字都直接省钱。全程只做减法，出错静默放行。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_token_saver` |
| 插件 id | `token_saver` |
| 版本 | 1.0.0 |
| 分类 | utility |
| 默认启用 | 是 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_token_saver/`） |
| 钩子 | on_pre_ai |
| 权限 | read_message, store_data |
| 设置项 | dedupeDuplicates、enabled、historyMediaChars、historyMode、keepRecentMessages、maxContentChars、maxDigestChars、maxPromptChars、verbose |
| 源码行数 | 229 |

## 安装

把整个 `pack_token_saver` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `token_saver`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`cfa5ac2a8b59693f…`），未做行为改动。
