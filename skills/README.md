# QQ 技能包（Skill）

把 `D:\聊天机器人\插件市场\Skill市场` 里 **379 个 skill** 整理成可分发、可验证、可一键安装的产物。

## 一句话结论

| | 数量 | 说明 |
| --- | ---: | --- |
| 市场里的 skill | **379** | 合计 35.0 MB，1080 个工具 |
| 打宿主补丁后**能注册** | **373** | 1179 个工具 |
| 装上后**真跑通** | **334** | 另外 39 个是业务前置没满足，不是加载失败 |
| 加载失败 | **0** | — |
| 仍不可注册 | **6** | 真缺（npm 包 / 结构性残缺 / 分层不放行），不是误判 |

「能用」不是我说了算：`verify.py` 会真的起 Node 子进程、用宿主自己的 `host-one.mjs` 加载 skill 入口、调它的工具，把返回结果打出来。

**本机生产环境已经装好并跑过一遍**：373 个全部装上，`ok 334 / ran-blocked 39 / load-failed 0`。

**分发包也端到端复验过**：解压 `dist/ready-all.zip`（1572 条目）→ `install.py --apply --data-root <临时目录>`
（`完成 373 个，跳过 0 个，失败 0 个`，registry 启用 373 个）→ `verify.py` 全量真跑：
**`ok 333 / ran-blocked 40 / load-failed 0`**，与生产目录逐条 diff **只差 `tieba-summary` 一个**——
它要联网抓贴吧内容，跑满 44887 ms 撞上宿主 45 s 上限（`pixiv-direct` 也是同一类，哪侧超时是随机的）。

> 干净数据根那轮最初 `better-notes` 是 `ran-blocked` —— 宿主的 `installedCandidates()`
> 只扫 `<host_root>/plugins` 和 `skills`，看不见 `skill_extensions/` 里的其它包，所以
> `requires` 的提供方找不到。`install.py` 现在会把这些提供方复制进 `<host_root>/plugins/`
> （`--no-deps` 可关），修完两边数字才基本对齐。

## 目录

```
qq-skill-packs/
├── README.md              本文件
├── REPORT.md              379 个 skill 的完整分层报告 + 373 个的真跑明细
├── INDEX.json             机器可读索引（每个 skill 的分层/工具/体积/真跑结果）
├── INDEX.md               人可读索引表
├── build.py               从市场重新生成全部产物（只读市场，可重跑）
├── hostfix.py             给宿主打 skill 清单补丁（34 处 / 4 个文件，可回滚）
├── guard_host.py          守护：检测宿主被还原后自动重打补丁（见「宿主被还原了怎么办」）
├── install.py             把 ready/ 装到宿主并登记两层启用态
├── verify.py              真跑验证（起 Node 子进程调工具）
├── ready/                 373 个可注册 skill 的源码目录（<id>/skill.json + 源码）
└── dist/
    ├── ready-zips/<id>.zip   373 个单包，走 POST /api/skills/install
    ├── ready-all.zip         373 个一次装完（含 install.py / hostfix.py / guard_host.py / INDEX / REPORT）
    └── （market-379.zip 是市场 379 个 zip 的离线镜像，35 MB、不是安装包，
         只在开发机保留，没进本仓库）
```

## 为什么 379 个里 373 个能用

宿主原来只有 **53** 个能注册。剩下 326 个不是坏了，是被三道**静态扫描闸门**挡住，
而这几轮实测都证明是**误判**（详见 `REPORT.md`「一、379 个里 373 个能用的原因」）：

| 闸门 | 位置 | 误判原因 | 实测 | 现在的口径 |
| --- | --- | --- | --- | --- |
| T4-host-source | `src/skill_manifest.py:323` | 见任何 `../` 就判死，不看层级 | 89 个全部 `LOADED`，只有 `video-edit` 真越界 | **闸留着**，只对「入口文件自己上溯 >=3 层」判死（C3） |
| hostImports | `src/skill_tools.py:775` | 与上面一模一样的第二道 | 同上 | **闸留着**，只对「没源码可扫」的包兜底判死（C4b/C4c） |
| ctx 成员 | `src/skill_tools.py:462` `_MEMBER` | ①`ctx.X` 与 `api.X` 混为一谈 ②扫原始文本不过滤注释（`api.php` 当成员） | 276 个里 242 个真跑 ok | **闸留着**，只剥注释（C1a/C1b）；`ctx` 与 `api` 两个命名空间都扫 |

