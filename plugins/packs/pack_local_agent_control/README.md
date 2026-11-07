# 本地电脑操作

主人私聊“电脑 状态/能力/打开X/音量N/暂停媒体”生成动作提案，在本地控制台批准后由 Windows Agent 执行（首版 L0/L1）。群聊/引用不触发；审批绑定参数；结果只回原私聊。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_local_agent_control` |
| 插件 id | `local_agent_control` |
| 版本 | 1.0.0 |
| 分类 | agent |
| 默认启用 | 否 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_local_agent_control/`） |
| 钩子 | on_ingest |
| 权限 | read_message |
| 设置项 | devices、emergencyStop、enabled、ownerIds |
| 源码行数 | 156 |

## 安装

把整个 `pack_local_agent_control` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `local_agent_control`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`570fd5888d144a65…`），未做行为改动。
