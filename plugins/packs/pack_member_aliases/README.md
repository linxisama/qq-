# 群友外号对照

移植自社区插件 member-aliases：谁在说话就告诉模型这人还叫什么；消息里出现某人的外号时，告诉模型指的是谁 —— 命中才加几行，没命中一个字不加。外号表可用口令维护：外号 / 外号 加 <QQ号> <外号> / 外号 删 <QQ号> <外号>（管理员或主人）；可选自动从"我叫X"里学（默认关）。

| 项 | 值 |
| --- | --- |
| 包 id | `pack_member_aliases` |
| 插件 id | `member_aliases` |
| 版本 | 1.0.0 |
| 分类 | knowledge |
| 默认启用 | 否 |
| 挂载通道 | 目录 mod（`custom_plugins/pack_member_aliases/`） |
| 钩子 | on_pre_ai、on_ingest |
| 权限 | read_message, store_data |
| 设置项 | autoLearn、enabled、maxLines、scanMentions、verbose |
| 源码行数 | 243 |

## 安装

把整个 `pack_member_aliases` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
或在控制台「插件 → 本地插件包」里选中这个目录。

`custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
安装版通常在 `%LOCALAPPDATA%\WhaleGirlQQ\data\qq-only\custom_plugins`。

## 兼容性

入口文件里的 `META.id` 仍是 `member_aliases`，与内置插件同名，挂载后会
**顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
`ef475a2bca83fcbd…`），未做行为改动。