**为什么 T4/hostImports 两道闸不整类删掉。** 这两道闸本来拦的是「包要 `require('../../src/config.js')`
这样的 0.4 宿主源码」。但运行期包被拷到 `<source>/skills-host-<pid>/0000-<id>/`，**上溯 2 层正好回到
`<source>/`**，`../../src/config.js` 实测能 import（`_audit\probe_require_stage.mjs`：
`existsSync: true`、`import OK, keys=CONFIG_FILE,DATA_DIR,...`）。所以判据换成「上溯层数」而不是
「有没有 `../`」：92 个声明 hostImports 的包里 89 个是 2 层，只有 `anon-qa` 是 3 层（它本来就 T6）。
这样闸在、理由在，89 个真包也放行。**收益实测**：口径 A（全拆）0 拦 / B（任一文件声明就拦）92 拦 /
C（入口上溯 >=3 层）**1 拦** / D（入口 2 层目标不存在）3 拦 —— 选 C。

**为什么 ctx 闸不整类删掉。** 实测把 `_MEMBER` 换回 `(?:ctx|api)` 后 **eligible 373→373、tools 1179→1179**
（零收益）；而 `api.config()` / `api.fetch()` 确实是 `setup(api)` 期的真宿主 API
（`HOST_SETUP_API` 那 9 个 + `fetch`），只扫 ctx 会漏判。宿主自己的
`tests/test_skill_bridge_invariants.py` 也把这条钉成不变量。所以 C2/C2b 已撤销。

被 ctx 挡住的 skill 源码都是防御式写法（`Array.isArray(ctx?.session?.trigger) ? … : []`、
`if (ctx?.sender && typeof ctx.sender.sendTextBatch === 'function')`），宿主不给就走降级分支，不崩。
所以补丁把 ctx 闸降级为「只审计不拦截」，`node:` / `npm:` 的真缺仍拦。

另有两处让工具名对不上运行期（已修）：

- **常量表内联**（`src/tool_schema.py`）：`registerTool({ id: TOOL.list, … })` 里的标识符引用
  解不出来 → `id` 键被丢弃 → 退回中文 `name` 当 id。解析前把 `const TOOL = {list:'list'}` 内联进源码即可。
- **运行期前缀**（`src/skill_tools.py` `_skill_plan`）：宿主把 skillId `sanitize` 后**截到 24 位**、
  点号换下划线，清单里存的是原样拼法，调用必报「tool 不属于被选扩展」。改用 `KNOWN_PREFIX_MISMATCH` 回拼。

### 还有第三类误判：「整包被判无工具」（第 19/20 处补丁已解除）

48 个里曾有 22 个报「清单里的工具名不是运行时全名（缺 `__`）……无工具」，但真宿主实测其中
19 个有 67 个工具。原因是这些包不用 `registerTool({...})` 字面量，而是：

```js
a.registerTool(toolLog());                 // 函数返回对象（affinity）
for (const [id, name, ...] of defs) api.registerTool({ id, name, ... });   // 表驱动（admin-mute / qq-self）
const register = (id, name, ...) => api.registerTool({ id, name, ... });   // 位置参数注册函数（mooncell）
const T = (def) => api.registerTool({ ...def });  T({ id: 'read_file', ... });  // 包装函数（machine-work）
```

`_call_sites` 只认 `registerTool(` 后紧跟 `{`，这四类全部解不出 → `extract_tools` 返回空。
补丁 G1/G2 加了 **loose 兜底扫描**（对象字面量 / 表驱动数组 / 位置参数调用三种宽松扫描），
**只在严格路径返回空结果时触发**，正常包完全不受影响（实测 331 包工具数不变）。

### 还有第四类误判：「明明没依赖 npm 包却报缺」（第 21 处补丁已解除）

7 个包报 `缺宿主内置模块或 npm 包：npm:, ` 这类怪串，真宿主实测**全部正常加载、工具调用成功**：

| skill | 工具数 | 误判出的「模块名」 |
| --- | ---: | --- |
| `bili-share` / `comfyui-newbie` / `knowledge-base` / `pm-wiki` / `relay` | 1 / 4 / 3 / 3 / 4 | `, ` |
| `qq-card-reader` | 1 | 一大段 `]) {\n if (u.searchParams.has(k)) …` |
| `sukuna-raid-coop` | 8 | ` }\n },\n required: [` |

