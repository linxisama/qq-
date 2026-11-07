# 表情包识别记忆

缓存视觉模型成功识别的单张表情含义，按协议图片标识、完整链接或内联图片指纹复用。只记表情模式需要协议提供表情标记或小图尺寸，普通照片不会凭空被当作表情。识别失败不写入；多图消息仍正常识图，避免漏看未缓存的图。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_sticker_memory` |
| 插件 id | `sticker_memory` |
| 版本 | 1.0.0 |
| 分类 | media |
| 默认启用 | 是 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_sticker_memory/`） |
| 钩子 | （无钩子，仅提供设置项） |
| 权限 | store_data |
| 设置项 | enabled、maxCacheEntries、recheckCrossChatDays、recheckSameChatHours、skipThreshold、stickerOnly |
| 源码行数 | 333 |

## 安装

把整个 `pack_sticker_memory` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `sticker_memory`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`95ba75ebd0291bbd…`），未做行为改动。
