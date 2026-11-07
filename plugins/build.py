"""把宿主 D:\\qq机器人5.0 的内置插件与能力桥拆成可独立安装的插件包。

宿主有两条互斥的插件通道（`src/plugins/manager.py` 已核实并实测）：

1. **目录 mod**（`custom_plugins/<包 id>/plugin.json` + 入口 .py）
   入口模块的 `__package__` 被设成 `src.plugins`，`from . import PluginBase` 等相对导入可用；
   但 runtime 被换成只读门面 `ModRuntime`（只有 mod_id/api_version/settings/get/
   has_permission/register_tool/log/note/now），并且每个钩子有 2 秒超时。
   入口里的 `META.id` 与内置同名时，`_mount_module` 的 `self._plugins[pid] = inst`
   会顶替内置实现（manifest 的 id 用 `pack_` 前缀，不撞 `builtin_conflict`）。

2. **裸 .py 覆盖**（`custom_plugins/<插件 id>.py`）
   `_import_plugin_module` 优先取这个文件，`is_mod=False`，拿的是活的 `QQRuntime`，
   没有门面也没有钩子超时。凡是在钩子里直接读 `runtime.mode/db/account/onebot/ai/...`
   的插件，只能走这条通道，行为才 100% 不变。

判定口径（保守）：只要源码里**任何位置**引用了门面之外的 `runtime.<成员>`，就走裸 .py。
静态扫描覆盖三种写法：直接属性、`getattr(runtime, "字面量")`、以及把 `runtime` 赋给
局部别名后再取属性。另外把「调用了宿主里会摸 runtime 的辅助函数」也算进来
（目前只有 `chat_state.scope_of`，它内部读 `runtime.mode` / `runtime.account()` /
`runtime.plugins`，从门面进必炸）。

产物：
    packs/<pack_id>/            目录 mod 包（plugin.json + 入口 + README）
    overrides/<id>.py           裸 .py 覆盖包
    dist/packs/<pack_id>.zip
    dist/overrides/<id>.zip
    dist/qq-plugin-packs-all.zip
    INDEX.json / INDEX.md
"""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
import sys
import textwrap
import zipfile
from pathlib import Path

HOST = Path(r"D:\qq机器人5.0")
OUT = Path(r"D:\插件\qq-plugin-packs")
HOST_VERSION = (HOST / "version.txt").read_text(encoding="utf-8").strip()

sys.path.insert(0, str(HOST))

from src.plugins.manager import PluginManager, PLUGIN_MODULES  # noqa: E402
from src.plugins import MOD_PERMISSIONS  # noqa: E402

SRC = HOST / "src" / "plugins"
DATA_MODULES = {"face_names"}            # 纯静态字典，不是插件
SKIP = {"__init__", "manager"} | DATA_MODULES

# ModRuntime 门面暴露的全部成员
FACADE = {"mod_id", "api_version", "settings", "get", "has_permission",
          "register_tool", "log", "note", "now"}

# 宿主里「自己会摸 runtime」的辅助函数：插件只要调了它，mod 通道必炸
HOST_HELPERS = {
    "scope_of": ("调用了宿主 chat_state.scope_of()，它内部读 runtime.mode / "
                 "runtime.account() / runtime.plugins"),
}

# 额外强制走裸 .py 的插件（静态扫描抓不到的动态原因）
FORCE_OVERRIDE = {
    "qqagent_bridge": "会起 node 子进程，远超目录 mod 的 2 秒钩子超时；且用 __file__ 定位宿主脚本",
}

# 钩子里会做「耗时不可控」的 IO：目录 mod 的单钩子围栏是 2 秒
# （`src/plugins/manager.py:24 MOD_HOOK_TIMEOUT`），超时会被整钩子跳过——
# 这不是崩溃，是**功能静默消失**，比崩溃更难查，所以一律走裸 .py 通道。
SLOW_PATTERNS = (
    ("read_public", "钩子里联网读网页，单次超时预算可达 4~6 秒，超过目录 mod 的 2 秒围栏"),
    ("urlopen", "钩子里直接 urlopen，耗时不可控，超过目录 mod 的 2 秒围栏"),
    ("urllib.request", "钩子里直接发 HTTP 请求，耗时不可控，超过目录 mod 的 2 秒围栏"),
    ("asyncio.sleep", "钩子里 await sleep，超过目录 mod 的 2 秒围栏就会被整钩子跳过"),
    ("subprocess", "钩子里起子进程，耗时不可控，超过目录 mod 的 2 秒围栏"),
)