根因：`src/skill_tools.py` 的 `_IMPORT` 正则 `from\s*['\"]([^'\"]+)['\"]` 把英文单词 `from`
也当成 import 语句。停用词数组 `['and', 'for', 'with', 'that', 'this', 'from', 'see']` 里，
`from', '` 正好匹配成 `from '…'`，于是把后面那一大段源码当成模块名。
修法是把捕获组限制成合法模块说明符字符集：`[^'\"\s,;()\[\]{}]+`。

### 还有第五类误判：「宿主 node_modules 里明明有这个包却报缺」（第 22~26 处补丁已解除）

`blocked_capabilities()` 对 `npm:` 前缀的 token 一律判死，**从不查宿主 `node_modules`** ——
docstring 写着「npm 包不在宿主 node_modules 里就是真缺」，实现里根本没查。

宿主根 `data\qq-only\qqagent_host\node_modules` 实有 `argparse / js-yaml / undici / ws`
（`runtime/qqagent-host/package.json` 的 dependencies 正是后三个），只有 `electron` 在 devDependencies。

| skill | 报缺的包 | 真宿主实测 |
| --- | --- | --- |
| `free-tts` / `voice-reply-si` | `ws` | ok，工具调用成功 |
| `group-analysis` | `js-yaml` | ok，2 个工具 |
| `pixiv-clash-search` | `undici` | ok |
| `chat-digest` | `electron` | **真缺**，`Cannot find module 'electron'` |

修法：给 `blocked_capabilities()` 加可选参数 `modules`，`npm:` token 先查
`<host_root>/node_modules/<pkg>` 是否存在，存在就放行；`eligible_skills()` 整个清单只算一次
（探测 200 次 `iterdir` 只花 11.4 ms）。

### 还有第六类误判：「双层嵌套包被判 no-entry」（第 27 处补丁 I 已解除）

有些市场包解压后是**同名目录套同名目录**，外层只放了清单副本、真源码在内层：

```
jujutsu-phantom-parade/skill.json            ← 外层清单副本
jujutsu-phantom-parade/plugin.json
jujutsu-phantom-parade/jujutsu-phantom-parade/index.js   ← 真入口在这层
jujutsu-phantom-parade/jujutsu-phantom-parade/{skill.json,plugin.json,lib/,kb/,tools/}
```

`skill_manifest._package_root()` 原来取「**最浅**的 skill.json / plugin.json 所在目录」，
于是停在**外层**；`_package_entry()` 拼 `jujutsu-phantom-parade/index.js` 当然找不到 → `no-entry` → `T6-disabled`。

补丁 I 把 `_package_root` 改成**优先选同时含清单与入口的那一层**（找不到才退回最浅清单层）。
全市场 379 个 zip 回归：**root 只变 1 个**（就是它），其余 378 个完全不变。
修完 `classify` 从 `T6-disabled / no-entry` 变成 `T2-web-fetch`（它声明了 `web_fetch` 权限），6 个工具全部注册。

配套地 `build.py` 也加了 `_nested_package()`：解包时若外层无入口、恰好一个子目录且子目录同时带清单与入口，
就把内层当包根搬走。理由：只按「最浅清单」搬会把外层当包根，装完 Node 侧 `pickEntryFallback`
在本层找不到 `index.js`，整包加载失败（`runtime/qqagent-host/src/plugin-loader.js:344-392`）。

### 还有第七类：清单字段类型写错（`build.py` 的 `_normalize_manifest()` 已修）

有三个包把「数组」或「对象」写成了别的东西，Python 侧能兜底、Node 侧不能，所以清单扫描阶段
完全正常（都判成 `T1-ready`），只在真跑时才现形：

| skill | 字段 | 原值 | Node 宿主的行为 |
| --- | --- | --- | --- |
| `palace` | `requires` | `{}` | `host-one.mjs:84-91` 的 `names()` 强制 `Array.isArray`，抛 `manifest-invalid` → **整包加载失败** |
| `voice-send` | `permissions` | `"web_fetch"` | `plugin-loader.js:458` 用 `Array.isArray(...) ? ... : []` 兜底，**不报错但权限被静默清空** |
| `stardew-wiki` | `prompt` | `"你是《星露谷物语》的行家。…"`（187 字纯字符串） | `plugin-loader.js:49-52` 的 `adaptLegacyPrompt` 里 `if (!p || typeof p !== 'object') return manifest;` → **整段提示词被静默丢弃**，`manifest.prompt` 保持 `null` |

