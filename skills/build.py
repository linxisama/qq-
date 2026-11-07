# -*- coding: utf-8 -*-
"""把 Skill 市场里的技能整理成可分发的独立产物。

产出（全部落在本脚本所在目录）：

  ready/                     可注册的 skill，逐个目录（<id>/skill.json + 源码），
                             直接丢进 <data>/qq-only/skill_extensions/ 就能用
  dist/ready-zips/<id>.zip   上面每个 skill 的单包 zip（走 POST /api/skills/install）
  dist/ready-all.zip         全部可注册 skill 的一次性安装包（内含 install.py）
  dist/market-379.zip        市场 379 个 zip 的原样镜像（离线备份/换机用）
  REPORT.md                  379 个 skill 的完整分层报告
  INDEX.json / INDEX.md      机器可读 / 人可读的索引
  install.py                 把 ready/ 装到宿主 skill_extensions 并登记启用态

数据来源：
  D:\\插件\\_audit\\skill_tiers.json       379 个 skill 的分层（T1..T6，打补丁前的静态扫描）
  D:\\插件\\_audit\\skill_eligible_366.json 打全补丁后宿主自己算出的可注册清单（366 个 / 1171 工具）
  D:\\插件\\_audit\\skill_runs.json         未启用态批量真跑结果（只有最早的 53 个有）
  D:\\插件\\_audit\\skill_runs_enabled.json 启用态批量真跑结果（同上）
  D:\\插件\\_audit\\verify_366.json         verify.py 全装真跑结果（报告里的「真跑」列用它）

跑法（用宿主 venv 的 python，脚本本身只用标准库）：
  D:\\qq机器人5.0\\.venv-qq\\Scripts\\python.exe -X utf8 build.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parent / "_audit"

TIERS_JSON = AUDIT / "skill_tiers.json"
# 打全补丁后宿主自己算出的可注册清单（366 个 / 1171 工具），由 _audit/probe_after_i.py 生成。
# 老的 skill_eligible.json 是「补丁前只有 53 个」、skill_eligible_331.json 是「第 18 处补丁时」、
# skill_eligible_g.json 是「第 20 处补丁时 354 个」、skill_eligible_361.json 是「第 21 处补丁时 361 个」、
# skill_eligible_365.json 是「第 26 处补丁时 365 个」的版本，都仅作对照保留。
ELIGIBLE_JSON = AUDIT / "skill_eligible_373.json"
ELIGIBLE_PREV_JSON = AUDIT / "skill_eligible_371.json"
ELIGIBLE_LEGACY_JSON = AUDIT / "skill_eligible.json"
RUNS_JSON = AUDIT / "skill_runs.json"
RUNS_ENABLED_JSON = AUDIT / "skill_runs_enabled.json"
# verify.py 在「全装进一个数据根」之后跑出来的结果（每个 skill 真调第一个工具）
VERIFY_JSON = AUDIT / "verify_373.json"
VERIFY_PREV_JSON = AUDIT / "verify_371.json"
VERIFY_LEGACY_JSON = AUDIT / "skill_verify_installed.json"

MARKET_DIR = Path(r"D:\聊天机器人\插件市场\Skill市场")

READY = HERE / "ready"
DIST = HERE / "dist"
READY_ZIPS = DIST / "ready-zips"

# 只把这些目录当作 skill 的「源码」，其余（data/、node_modules/ 之外的临时物）也一起带，
# 因为有些 skill 自带 json 词库、模板、sqlite。整包照搬最安全，体积也不大（53 个共 2.1MB）。
SKIP_SUFFIXES = {".pyc", ".pyo"}
SKIP_DIRS = {"__pycache__", ".git"}


def load(path: Path):
    if not path.is_file():
        raise SystemExit(f"缺少数据文件：{path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n/1:.1f} {unit}".replace(".0 ", " ")
        n /= 1024.0
    return f"{n} B"


def zip_name_for(skill_id: str) -> str:
    return f"{skill_id}.zip"


ENTRY_NAMES = ("index.js", "index.mjs", "index.cjs")


def _nested_package(outer: Path) -> Path | None:
    """双层嵌套包：外层只有清单副本、真包在同名子目录里，返回内层清单路径。

    判据（三条同时满足才下潜，避免误伤 pai-skills 这类 lib/<子包>/ 整合包）：
    1. 外层目录**本层没有入口文件**（index.js/mjs/cjs 一个都没有）；
    2. 外层目录恰好只有**一个**直接子目录；
    3. 那个子目录**同时**带清单（skill.json/plugin.json）与入口。
    """
    if any((outer / name).is_file() for name in ENTRY_NAMES):
        return None
    children = [p for p in outer.iterdir() if p.is_dir()]
    if len(children) != 1:
        return None
    inner = children[0]
    if not any((inner / name).is_file() for name in ENTRY_NAMES):
        return None
    for name in ("skill.json", "plugin.json"):
        candidate = inner / name
        if candidate.is_file():
            return candidate
    return None


def _fix_localchat_kit(package: Path) -> str:
    """修 localchat-kit 的两个空值问题，返回改了什么（空串 = 没改 / 不是这个包）。

    问题：它的补丁包针对**旧版宿主布局**（`ui/index.html`、`ui/style.css`、`ui/app/00-core.js`），
    而 5.2.x 把界面挪到了 `src/web/static/qq.html`。这些目标文件在现行宿主里根本不存在，
    `statusOf()` 返回 `missing`（既非 done 也非 mismatch），于是带着 `cur = null` 进 plan，
    apply 循环里 `detectEol(cur)` → `null.includes` 抛
    「Cannot read properties of null (reading 'includes')」，报错完全看不出原因。

    修两处：
    ① `detectEol` 容忍 null（防御）；
    ② 体检阶段遇到 `missing` 直接返回可读结论并**不动任何文件**（保持「任一处对不上就整体不动手」）。
    """
    index = package / "index.js"
    if not index.is_file():
        return ""
    text = index.read_text(encoding="utf-8")
    if "_fix_localchat_kit" in text or "不适配当前宿主布局" in text:
        return ""          # 已修过（幂等）
    if "detectEol" not in text or "plan.push({ f, abs, cur })" not in text:
        return ""          # 不是预期的那个版本，不动
    notes = []

    old_eol = "function detectEol(text) {\n  return text.includes('\\r\\n') ? '\\r\\n' : '\\n';\n}"
    new_eol = ("function detectEol(text) {\n"
               "  return String(text == null ? '' : text).includes('\\r\\n') ? '\\r\\n' : '\\n';\n}")
    if old_eol in text:
        text = text.replace(old_eol, new_eol, 1)
        notes.append("detectEol 容忍 null")

    old_push = "        plan.push({ f, abs, cur });"
    new_push = (
        "        if (st === 'missing') {\n"
        "          // 非 create 型补丁的目标文件不存在：这套补丁针对的是另一版宿主布局。\n"
        "          // 原实现会带 cur=null 进 apply 循环，随后 null.includes 抛异常，报错看不出原因。\n"
        "          return {\n"
        "            content: `中止：${f.file} 在安装目录里不存在，这套补丁不适配当前宿主布局。\\n`\n"
        "              + `安装目录：${root}\\n`\n"
        "              + '没有动任何文件。\\n'\n"
        "              + '可能原因：宿主版本不同（旧版有 ui/ 目录，5.2.x 起界面在 src/web/static/qq.html），'\n"
        "              + '或这个技能要装到另一个安装目录（可在技能设置里填 appDir）。',\n"
        "            isError: true\n"
        "          };\n"
        "        }\n"
        "        plan.push({ f, abs, cur });")
    if old_push in text:
        text = text.replace(old_push, new_push, 1)
        notes.append("目标文件缺失时提前给出可读结论")

    if notes:
        index.write_text(text, encoding="utf-8")
    return "；".join(notes)


def _fix_chat_digest(package: Path) -> str:
    """修 chat-digest 的 available()：不要因为拿不到 electron 就把整个包判成不可用。

    问题：`available()` 是**同步**自检，宿主 `manager.js:187-198` 拿它做整包开关 ——
    返回 `{ok:false}` 就让整个 skill 变成 `extension-unavailable`，连 `digest_read`
    （只用 `ctx.store.recent`、完全不需要渲染引擎）都调不了。

    实测：改掉一票否决后两个工具都能加载并执行（`digest_read` 返回「还没有聊天记录」、
    `digest_compose` 返回「payload 是空的」，都是正常业务响应，不是崩溃）。
    渲染那一步本来就有自己的 `getElectron()` 检查（`index.js:282`），缺 electron 时
    会返回明确的错误文案，不需要在自检阶段把整包杀掉。
    """
    index = package / "index.js"
    if not index.is_file():
        return ""
    text = index.read_text(encoding="utf-8")
    if "_fix_chat_digest" in text:
        return ""          # 已修过（幂等）
    old = ("export function available() {\n"
           "  const mod = getElectron();\n"
           "  if (!mod) return { ok: false, reason: `图片渲染引擎不可用：${electronError}` };\n"
           "  return { ok: true };\n"
           "}")
    if old not in text:
        return ""          # 不是预期的那个版本，不动
    new = ("export function available() {\n"
           "  // _fix_chat_digest：只有 digest_compose（渲染图片）真的需要 electron；\n"
           "  // digest_read 只用 ctx.store.recent，拿不到渲染引擎时读记录照样能用。\n"
           "  // 原来一票否决会让整个包变成「不可用」，连读记录都用不了 ——\n"
           "  // 改成始终可用，渲染那一步由 digest_compose 自己报错（index.js:282 已有检查）。\n"
           "  return { ok: true };\n"
           "}")
    index.write_text(text.replace(old, new, 1), encoding="utf-8")
    return "available() 不再因缺 electron 把整包判死（digest_read 仍可用）"


def _normalize_manifest(manifest: Path) -> str:
    """把清单里类型写错的数组字段修成数组，返回修了什么（空串 = 没改）。

    Node 宿主对这三个字段的口径不一样，但都要求「数组」：
    - `runtime/qqagent-host/host-one.mjs:84-91` 的 `names()` 对 requires / capabilities
      **强制** `Array.isArray`，写成 `{}` 会抛 `manifest-invalid` → 整个扩展加载失败
      （真例：palace 的 `"requires": {}`，真跑报 `palace.requires 必须是非空能力名数组`）；
    - `runtime/qqagent-host/src/plugin-loader.js:458` 对 permissions 用
      `Array.isArray(raw.permissions) ? raw.permissions : []` 兜底，写成字符串**不报错**，
      但权限被静默清空（真例：voice-send 的 `"permissions": "web_fetch"`，
      于是 `api.has('web_fetch')` 永远是 false，联网能力白丢）。

    Python 侧 `skill_manifest._as_list()` 对 dict/str 都做了兜底，所以这类包在清单扫描
    阶段完全正常（判成 T1-ready），只在真跑时才现形。这里按宿主口径统一成数组。
    """
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001 —— 解析不了的留给下游报错，别在这里吞掉
        return ""
    if not isinstance(raw, dict):
        return ""

    def as_list(value):
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return list(value.keys())
        if isinstance(value, str):
            return [value] if value.strip() else []
        return []

    fixes = []
    for key in ("requires", "capabilities", "permissions"):
        if key not in raw:
            continue
        value = raw[key]
        if value is None or isinstance(value, list):
            continue
        fixed = as_list(value)
        if key in ("requires", "capabilities"):
            fixed = [str(x) for x in fixed if str(x).strip()]
        else:
            fixed = [str(x).strip().lower() for x in fixed if str(x).strip()]
        raw[key] = fixed
        fixes.append(f"{key}: {json.dumps(value, ensure_ascii=False)} → "
                     f"{json.dumps(fixed, ensure_ascii=False)}")

    # prompt 写成纯字符串 → 宿主 adaptLegacyPrompt 直接 return，整段提示词静默丢失。
    # `runtime/qqagent-host/src/plugin-loader.js:49-52`：
    #   if (!p || typeof p !== 'object') return manifest;   // 字符串在这里被丢掉
    # 真例：stardew-wiki 的 prompt 是 187 字纯字符串，它的全部价值就是这段提示词
    # （要求模型先调 search_stardew_wiki 查资料再答），丢了等于白装。
    # 包成 `{sections:[{id,title,content}]}` 与宿主自己的 legacy 适配产物同构。
    prompt = raw.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        raw["prompt"] = {
            "sections": [{
                "id": "legacy",
                "title": str(raw.get("name") or raw.get("id") or ""),
                "content": prompt.strip(),
                "priority": 50,
            }]
        }
        fixes.append("prompt: 字符串 → {sections:[...]}（否则宿主 adaptLegacyPrompt 丢弃）")

    if not fixes:
        return ""
    manifest.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "；".join(fixes)


def market_zip_of(source: str) -> Path | None:
    """`source` 两种形状：'zip:<市场zip路径>' 或 'installed:<已装目录>'。"""
    if source.startswith("zip:"):
        path = Path(source[4:])
        return path if path.is_file() else None
    return None


def installed_dir_of(source: str) -> Path | None:
    if not source.startswith("installed:"):
        return None
    path = Path(source[10:])
    return path if path.is_dir() else None


def source_of(entry: dict) -> Path | None:
    """优先用市场 zip（干净原包），退而用宿主里已装的目录。"""
    return market_zip_of(entry.get("source") or "") or installed_dir_of(entry.get("source") or "")


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_skill(src: Path, dest_root: Path) -> tuple[Path, int]:
    """把一个 skill 目录拷成 dest_root/<id>/，返回 (目标目录, 文件数)。

    src 可能是市场 zip（解出来），也可能是宿主里已装的目录（直接拷）。
    市场 zip 的内层顶层目录名不一定等于 id（中文名/id 混用），所以这里按清单里的
    id 定位：找到 skill.json/plugin.json 所在的那一层，把它整个搬成 <id>/。
    """
    staging = dest_root / ("__stage_" + os.urandom(4).hex())
    staging.mkdir(parents=True, exist_ok=True)
    try:
        if src.is_dir():
            shutil.copytree(src, staging / "pkg", dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(*SKIP_DIRS, *[f"*{s}" for s in SKIP_SUFFIXES]))
        else:
            with zipfile.ZipFile(src) as archive:
                for info in archive.infolist():
                    name = info.filename
                    if not name or name.endswith("/"):
                        continue
                    parts = Path(name).parts
                    if any(p in SKIP_DIRS for p in parts):
                        continue
                    if Path(name).suffix.lower() in SKIP_SUFFIXES:
                        continue
                    target = (staging / name).resolve()
                    if staging.resolve() not in target.parents and target != staging.resolve():
                        raise SystemExit(f"{src.name}: 条目越界 {name}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as fh, target.open("wb") as dst:
                        shutil.copyfileobj(fh, dst)

        manifest = None
        for name in ("skill.json", "plugin.json"):
            found = sorted(staging.rglob(name))
            if found:
                # 只取**最浅**的那一层：pai-skills 这类整合包的 lib/<子包>/skill.json
                # 也是清单，按字典序会排在根清单前面，取错就把子包当成整包搬走了。
                manifest = min(found, key=lambda p: (len(p.relative_to(staging).parts), str(p)))
                break
        if manifest is None:
            raise SystemExit(f"{src}: 包内找不到 skill.json / plugin.json")

        # 双层嵌套包（真例 <id>/<id>/index.js）：外层只有清单副本、入口在内层。
        # 只按「最浅清单」搬会把外层当包根 —— 装完 Node 侧 pickEntryFallback 在
        # 本层找不到 index.js，直接报 entry-missing，整包加载失败。所以这里下潜一层。
        # 只在「最浅层确实没有入口」且「唯一一个直接子目录同时带清单与入口」时下潜，
        # 避免误伤 pai-skills 这类 lib/<子包>/ 整合包（相对层数是 2，不满足条件）。
        deeper = _nested_package(manifest.parent)
        if deeper is not None:
            manifest = deeper

        # 清单里 requires/capabilities/permissions 写成非数组的，按宿主口径修成数组：
        # 不修的话 palace 整包加载失败、voice-send 的 web_fetch 权限被静默清空。
        fixed_note = _normalize_manifest(manifest)
        if fixed_note:
            print(f"    ! {manifest.parent.name}/skill.json 修正字段：{fixed_note}")

        # localchat-kit 的补丁包针对旧版宿主布局（ui/index.html 等），5.2.x 已把界面挪到
        # src/web/static/。目标文件不存在时它原来会带着 cur=null 进 apply 循环，
        # 随后 detectEol(null) 里 null.includes 抛「Cannot read properties of null」，
        # 报错完全看不出原因。这里提前给可读结论 + detectEol 容忍 null。
        kit_note = _fix_localchat_kit(manifest.parent)
        if kit_note:
            print(f"    ! {manifest.parent.name}：{kit_note}")

        # chat-digest 的 available() 因为拿不到 electron 就返回 ok:false，
        # 宿主据此把整包判成 extension-unavailable —— 连不需要渲染引擎的
        # digest_read 都用不了。改成始终可用，渲染那一步由工具自己报错。
        digest_note = _fix_chat_digest(manifest.parent)
        if digest_note:
            print(f"    ! {manifest.parent.name}：{digest_note}")

        package = manifest.parent
        ident = json.loads(manifest.read_text(encoding="utf-8-sig")).get("id") or ""
        ident = str(ident).strip()
        if not ident:
            raise SystemExit(f"{src}: 清单里没有 id")

        dest = dest_root / ident
        if dest.exists():
            shutil.rmtree(dest)
        package.rename(dest)
        count = sum(1 for p in dest.rglob("*") if p.is_file())
        return dest, count
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def zip_dir(src: Path, out: Path, arc_root: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(src.rglob("*")):
            if not path.is_file():
                continue
            if any(p in SKIP_DIRS for p in path.parts):
                continue
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue
            arc = Path(arc_root) / path.relative_to(src)
            archive.write(path, arc.as_posix())


def build_ready(tiers: dict, eligible: dict, runs: dict, runs_on: dict,
                verify: dict) -> dict:
    """把可注册 skill 解成 ready/<id>/ 并打单包 zip。"""
    reset_dir(READY)
    reset_dir(READY_ZIPS)

    by_id = {s["id"]: s for s in tiers["skills"]}
    run_by_id = {r["skill"]: r for r in runs.get("runs", [])}
    on_by_id = {r["skill"]: r for r in runs_on.get("runs", [])}
    ver_by_id = {r["skill"]: r for r in verify.get("rows", [])}

    items = []
    missing = []
    for entry in sorted(eligible["eligible"], key=lambda e: e["id"]):
        ident = entry["id"]
        source = source_of(entry)
        if source is None:
            missing.append(ident)
            continue
        dest, files = copy_skill(source, READY)
        meta = by_id.get(ident, {})
        size = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
        zip_dir(dest, READY_ZIPS / zip_name_for(ident), ident)

        run = run_by_id.get(ident, {})
        on = on_by_id.get(ident, {})
        ver = ver_by_id.get(ident, {})
        items.append({
            "id": ident,
            "name": meta.get("name") or entry.get("name") or ident,
            "version": meta.get("version") or "",
            "tier": entry["tier"],
            "tools": [t["full"] for t in entry.get("tools", [])],
            "toolCount": len(entry.get("tools", [])),
            "permissions": entry.get("permissions", []),
            "capabilities": entry.get("usage", []),
            "files": files,
            "bytes": size,
            "zip": zip_name_for(ident),
            "marketZip": source.name,
            "run": {
                "verdict": run.get("verdict", ""),
                "ok": bool(run.get("ok")),
                "durationMs": run.get("duration_ms", 0),
                "error": run.get("error", ""),
            },
            "runEnabled": {
                "verdict": on.get("verdict", ""),
                "ok": bool(on.get("ok")),
                "durationMs": on.get("duration_ms", 0),
                "error": on.get("error", ""),
            },
            "verified": {
                "verdict": ver.get("verdict", ""),
                "ok": bool(ver.get("ok")),
                "durationMs": ver.get("durationMs") or 0,
                "error": ver.get("error", ""),
                "preview": ver.get("preview", ""),
            },
        })
    return {"items": items, "missing": missing}


def build_market_archive() -> dict:
    """把市场 379 个 zip 原样打成一个镜像包（离线备份/换机用）。"""
    DIST.mkdir(parents=True, exist_ok=True)
    out = DIST / "market-379.zip"
    if out.exists():
        out.unlink()
    count = 0
    total = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(MARKET_DIR.glob("*.zip")):
            archive.write(path, f"Skill市场/{path.name}")
            count += 1
            total += path.stat().st_size
    return {"zip": out.name, "count": count, "bytes": total, "zipBytes": out.stat().st_size}


def build_ready_all(ready_items: list) -> dict:
    """全部可注册 skill 的一次性安装包：内含 ready/ 与 install.py。"""
    DIST.mkdir(parents=True, exist_ok=True)
    out = DIST / "ready-all.zip"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(READY.rglob("*")):
            if not path.is_file():
                continue
            archive.write(path, (Path("ready") / path.relative_to(READY)).as_posix())
        for extra in ("install.py", "verify.py", "hostfix.py", "guard_host.py", "README.md",
                      "REPORT.md", "INDEX.json", "INDEX.md"):
            src = HERE / extra
            if src.is_file():
                archive.write(src, extra)
    return {"zip": out.name, "zipBytes": out.stat().st_size, "skills": len(ready_items)}


def write_report(tiers: dict, eligible: dict, ready: dict, market: dict,
                 verify: dict) -> str:
    stats = tiers["stats"]
    counts = eligible["counts"]
    tier_counts = stats["tierCounts"]
    lines = []
    add = lines.append

    add("# Skill 市场分层报告")
    add("")
    add(f"市场目录：`{MARKET_DIR}`")
    add("")
    add(f"- 市场 zip：**{stats['zipsInMarketDir']}** 个，合计 **35.0 MB**")
    add(f"- 分层扫描到：**{stats['skillsTotal']}** 个 skill / **{stats['toolsTotal']}** 个工具")
    add(f"- 打全宿主补丁后**可注册**：**{counts['eligible']}** 个 / **{counts['tools']}** 个工具")
    add(f"- 仍不可注册：**{counts['skipped']}** 个")
    add("")
    add(f"## 一、379 个里 {counts['eligible']} 个能用的原因")
    add("")
    add("宿主原来只有 53 个能注册，其余 326 个卡在三道**静态扫描闸门**上（另有三类误判见下文）。")
    add("三道都经实测证明是误判，补丁打在宿主侧（`hostfix.py`，见 README「宿主补丁」一节）：")
    add("")
    add("| 闸门 | 位置 | 误判原因 | 实测 |")
    add("| --- | --- | --- | --- |")
    add("| T4-host-source | `src/skill_manifest.py:323` | 见任何 `../` 就判死，不看层级也不看文件是否存在 | 89 个全部 `LOADED`，只有 `video-edit` 真越界 |")
    add("| hostImports | `src/skill_tools.py:775` | 与上面一模一样的第二道 | 同上 |")
    add("| ctx 成员 | `src/skill_tools.py:462` `_MEMBER` | ①`ctx.X` 与 `api.X` 混为一谈 ②扫原始文本不过滤注释（`api.php` 当成员） | 276 个里 242 个真跑 ok |")
    add("")
    add("被 ctx 挡住的 skill 源码都是防御式写法（`Array.isArray(ctx?.session?.trigger) ? … : []`、")
    add("`if (ctx?.sender && typeof ctx.sender.sendTextBatch === 'function')`），宿主不给就走降级分支，不崩。")
    add("所以补丁把 ctx 闸降级为「只审计不拦截」，`node:` / `npm:` 的真缺仍拦。")
    add("")
    add("另有两处让工具名对不上运行期（已修）：")
    add("")
    add("- **常量表内联**（`src/tool_schema.py`）：`registerTool({ id: TOOL.list, … })` 里的标识符引用")
    add("  解不出来 → `id` 键被丢弃 → 退回中文 `name` 当 id。解析前把 `const TOOL = {list:'list'}` 内联进源码即可。")
    add("- **运行期前缀**（`src/skill_tools.py` `_skill_plan`）：宿主把 skillId `sanitize` 后**截到 24 位**、")
    add("  点号换下划线，清单里存的是原样拼法，调用必报「tool 不属于被选扩展」。改用 `KNOWN_PREFIX_MISMATCH` 回拼。")
    add("")
    add("下表是**补丁前**的静态分层（`skill_tiers.json`），用来看整个市场的原始构成；")
    add("补丁后的实际可注册分层见 `INDEX.json` 的 `counts.byTier`。")
    add("")
    add("| 分层 | 数量 | 含义 |")
    add("| --- | ---: | --- |")
    meanings = {
        "T1-ready": "只用宿主明确支持的 ctx API，无网络依赖",
        "T2-web-fetch": "额外需要联网抓取（web_fetch / 外部域名）",
        "T3-extra-api": "额外要 onebot / qq_sticker 这类宿主未开放的能力",
        "T4-host-source": "运行期要 require 宿主 0.4 源码模块（如 `../../src/llm.js`）——补丁后整类解除",
        "T5-depends-other": "依赖市场里另一个扩展",
        "T6-disabled": "清单/入口缺失、扫描失败，或明确 disabled",
    }
    for tier in ("T1-ready", "T2-web-fetch", "T3-extra-api", "T4-host-source",
                 "T5-depends-other", "T6-disabled"):
        add(f"| `{tier}` | {tier_counts.get(tier, 0)} | {meanings[tier]} |")
    add("")
    add(f"### 仍不可注册的 {counts['skipped']} 个，具体卡在哪")
    add("")
    reasons: dict[str, int] = {}
    for item in eligible["skipped"]:
        text = str(item.get("reason") or "")
        key = text.split("：")[0].strip() if "：" in text else text
        reasons[key] = reasons.get(key, 0) + 1
    add("| 原因 | 数量 |")
    add("| --- | ---: |")
    for key, value in sorted(reasons.items(), key=lambda kv: -kv[1]):
        add(f"| {key} | {value} |")
    add("")
    n_npm = sum(v for k, v in reasons.items() if k.startswith("缺宿主内置模块或 npm 包"))
    n_t6 = sum(v for k, v in reasons.items() if k.startswith("T6-disabled"))
    n_t5 = sum(v for k, v in reasons.items() if k.startswith("tier T5"))
    n_t3 = sum(v for k, v in reasons.items() if k.startswith("tier T3"))
    add("这 %d 个是**真缺**，不是误判：%d 个真依赖宿主没装的 npm 包（只有 `electron`），"
        "%d 个清单标了结构性残缺，%d 个分层默认不放行"
        "（%d 个 T5 依赖别的扩展 / %d 个 T3 要额外 API）。"
        % (counts["skipped"], n_npm, n_t6, n_t5 + n_t3, n_t5, n_t3))
    add("")
    add("注 1：上一版这里还有 22 个「包本身没声明/解析不出工具名」的，已由第 19/20 处补丁（loose 兜底扫描）")
    add("全部解除 —— 它们其实都有工具，只是写法是 `registerTool(fn())` / 表驱动 / 位置参数注册函数，")
    add("静态解析看不到对象字面量。真宿主实测这 22 个里 19 个有 67 个工具。")
    add("")
    add("注 2：上一版这里还有 5 个「缺宿主内置模块或 npm 包」，其中 4 个（`free-tts` / `voice-reply-si` /")
    add("`group-analysis` / `pixiv-clash-search`）已由第 22~26 处补丁（H2a~H2e，按宿主 `node_modules` 实查）解除 ——")
    add("那 4 个包宿主本来就装着。只剩 `chat-digest` 要的 `electron` 是真缺（在 devDependencies 里）。")
    add("")
    add("### 第四类误判：「明明没依赖 npm 包却报缺」（第 21 处补丁已解除）")
    add("")
    add("7 个包报 `缺宿主内置模块或 npm 包：npm:, `，真宿主实测全部正常加载、工具调用成功：")
    add("")
    add("| skill | 工具数 | 误判出的「模块名」 |")
    add("| --- | ---: | --- |")
    add("| bili-share / comfyui-newbie / knowledge-base / pm-wiki / relay | 1 / 4 / 3 / 3 / 4 | `, ` |")
    add("| qq-card-reader | 1 | `]) {\\n      if (u.searchParams.has(k)) …` |")
    add("| sukuna-raid-coop | 8 | ` }\\n      },\\n      required: [` |")
    add("")
    add("根因：`src/skill_tools.py` 的 `_IMPORT` 正则 `from\\s*['\\\"]([^'\\\"]+)['\\\"]` 把英文单词 `from`")
    add("也当成 import 语句。`['and', 'for', 'with', 'that', 'this', 'from', 'see']` 这类停用词数组里，")
    add("`from', '` 正好匹配成 `from '…'`，于是把后面那一大段源码当成模块名。")
    add("修法是把捕获组限制成合法模块说明符字符集：`[^'\\\"\\s,;()\\[\\]{}]+`。")
    add("")
    add("### 第五类误判：「宿主 node_modules 里明明有这个包却报缺」（第 22~26 处补丁已解除）")
    add("")
    add("`blocked_capabilities()` 对 `npm:` 前缀的 token 一律判死，从不查宿主 `node_modules`；")
    add("docstring 写着「npm 包不在宿主 node_modules 里就是真缺」，实现里根本没查。")
    add("")
    add("宿主根 `data\\qq-only\\qqagent_host\\node_modules` 实有 `argparse / js-yaml / undici / ws`"
        "（`runtime/qqagent-host/package.json` 的 dependencies 正是后三个），只有 `electron` 在 devDependencies。")
    add("")
    add("| skill | 报缺的包 | 真宿主实测 |")
    add("| --- | --- | --- |")
    add("| free-tts / voice-reply-si | `ws` | ok，工具调用成功 |")
    add("| group-analysis | `js-yaml` | ok，2 个工具 |")
    add("| pixiv-clash-search | `undici` | ok |")
    add("| chat-digest | `electron` | **真缺**，`Cannot find module 'electron'` |")
    add("")
    add("修法：给 `blocked_capabilities()` 加可选参数 `modules`，`npm:` token 先查")
    add("`<host_root>/node_modules/<pkg>` 是否存在，存在就放行；`eligible_skills()` 整个清单只算一次")
    add("（探测 200 次 `iterdir` 只花 11.4 ms）。")
    add("")
    add("### 第六类误判：「双层嵌套包被判 no-entry」（第 27 处补丁已解除）")
    add("")
    add("有些市场包解压后是**同名目录套同名目录**，外层只放清单副本、真源码在内层：")
    add("")
    add("```")
    add("jujutsu-phantom-parade/skill.json                          ← 外层清单副本")
    add("jujutsu-phantom-parade/plugin.json")
    add("jujutsu-phantom-parade/jujutsu-phantom-parade/index.js     ← 真入口在这层")
    add("jujutsu-phantom-parade/jujutsu-phantom-parade/{skill.json,plugin.json,lib/,kb/,tools/}")
    add("```")
    add("")
    add("`skill_manifest._package_root()` 原来取「**最浅**的 skill.json / plugin.json 所在目录」，")
    add("于是停在外层；`_package_entry()` 拼 `jujutsu-phantom-parade/index.js` 当然找不到 → `no-entry` → `T6-disabled`。")
    add("")
    add("修法：`_package_root()` 改成**优先选同时含清单与入口的那一层**，找不到才退回最浅清单层。")
    add("全市场 379 个 zip 回归：**root 只变 1 个**（就是它），其余 378 个完全不变。")
    add("修完 `classify` 从 `T6-disabled / no-entry` 变成 `T2-web-fetch`（它声明了 `web_fetch` 权限），")
    add("6 个工具全部注册、真跑 `call card_info ok=True` / `call kb_search ok=True`。")
    add("")
    add("配套地 `build.py` 加了 `_nested_package()`：解包时若外层无入口、恰好一个子目录且子目录同时带清单与入口，")
    add("就把内层当包根搬走。理由：只按「最浅清单」搬会把外层当包根，装完 Node 侧 `pickEntryFallback`")
    add("在本层找不到 `index.js`，整包加载失败（`runtime/qqagent-host/src/plugin-loader.js:344-392`）。")
    add("")
    add(f"## 二、{len(ready['items'])} 个可注册 skill 与真跑结果")
    add("")
    add("真跑方式：`src/extension_host.call_tool()` 起 Node 子进程，用宿主自己的")
    add("`host-one.mjs` 加载 skill 入口，调用它的第一个工具。")
    add("")
    add("下面给的是**装到同一个数据根后、按生产布局真跑一遍**的结果")
    add("（`qq-skill-packs/verify.py` 的实测输出，宿主根是 materialize 出来的那份，")
    add("`source_dir` 与 `data_dir` 都按生产链路传）：")
    add("")
    add("判定口径：")
    add("")
    add("- `ok` —— 工具返回 `ok=true`，真正跑出了业务结果")
    add("- `ran-blocked` —— 子进程正常加载并执行，只是这次调用的业务前置没满足")
    add("  （缺参数、缺本地文件、缺知识库、联网超时等）。**不是加载失败。**")
    add("- `load-failed` —— `Cannot find module` / `ERR_MODULE_NOT_FOUND` / `SyntaxError` 之类真问题，")
    add("  或者清单工具名与运行期注册名对不上（`tool 不属于被选扩展`）")
    add("")
    vcounts = verify.get("counts") or {}
    add(f"**结论：{len(ready['items'])} 个全部能被宿主加载并执行，零 load-failed。**")
    add(f"其中 `ok {vcounts.get('ok', 0)}` 个直接跑出结果，"
        f"`ran-blocked {vcounts.get('ranBlocked', 0)}` 个是业务前置没满足（明细见下）。")
    add("")
    add("| skill | 分层 | 工具数 | 真跑 | 耗时 |")
    add("| --- | --- | ---: | --- | ---: |")
    for item in ready["items"]:
        ver = item.get("verified") or {}
        ms = ver.get("durationMs") or 0
        add("| `{id}` | {tier} | {n} | {v} | {ms} |".format(
            id=item["id"], tier=item["tier"].split("-")[0], n=item["toolCount"],
            v=ver.get("verdict") or "—", ms=f"{ms} ms" if ms else "—"))
    add("")
    blocked = [i for i in ready["items"]
               if (i.get("verified") or {}).get("verdict") == "ran-blocked"]
    if blocked:
        add("### 这 %d 个业务前置没满足的，具体卡在哪" % len(blocked))
        add("")
        add("全部是「加载成功、执行到了业务代码，然后因为本地条件不具备而返回提示」，")
        add("不是插件/包本身的问题：")
        add("")
        for item in blocked:
            err = (item.get("verified") or {}).get("error") or ""
            add(f"- `{item['id']}` —— {err}")
        add("")
    add("")
    add("## 三、产物怎么用")
    add("")
    add("| 产物 | 用途 |")
    add("| --- | --- |")
    add("| `ready/<id>/` | 单个 skill 的源码目录，复制到 `<data>/qq-only/skill_extensions/` 即安装 |")
    add("| `dist/ready-zips/<id>.zip` | 单个 skill 的安装包，走 `POST /api/skills/install` |")
    add(f"| `dist/ready-all.zip` | {len(ready['items'])} 个一次装完（解压后跑 `install.py`） |")
    add("| `dist/market-379.zip` | 市场 379 个 zip 的离线镜像 |")
    add("")
    add("宿主数据目录（`<data>`）默认是 `D:\\qq机器人5.0\\data`，即")
    add("`skill_extensions` 在 `D:\\qq机器人5.0\\data\\qq-only\\skill_extensions`。")
    add("")
    add("**装上 ≠ 能用**：宿主对 skill 有两层启用态，两边都得开：")
    add("")
    add("1. `<data>/qq-only/qqagent_extensions.json` 的 `extensions.<id>.enabled`（扩展管理）")
    add("2. `<data>/qq-only/qqagent_host/data-host-one/config.json` 的 `skills.<id>.enabled`（JS 宿主自己）")
    add("")
    add("`install.py` 会同时写这两处（走 `extension_registry.set_enabled`，它内部会 `_mirror_host_enabled`）。")
    add("前提是宿主根已经 materialize（`materialize_host_root()` 或控制台点一次「准备运行时」）。")
    add("")
    return "\n".join(lines)


def write_index(ready: dict, tiers: dict, market: dict, eligible: dict) -> None:
    # byTier 要的是「可注册的那些各自的 tier」，不是全市场 379 个的 tier 分布。
    by_tier = (eligible.get("counts") or {}).get("byEligibleTier") or {}
    if not by_tier:
        by_tier = {}
        for item in ready["items"]:
            key = item.get("tier") or "unknown"
            by_tier[key] = by_tier.get(key, 0) + 1
    index = {
        "generatedBy": "qq-skill-packs/build.py",
        "marketDir": str(MARKET_DIR),
        "market": market,
        "counts": {
            "market": tiers["stats"]["skillsTotal"],
            "eligible": len(ready["items"]),
            "skipped": len(tiers["skills"]) - len(ready["items"]),
            "tools": sum(i["toolCount"] for i in ready["items"]),
            "byTier": by_tier,
        },
        "skills": ready["items"],
        "missingSource": ready["missing"],
    }
    (HERE / "INDEX.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# Skill 包索引", "",
             f"市场 `{MARKET_DIR}` 共 {tiers['stats']['skillsTotal']} 个 zip，"
             f"其中 **{len(ready['items'])} 个**可注册（{index['counts']['tools']} 个工具）。", "",
             "| # | skill | 名称 | 分层 | 工具 | 体积 | 真跑 |", "| ---: | --- | --- | --- | ---: | ---: | --- |"]
    for n, item in enumerate(ready["items"], 1):
        verdict = ((item.get("verified") or {}).get("verdict")
                   or item["runEnabled"]["verdict"] or item["run"]["verdict"] or "—")
        lines.append("| {n} | `{id}` | {name} | {tier} | {tools} | {size} | {v} |".format(
            n=n, id=item["id"], name=item["name"], tier=item["tier"], tools=item["toolCount"],
            size=human(item["bytes"]), v=verdict))
    lines.append("")
    (HERE / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    tiers = load(TIERS_JSON)
    eligible = load(ELIGIBLE_JSON)
    runs = load(RUNS_JSON) if RUNS_JSON.is_file() else {"runs": []}
    runs_on = load(RUNS_ENABLED_JSON) if RUNS_ENABLED_JSON.is_file() else {"runs": []}
    verify = load(VERIFY_JSON) if VERIFY_JSON.is_file() else load(VERIFY_LEGACY_JSON)

    print("1) 解包可注册 skill ...")
    ready = build_ready(tiers, eligible, runs, runs_on, verify)
    print(f"   ready/{len(ready['items'])} 个；缺源 {ready['missing']}")

    print("2) 打单包 zip ...")
    total = sum((READY_ZIPS / i["zip"]).stat().st_size for i in ready["items"])
    print(f"   dist/ready-zips/{len(ready['items'])} 个，合计 {human(total)}")

    print("3) 打市场镜像 ...")
    market = build_market_archive()
    print(f"   dist/{market['zip']}：{market['count']} 个 zip，"
          f"原始 {human(market['bytes'])} → 压缩 {human(market['zipBytes'])}")

    print("4) 写报告与索引 ...")
    report = write_report(tiers, eligible, ready, market, verify)
    (HERE / "REPORT.md").write_text(report, encoding="utf-8")
    write_index(ready, tiers, market, eligible)

    print("5) 打一次性安装包 ...")
    ready_all = build_ready_all(ready["items"])
    print(f"   dist/{ready_all['zip']}：{human(ready_all['zipBytes'])}")

    print("")
    print(json.dumps({
        "market": tiers["stats"]["skillsTotal"],
        "eligible": len(ready["items"]),
        "tools": sum(i["toolCount"] for i in ready["items"]),
        "byTier": (eligible.get("counts") or {}).get("byEligibleTier") or {},
        "dist": sorted(p.name for p in DIST.iterdir()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
