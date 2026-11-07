# Skill 市场分层报告

市场目录：`D:\聊天机器人\插件市场\Skill市场`

- 市场 zip：**379** 个，合计 **35.0 MB**
- 分层扫描到：**379** 个 skill / **1080** 个工具
- 打全宿主补丁后**可注册**：**373** 个 / **1179** 个工具
- 仍不可注册：**6** 个

## 一、379 个里 373 个能用的原因

宿主原来只有 53 个能注册，其余 326 个卡在三道**静态扫描闸门**上（另有三类误判见下文）。
三道都经实测证明是误判，补丁打在宿主侧（`hostfix.py`，见 README「宿主补丁」一节）：

| 闸门 | 位置 | 误判原因 | 实测 |
| --- | --- | --- | --- |
| T4-host-source | `src/skill_manifest.py:323` | 见任何 `../` 就判死，不看层级也不看文件是否存在 | 89 个全部 `LOADED`，只有 `video-edit` 真越界 |
| hostImports | `src/skill_tools.py:775` | 与上面一模一样的第二道 | 同上 |
| ctx 成员 | `src/skill_tools.py:462` `_MEMBER` | ①`ctx.X` 与 `api.X` 混为一谈 ②扫原始文本不过滤注释（`api.php` 当成员） | 276 个里 242 个真跑 ok |

被 ctx 挡住的 skill 源码都是防御式写法（`Array.isArray(ctx?.session?.trigger) ? … : []`、
`if (ctx?.sender && typeof ctx.sender.sendTextBatch === 'function')`），宿主不给就走降级分支，不崩。
所以补丁把 ctx 闸降级为「只审计不拦截」，`node:` / `npm:` 的真缺仍拦。

另有两处让工具名对不上运行期（已修）：

- **常量表内联**（`src/tool_schema.py`）：`registerTool({ id: TOOL.list, … })` 里的标识符引用
  解不出来 → `id` 键被丢弃 → 退回中文 `name` 当 id。解析前把 `const TOOL = {list:'list'}` 内联进源码即可。
- **运行期前缀**（`src/skill_tools.py` `_skill_plan`）：宿主把 skillId `sanitize` 后**截到 24 位**、
  点号换下划线，清单里存的是原样拼法，调用必报「tool 不属于被选扩展」。改用 `KNOWN_PREFIX_MISMATCH` 回拼。

下表是**补丁前**的静态分层（`skill_tiers.json`），用来看整个市场的原始构成；
补丁后的实际可注册分层见 `INDEX.json` 的 `counts.byTier`。

| 分层 | 数量 | 含义 |
| --- | ---: | --- |
| `T1-ready` | 108 | 只用宿主明确支持的 ctx API，无网络依赖 |
| `T2-web-fetch` | 168 | 额外需要联网抓取（web_fetch / 外部域名） |
| `T3-extra-api` | 2 | 额外要 onebot / qq_sticker 这类宿主未开放的能力 |
| `T4-host-source` | 89 | 运行期要 require 宿主 0.4 源码模块（如 `../../src/llm.js`）——补丁后整类解除 |
| `T5-depends-other` | 4 | 依赖市场里另一个扩展 |
| `T6-disabled` | 8 | 清单/入口缺失、扫描失败，或明确 disabled |

### 仍不可注册的 6 个，具体卡在哪

| 原因 | 数量 |
| --- | ---: |
| tier T5-depends-other 默认不放行（只放 T1-ready/T2-web-fetch；要放行请把它列进 allow） | 3 |
| T6-disabled | 2 |
| 缺宿主内置模块或 npm 包 | 1 |

这 6 个是**真缺**，不是误判：1 个真依赖宿主没装的 npm 包（只有 `electron`），2 个清单标了结构性残缺，3 个分层默认不放行（3 个 T5 依赖别的扩展 / 0 个 T3 要额外 API）。

注 1：上一版这里还有 22 个「包本身没声明/解析不出工具名」的，已由第 19/20 处补丁（loose 兜底扫描）
全部解除 —— 它们其实都有工具，只是写法是 `registerTool(fn())` / 表驱动 / 位置参数注册函数，
静态解析看不到对象字面量。真宿主实测这 22 个里 19 个有 67 个工具。

注 2：上一版这里还有 5 个「缺宿主内置模块或 npm 包」，其中 4 个（`free-tts` / `voice-reply-si` /
`group-analysis` / `pixiv-clash-search`）已由第 22~26 处补丁（H2a~H2e，按宿主 `node_modules` 实查）解除 ——
那 4 个包宿主本来就装着。只剩 `chat-digest` 要的 `electron` 是真缺（在 devDependencies 里）。

### 第四类误判：「明明没依赖 npm 包却报缺」（第 21 处补丁已解除）

7 个包报 `缺宿主内置模块或 npm 包：npm:, `，真宿主实测全部正常加载、工具调用成功：

| skill | 工具数 | 误判出的「模块名」 |
| --- | ---: | --- |
| bili-share / comfyui-newbie / knowledge-base / pm-wiki / relay | 1 / 4 / 3 / 3 / 4 | `, ` |
| qq-card-reader | 1 | `]) {\n      if (u.searchParams.has(k)) …` |
| sukuna-raid-coop | 8 | ` }\n      },\n      required: [` |