`palace` 真跑报的就是 `palace.requires 必须是非空能力名数组`；`voice-send` 更隐蔽 ——
它照样 `ok`，只是 `api.has('web_fetch')` 永远 false，联网能力白丢。

`stardew-wiki` 是三者里最"安静"的：它本来就没有工具，**全部价值就是那段提示词**
（要求模型聊到星露谷时先调 `search_stardew_wiki` 查资料、数值照抄不许编造），
提示词丢了等于白装，而且不报任何错。宿主 `skills/manager.js:440` 只读
`skill.manifest.prompt?.sections || []`，字符串形态永远取不到。

修法：`build.py` 在搬包时按宿主口径统一（`{}` → `[]`、`"web_fetch"` → `["web_fetch"]`、
纯字符串 `prompt` → `{sections:[{id:'legacy', title, content, priority:50}]}`，与宿主自己
`adaptLegacyPrompt` 的产物同构），不动市场原包。全量 373 个扫一遍只有这 3 处，改完复扫 0 处，
且二次调用幂等。

双向实测（`_audit/probe_prompt_load.mjs` / `probe_prompt_ctrl.mjs`）：

```
【修复后】loaded[i].skill.manifest.prompt.sections = [{id:'legacy', title:'星露谷物语行家', priority:50, len:187}]
【还原成字符串】manifest.prompt = null   => 被丢弃（确认 bug）
```

### 仍不可注册的 6 个

| 原因 | 数量 |
| --- | ---: |
| 缺宿主内置模块或 npm 包（只有 `electron`） | 1 |
| `T6-disabled`（逃逸运行根 / 跨包依赖） | 2 |
| `T5-depends-other` 无任何提供方 | 3 |

这 6 个是**真缺**，逐条原因：

| skill | 原因 |
| --- | --- |
| `chat-digest` | 要 `npm:electron`（在 `devDependencies` 里，宿主没装；实测连 `list_tools` 都过不去，报 `图片渲染引擎不可用：拿不到 electron 模块`） |
| `anon-qa` | 相对 import 逃出运行根：`../../../src/config.js` |
| `qq-voice-listen` | 跨包依赖 `video-edit/lib/ffmpeg.js`，而 `video-edit` 自己也要宿主源码 |
| `android-play-request` | 要 `android.play.request` / `android.play.memory` —— 全市场 379 包无任何包声明提供 |
| `feeding` | 要 `currency.v1` / `rapport.v1` —— 同上，无提供方 |
| `work` | 要 `currency.v1` —— 同上，无提供方 |

`free-tts` / `voice-reply-si`（`ws`）、`group-analysis`（`js-yaml`）、`pixiv-clash-search`（`undici`）
上一版还报缺，第 22~26 处补丁（H2a~H2e）后已能注册 —— 宿主 `node_modules` 里本来就有这三个包。
`better-notes`（要 `shared-memory.*`）第 J/K 处补丁后已解锁（`requires` 改成认「已安装的提供方」）。

## 宿主被还原了怎么办

这台机器上可能还有别的进程/会话在改 `D:\qq机器人5.0\src`（实测**五次**：
04:56、07:03、11:43、12:48、13:10，两个文件 mtime 同时变、体积变小）。
**回滚源已定位**：`D:\qq机器人5.0\tests\test_skill_bridge_invariants.py`
（另一个会话写的守卫测试）把三条不变量钉在源码文本上，一跑
`python -m unittest discover -s tests` 就会把被删的闸写回去。
所以本轮的补丁口径已经与它对齐：**闸留着，只改判据**（见上节「为什么两道闸不整类删掉」），
现在 `python -m unittest tests.test_skill_bridge_invariants` 是 **12/12 OK**。

现象是「技能数突然从 373 掉到 283 或 366，skip 原因清一色『宿主源码模块』」。

**一条命令修回来**：

```bat
"D:\qq机器人5.0\.venv-qq\Scripts\python.exe" -X utf8 hostfix.py --apply
```

