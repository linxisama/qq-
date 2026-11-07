# 语音转文字（QQ 原生）

通过普通 QQ / OneBot 协议端的 fetch_ptt_text 接口转写语音。默认关闭，是否可用取决于当前协议端；失败时明确说明，不能猜测。官方接入附件自带的转写文字由消息链路直接读取，无需开启本插件。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_speech_to_text_qq` |
| 插件 id | `speech_to_text_qq` |
| 版本 | 1.0.0 |
| 分类 | media |
| 默认启用 | 否 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_speech_to_text_qq/`） |
| 钩子 | on_prepare、on_pre_ai |
| 权限 | read_message |
| 设置项 | budgetMs、debugLog、enabled、timeoutMs |
| 源码行数 | 214 |

## 安装

把整个 `pack_speech_to_text_qq` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `speech_to_text_qq`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`44677a3688a5449b…`），未做行为改动。
