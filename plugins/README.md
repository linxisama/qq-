# QQ 工作台插件独立包（5.2.112）

把 `D:\qq机器人5.0\src\plugins\` 里的内置插件和能力桥，拆成 **66 个可以单独安装、单独卸载** 的插件包。

| 项 | 值 |
| --- | --- |
| 宿主版本 | 5.2.112 |
| 插件总数 | 66（内置 63 + 宿主未自动加载的 3 个） |
| 目录 mod 包 | 32（`packs/`，整目录复制即挂载） |
| 裸 .py 覆盖包 | 34（`overrides/`，单文件，需登记 `custom_plugins.json`） |
| 源码补丁 | 1（`qqagent_bridge`，随包发货） |
| 宿主补丁 | 3（`qq_app` / `ai_engine` / `chat_state`，见 `patches/`，仅能力桥扩张需要） |
| 逐包验证 | 66/66 通过 |
| 全量共存验证 | 66/66 挂载，0 拒载 |
| **本机生产环境** | **已装 66 个，安装后复验通过** |

## 为什么不是 67 个

`src/plugins/` 下有 67 个 `.py`，其中 **`face_names.py` 不是插件**——整文件只有一个
`FACE_NAMES` 静态字典，被 `face_decode` 等插件 import 当数据用，没有 `PluginBase`
子类。它留在宿主里：目录 mod 的模块 `__package__` 被强制成 `src.plugins`
（`src/plugins/manager.py:1378`），所以 `from .face_names import FACE_NAMES` 仍然解析到
宿主那个模块，不需要随包发货（`face_decode` 另有空字典兜底，缺了也能跑）。

另外 3 个（`audio_assets_config`、`local_agent_control`、`voice_reply`）源码在、
但不在 `PLUGIN_MODULES` 里，宿主不会自动加载；拆成目录包后反而能被正常挂载。

## 两条通道，怎么选

宿主的插件加载器有两条并行通道（`src/plugins/manager.py:1340-1362`），
本目录按插件实际用到的 `runtime` 成员自动分流：

### 目录 mod（32 个）

入口只访问 `ModRuntime` 门面的 9 个成员（`mod_id / api_version / settings / get /
has_permission / register_tool / log / note / now`），可以走受限通道。

* 落点：`custom_plugins/<pack_id>/`（`plugin.json` + `<id>.py` + `README.md`）
* **不登记** `custom_plugins.json`，以磁盘 `plugin.json` 为唯一事实
* 钩子有 2 秒超时围栏，超时跳过、连续 3 次失败自动禁用
* 入口里的 `META.id` 保持内置原名，挂载后**顶替**内置实现；删掉目录即恢复内置版

### 裸 .py 覆盖（34 个）

两类原因，判定理由逐条记在 `INDEX.json` 的 `channel_reason`（可同时命中）：

1. **门面不提供它要的成员**（30 个）——要读 `runtime.mode / account() / db / ai /
   onebot / plugins / style / config / pc / reply_meta / stickers / ...`
2. **钩子里有耗时不可控的 IO**（6 个：`hot_trend_tracker`、`search_query_hygiene`、
   `share_card`、`qqagent_bridge`、`market_probe`、`pixiv_illust`，后两个同时属于第 1 类）
   ——它们联网或起子进程，超时预算 4~6 秒甚至更久，撞上目录 mod 的 2 秒围栏会被
   **整个钩子跳过**：功能静默消失，比崩溃更难查

走覆盖通道时拿的是**活 QQRuntime**，行为与内置版逐字节一致。

* 落点：`custom_plugins/<id>.py`，**必须**写进 `custom_plugins.json` 的
  `{"plugins": ["<id>", ...]}`，否则重启后不加载
* 第 1 类里还有一种更隐蔽的：`getattr(runtime, 'chat_state', None)` 这类三参写法在
  门面下不抛错，但永远拿到 `None`，功能**静默失效**——所以判 override 是保行为，
  不是仅防崩

## 目录结构

```
qq-plugin-packs/
├── packs/<pack_id>/          32 个目录 mod 包（plugin.json + 入口 .py + README.md）
├── overrides/<id>.py         34 个裸 .py 覆盖包
├── patches/                  能力桥扩张的宿主补丁（4 份 unified diff）
├── dist/
│   ├── packs/<pack_id>.zip   单包 ZIP（ZIP 内只有一个包根，可走 install-local）
│   ├── overrides/<id>.zip    单文件 ZIP
│   └── qq-plugin-packs-all.zip  合集（含 INDEX.md/json + install.py + verify*.py）
├── INDEX.md                  人读索引（按通道分组，含判定理由）
├── INDEX.json                机读索引（含 sha256、行号、权限、钩子）
├── build.py                  重新生成全部产物
├── install.py                装进宿主 custom_plugins
├── verify.py                 产物级验证（四轮）
├── verify_installed.py       安装后布局验证
└── probe_bridge_root.py      桥的宿主根补丁验证（三落点 × 两配置，比对原版）
```

> 合集 zip 是**分发包装**，不是插件包：它没有 `plugin.json`，直接丢给
> `POST /api/plugins/install-local` 会被宿主拒（`missing-manifest`）。解压后用里面的
> `install.py`，或挑 `dist/packs/*.zip` / `dist/overrides/*.zip` 单包装。

## 安装

### 自动（推荐）

```bash
# 预演，只打印不写盘
python install.py

# 真装（自动找 custom_plugins 目录，优先问在线控制台 GET /api/plugins/custom）
python install.py --apply

# 只装某几个，并顺带启用
python install.py --apply --only sleep_mode,qqagent_bridge --enable

# 只装某一通道
python install.py --apply --channel mod

# 覆盖同名已有项（覆盖前自动备份 .bak-<uuid>）
python install.py --apply --overwrite

# 反向卸载
python install.py --apply --uninstall
```

`--dir` 可显式指定 `custom_plugins` 路径；`--url` 默认 `http://127.0.0.1:8090`
（`qq_main.py:10` 的端口）。

### 手动

* **目录包**：整个 `pack_xxx/` 目录复制进 `custom_plugins/`（目录名必须 == `plugin.json.id`）
* **裸 .py**：`<id>.py` 复制进 `custom_plugins/`，再把 id 加进 `custom_plugins.json`
  的 `{"plugins": ["<id>", ...]}`
* 单包 ZIP（`dist/overrides/*.zip`）可以走 `POST /api/plugins/install-local`；目录包的
  ZIP **不行**，见下

装完**重启 QQ 工作台**生效。

> 控制台的「插件 → 本地插件包」列表**只扫宿主自己的 `plugin_packages/`**
> （`src/qq_app.py:_packs_root()` → `<bot.root>/plugin_packages`，源码态退回仓库根）。
> 想用那个入口，得先把 `pack_xxx/` 复制进 `<宿主>/plugin_packages/`，再从控制台点安装。
> 不想动宿主仓库就用 `install.py`，或直接把目录复制进 `custom_plugins/`。

> **`install-local` 只认单文件**：`plugin_installer._pick_from_archive` 只取入口那一个
> `.py`，`plugin.json`/`README.md` 会被丢掉。实测 `pack_sleep_mode.zip` 走它会被装成
> `custom_plugins/sleep_mode.py`（裸通道，`plugin_id=sleep_mode`）——目录包**不要**这么装。

> 两条通道**只留一个**：同目录下同时存在 `pack_x/` 和 `x.py` 时，目录包会被
> `file_conflict` 拒载（`plugin_packages/README.md` 的既有约定）。

## 兼容性改动

### 一、桥的宿主根定位（只有 `qqagent_bridge.py`，随包发货）

原代码用 `REPO_ROOT = Path(__file__).resolve().parents[2]` 定位
`runtime/qqagent-host/host-one.mjs`。搬进 `custom_plugins/` 后 `parents[2]` 指向数据
目录——**指错但看起来有值**，这是最坏的一种失效。改为 `_pack_repo_root()` 逐级向上
探测（找 `runtime/qqagent-host/host-one.mjs` 或 `src/plugins/qqagent_bridge.py`），
探测不到才退回原位置。`sha256` 前后值记在 `INDEX.json` 的
`sha256_source` / `sha256_shipped`。

其余 65 个包**源码零改动**，`sha256_source == sha256_shipped`。

### 二、能力桥扩张（5 个消费点，需要打宿主补丁）

`qqagent_bridge` 的 `ALLOWED_PROVIDERS` 原本只有 7 个能力名，而市场 702 个 approved
包里声明了 **499 种**。宿主自己只消费 8 个，桥已接 5 个，缺的 5 个都落在「宿主有调用点、
桥没接」这一格：

| 能力 | 接在哪 | 桥的方法 | 宿主调用点 |
| --- | --- | --- | --- |
| `tool.guard` | `on_before_tool` | `tool_guard()` | `src/tool-registry.js:198` |
| `media.download` | 消息入口 | `media_download()` | `src/app.js:1000` |
| `message.speaker-format` | `turn_text` | `speaker_format()` | `src/prompt.js:305` |
| `llm.endpoint-pick` | `AIEngine.chat` | `endpoint_pick()` | `src/llm.js:279` |
| `llm.endpoint-feedback` | `AIEngine.chat` | `endpoint_feedback()` | `src/llm.js:499` |

**这五个能力的消费点在 Python 宿主里**，所以除了插件包，还要给宿主打补丁：

```bash
cd D:\qq机器人5.0
git apply -p1 D:\插件\qq-plugin-packs\patches\qq_app.patch          # 或 patch -p1 < ...
git apply -p1 D:\插件\qq-plugin-packs\patches\ai_engine.patch
git apply -p1 D:\插件\qq-plugin-packs\patches\chat_state.patch
```

`patches/qqagent_bridge.patch` 是桥本体（与 `overrides/qqagent_bridge.py` 等价），
**装了插件包就不用打它**，留着只用于核对。

四个补丁的规模：`qq_app.py` +163/-0（7 hunk）、`ai_engine.py` +61/-3（6 hunk）、
`chat_state.py` +15/-4（2 hunk）、`plugins/qqagent_bridge.py` +407/-15（17 hunk，
其中 2 个 hunk 是模块 docstring 的说明文字，+24/-1；纯代码部分是 15 hunk +383/-14）。

**不打补丁的后果**：5 个能力仍然出现在 `bridge_status()` 里（不再是 `deadInHost`），
但没有任何 Python 侧代码去调用它们，等于空转。**打了补丁不装扩展**：同样空转，
`_provider_profiles()` 返回空列表，五个消费点立刻返回空值——**一律 fail-open，
不会影响原有回复链**。

#### 实现上的三个约束（不是偷懒）

1. **`sender` 恒为 `None`**：`src/extension_host.py:70 build_argv` 把 payload 走
   `json.dumps` 塞进 argv，**函数无法序列化**。扩展自己有降级分支
   （`media-download/bili.js:651` 的 `if (sender?.sendMedia) ... else if (onebot?.sendSegments)`），
   两者都缺也照样下载成功、只是不发送。真发由 `QQRuntime._deliver_media` 走
   Python 侧发送通道完成（限频/去重/留档都在那条链路上），与宿主
   `sender.js:380`「插件不得绕过 SendQueue 直发」同向。
2. **`onebot` 只给 `selfId` / `selfNickname` 两个标量**，不给 `getMsg` / `sendSegments`
   等方法。`media-download` 的 `resolveBvid` 只在带 `messageId` 时调 `getMsg`，
   只给 URL 时不碰它，所以不影响主路径。
3. **`endpoint_pick` 的 `id` 与 `extensionId` 语义不同**：宿主 `llm.js:282`
   `poolAccountId = picked.id || ''`，feedback 的 `accountId` 要用 `id`。
   桥两个都返回，调用方按需取。

#### `maxProfiles` 上限 8 → 32

宿主一次能力调用就是一个独立 node 进程（冷启动约 1.4s，热调用 55~75ms），
所以「每轮调用几个扩展」直接等于每轮延迟。上限从 8 提到 `MAX_PROFILES_LIMIT = 32`，
**默认值仍是 2**，调大由用户按自己的扩展数量权衡。

### 这个补丁的边界（别误解）

桥解析宿主脚本**真正的主路径是 `_resolve_paths()`**，它先走 `_host_root(conf)`：
用户填的 `hostRoot` → `src.qqagent_host.resolve_host_root()`（安装态 / 兼容层 / 开发态
候选）。`REPO_ROOT` 只是兜底。

所以：**插件装到与宿主仓库无关的数据目录时，需要填 `hostRoot`**（或让宿主先
`materialize_host_root` 把 JS 宿主拷到 `<data_dir>/qq-only/qqagent_host`）。
这不是补丁引入的限制——原版在没有 `hostRoot` 且宿主根未 materialize 时，
`_resolve_paths` 返回的 `host_script` 同样是空字符串（`if root:` 分支才填）。

`probe_bridge_root.py` 就是按「不比原版差」而不是「无配置也能跑」来验收的：

```
场景：无配置（宿主根未 materialize）     原版 未命中  补丁版 未命中  不差于原版
场景：填 hostRoot                       原版 命中    补丁版 命中    不差于原版
补丁版在仓库布局下：REPO_ROOT=…\repo_like  host-one.mjs 存在=True  与预期一致=True
结论：通过
```

> 坑：`hostRoot` 指的是 **JS 宿主根**（要含 `src/config.js` + `src/plugin-loader.js`），
> 即 `runtime/qqagent-host/`，**不是** Python 仓库根 `D:\qq机器人5.0`。填错会被
> `_is_host_root()` 判否，然后静默回退到空字符串。

桥必须走覆盖通道的三个理由（`INDEX.json` 的 `channel_reason`）：

1. 要起 node 子进程，单次调用远超目录 mod 的 2 秒钩子超时
2. 用 `__file__` 定位宿主脚本
3. 宿主对 `qqagent_bridge` 这个 id 有 17 处硬引用（`src/qq_app.py:51,1199,1697,…`），
   `META.id` 必须保持不变，否则控制台整条能力桥 UI/路由全断

## 验证

```bash
python verify.py             # 产物级：逐包隔离 + 全量共存 + 清单校验
python verify_installed.py   # 安装后：读真实 custom_plugins 目录再加载一遍
python probe_bridge_root.py  # 桥的宿主根补丁：三个落点 × 两种配置，比对原版
```

`verify_installed.py` **必须传安装目录**，不传会验默认的测试目录：

```bash
python verify_installed.py "D:\qq机器人5.0\data\qq-only"
```

`verify.py` 四轮：

* **A 逐包隔离**：每个包单独一个 `data_dir`，确认只挂自己、通道判定与实测一致，
  再经 `manager._call_mod_hook` 走**真实调用路径**跑 9 个钩子
* **B 全量共存**：66 个包同装一个目录，比对 `_plugins` / `_is_mod` / `_mod_refusals` /
  `_load_problems` / `_last_import_error`
* **D 清单校验**：用宿主自带 `src.plugin_packs.inspect_dir` 只读校验每个目录包

最新结果：

```
=== A 逐包隔离: 66 个包，有问题 0 个 ===
=== B 全量共存: mounted=66/66 ===
  missing=[]  wrong_channel=[]  refusals={}  last_import_error=None
=== D 清单校验: 32 个目录包，不合格 0 个 ===
结论：通过
```

`verify_installed.py` 额外校验**登记正确性**：裸 .py 必须在
`custom_plugins.json` 里，目录包必须不在（否则重启后行为不符）。

它不会把「多出来的插件」当失败——你自己装的 `demo_probe`、`dsh_heart` 本来就不在包里。

### 本机生产环境实测（已装）

```
=== 安装目录 D:\qq机器人5.0\data\qq-only ===
宿主加载耗时 0.34s｜挂载 68/66
  missing=[]  extra=['demo_probe', 'dsh_heart']  wrong_channel=[]
  refusals={}  load_problems=[]  last_import_error=None
  裸 .py 登记数=34｜目录包目录数=32
结论：通过
```

`挂载 68/66` 是因为宿主同时还加载了你原有的 2 个自定义插件。

## 与内置版的关系

* 装了包 = 用包里的实现**顶替**同名内置插件（`self._plugins[pid] = inst` 覆盖写）
* 删掉包 = 下次启动自动恢复内置版
* 设置项沿用同名键，已有配置不丢（`if pid not in self._settings` 才写默认值）
* 26 个包 `enabled_by_default: true`，与内置版的默认开启状态一致；
  其余 40 个默认关闭，装完不会改变现有行为

## 已知边界

* **多账号**：宿主的插件库按账号隔离（`src/qq_app.py:456 _plugin_dir()`）。装到哪个
  `custom_plugins` 就只对那个账号生效，`install.py` 优先问在线控制台要路径。
* **目录包不能走 `install-local` 接口**：`plugin_installer._pick_from_archive` 只取
  单个源码文件落成 `<id>.py`，`plugin.json` 和 `README.md` 会被丢掉。目录包只能
  复制目录、或用 `POST /api/plugins/packs/install`。
* **钩子超时**：目录 mod 的单钩子必须 < 2 秒。实测最慢的是
  `hot_trend_tracker.tick` 830ms，其余全 < 11ms，都在安全区内。
* **宿主版本**：`plugin.json` 里 `min_host_version: 5.2.112`。宿主降级到更早版本时，
  `plugin_packs` 校验器会报 `host-too-old`。

## 重新生成

```bash
python build.py     # 读 D:\qq机器人5.0\src\plugins，重写 packs/ overrides/ dist/ INDEX.*
python verify.py    # 必须重跑：产物变了就得重新验证
```

`build.py` 用真 `PluginManager` 实例化一遍取 META（比 AST 可靠），
通道判定用保守扫描（宁可多判 override）。改了宿主源码后重跑这两个即可。

宿主补丁（`patches/`）单独生成，脚本在 `D:\插件\_audit\gen_hostpatch.py`：

```bash
python D:\插件\_audit\gen_hostpatch.py
```

它拿 `D:\插件\_audit\hostcopy\src`（5.2.112 的改动前原始副本）对
`D:\qq机器人5.0\src` 做 unified diff。**两边都先按 LF 归一**——`agent_tools.py`、
`skill_tools.py`、`tool_schema.py` 这三个文件在快照与现行版本之间有 LF/CRLF 翻转，
不归一的话会生成整文件替换的假补丁。本目录这 4 个文件不受影响，但脚本保持归一以防后患。

生成后请核对 hunk 数：`qq_app.py` 7、`ai_engine.py` 6、`chat_state.py` 2、
`plugins/qqagent_bridge.py` 17（其中 2 个是 docstring）。数字对不上说明宿主源码在快照
之后又被改过，需要先重新确认基准，不要直接打补丁。