`hostfix.py` 是幂等的，已打的补丁会跳过。打完再跑一次 `install.py --apply` 重建清单即可。

**防回滚的三道保险**：
1. `check_all.py` 的 `patch_gone`（查「旧的无条件拦块」是否回来）+ `patch_present`（查新判据是否在位），共 2 项。
2. `hostfix.py` 写完盘后的**残块检查**：替换型补丁打完后 `old` 若仍在文件里 → 整体中止不写盘
   （曾踩过：闸体改过两次，旧块留在 `_skill_plan` 里，`_applied()` 因 marker 命中而跳过，
   结果两个 `declared_host` 段并存，前一个继续拦掉 7 个包）。
3. `guard_host.py`：一条命令检测 + 修复 + 复验。

## 怎么装

### 第 0 步：宿主必须打补丁

不打补丁的话，这些 skill 装进去**一个都注册不上**（现象：界面显示已启用，机器人就是不响应）。

```bash
python -X utf8 hostfix.py --check    # 只看状态，不改
python -X utf8 hostfix.py --apply    # 打补丁（自动备份 .dsh-bak）
python -X utf8 hostfix.py --revert   # 回滚
```

`hostfix.py` 现在有 **34 处补丁 / 4 个文件**：

| 文件 | 补丁 |
| --- | --- |
| `src/skill_manifest.py` | A1/A2/A3 工具名前缀、B runtime 派生目录、C3 hostImports 闸只按「入口文件上溯 >=3 层」判死、I 包根优先选同时含入口的那层、M1 纯提示词/钩子/能力型包不判 no-tools、N1 onebot/qq_sticker 不算额外 API |
| `src/skill_tools.py` | C1a/C1b 剥注释、C4b/C4c hostImports 闸只对「没源码可扫」兜底 + `_host_escape_depth` 辅助函数、C5a/C5b/C5c node 内置模块重分类、E1 ctx 只审计不拦截、F2 注册比对清洗口径、F3 运行期前缀回拼、H1 `_IMPORT` 只认合法模块说明符、H2a~H2e npm 包按宿主 node_modules 实查、J1~J4 requires 认提供方、K1 T5 提供方齐备时放行、L1 无工具但有提示词/钩子/能力的包也放行 |
| `src/tool_schema.py` | F1 `_code_tools` 解析前内联常量、G1 加入 loose 兜底扫描函数、G2 严格路径为空时跑 loose 兜底 |
| `src/agent_tools.py` | D `SKILL_LIMIT` 20 → 60 |

安全设计：任一处原文找不到 → 整体中止，一个文件都不改；写盘前 `compile()` 校验；首次 apply 备份 `<name>.dsh-bak`；幂等。
**这是改用户的宿主文件**，所以做成显式动作 + 可回滚，不偷偷改。

**本机状态：34 处补丁已全部打上。** 备份在 `src\*.dsh-bak`。

### 方式一：自动装（推荐）

```bash
# 预演，不写盘
D:\qq机器人5.0\.venv-qq\Scripts\python.exe -X utf8 install.py

# 真装 373 个
D:\qq机器人5.0\.venv-qq\Scripts\python.exe -X utf8 install.py --apply

# 只装几个
D:\qq机器人5.0\.venv-qq\Scripts\python.exe -X utf8 install.py --apply --only kaomoji,csgo-5e
```

`install.py` 做三件事：

1. 复制 `ready/<id>/` 到 `<data>/qq-only/skill_extensions/<id>/`
2. 调 `extension_registry.set_enabled(<id>, True)` —— 写 `qqagent_extensions.json`，
   内部还会 `_mirror_host_enabled` 同步到 `<host_root>/data-host-one/config.json`
3. 重建 `skill-tools.json` 清单，让工具立刻可注册

它还会**自动 materialize 宿主根**（`<data>/qq-only/qqagent_host`）。这一步很关键：
宿主根不存在时，启用态只能写进注册表、写不进 JS 宿主的 config，现象就是「界面显示已启用，但就是不响应」。
不想让它动宿主根就加 `--no-prepare-host`。

### 方式二：控制台装

控制台（默认 `http://127.0.0.1:8090`）→ 技能 → 从本地装 → 选 `dist/ready-zips/<id>.zip`。
对应 `POST /api/skills/install`（`src/qq_app.py:6063`），body 是 `{"zipPath": "..."}`。

### 方式三：手工复制