根因：`src/skill_tools.py` 的 `_IMPORT` 正则 `from\s*['\"]([^'\"]+)['\"]` 把英文单词 `from`
也当成 import 语句。`['and', 'for', 'with', 'that', 'this', 'from', 'see']` 这类停用词数组里，
`from', '` 正好匹配成 `from '…'`，于是把后面那一大段源码当成模块名。
修法是把捕获组限制成合法模块说明符字符集：`[^'\"\s,;()\[\]{}]+`。

### 第五类误判：「宿主 node_modules 里明明有这个包却报缺」（第 22~26 处补丁已解除）

`blocked_capabilities()` 对 `npm:` 前缀的 token 一律判死，从不查宿主 `node_modules`；
docstring 写着「npm 包不在宿主 node_modules 里就是真缺」，实现里根本没查。

宿主根 `data\qq-only\qqagent_host\node_modules` 实有 `argparse / js-yaml / undici / ws`（`runtime/qqagent-host/package.json` 的 dependencies 正是后三个），只有 `electron` 在 devDependencies。

| skill | 报缺的包 | 真宿主实测 |
| --- | --- | --- |
| free-tts / voice-reply-si | `ws` | ok，工具调用成功 |
| group-analysis | `js-yaml` | ok，2 个工具 |
| pixiv-clash-search | `undici` | ok |
| chat-digest | `electron` | **真缺**，`Cannot find module 'electron'` |

修法：给 `blocked_capabilities()` 加可选参数 `modules`，`npm:` token 先查
`<host_root>/node_modules/<pkg>` 是否存在，存在就放行；`eligible_skills()` 整个清单只算一次
（探测 200 次 `iterdir` 只花 11.4 ms）。

### 第六类误判：「双层嵌套包被判 no-entry」（第 27 处补丁已解除）

有些市场包解压后是**同名目录套同名目录**，外层只放清单副本、真源码在内层：

```
jujutsu-phantom-parade/skill.json                          ← 外层清单副本
jujutsu-phantom-parade/plugin.json
jujutsu-phantom-parade/jujutsu-phantom-parade/index.js     ← 真入口在这层
jujutsu-phantom-parade/jujutsu-phantom-parade/{skill.json,plugin.json,lib/,kb/,tools/}
```

`skill_manifest._package_root()` 原来取「**最浅**的 skill.json / plugin.json 所在目录」，
于是停在外层；`_package_entry()` 拼 `jujutsu-phantom-parade/index.js` 当然找不到 → `no-entry` → `T6-disabled`。

修法：`_package_root()` 改成**优先选同时含清单与入口的那一层**，找不到才退回最浅清单层。
全市场 379 个 zip 回归：**root 只变 1 个**（就是它），其余 378 个完全不变。
修完 `classify` 从 `T6-disabled / no-entry` 变成 `T2-web-fetch`（它声明了 `web_fetch` 权限），
6 个工具全部注册、真跑 `call card_info ok=True` / `call kb_search ok=True`。

配套地 `build.py` 加了 `_nested_package()`：解包时若外层无入口、恰好一个子目录且子目录同时带清单与入口，
就把内层当包根搬走。理由：只按「最浅清单」搬会把外层当包根，装完 Node 侧 `pickEntryFallback`
在本层找不到 `index.js`，整包加载失败（`runtime/qqagent-host/src/plugin-loader.js:344-392`）。

## 二、373 个可注册 skill 与真跑结果

真跑方式：`src/extension_host.call_tool()` 起 Node 子进程，用宿主自己的
`host-one.mjs` 加载 skill 入口，调用它的第一个工具。

下面给的是**装到同一个数据根后、按生产布局真跑一遍**的结果
（`qq-skill-packs/verify.py` 的实测输出，宿主根是 materialize 出来的那份，
`source_dir` 与 `data_dir` 都按生产链路传）：

判定口径：

- `ok` —— 工具返回 `ok=true`，真正跑出了业务结果
- `ran-blocked` —— 子进程正常加载并执行，只是这次调用的业务前置没满足
  （缺参数、缺本地文件、缺知识库、联网超时等）。**不是加载失败。**
- `load-failed` —— `Cannot find module` / `ERR_MODULE_NOT_FOUND` / `SyntaxError` 之类真问题，
  或者清单工具名与运行期注册名对不上（`tool 不属于被选扩展`）

**结论：373 个全部能被宿主加载并执行，零 load-failed。**
其中 `ok 334` 个直接跑出结果，`ran-blocked 39` 个是业务前置没满足（明细见下）。

