# 表情包管理

点击“管理表情库”查看缩略图、搜索、上传、修改标签与含义、让AI识图及删除本地收藏。只管理机器人自己的本地库，不同步删除QQ收藏，也不改写核心程序。手动图库仍在“表情包与自定义图库”中配置。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_sticker_admin` |
| 插件 id | `sticker_admin` |
| 版本 | 1.0.0 |
| 分类 | media |
| 默认启用 | 是 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_sticker_admin/`） |
| 钩子 | （无钩子，仅提供设置项） |
| 权限 | read_message |
| 设置项 | enabled、gifFrames |
| 源码行数 | 11 |

## 安装

把整个 `pack_sticker_admin` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `sticker_admin`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`0fe72a66dad3cc8b…`），未做行为改动。