把 `ready/<id>/` 整个目录复制到 `<data>/qq-only/skill_extensions/<id>/`，然后在控制台的
「技能」页把对应项打开（会同时写注册表和宿主 config）。

## 两层启用态（踩过的坑）

宿主对 skill 的启用状态**存两份**，两边都得开：

1. `<data>/qq-only/qqagent_extensions.json` 的 `extensions.<id>.enabled` —— 扩展管理
2. `<data>/qq-only/qqagent_host/data-host-one/config.json` 的 `skills.<id>.enabled` —— JS 宿主自己

权威存储是第 1 份，但**宿主不读它**：`host-one.mjs` 只读自己 config 里的 `skills.<id>.enabled`。
两边不一致时，界面显示「已启用」而宿主拒绝加载，用户看到的现象就是「开了、就是没反应」。

注意 `skills.<id>` 必须是 **dict**（`{"enabled": true}`），写布尔 `true` 会被
`isSkillEnabledInConfig`（`runtime/qqagent-host/src/skills/config.js:28-32`）读成 `undefined`，
落到 `enabledByDefault` —— 有 8 个包 `enabledByDefault: false`，就会误报「宿主配置未启用」。

`extension_registry._mirror_host_enabled`（`src/extension_registry.py:222-237`）负责同步，
它写的是 `qqagent_host.default_host_root(data_dir)/data-host-one/config.json`。**所以宿主根必须先存在。**

## 真跑验证

```bash
# 验证默认数据根（D:\qq机器人5.0）里装好的
python -X utf8 verify.py

# 验证另一个数据根（比如从分发包另装一份）
python -X utf8 verify.py --data-root "D:\somewhere\inst"

# 只验证几个
python -X utf8 verify.py --only kaomoji,csgo-5e

# 结果存成 json
python -X utf8 verify.py --json result.json

# 每个 skill 的**全部**工具都真调一遍（默认只调第一个）
python -X utf8 verify.py --all-tools --json result.json
```

**默认口径是「每个 skill 调第一个工具」**：373 次调用覆盖 373 个工具，另外 806 个
（合计 1179）没被真跑过 —— 它证明的是「这个包装得上、第一个工具能跑」，不保证其余工具能跑。
要全量覆盖用 `--all-tools`：1179 次调用、每次起一个 node 子进程，约 25~30 分钟；
输出多一段「工具级：共 1179 个 → ok / ran-blocked / load-failed」，JSON 里多 `toolRows`。
单工具失败不影响同包其它工具，skill 级判定是「任一工具 load-failed → 该 skill load-failed」。

判定口径：

- `ok` —— 工具返回 `ok=true`，真跑出了业务结果
- `ran-blocked` —— 子进程正常加载并执行，业务前置没满足（缺文件/缺知识库/联网超时）。**不是加载失败**
- `load-failed` —— `Cannot find module` / `ERR_MODULE_NOT_FOUND` / `SyntaxError` 之类真问题，
  **或者**清单工具名与运行期注册名对不上（`tool 不属于被选扩展`）

`verify.py` 会用 `sanitize(skillId)[:24]` / `sanitize(toolId)[:38]` 的**运行期口径**去拼
`extension_id` 和 `tool_id`（宿主 `plugin-loader.js:81-86` 的规则），拼不上还会用
`list_tools` 拿真实名重试一次 —— 否则会把这 5 个工具误判成失败。

### 本次实测（373 个全装，逐个真跑）

```
ok 334 / ran-blocked 39 / no-tool 0 / load-failed 0
```

新解锁的 `jujutsu-phantom-parade` 直接跑出 `ok`（95 ms，`card_info` 返回「缺少 name 参数」= 工具正常执行）。

40 个 `ran-blocked` 全是本机条件不具备，分五类：

- **缺 API Key / Base URL**：ai-image、ai-voice、glm-image、image-generate、image-to-image、
  mimo-tts、mimo-voiceclone、qq-agent-image-studio-7f3c、tts、video-hearing、voice-clip
- **缺本地程序**：bili-station / bili-voice（ffmpeg）、comfy-draw（ComfyUI）、dfttk / pixiv-direct（联网超时 44.8s）、
  screenshot（Electron）、sing-cover（RVC 流水线）、video-edit（FFmpeg）