# 只在裸 .py 通道里需要打的补丁：让桥从任意安装位置都能找到宿主根
BRIDGE_ROOT_OLD = "REPO_ROOT = Path(__file__).resolve().parents[2]"
BRIDGE_ROOT_NEW = '''def _pack_repo_root() -> Path:
    """从本文件位置向上找宿主仓库：仓库内、custom_plugins/ 下都能命中。

    原实现写死 `parents[2]`，插件被搬到 `custom_plugins/<id>/` 或
    `custom_plugins/<id>.py` 之后会指到数据目录，`runtime/qqagent-host/host-one.mjs`
    随之失效。这里逐级向上探测，探测不到再退回原来的相对位置。

    注意：这只是**兜底**。桥真正解析路径时先走 `_host_root(conf)`，由
    `src/qqagent_host.resolve_host_root()` 从安装位置 / 兼容层 / 开发态候选里找；
    插件装在完全独立的数据目录（比如 `D:\\插件`）时，上面这些向上探测都碰不到宿主，
    此时靠用户填 `hostRoot` 或宿主自己 `materialize_host_root` 出来的
    `<data_dir>/qq-only/qqagent_host` 生效——这两条路都在 `_host_root` 里，不在这里。
    """
    here = Path(__file__).resolve()
    for base in here.parents:
        if (base / "runtime" / "qqagent-host" / "host-one.mjs").is_file():
            return base
        if (base / "src" / "plugins" / "qqagent_bridge.py").is_file():
            return base
    return here.parent


REPO_ROOT = _pack_repo_root()'''


# --------------------------------------------------------------------------- #
# 静态分析
# --------------------------------------------------------------------------- #
def _runtime_aliases(tree: ast.AST) -> set[str]:
    """`x = runtime` / `x: T = runtime` 这类别名，用来抓 `x.mode`。"""
    names = {"runtime"}
    for _ in range(3):                       # 少量迭代即可收敛（别名套别名）
        before = len(names)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                value = node.value
                if not isinstance(value, ast.Name) or value.id not in names:
                    continue
                for t in targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
        if len(names) == before:
            break
    return names


def runtime_refs(tree: ast.AST) -> dict[str, list[int]]:
    """源码里引用到的 `runtime.<成员>`，返回 {成员: [行号...]}。"""
    aliases = _runtime_aliases(tree)
    out: dict[str, list[int]] = {}

    def add(name: str, line: int) -> None:
        out.setdefault(name, [])
        if line not in out[name]:
            out[name].append(line)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id in aliases:
            add(node.attr, node.lineno)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "getattr" and len(node.args) == 2:
            # getattr(runtime, "x") 两参形式：缺属性直接抛 AttributeError，等于硬访问。
            # 三参形式 getattr(runtime, "x", default) 会吞掉 AttributeError，门面下安全，不计。
            arg0, arg1 = node.args
            if isinstance(arg0, ast.Name) and arg0.id in aliases \
                    and isinstance(arg1, ast.Constant) and isinstance(arg1.value, str):
                add(arg1.value, node.lineno)
    return out