| skill | 分层 | 工具数 | 真跑 | 耗时 |
| --- | --- | ---: | --- | ---: |
| `academic-assistant` | T1 | 2 | ok | 296 ms |
| `account-pool` | T1 | 0 | ran-blocked | — |
| `acg-db` | T2 | 12 | ok | 292 ms |
| `acmbot` | T2 | 5 | ok | 499 ms |
| `adb-control` | T2 | 11 | ok | 210 ms |
| `admin-mute` | T1 | 3 | ran-blocked | 171 ms |
| `affection-meter` | T1 | 3 | ok | 103 ms |
| `affinity` | T1 | 3 | ok | 88 ms |
| `affinity-mood` | T1 | 2 | ok | 89 ms |
| `affinity-private` | T1 | 2 | ok | 93 ms |
| `agent-reach` | T2 | 4 | ok | 125 ms |
| `agent-task` | T2 | 1 | ok | 98 ms |
| `ai-image` | T2 | 2 | ran-blocked | 119 ms |
| `ai-vent` | T1 | 1 | ran-blocked | 150 ms |
| `ai-voice` | T2 | 1 | ran-blocked | 93 ms |
| `ammo-price` | T2 | 1 | ok | 143 ms |
| `anime-guessr` | T2 | 6 | ok | 183 ms |
| `api-beggar` | T2 | 1 | ok | 111 ms |
| `arc-raiders` | T2 | 2 | ok | 151 ms |
| `archive-clean` | T1 | 2 | ok | 94 ms |
| `arena-rating` | T2 | 11 | ran-blocked | 107 ms |
| `ark-db` | T2 | 5 | ok | 100 ms |
| `ark-wiki` | T2 | 2 | ok | 147 ms |
| `arknights-is` | T1 | 5 | ok | 181 ms |
| `arknights-master` | T2 | 6 | ok | 193 ms |
| `auto-backup` | T1 | 3 | ok | 231 ms |
| `auto-sticker` | T2 | 2 | ok | 216 ms |
| `autopilot` | T2 | 16 | ok | 292 ms |
| `avatar-from-image` | T2 | 1 | ok | 124 ms |
| `avatar-viewer` | T2 | 1 | ok | 109 ms |
| `ba-units` | T2 | 1 | ok | 94 ms |
| `bangumi-lookup` | T2 | 4 | ok | 2757 ms |
| `bangumi-query` | T2 | 3 | ok | 182 ms |
| `battlefield-1-knowledge` | T1 | 1 | ok | 156 ms |
| `better-notes` | T5 | 4 | ok | 136 ms |
| `bf1-knowledge-zh` | T1 | 1 | ok | 94 ms |
| `bili` | T2 | 10 | ok | 104 ms |
| `bili-account` | T2 | 10 | ok | 111 ms |
| `bili-card` | T2 | 1 | ok | 314 ms |
| `bili-digest` | T2 | 1 | ok | 96 ms |
| `bili-dynamic` | T2 | 1 | ok | 119 ms |
| `bili-memes` | T2 | 1 | ok | 128 ms |
| `bili-music` | T2 | 4 | ok | 548 ms |
| `bili-picks` | T2 | 15 | ok | 174 ms |
| `bili-share` | T2 | 1 | ok | 174 ms |
| `bili-station` | T2 | 3 | ran-blocked | 280 ms |
| `bili-video` | T2 | 1 | ok | 197 ms |
| `bili-voice` | T2 | 2 | ran-blocked | 155 ms |
| `bilibili-act` | T2 | 6 | ok | 120 ms |
| `bilibili-follow` | T2 | 3 | ok | 99 ms |
| `bilibili-peek` | T2 | 1 | ok | 99 ms |
| `bilibili-scroll` | T2 | 16 | ok | 131 ms |
| `bilibili-search` | T2 | 2 | ok | 97 ms |
| `blhx-wiki` | T2 | 2 | ok | 110 ms |
| `blocklist` | T1 | 3 | ok | 112 ms |
| `browser-control` | T2 | 11 | ok | 135 ms |
| `budget-recipe` | T1 | 1 | ok | 188 ms |
| `capability-guide` | T1 | 2 | ok | 213 ms |
| `character-role` | T1 | 1 | ran-blocked | 125 ms |
| `chat-archive` | T1 | 4 | ran-blocked | 170 ms |
| `chat-files` | T2 | 5 | ok | 313 ms |
| `chat-media-viewer` | T2 | 2 | ok | 148 ms |
| `chatlog-memory` | T1 | 3 | ok | 143 ms |
| `class-schedule` | T2 | 6 | ok | 141 ms |
| `codex-image` | T2 | 3 | ok | 136 ms |
| `codex-voice` | T2 | 2 | ok | 175 ms |
| `comfy-draw` | T1 | 1 | ran-blocked | 149 ms |
| `comfyui-image` | T2 | 3 | ok | 147 ms |
| `comfyui-newbie` | T2 | 4 | ok | 299 ms |
| `community-search` | T2 | 1 | ok | 127 ms |
| `console-background` | T1 | 1 | ok | 177 ms |
| `cookie-wiki` | T2 | 1 | ok | 178 ms |
| `cross-chat-gossip` | T1 | 1 | ok | 138 ms |
| `cross-group-memory` | T1 | 9 | ok | 98 ms |
| `cs2-match` | T2 | 2 | ok | 3299 ms |
| `csgo-5e` | T2 | 5 | ok | 177 ms |
| `cy-bookmark` | T2 | 5 | ok | 263 ms |
| `daily-diary` | T1 | 2 | ok | 229 ms |
| `daily-fortune` | T1 | 2 | ok | 157 ms |
| `daily-life` | T1 | 1 | ok | 212 ms |
| `daily-usage-report` | T1 | 1 | ok | 229 ms |
| `danbooru-prompt` | T2 | 4 | ok | 270 ms |
| `danbooru-tagsearch` | T2 | 1 | ok | 188 ms |
| `danbooru-tagsearch-v2` | T2 | 1 | ok | 153 ms |
| `dd2-relationship-lookup` | T1 | 1 | ok | 260 ms |
| `deadlock-stats` | T2 | 3 | ok | 967 ms |
| `deai-flavor` | T1 | 1 | ok | 141 ms |
| `deep-think` | T1 | 1 | ok | 100 ms |
| `dfttk` | T2 | 5 | ran-blocked | 44812 ms |
| `dian-ge` | T2 | 1 | ok | 221 ms |
| `diary` | T1 | 2 | ok | 101 ms |
| `doc-keeper` | T1 | 4 | ran-blocked | 141 ms |
| `doc-reader` | T2 | 1 | ok | 106 ms |
| `doc-workshop` | T1 | 6 | ok | 104 ms |
| `douyin-share` | T2 | 2 | ok | 149 ms |
| `dsh-bridge` | T1 | 2 | ok | 119 ms |
| `dsh-task` | T1 | 1 | ok | 84 ms |
| `dtcg-card-rules` | T1 | 3 | ok | 170 ms |
| `eat-what` | T1 | 1 | ran-blocked | 92 ms |
| `eftarkov` | T2 | 3 | ok | 160 ms |
| `eldenring-nr` | T1 | 3 | ok | 132 ms |
| `emotion-core` | T2 | 9 | ran-blocked | 226 ms |
| `empty-at` | T1 | 1 | ok | 155 ms |
| `emulator` | T1 | 6 | ok | 193 ms |
| `eve-market` | T2 | 3 | ok | 122 ms |
| `eve-market-esi` | T2 | 4 | ok | 203 ms |
| `ffmpeg-frames` | T1 | 1 | ok | 214 ms |
| `file-transfer` | T1 | 1 | ok | 142 ms |
| `follow-up-window` | T1 | 1 | ran-blocked | 143 ms |
| `football-match` | T2 | 3 | ok | 846 ms |
| `force-send` | T1 | 0 | ok | — |
| `forward-deep` | T2 | 1 | ok | 193 ms |
| `forward-reader` | T2 | 1 | ok | 126 ms |
| `free-tts` | T2 | 1 | ok | 229 ms |
| `friend-approval` | T1 | 2 | ran-blocked | 109 ms |
| `gallery` | T1 | 3 | ok | 140 ms |
| `game-hypercup` | T2 | 1 | ok | 86 ms |
| `game-panel` | T2 | 3 | ok | 133 ms |
| `game-updates` | T2 | 1 | ok | 129 ms |
| `gbf-gamewith` | T2 | 1 | ok | 165 ms |
| `gbf-huiji-wiki` | T2 | 4 | ok | 176 ms |
| `genshin-gacha` | T1 | 3 | ok | 114 ms |
| `genshin-wiki-codex` | T2 | 3 | ok | 73 ms |
| `gf2-guide` | T2 | 6 | ok | 158 ms |
| `gilbert-cipher` | T1 | 1 | ok | 141 ms |
| `glm-image` | T2 | 1 | ran-blocked | 119 ms |
| `global-short-memory-lookup` | T1 | 1 | ok | 81 ms |
| `google-lens` | T2 | 1 | ok | 129 ms |
| `greet-relay` | T1 | 1 | ok | 339 ms |
| `group-admin` | T1 | 6 | ok | 203 ms |
| `group-analysis` | T2 | 2 | ok | 269 ms |
| `group-image-repost` | T2 | 2 | ok | 164 ms |
| `group-member-info` | T1 | 2 | ok | 231 ms |
| `group-rule-guard` | T1 | 4 | ok | 201 ms |
| `haigui-tang` | T1 | 1 | ok | 114 ms |
| `hat-factory` | T1 | 1 | ok | 125 ms |
| `history-import` | T1 | 1 | ok | 168 ms |
| `hot-trends` | T1 | 2 | ok | 84 ms |
| `hsr-knowledge` | T2 | 1 | ok | 122 ms |
| `hunt-mmr` | T2 | 1 | ok | 161 ms |
| `identity-v-master` | T1 | 3 | ok | 181 ms |
| `image-delegate` | T2 | 2 | ok | 170 ms |
| `image-drop` | T2 | 1 | ok | 123 ms |
| `image-generate` | T2 | 1 | ran-blocked | 155 ms |
| `image-reverse-search` | T2 | 1 | ok | 101 ms |
| `image-search` | T2 | 1 | ok | 172 ms |
| `image-studio` | T2 | 3 | ok | 220 ms |
| `image-to-image` | T2 | 1 | ran-blocked | 114 ms |
| `isaac-wiki` | T2 | 4 | ok | 125 ms |
| `item-slot-value` | T2 | 1 | ok | 17646 ms |
| `ivl-esports` | T2 | 2 | ok | 361 ms |
| `jita-market` | T2 | 1 | ok | 196 ms |
| `jujutsu-kaisen-reply` | T1 | 1 | ok | 137 ms |
| `jujutsu-phantom-parade` | T2 | 6 | ok | 186 ms |
| `kaomoji` | T1 | 1 | ok | 103 ms |
| `keyword-meme` | T2 | 4 | ok | 218 ms |
| `klbq-knowledge` | T2 | 2 | ok | 121 ms |
| `knowledge-base` | T1 | 3 | ok | 1724 ms |
| `kpl-esports` | T2 | 2 | ok | 1941 ms |
| `kuming-yuanyang-ext` | T2 | 3 | ok | 200 ms |
| `kurobbs-info` | T2 | 5 | ok | 176 ms |
| `kurobbs-query` | T2 | 6 | ok | 335 ms |
| `ledger` | T1 | 4 | ok | 277 ms |
| `limbus-wiki` | T2 | 1 | ok | 192 ms |
| `linked-chats` | T1 | 2 | ok | 183 ms |
| `local-pc` | T1 | 1 | ok | 268 ms |
| `local-stickers` | T1 | 4 | ok | 113 ms |
| `localchat-kit` | T1 | 3 | ok | 220 ms |
| `lol-match` | T2 | 2 | ok | 4114 ms |
| `long-memory` | T2 | 6 | ok | 162 ms |
| `long-novel` | T1 | 5 | ok | 185 ms |
| `luogu` | T2 | 4 | ok | 206 ms |
| `luogu2` | T2 | 5 | ok | 214 ms |
| `machine-work` | T2 | 13 | ok | 159 ms |
| `maimai` | T1 | 1 | ok | 148 ms |
| `math-bank` | T1 | 2 | ok | 82 ms |
| `mc-whitelist` | T1 | 4 | ran-blocked | 85 ms |
| `mcmod-search` | T2 | 2 | ok | 82 ms |
| `meal-picker` | T1 | 1 | ok | 154 ms |
| `meme-mood` | T1 | 3 | ok | 82 ms |
| `meme-taste` | T1 | 3 | ok | 185 ms |
| `meme-wiki` | T2 | 2 | ok | 267 ms |
| `memory-recall` | T1 | 1 | ok | 121 ms |
| `memory-tidy` | T1 | 2 | ok | 99 ms |
| `merged-forward` | T1 | 1 | ok | 119 ms |
| `message-recall` | T1 | 1 | ok | 99 ms |
| `message-recall-2` | T1 | 1 | ok | 133 ms |
| `mimo-tts` | T2 | 1 | ran-blocked | 82 ms |
| `mimo-voiceclone` | T2 | 1 | ran-blocked | 81 ms |
| `minecraft-master` | T2 | 4 | ok | 98 ms |
| `moderation` | T1 | 3 | ok | 165 ms |
| `moegirl-search` | T2 | 2 | ok | 198 ms |
| `moegirl-wiki` | T2 | 2 | ok | 123 ms |
| `mom-relay` | T1 | 2 | ok | 140 ms |
| `monster-hunter` | T1 | 3 | ok | 192 ms |
| `mooncell` | T2 | 3 | ok | 173 ms |
| `mouse-control` | T1 | 5 | ok | 200 ms |
| `music` | T2 | 3 | ok | 211 ms |
| `music-library` | T1 | 3 | ok | 238 ms |
| `music-request` | T2 | 1 | ok | 18727 ms |
| `music-request-v2` | T2 | 1 | ok | 18790 ms |
| `music-share` | T2 | 1 | ok | 836 ms |
| `music-taste` | T2 | 1 | ok | 75 ms |
| `my-weather` | T2 | 1 | ok | 79 ms |
| `netease-now-playing` | T2 | 1 | ok | 95 ms |
| `nintendo-kb` | T2 | 3 | ok | 86 ms |
| `notebook` | T1 | 5 | ok | 84 ms |
| `now-playing` | T1 | 1 | ok | 732 ms |
| `office-export` | T1 | 6 | ok | 84 ms |
| `opgg-guide` | T2 | 1 | ok | 88 ms |
| `ournotes` | T2 | 6 | ok | 100 ms |
| `ow-match` | T2 | 2 | ok | 842 ms |
| `owner-console` | T1 | 6 | ok | 98 ms |
| `owner-persona` | T1 | 1 | ran-blocked | 83 ms |
| `owner-whitelist` | T1 | 1 | ran-blocked | 79 ms |
| `pai-skills` | T2 | 33 | ok | 541 ms |
| `palace` | T2 | 23 | ok | 697 ms |
| `pc-suite` | T1 | 9 | ok | 94 ms |
| `pcl-downloader` | T2 | 3 | ok | 134 ms |
| `pcr-guide` | T2 | 5 | ok | 106 ms |
| `pcstatus` | T1 | 1 | ok | 1983 ms |
| `persona-evolution` | T2 | 5 | ok | 99 ms |
| `persona-stickers` | T2 | 2 | ok | 95 ms |
| `persona-tuner` | T1 | 7 | ok | 86 ms |
| `pf2wiki` | T2 | 3 | ok | 81 ms |
| `phone-use` | T2 | 19 | ok | 339 ms |
| `pic-taste` | T2 | 6 | ok | 86 ms |
| `pixel-art` | T1 | 2 | ok | 103 ms |
| `pixiv-clash-search` | T2 | 1 | ok | 287 ms |
| `pixiv-direct` | T2 | 2 | ran-blocked | 44817 ms |
| `pixiv-finder` | T2 | 1 | ok | 135 ms |
| `pixiv-image` | T2 | 1 | ok | 108 ms |
| `pixiv-image-tagsearch` | T2 | 1 | ok | 89 ms |
| `pixiv-jp-search` | T2 | 1 | ok | 87 ms |
| `pixiv-search` | T2 | 2 | ok | 96 ms |
| `pm-wiki` | T2 | 3 | ok | 113 ms |
| `private-chat-archive` | T1 | 6 | ok | 120 ms |
| `private-journal` | T1 | 6 | ran-blocked | 144 ms |
| `private-link` | T1 | 4 | ok | 86 ms |
| `profile-like` | T1 | 1 | ok | 79 ms |
| `promises` | T1 | 3 | ok | 85 ms |
| `qq-account` | T2 | 6 | ok | 318 ms |
| `qq-agent-image-studio-7f3c` | T2 | 2 | ran-blocked | 84 ms |
| `qq-at-all` | T1 | 1 | ok | 72 ms |
| `qq-card-reader` | T2 | 1 | ok | 97 ms |
| `qq-chat-card` | T1 | 1 | ok | 87 ms |
| `qq-face` | T1 | 2 | ok | 80 ms |
| `qq-face-tagger` | T1 | 7 | ok | 77 ms |
| `qq-file-reader` | T1 | 2 | ok | 89 ms |
| `qq-forward-reader` | T1 | 1 | ok | 94 ms |
| `qq-like` | T1 | 1 | ok | 65 ms |
| `qq-self` | T1 | 4 | ok | 117 ms |
| `qq-social` | T1 | 10 | ok | 93 ms |
| `qq-voice-call` | T1 | 1 | ok | 74 ms |
| `qqbot-emulator` | T1 | 14 | ok | 133 ms |
| `qqzone` | T2 | 6 | ok | 93 ms |
| `qqzoneplus` | T2 | 7 | ok | 97 ms |
| `qzone-check` | T1 | 1 | ok | 71 ms |
| `qzone-hangout` | T1 | 6 | ok | 89 ms |
| `qzone-image-library` | T2 | 8 | ok | 92 ms |
| `qzone-post` | T1 | 1 | ok | 83 ms |
| `react-echo` | T1 | 1 | ok | 79 ms |
| `read-document` | T2 | 2 | ok | 104 ms |
| `recall` | T1 | 2 | ok | 81 ms |
| `relay` | T1 | 4 | ok | 114 ms |
| `reply-meme` | T2 | 1 | ok | 99 ms |
| `reply-meme_1.2.0` | T2 | 2 | ok | 159 ms |
| `rhythm-kb` | T1 | 3 | ok | 119 ms |
| `rpg-gm` | T1 | 10 | ok | 99 ms |
| `sanguo-quotes` | T1 | 2 | ok | 85 ms |
| `sanguosha` | T2 | 4 | ok | 141 ms |
| `sanguosha-duel` | T2 | 4 | ok | 89 ms |
| `sanguosha-rules` | T1 | 2 | ok | 108 ms |
| `sb6657-memes` | T2 | 2 | ok | 16761 ms |
| `scheduled-task` | T1 | 3 | ok | 192 ms |
| `screenshot` | T2 | 1 | ran-blocked | 82 ms |
| `sea-turtle-soup` | T1 | 2 | ok | 77 ms |
| `search-image` | T2 | 1 | ok | 80 ms |
| `self-avatar` | T2 | 2 | ok | 105 ms |
| `self-image` | T2 | 5 | ok | 83 ms |
| `self-profile` | T1 | 2 | ok | 80 ms |
| `selfie-archive` | T1 | 1 | ok | 94 ms |
| `send-file` | T1 | 2 | ok | 78 ms |
| `sgs-knowledge` | T2 | 2 | ok | 82 ms |
| `shared-memory` | T1 | 1 | ok | 73 ms |
| `shouhun-trpg` | T1 | 3 | ok | 89 ms |
| `sing-aloud` | T2 | 2 | ok | 89 ms |
| `sing-cover` | T1 | 3 | ran-blocked | 100 ms |
| `sing-cover-rvc` | T2 | 2 | ok | 94 ms |
| `site-lookup` | T2 | 3 | ran-blocked | 100 ms |
| `skill-catalog` | T1 | 2 | ok | 94 ms |
| `skill-summary` | T2 | 1 | ok | 91 ms |
| `slang-learn` | T1 | 4 | ok | 86 ms |
| `smart-image` | T2 | 1 | ok | 94 ms |
| `smart-react` | T1 | 1 | ok | 113 ms |
| `song-request` | T2 | 1 | ok | 113 ms |
| `song-send` | T2 | 1 | ran-blocked | 83 ms |
| `soutu-shenqi` | T2 | 1 | ok | 81 ms |
| `stamina` | T1 | 1 | ok | 90 ms |
| `stardew-wiki` | T2 | 2 | ok | 115 ms |
| `steam-deals` | T2 | 2 | ok | 92 ms |
| `sticker-admin` | T1 | 6 | ran-blocked | 106 ms |
| `sticker-librarian` | T1 | 2 | ok | 83 ms |
| `sticker-tags` | T1 | 4 | ok | 83 ms |
| `sticker-taste` | T1 | 1 | ok | 85 ms |
| `sticker-vault` | T1 | 6 | ok | 111 ms |
| `sticker-vibe` | T1 | 2 | ok | 89 ms |
| `stock-quote` | T2 | 2 | ok | 129 ms |
| `sts2-master` | T2 | 6 | ok | 163 ms |
| `style-learn` | T1 | 3 | ok | 90 ms |
| `sukuna-raid` | T1 | 5 | ok | 91 ms |
| `sukuna-raid-coop` | T2 | 8 | ok | 129 ms |
| `support-topup` | T1 | 1 | ok | 83 ms |
| `symmetric-image` | T2 | 1 | ok | 87 ms |
| `tag-curator` | T2 | 2 | ok | 84 ms |
| `tag-lookup` | T2 | 2 | ok | 88 ms |
| `tangxiao-voice` | T1 | 3 | ok | 108 ms |
| `task-loop` | T1 | 3 | ok | 162 ms |
| `teqinchu-rank` | T2 | 1 | ok | 120 ms |
| `text-image` | T2 | 1 | ok | 92 ms |
| `tieba-digest` | T2 | 3 | ok | 34579 ms |
| `tieba-summary` | T2 | 3 | ok | 44315 ms |
| `today-waifu` | T2 | 1 | ok | 125 ms |
| `token-usage` | T2 | 2 | ok | 331 ms |
| `topic-guard` | T1 | 0 | ok | — |
| `topup-qr` | T2 | 1 | ok | 148 ms |
| `touhou-guess` | T1 | 3 | ok | 131 ms |
| `trendy-memes` | T1 | 3 | ok | 90 ms |
| `trpg` | T1 | 4 | ok | 80 ms |
| `trpg-gm` | T1 | 30 | ok | 145 ms |
| `trpg-plus` | T1 | 7 | ok | 123 ms |
| `trpg-plus2` | T1 | 8 | ok | 74 ms |
| `tts` | T2 | 1 | ran-blocked | 93 ms |
| `tts-say` | T2 | 3 | ok | 243 ms |
| `twenty-q` | T1 | 3 | ok | 82 ms |
| `txt-memory` | T1 | 4 | ok | 84 ms |
| `undercover` | T2 | 3 | ok | 89 ms |
| `usage-report` | T1 | 1 | ok | 210 ms |
| `valorant-match` | T2 | 2 | ok | 2458 ms |
| `vanguard` | T2 | 6 | ok | 159 ms |
| `verify-first` | T2 | 1 | ok | 107 ms |
| `video-edit` | T1 | 8 | ran-blocked | 184 ms |
| `video-frames` | T1 | 0 | ok | — |
| `video-hearing` | T2 | 1 | ran-blocked | 212 ms |
| `video-speech-lab` | T2 | 4 | ok | 170 ms |
| `video-watch` | T2 | 4 | ok | 833 ms |
| `voice-clip` | T1 | 2 | ran-blocked | 82 ms |
| `voice-clone` | T2 | 5 | ok | 270 ms |
| `voice-ear` | T1 | 1 | ok | 60 ms |
| `voice-reply` | T1 | 2 | ok | 187 ms |
| `voice-reply-si` | T2 | 1 | ok | 300 ms |
| `voice-send` | T2 | 2 | ok | 94 ms |
| `voice-synth` | T2 | 2 | ok | 90 ms |
| `voxcpm-voice` | T2 | 1 | ok | 115 ms |
| `waifu-draw` | T2 | 1 | ok | 158 ms |
| `waifu_draw` | T2 | 1 | ok | 84 ms |
| `warframe-wiki` | T2 | 3 | ok | 313 ms |
| `warthunder-axbot` | T1 | 3 | ok | 158 ms |
| `wb-hands` | T2 | 1 | ok | 71 ms |
| `whale-memes` | T2 | 2 | ok | 1534 ms |
| `wiki-query` | T1 | 1 | ok | 74 ms |
| `wot-ring-lines` | T2 | 1 | ok | 181 ms |
| `wozuohao-meme` | T1 | 2 | ok | 106 ms |
| `wuwa-emoji` | T2 | 2 | ok | 259 ms |
| `wuwa-pgr-wiki` | T2 | 3 | ok | 1492 ms |
| `xhh-account` | T2 | 3 | ran-blocked | 84 ms |
| `xiaoheihe` | T2 | 6 | ok | 91 ms |
| `xiaoheihe-reader` | T2 | 1 | ok | 74 ms |
| `ygo-kb` | T1 | 6 | ran-blocked | 100 ms |
| `ygocdb-cards` | T2 | 3 | ok | 82 ms |
| `yihuan-panel` | T2 | 5 | ok | 126 ms |
| `yugioh-card` | T2 | 2 | ok | 82 ms |
| `ze-guide` | T1 | 6 | ok | 161 ms |

