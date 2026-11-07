# QQ表情转译

把 [表情14] 这类数字占位符翻成 [表情:微笑]，让模型读懂 QQ 内置表情。新消息由传输层直接渲染；本插件兜底历史记录与合并转发里的旧格式。查不到的 id（限时/季节表情）保持原样，不会瞎编名字。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_face_decode` |
| 插件 id | `face_decode` |
| 版本 | 1.0.0 |
| 分类 | utility |
| 默认启用 | 是 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_face_decode/`） |
| 钩子 | on_pre_ai |
| 权限 | read_message |
| 设置项 | enabled、includeAssistant、userOnly |
| 源码行数 | 133 |

## 安装

把整个 `pack_face_decode` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `face_decode`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`57044b94a46eb54d…`），未做行为改动。