def host_helper_calls(tree: ast.AST) -> dict[str, list[int]]:
    """调用了哪些「自己会摸 runtime」的宿主辅助函数。"""
    out: dict[str, list[int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in HOST_HELPERS:
            out.setdefault(node.func.id, []).append(node.lineno)
    return out


def defined_hooks(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith(
                    ("on_", "wants_", "volatile_", "validate_", "post_load", "tick")):
                names.append(item.name)
    return names


def _imported_top_modules(tree: ast.AST) -> set[str]:
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])
    return mods


def uses_state(tree: ast.AST) -> bool:
    text = ast.unparse(tree)
    return any(k in text for k in ("state_file(", "save_state(", "load_state("))


def uses_network(tree: ast.AST) -> bool:
    return bool(_imported_top_modules(tree) & {"requests", "aiohttp", "httpx", "urllib", "socket"})


def uses_file(tree: ast.AST) -> bool:
    return "__file__" in ast.unparse(tree)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# 取每个插件的真实 META（实例化一遍，比 AST 扫可靠）
# --------------------------------------------------------------------------- #
def load_metas() -> dict:
    tmp = OUT / ".build" / "meta"
    if tmp.exists():
        shutil.rmtree(tmp)
    cp = tmp / "custom_plugins"
    cp.mkdir(parents=True)
    ids = []
    for path in sorted(SRC.glob("*.py")):
        if path.stem in SKIP:
            continue
        shutil.copy2(path, cp / f"{path.stem}.py")
        ids.append(path.stem)
    extra = [i for i in ids if i not in PLUGIN_MODULES]
    (tmp / "custom_plugins.json").write_text(
        json.dumps({"plugins": extra}, ensure_ascii=False), encoding="utf-8")
    mgr = PluginManager(tmp)
    metas: dict[str, dict] = {}
    for pid, inst in mgr._plugins.items():
        m = inst.META
        metas[pid] = {
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "category": m.category,
            "enabled_by_default": bool(m.enabled_by_default),
            "config_keys": sorted(m.config_schema),
            "default_settings": m.default_settings,
        }
    missing = [i for i in ids if i not in metas]
    if missing:
        raise SystemExit(f"这些插件没能挂载，无法取 META：{missing}")
    return metas


# --------------------------------------------------------------------------- #
# 打包
# --------------------------------------------------------------------------- #
def zip_dir(src: Path, dest: Path, top: str) -> None:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                zf.write(p, f"{top}/{p.relative_to(src).as_posix()}")


def zip_file(src: Path, dest: Path, arcname: str) -> None:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(src, arcname)


def patch_source(pid: str, code: str) -> tuple[str, str]:
    """按插件做最小源码补丁，返回 (新源码, 补丁说明)。"""
    if pid != "qqagent_bridge":
        return code, ""
    if BRIDGE_ROOT_OLD not in code:
        raise SystemExit("qqagent_bridge 的 REPO_ROOT 定位行变了，补丁失效，请人工核对")
    if code.count(BRIDGE_ROOT_OLD) != 1:
        raise SystemExit("qqagent_bridge 的 REPO_ROOT 定位行出现多次，补丁不安全")
    return code.replace(BRIDGE_ROOT_OLD, BRIDGE_ROOT_NEW), \
        "宿主根定位由 `parents[2]` 改为逐级向上探测，装到 custom_plugins/ 下仍能找到 runtime/qqagent-host"


def build() -> dict:
    for sub in ("packs", "overrides", "dist"):
        target = OUT / sub
        if target.exists():
            shutil.rmtree(target)
    for sub in ("packs", "overrides", "dist/packs", "dist/overrides"):
        (OUT / sub).mkdir(parents=True)

    metas = load_metas()
    entries: list[dict] = []

    for path in sorted(SRC.glob("*.py")):
        pid = path.stem
        if pid in SKIP:
            continue
        raw = path.read_text(encoding="utf-8")
        tree = ast.parse(raw)
        refs = runtime_refs(tree)
        blocked = sorted(k for k in refs if k not in FACADE)
        helpers = host_helper_calls(tree)
        hooks = defined_hooks(tree)
        meta = metas[pid]

        reasons: list[str] = []
        if blocked:
            reasons.append("钩子直接读宿主 runtime." + "/runtime.".join(blocked))
        for fn in sorted(helpers):
            reasons.append(HOST_HELPERS[fn])
        for needle, why in SLOW_PATTERNS:
            if needle in raw:
                reasons.append(why)
        if pid in FORCE_OVERRIDE:
            reasons.append(FORCE_OVERRIDE[pid])
        channel = "override" if reasons else "mod"

        code, patch_note = patch_source(pid, raw)
        if patch_note:
            reasons.append(patch_note)

        perms: list[str] = []
        if any(h in hooks for h in ("on_ingest", "on_block", "wants_reply", "on_pre_ai",
                                    "on_prepare", "volatile_hint")):
            perms.append("read_message")
        if any(h in hooks for h in ("on_sent", "on_post_reply", "tick")):
            perms.append("send_message")
        if uses_state(tree):
            perms.append("store_data")
        if uses_network(tree):
            perms.append("network")
        perms = [p for p in perms if p in MOD_PERMISSIONS] or ["read_message"]

        entry = {
            "id": pid,
            "pack_id": f"pack_{pid}" if channel == "mod" else pid,
            "name": meta["name"],
            "description": meta["description"],
            "category": meta["category"],
            "channel": channel,
            "channel_reason": "；".join(reasons)
                              or "只访问 ModRuntime 门面，可安全走目录 mod",
            "patched": bool(patch_note),
            "builtin": pid in PLUGIN_MODULES,
            "enabled_by_default": meta["enabled_by_default"],
            "hooks": hooks,
            "permissions": perms,
            "config_keys": meta["config_keys"],
            "lines": raw.count("\n") + 1,
            "sha256_source": sha256_text(raw),
            "sha256_shipped": sha256_text(code),
            "blocked_runtime_attrs": blocked,
            "runtime_ref_lines": {k: v for k, v in sorted(refs.items()) if k not in FACADE},
        }

        if channel == "mod":
            pdir = OUT / "packs" / entry["pack_id"]
            pdir.mkdir()
            (pdir / f"{pid}.py").write_text(code, encoding="utf-8")
            manifest = {
                "id": entry["pack_id"],
                "name": f"{meta['name']}（独立包）",
                "version": "1.0.0",
                "api_version": 1,
                "entry": f"{pid}.py",
                "permissions": perms,
                "description": meta["description"] or f"{meta['name']} 的独立插件包",
                "host": "WhaleGirlQQ",
                "min_host_version": HOST_VERSION,
                "enabled_by_default": meta["enabled_by_default"],
                "category": meta["category"],
                "source": f"builtin:{pid}",
            }
            (pdir / "plugin.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            (pdir / "README.md").write_text(pack_readme(entry, meta, manifest),
                                            encoding="utf-8")
            entry["files"] = sorted(p.name for p in pdir.iterdir())
            zip_dir(pdir, OUT / "dist" / "packs" / f"{entry['pack_id']}.zip",
                    top=entry["pack_id"])
        else:
            target = OUT / "overrides" / f"{pid}.py"
            target.write_text(code, encoding="utf-8")
            entry["files"] = [f"{pid}.py"]
            zip_file(target, OUT / "dist" / "overrides" / f"{pid}.zip", arcname=f"{pid}.py")

        entries.append(entry)

    report = {
        "host_version": HOST_VERSION,
        "total": len(entries),
        "mod": sum(1 for e in entries if e["channel"] == "mod"),
        "override": sum(1 for e in entries if e["channel"] == "override"),
        "builtin": sum(1 for e in entries if e["builtin"]),
        "extra": sum(1 for e in entries if not e["builtin"]),
        "patched": [e["id"] for e in entries if e["patched"]],
        "plugins": entries,
    }
    (OUT / "INDEX.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "INDEX.md").write_text(index_markdown(report), encoding="utf-8")

    all_zip = OUT / "dist" / "qq-plugin-packs-all.zip"
    # 只排除 build.py 本身（它依赖宿主仓库路径，脱离环境跑不了）；
    # install.py / verify*.py 一起发出去，用户拿到 zip 就能自己校验和安装。
    skip_names = {"build.py", "INDEX.md", "INDEX.json"}
    with zipfile.ZipFile(all_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(OUT.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(OUT)
            if rel.parts[0] == "dist" or rel.parts[0].startswith("."):
                continue
            if p.name in skip_names:
                continue
            zf.write(p, f"qq-plugin-packs/{rel.as_posix()}")
        for name in ("INDEX.md", "INDEX.json"):
            zf.write(OUT / name, f"qq-plugin-packs/{name}")

    shutil.rmtree(OUT / ".build", ignore_errors=True)
    return report


# --------------------------------------------------------------------------- #
# 文档
# --------------------------------------------------------------------------- #
def pack_readme(entry: dict, meta: dict, manifest: dict) -> str:
    hooks = "、".join(entry["hooks"]) or "（无钩子，仅提供设置项）"
    config = "、".join(entry["config_keys"]) or "—"
    return textwrap.dedent(f"""\
        # {meta['name']}

        {meta['description']}

        | 项 | 值 |
        | --- | --- |
        | 包 id | `{manifest['id']}` |
        | 插件 id | `{meta['id']}` |
        | 版本 | {manifest['version']} |
        | 分类 | {meta['category']} |
        | 默认启用 | {'是' if meta['enabled_by_default'] else '否'} |
        | 挂载通道 | 目录 mod（`custom_plugins/{manifest['id']}/`） |
        | 钩子 | {hooks} |
        | 权限 | {', '.join(entry['permissions'])} |
        | 设置项 | {config} |
        | 源码行数 | {entry['lines']} |

        ## 安装

        把整个 `{manifest['id']}` 目录复制进 QQ 工作台的 `custom_plugins` 目录，重启即生效；
        或在控制台「插件 → 本地插件包」里选中这个目录。

        `custom_plugins` 的真实路径看 `GET /api/plugins/custom` 返回的 `dir`，
        安装版通常在 `%LOCALAPPDATA%\\WhaleGirlQQ\\data\\qq-only\\custom_plugins`。

        ## 兼容性

        入口文件里的 `META.id` 仍是 `{meta['id']}`，与内置插件同名，挂载后会
        **顶替内置实现**；删掉本目录即恢复内置版本。设置项沿用同名键，已有配置不会丢。

        本插件只访问 `ModRuntime` 门面，单个钩子耗时须低于 2 秒（超时会被跳过，
        连续 3 次失败后自动禁用）。源码与内置版本逐字节一致（sha256
        `{entry['sha256_shipped'][:16]}…`），未做行为改动。
        """)


def index_markdown(report: dict) -> str:
    lines = [
        "# QQ 工作台插件包索引",
        "",
        f"宿主版本 `{report['host_version']}`，共 **{report['total']}** 个独立插件包："
        f"目录 mod **{report['mod']}** 个、裸 .py 覆盖 **{report['override']}** 个。",
        f"其中与内置同名的 {report['builtin']} 个，宿主默认不加载的 {report['extra']} 个。",
        "",
        "## 目录 mod 包（`packs/`）",
        "",
        "整目录复制进 `custom_plugins/` 即挂载；入口保留原 `META.id`，挂载后顶替内置实现。",
        "",
        "| 包 id | 插件 id | 名称 | 分类 | 默认启用 | 钩子 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for e in report["plugins"]:
        if e["channel"] != "mod":
            continue
        lines.append(f"| `{e['pack_id']}` | `{e['id']}` | {e['name']} | {e['category']} | "
                     f"{'是' if e['enabled_by_default'] else '否'} | "
                     f"{', '.join(e['hooks']) or '—'} |")
    lines += [
        "",
        "## 裸 .py 覆盖包（`overrides/`）",
        "",
        "这些插件在钩子里直接读宿主 `runtime` 的成员（`mode`/`db`/`account`/`onebot`/`ai`/…），"
        "目录 mod 通道只给只读门面 `ModRuntime`，一调用就 `AttributeError`；"
        "因此必须以单文件形式放进 `custom_plugins/<插件 id>.py`，走同名覆盖通道拿活的 `QQRuntime`。",
        "",
        "| 插件 id | 名称 | 分类 | 默认启用 | 走覆盖通道的原因 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for e in report["plugins"]:
        if e["channel"] != "override":
            continue
        lines.append(f"| `{e['id']}` | {e['name']} | {e['category']} | "
                     f"{'是' if e['enabled_by_default'] else '否'} | {e['channel_reason']} |")
    if report["patched"]:
        lines += ["", "## 做过源码补丁的包", ""]
        for e in report["plugins"]:
            if e["patched"]:
                lines.append(f"- `{e['id']}`：{e['channel_reason']}")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    rep = build()
    print(json.dumps({k: v for k, v in rep.items() if k != "plugins"},
                     ensure_ascii=False, indent=2))
    for e in rep["plugins"]:
        print(f"  {e['channel']:9} {e['pack_id']:28} {e['name']}")