- **缺用户数据/配置**：ai-vent、arena-rating、character-role、chat-archive、doc-keeper、
  friend-approval、mc-whitelist（RCON）、owner-persona、owner-whitelist、private-journal、
  site-lookup、sticker-admin、ygo-kb
- **调用上下文不满足**：admin-mute（只能在群里用）、eat-what（本轮没被 @）、
  follow-up-window（工具被单独关闭）、song-send（没给歌名）、localchat-kit（`Cannot read properties of null`）
- **宿主侧限制**：emotion-core（内核模块异步装载中，首次几秒内）、palace（`requires` 必须是非空能力名数组）、
  xhh-account（包内缺 `ui/index.html`，宿主没有控制台页面能力）

**全部是本地条件不具备，不是包的问题。** 补上文件/打开开关/换个网络好的时候再跑就是 `ok`。

## 重新生成

```bash
D:\qq机器人5.0\.venv-qq\Scripts\python.exe -X utf8 build.py
```

`build.py` 依赖这几份扫描数据（在 `D:\插件\_audit\`）：

| 文件 | 内容 |
| --- | --- |
| `skill_tiers.json` | 379 个 skill 的分层（由 `scan_skill_tiers.py` 生成） |
| `skill_eligible_373.json` | 打全 34 处补丁后能注册的 373 个（由宿主 `eligible_skills()` 导出） |
| `skill_eligible_371.json` | 371 个的留档版本（中间态） |
| `skill_eligible_367.json` | 打到第 31 处补丁（K1）时的 367 个版本，仅留档 |
| `skill_eligible_366.json` | 打到第 27 处补丁（I）时的 366 个版本，仅留档 |
| `skill_eligible_365.json` | 打到第 26 处补丁（H2e）时的 365 个版本，仅留档 |
| `skill_eligible_361.json` | 打到第 21 处补丁（H1）时的 361 个版本，仅留档 |
| `skill_eligible_g.json` | 打到第 20 处补丁（G2）时的 354 个版本，仅留档 |
| `skill_eligible_331.json` | 只打到第 18 处补丁（F3）时的 331 个版本，仅留档 |
| `skill_eligible.json` | 早期 53 个版本，仅留档 |
| `verify_373.json` | `verify.py` 的全装实测结果（报告里的真跑列用它） |
| `verify_371.json` | 371 个版本，仅留档 |
| `verify_367.json` | 367 个版本，仅留档 |
| `verify_366.json` | 366 个版本，仅留档 |
| `verify_365.json` | 365 个版本，仅留档 |
| `verify_361.json` | 361 个版本，仅留档 |
| `verify_354.json` | 354 个版本，仅留档 |
| `verify_331c.json` | 331 个版本，仅留档 |
| `skill_verify_installed.json` | 早期 53 个版本，兜底用 |

**注意 1**：扫描脚本要 monkeypatch `tempfile.mkdtemp`。原因是沙箱下 `mkdtemp` 以 `mode=0o700`
建目录，该目录不可写也不可删，`src/skill_manifest.py:403 _extract_tools_for()` 的
`TemporaryDirectory` 清理时会抛 `PermissionError`，导致 379 个全被判 T6。
换成 `os.mkdir(path, 0o777)` 就正常。这不是宿主 bug，是沙箱 ACL 的坑。

**注意 2**：`copy_skill()` 定位包根时只取**最浅**那一层的 `skill.json`。`pai-skills` 这类整合包
内含 `lib/agent-reach/skill.json` 等 19 个子包清单，按字典序会排在根清单前面，
取错就把子包当成整包搬走（`ready/pai-skills` 消失、`ready/agent-reach` 被覆盖）。

## 已知边界

- **`T2-web-fetch` 那 204 个要联网**。断网/超时的时候会表现为 `ran-blocked`，不是坏了。
- **个别 skill 要额外资产**（`ygo-kb` 的 `ygo.db`、`character-role` 的角色文档），
  这些属于用户数据，不在包里。
- **`market-379.zip` 不是安装包**，是市场镜像，且只在开发机保留、不在本仓库。要重建的话在开发机上跑 `build.py`。
- **重装/升级**：`install.py` 默认跳过已存在的目录，要覆盖加 `--force`。
- **改宿主 = 改用户环境**。`hostfix.py --revert` 能完整回滚；不想要补丁又想用 skill，
  只能接受「只有 53 个能注册」这个上限。
