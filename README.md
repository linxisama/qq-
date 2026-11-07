# qqplugin · QQ 工作台插件与技能合集

把 [WhaleGirlQQ / QQ 工作台](https://github.com/linxisama/qq-)（下称"宿主"）里散落的插件与技能市场
整理成**可单独安装、可复验、可重建**的四套产物。

宿主版本基线：**5.2.112**（`version.txt`）。全部产物都在这台机器上逐条真跑过，数字见各目录的 `REPORT.md`。

---

## 四套产物

| 目录 | 内容 | 数量 | 装到哪 | 入口 |
|------|------|------|--------|------|
| [`plugins/`](plugins/) | 从宿主内置插件里拆出来的独立包：32 个目录 mod + 34 个裸 `.py` override | **66 个** | `<data-root>/data/qq-only/custom_plugins/` | `plugins/install.py` |
| [`skills/`](skills/) | Skill 市场 379 个包里能注册的全部 skill，含宿主补丁 | **373 个 skill / 1179 个工具** | `<data-root>/data/qq-only/skill_extensions/` | `skills/install.py` |
| [`market/`](market/) | 42 个单文件插件 zip，走控制台「插件中心」安装 | **42 个** | 控制台插件中心 | 控制台 UI |
| [`heart/`](heart/) | 心情系统插件 + 宿主路由补丁 | 1 个 | `custom_plugins/` + `src/heart_api.py` | `heart/install.py` |

`plugins/` 与 `market/` 有 42 个 id 重叠：同一份插件代码的两种分发格式。
`market/` 走控制台安装器（`plugin_install_service`），`plugins/` 走 `custom_plugins` 目录直装。
**同一个 id 只装一种**，否则 `PluginManager` 会看到两份。

两边的源码由 `market/build.py` 保持同步：它只替换 zip 里的 `<id>.py`，
保留市场包原有的 `plugin.json` 与 `使用说明.md`（`plugin.json` 的 `config` 数组是
从插件的 `FieldSchema` 反解出来的，`plugins/` 侧没有等价物，覆盖会丢设置项）。
`python market/build.py` 预演、`--apply` 重打、`--bundle` 再打整包。

市场包的 `plugin.json` 必须带 `"api_version": 1`，否则宿主 `_read_mod_manifest`
（`src/plugins/manager.py:846`）会以 `bad_api_version` 把目录 mod 拒掉，只剩裸 `.py`
通道生效 —— 插件能跑，但拿不到 ModRuntime 门面（钩子 2s 超时保护、工具注册走 mod 表都失效）。
本仓库的 42 个包已全部补上；`plugins/` 侧 32 个目录包本来就带这个字段。

---

## 快速开始

```bash
# 0) 准备：用宿主自己的 venv python（不要用系统 python）
set PY=D:\qq机器人5.0\.venv-qq\Scripts\python.exe

# 1) 插件包（66 个）—— 默认只预演
%PY% -X utf8 plugins\install.py
%PY% -X utf8 plugins\install.py --apply

# 2) 技能包（373 个）—— 首次运行会从 dist\ready-all.zip 就地解压
%PY% -X utf8 skills\install.py --fix-host
%PY% -X utf8 skills\install.py --fix-host --apply

# 3) 心情插件
%PY% -X utf8 heart\install.py
%PY% -X utf8 heart\install.py --apply

# 4) 重启控制台
```

所有安装器**默认只预演**，加 `--apply` 才写盘。

装完想确认没问题，跑一条自检（只读，不装不改）：

```bash
%PY% -X utf8 selfcheck.py           # 全部：结构 + 插件挂载 + 技能真跑 + 市场包 + 心情插件
%PY% -X utf8 selfcheck.py --quick   # 跳过技能真跑（省 10 分钟）
```

15 项检查，退出码 0 表示全过；`--quick` 时技能那一项显示 `skip`。

---

## 关键前提：宿主补丁

技能包能不能注册，取决于宿主 `src/` 里 34 处补丁。不打补丁的话，装完的 skill 在清单里是裸工具名，
`_skill_plan()` 判「缺 `__` 前缀」，结果是 **eligible=0、一个都注册不上**。这不是安装问题，是宿主 bug。

```bash
%PY% -X utf8 skills\hostfix.py --check   # 只看：已修 34 / 待修 0 / 找不到 0
%PY% -X utf8 skills\hostfix.py --apply   # 打补丁（写前备份 .dsh-bak）
%PY% -X utf8 skills\guard_host.py        # 被别的进程还原了？一条命令修回
```

补丁分布：`src/skill_tools.py` 22 处、`src/skill_manifest.py` 8 处、`src/tool_schema.py` 3 处、
`src/agent_tools.py` 1 处。逐条说明见 [`skills/README.md`](skills/README.md)。

---

## 分发包

不想跑脚本的话，直接用 zip：

| 文件 | 大小 | 内容 |
|------|------|------|
| `plugins/dist/qq-plugin-packs-all.zip` | 368 KB | 66 个插件包 + 4 份 `.patch` |
| `skills/dist/ready-all.zip` | 35 MB | 373 个 skill（1572 条目）+ 根级脚本与文档 |
| `market/qq插件-市场-5.2.51.zip` | 311 KB | 42 个市场包 + index + 使用说明（86 条目） |
| `heart/dsh-heart-qq-0.1.0.zip` | 32 KB | 心情插件自包含分发包 |

逐包 zip（`skills/dist/ready-zips/`，373 个共 34.9 MB）**没有进仓库** —— 内容与 `ready-all.zip` 完全重复。
要单独分发某个 skill，直接从 `ready-all.zip` 里取 `ready/<id>/` 即可；`install.py` 首次运行也会自动解压到 `skills/ready/`。

---

## 实测结论

| 项 | 结果 |
|----|------|
| 插件包装机 | `plugins/verify.py` → **mounted 66/66**，`missing=[]`、`wrong_channel=[]`、`refusals={}`；生产机因含 2 个宿主内置同名包显示 68/66 |
| 技能包注册 | **373/373 注册成功，failed 0** |
| 技能包真跑 | **ok 334 / ran-blocked 39 / load-failed 0 / no-tool 0**（373 条逐个调用；生产机同批次是 ok 333/40，只差 `tieba-summary` 撞 45s 超时） |
| 模拟 clone | 只带 git 跟踪的文件（无 `ready/`、无 `ready-zips/`）→ `install.py --apply` 373 个全装成 → `verify.py` **ok 334 / ran-blocked 39**，与生产只差 `tieba-summary` |
| 市场包 | `market/tools/verify_market.py --console D:\qq机器人5.0` → **42 个全部 PASS**，`index.json` 的 sha256 与字节数逐条对得上 |
| 心情插件 | `heart/verify.py` → **全部通过**（宿主 6 个面板接线点全在） |
| 宿主补丁 | `hostfix.py --check` **34/34 已修**；守卫测试 `tests/test_skill_bridge_invariants.py` **13/13 OK** |
| 一致性 | 仓库脚本与 `dist/ready-all.zip` 内副本 sha256 全一致（8 个根级文件） |
| 真 clone | 从 GitHub 重新 `git clone` 到空目录 → `plugins/install.py --apply` 66 个、`plugins/verify.py` 66/66；`skills/install.py --apply` 373 个、`skills/verify.py` 抽样 3 个全通过；`market/tools/verify_market.py` 42/42；`heart/verify.py` 全部通过 |
| 可复现打包 | `plugins/build.py` 连跑两次，**67 个 zip 逐字节完全相同**（时间戳固定 `2020-01-01`，`QQ_ZIP_DATE` 可覆盖） |
| 路径容错 | `QQ_HOST_ROOT` 指到不存在的目录 → `install.py` / `verify.py` 均 exit 1 并打印「看起来不是 QQ Agent 仓库根（缺 src/skill_tools.py）」 |

39~40 个 `ran-blocked` 全部是**业务前置**（缺 API Key 7、缺 ffmpeg 3、缺群号参数 3、网络超时 2、缺知识库 1、
业务状态未满足 24），**没有一个是包自身可修的**。详见 [`skills/REPORT.md`](skills/REPORT.md)。

---

## 环境要求

- **Windows**（宿主是 Windows 桌面程序；脚本本身是纯标准库 Python）
- 宿主自带的 **Python 3.12**（`.venv-qq`）；纯标准库，无第三方依赖
- 宿主版本 **5.2.112**（补丁锚点按这个版本写；版本不符会报「找不到锚点」而不是乱改）
- `node` 在 `PATH` 里（技能包真跑要用宿主的 `host-one.mjs`）

**宿主根怎么找**：脚本按 `QQ_HOST_ROOT` 环境变量 > `D:\qq机器人5.0`（本机开发布局）
> `%LOCALAPPDATA%\WhaleGirlQQ` > `~\WhaleGirlQQ` 的顺序探测；都不中就退回
`D:\qq机器人5.0` 并由脚本报「看起来不是 QQ Agent 仓库根（缺 src/skill_tools.py）」，
不会在错的盘上静默建目录。也可以显式传 `--root` / `--dir`。

---

## 仓库结构

```
qqplugin/
├─ README.md              本文件
├─ selfcheck.py           一键自检（只读；结构 + 四套产物都验一遍）
├─ plugins/               66 个插件包（目录 mod + 裸 py override）
│  ├─ packs/              32 个目录包
│  ├─ overrides/          34 个裸 .py
│  ├─ patches/            4 份宿主补丁（unified diff）
│  ├─ dist/               分发包
│  ├─ INDEX.json/md       逐条清单
│  └─ build.py install.py verify.py
├─ skills/                373 个 skill
│  ├─ dist/ready-all.zip  全量包（首次安装自动解压，1572 条目）
│  ├─ INDEX.json/md       逐条清单（373 条）
│  ├─ REPORT.md           逐条实测结果
│  └─ build.py install.py verify.py hostfix.py guard_host.py
├─ market/                42 个单文件插件 zip
│  ├─ packages/           42 个 zip
│  ├─ 使用说明/            每个插件一页
│  ├─ index.json          机器可读索引（id/版本/分类/sha256/字节数）
│  └─ tools/verify_market.py
└─ heart/                 心情系统插件
   ├─ dsh-heart-qq/       插件本体
   ├─ host/heart_api.py   宿主模块
   └─ install.py verify.py
```

---

## 已知限制

- **6 个 skill 装不上**，都是真缺东西，不是 bug：`android-play-request`/`feeding`/`work`
  要的能力全市场没有包提供；`anon-qa` 逃出运行根；`qq-voice-listen` 跨包依赖一个自己也不可用的包；
  `chat-digest` 硬依赖 `electron`（`npm:electron` 闸判定不放行）。
- **能力桥扩展**（白名单 7→12、5 个新消费点）在宿主 5.2.110 上是死代码 —— 需要宿主升级到 5.2.112+
  才有调用点。本仓库只提供源码侧改动，不含重打包的 exe。
- **宿主 `src/` 会被外部进程还原**。已实测 6 次（04:56 / 07:03 / 11:43 / 12:48 / 13:10 / 16:57），
  回滚源是 `tests/test_skill_bridge_invariants.py` 在跑 `unittest` 时按断言改写源码。
  现该测试 13/13 通过；万一再被还原，跑 `skills/guard_host.py` 一条命令修回，
  用 `skills/hostfix.py --check` 确认「全部已修，无需操作」。

---

## 许可

插件与 skill 代码来自 QQ 工作台及其插件市场，版权归原作者。本仓库只做兼容性整理与打包分发。
