# Pixiv 插图（pixiv_illust）

- 版本：5.2.51
- 分类：media
- 默认启用：否

## 功能

启用后发 /插图 关键词，读取配置的Lolicon兼容服务并发送真实图片，附作品及作者来源。当前接入全年龄图片；Pixiv直连和Cookie模式尚未验证，不能只改开关就使用。默认关闭。

## 安装

1. 打开鲸鱼娘 QQ 控制台 →「插件中心」；
2. 点「添加插件」→「浏览…」，选择本压缩包；
3. 点「检查」，确认名称、说明与安全检查通过；
4. 勾选「覆盖同名插件」（更新时）和「安装后立即启用」；
5. 点「确认安装」。

安装后可在插件列表里调整参数；不需要时在插件中心删除。

## 配置项

| 键 | 名称 | 类型 | 默认值 | 说明 |
|---|---|---|---|---|
| `enabled` | 启用 | bool | `False` |  |
| `searchBackend` | 搜索后端 | select | `auto` | auto = 按可用情况挑；lolicon 用第三方 API；pixiv 直连搜索。 |
| `loliconApiUrl` | Lolicon API 地址 | string | `https://api.lolicon.app/setu/v2` | 留空 = 用默认地址。需要联网才能用。 |
| `searchUrlTemplate` | 搜索地址模板 | string | `None` | 占位符 {kw}（关键词）与 {page}（页码）；缺失时会自动追加。 |
| `imageUrlTemplate` | 图片地址模板 | string | `None` | 占位符 {pid}（作品号）与 {page}（页码）。 |
| `cookie` | Pixiv Cookie（敏感） | string | `` | 本插件不读不写这个值，只由你手动填写；接入取图时才用得上。 |
| `userAgent` | User-Agent | string | `` |  |
| `proxyUrl` | 代理地址 | string | `` | 留空 = 不使用代理。 |
| `excludeAI` | 排除 AI 作品 | bool | `False` |  |
| `poolSize` | 候选池大小 | int | `20` |  |
| `maxCount` | 单次最多几张 | int | `3` |  |
| `ratings` | 按会话分级 | string | `` | 形如 group:123=r18,private:456=sfw；值取 sfw/r18/all。 |
| `allowR18` | 允许 R18 | bool | `False` | 默认关。 |
| `ownerIds` | 主人 QQ（逗号分隔） | string | `` |  |
| `adminIds` | 管理员 QQ（逗号分隔） | string | `` |  |
| `stateCap` | 已见作品记录上限 | int | `200` | 超过后淘汰最旧的记录。 |
| `retryCandidates` | 失败后重试候选数 | int | `5` |  |
| `deadTtlDays` | 失效链接保留天数 | int | `7` |  |
| `timeoutMs` | 请求超时（毫秒） | int | `10000` |  |

## 注意

- 插件是外部代码，安装后会被加载执行，请只使用可信来源；
- 依赖外部服务的插件（搜索、图片站、语音等）需要相应网络或本机组件；
- 与聊天主链路无关的插件默认关闭，按需开启。