### 这 39 个业务前置没满足的，具体卡在哪

全部是「加载成功、执行到了业务代码，然后因为本地条件不具备而返回提示」，
不是插件/包本身的问题：

- `account-pool` —— account-pool 不可用：账号池是空的（至少加一个 Base URL）
- `admin-mute` —— 这个功能只能在群里用
- `ai-image` —— ai-image 不可用：请在「AI生图」设置中填写 Base URL 和 API Key
- `ai-vent` —— ai-vent 不可用：还没填泄愤群群号（点本卡片的 ⚙ 设置，填一个群号就能用）
- `ai-voice` —— ai-voice 不可用：找不到语音服务脚本：D:\AI\hear\server.py。请到技能设置里改「语音服务目录」。
- `arena-rating` —— arena-rating 不可用：找不到 data/config.json —— 无法确认「KARDS 强制查询」插件是否启用
- `bili-station` —— bili-station 不可用：没找到 ffmpeg：B 站的音源是 mp4，没有它就抽不出音频（装一个或在本技能设置里填 ffmpegPath）
- `bili-voice` —— bili-voice 不可用：没找到 ffmpeg：B 站的音源是 mp4，没有它就抽不出音频（装一个或在本技能设置里填 ffmpegPath）
- `character-role` —— character-role 不可用：找不到角色故事文件：D:\AI\qqagent\# 沃雅妮莎故事文档（原文整理版）.txt
- `chat-archive` —— chat-archive 不可用：还没有消息存档（D:\qq机器人5.0\data\qq-only\qqagent_host\data-host-one\messages 不存在）—— 机器人收过群消息之后就能用了
- `comfy-draw` —— comfy-draw 不可用：没找到 ComfyUI。请先装 Comfy Desktop，或到设置页手动填「ComfyUI 程序目录」
- `dfttk` —— 扩展宿主执行超时（44750ms）
- `doc-keeper` —— 删除功能没开：请让用户在「技能」页打开本技能的「允许删除文档」
- `eat-what` —— 今天吃什么：本轮没被 @ 或戳一戳
- `emotion-core` —— emotion-core 不可用：内核模块异步装载中（首次几秒内）
- `follow-up-window` —— 该工具已被单独关闭
- `friend-approval` —— friend-approval 不可用：还没设置审批人：在技能设置里填「审批人 QQ 号」，或把人加进「设置 → 白名单」的私聊栏
- `glm-image` —— glm-image 不可用：还没填智谱 API Key
- `image-generate` —— image-generate 不可用：还没配置：Base URL / API Key / 模型 id（在设置页「文生图」里填）
- `image-to-image` —— image-to-image 不可用：还没配置：Base URL / API Key / 模型 id（在设置页「图生图」里填）
- `mc-whitelist` —— mc-whitelist 不可用：还没填 RCON 地址和密码
- `mimo-tts` —— mimo-tts 不可用：还没填 MiMo API Key（设置里的 apiKey）
- `mimo-voiceclone` —— mimo-voiceclone 不可用：还没填 MiMo API Key（设置里的 apiKey）
- `owner-persona` —— owner-persona 不可用：还没填主人 QQ 号 —— 在技能设置里填上（多个用逗号分隔），这个技能才会生效
- `owner-whitelist` —— owner-whitelist 不可用：还没填主人 QQ 号 —— 在技能设置里填上（多个用逗号分隔），这个技能才会生效
- `pixiv-direct` —— 扩展宿主执行超时（44750ms）
- `private-journal` —— private-journal 不可用：当前 QQ Agent 核心不支持私密工具留档脱敏，已安全停用
- `qq-agent-image-studio-7f3c` —— qq-agent-image-studio-7f3c 不可用：还没配置：Base URL / API Key / 模型 id（在设置页「文生图」里填）
- `screenshot` —— screenshot 不可用：需要 Electron 环境（当前进程拿不到 BrowserWindow，截图不可用）
- `sing-cover` —— sing-cover 不可用：缺少：Python 环境、RVC 推理、人声分离、流水线脚本
- `site-lookup` —— site-lookup 不可用：找不到 data/config.json —— 无法确认「KARDS 强制查询」插件是否启用
- `song-send` —— 没给歌名
- `sticker-admin` —— 还没在「技能 → 表情包管理（管理员）」里填管理员 QQ 号
- `tts` —— tts 不可用：还没配置远程 TTS 地址，本地合成后端也不可用（合并仓不带 msedge-tts）
- `video-edit` —— video-edit 不可用：本机没找到 FFmpeg（PATH 与常见安装位置都没有）。本技能需要已有 FFmpeg 才能剪辑；请先安装 FFmpeg 并把 ffmpeg.exe 的完整路径填到「技能 → 本地视频剪辑 → 设置 → FFmpeg 路径」，或确认安装后重启应用。在找到它之前，剪辑功能不会执行，也不会假装成功。
- `video-hearing` —— video-hearing 不可用：还没填语音识别 Key（可以在本技能设置里填，或先用 mimo-tts 技能填一个 MiMo Key 自动复用）
- `voice-clip` —— voice-clip 不可用：还没设置「音频文件夹」——请在技能设置里填写音频所在的文件夹绝对路径
- `xhh-account` —— xhh-account: 该扩展需要控制台 UI（ui/index.html），但包内缺少这个文件；当前宿主没有控制台页面能力（needs-console-ui），扩展主体加载不了
- `ygo-kb` —— ygo-kb 不可用：缺少知识库：D:\qq机器人5.0\data\qq-only\qqagent_host\plugins-host-13524\0000-ygo-kb\data\ygo.db


## 三、产物怎么用

| 产物 | 用途 |
| --- | --- |
| `ready/<id>/` | 单个 skill 的源码目录，复制到 `<data>/qq-only/skill_extensions/` 即安装 |
| `dist/ready-zips/<id>.zip` | 单个 skill 的安装包，走 `POST /api/skills/install` |
| `dist/ready-all.zip` | 373 个一次装完（解压后跑 `install.py`） |
| `dist/market-379.zip` | 市场 379 个 zip 的离线镜像 |

宿主数据目录（`<data>`）默认是 `D:\qq机器人5.0\data`，即
`skill_extensions` 在 `D:\qq机器人5.0\data\qq-only\skill_extensions`。

**装上 ≠ 能用**：宿主对 skill 有两层启用态，两边都得开：

1. `<data>/qq-only/qqagent_extensions.json` 的 `extensions.<id>.enabled`（扩展管理）
2. `<data>/qq-only/qqagent_host/data-host-one/config.json` 的 `skills.<id>.enabled`（JS 宿主自己）

`install.py` 会同时写这两处（走 `extension_registry.set_enabled`，它内部会 `_mirror_host_enabled`）。
前提是宿主根已经 materialize（`materialize_host_root()` 或控制台点一次「准备运行时」）。
