# -*- coding: utf-8 -*-
"""验证装好的 skill 真能被宿主加载并执行。

它按**生产布局**跑：宿主根 = `<data-root>/data/qq-only/qqagent_host`（materialize 出来的那份），
`source_dir` 传这个根，`data_dir` 传 `<data-root>/data`。这样 host-one.mjs 的缺省数据目录
（`<source>/data-host-one`）与 extension_registry 写启用态的位置天然一致。

用法：

    # 验证默认数据根（D:\\qq机器人5.0）里装好的 skill，每个跑它的第一个工具
    python verify.py

    # 验证另一个数据根（比如从分发包另装一份）
    python verify.py --data-root "D:\\somewhere\\inst"

    # 只验证指定几个
    python verify.py --only kaomoji,csgo-5e
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

def _default_host() -> Path:
    """探测宿主根：环境变量 > 本机开发布局 > 常见安装位置。"""
    import os

    env = os.environ.get("QQ_HOST_ROOT", "").strip()
    if env:
        return Path(env)
    dev = Path(r"D:\qq机器人5.0")
    if dev.is_dir():
        return dev
    local = os.environ.get("LOCALAPPDATA")
    for cand in ([Path(local) / "WhaleGirlQQ"] if local else []) + [Path.home() / "WhaleGirlQQ"]:
        if cand.is_dir():
            return cand
    return dev  # 都不在就保持原值，由调用方报「宿主根不存在」


DEFAULT_HOST = _default_host()

# 运行期宿主给工具 id 加的清洗规则，见 runtime/qqagent-host/src/plugin-loader.js:81-86：
#   sanitize = (s) => String(s ?? '').replace(/[^a-zA-Z0-9_-]/g, '_')
#   sid = sanitize(skillId).slice(0, 24)   tid = sanitize(def.id).slice(0, 38)
#   prefixedId = `${sid}__${tid}`
# 清单里存的是 skill id 的原样拼法，两者在「id 带点号」或「id 超过 24 字符」时不一致。
_BAD = re.compile(r"[^a-zA-Z0-9_-]")


def live_prefix(skill_id: str) -> str:
    return _BAD.sub("_", str(skill_id or ""))[:24]


def live_tool_id(full_name: str) -> str:
    """清单里的 `<清单id>__<raw>` → 运行期真正注册的 id。"""
    text = str(full_name or "")
    prefix, sep, rest = text.partition("__")
    if not sep:
        return _BAD.sub("_", text)[:38]
    return live_prefix(prefix) + "__" + _BAD.sub("_", rest)[:38]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="真跑验证已安装的 skill")
    parser.add_argument("--root", default=str(DEFAULT_HOST))
    parser.add_argument("--data-root", default="")
    parser.add_argument("--only", default="")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--json", default="", help="把结果写到这个 json 文件")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root = Path(args.root).expanduser()
    data_root = Path(args.data_root).expanduser() if args.data_root else root
    # 先校验宿主根再 import：否则 --root 指错时用户只看到
    # `ModuleNotFoundError: No module named 'src'`，不知道是自己路径写错了。
    if not (root / "src" / "skill_tools.py").is_file():
        raise SystemExit(
            f"{root} 看起来不是 QQ Agent 仓库根（缺 src/skill_tools.py）。\n"
            f"  用 --root 指向宿主仓库根，或设环境变量 QQ_HOST_ROOT。")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from src import (extension_host, extension_registry, qqagent_host,
                     skill_manifest, skill_tools)

    root_text = str(data_root)

    class _RT:
        data_root = root_text

    data_dir = skill_tools.data_dir(_RT())          # <data-root>/data/qq-only
    extensions = skill_tools.extensions_dir(_RT())
    host_root = qqagent_host.default_host_root(data_dir)
    # extension_host / extension_registry 的 data_dir 是**上一级**（<data-root>/data）：
    # 它们各自再拼 'qq-only'（extension_registry.state_path、extension_host.CALL_CWD_PARTS）。
    # 传 <data-root> 会让启用表落到 <data-root>/qq-only/qqagent_extensions.json（不存在）
    # → enabled_ids 恒为 [] → 所有带 requires 的包永远报「依赖未启用」。
    host_data_dir = data_dir.parent

    print(f"数据根   : {data_root}")
    print(f"数据目录 : {host_data_dir}（extension_host / registry 用这级）")
    print(f"skill 目录: {extensions}")
    print(f"宿主根   : {host_root}  存在={host_root.is_dir()}")
    print("")

    if not host_root.is_dir():
        print("宿主根不存在：先跑 install.py（它会自动 materialize），或控制台点一次「准备运行时」")
        return 1

    installed = sorted(p.name for p in extensions.iterdir() if p.is_dir()) \
        if extensions.is_dir() else []
    if args.only:
        wanted = [s.strip() for s in args.only.split(",") if s.strip()]
        installed = [s for s in installed if s in wanted]

    print(f"已安装 {len(installed)} 个 skill")

    # 清单是缓存：先用**这次要验证的宿主**强制重建一次，否则会拿别的宿主/别的 CWD 留下的旧清单，
    # 表现成「tool id 不属于这个扩展」（清单里是裸名 nav，call_tool 要 <id>__nav）。
    try:
        report = skill_manifest.ensure_manifest(_RT(), 0, True)
        print(f"重建清单 : ok={report.get('ok')} skills={report.get('skills')} "
              f"stamp={str(report.get('stamp') or '')[:12]}")
        if not report.get("ok"):
            print(f"  警告：清单没重建成功（{json.dumps(report.get('error'), ensure_ascii=False)[:200]}）；"
                  f"下面的结果可能是旧清单造成的假象")
    except Exception as exc:  # noqa: BLE001
        print(f"  警告：重建清单抛异常（{type(exc).__name__}: {exc}）；继续用现有清单")

    # 工具清单：从宿主重建的 skill-tools.json 里读，拿每个 skill 的第一个工具名
    manifest_path = data_dir / skill_tools.MANIFEST_FILE
    first_tool = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest.get("skills") or []:
            sid = str(item.get("id") or "")
            tools = [str(t.get("name") or "") for t in (item.get("tools") or [])
                     if isinstance(t, dict) and t.get("name")]
            if sid and tools:
                first_tool[sid] = tools[0]
    naked = [sid for sid, name in first_tool.items() if "__" not in name]
    if naked:
        print(f"  注意：{len(naked)} 个 skill 的工具名没有 __ 前缀（宿主 skill 清单补丁没打？）："
              f"{naked[:5]}")

    enabled = set()
    try:
        state = extension_registry.load(data_dir.parent)
        enabled = {k for k, v in (state.get("extensions") or {}).items()
                   if isinstance(v, dict) and v.get("enabled")}
    except Exception:
        pass

    cfg = {}
    try:
        cfg = {k: bool(v.get("enabled")) for k, v in
               (qqagent_host.read_host_config(host_root).get("skills") or {}).items()}
    except Exception:
        pass

    async def call_one(sid, tool):
        """按运行期口径调用；清单名对不上时用 list_tools 取真实工具名再试一次。"""
        package = extensions / sid
        ext_id = live_prefix(sid)
        out = await extension_host.call_tool(
            node="node", host_script=str(host_root / "host-one.mjs"),
            extension=str(package), source_dir=str(host_root),
            tool_id=live_tool_id(tool), arguments={}, timeout=args.timeout,
            data_dir=str(host_data_dir), extension_id=ext_id)
        err = str(out.get("error") or "")
        if out.get("ok") or "不属于" not in err:
            return out, tool
        try:
            listed = await extension_host.list_tools(
                node="node", host_script=str(host_root / "host-one.mjs"),
                extension=str(package), source_dir=str(host_root),
                timeout=args.timeout, data_dir=str(host_data_dir), extension_id=ext_id)
        except Exception:  # noqa: BLE001
            return out, tool
        real = []
        for item in (listed.get("tools") or []):
            name = item.get("id") if isinstance(item, dict) else item
            if name and str(name).startswith(ext_id + "__"):
                real.append(str(name))
        if not real:
            return out, tool
        retry = await extension_host.call_tool(
            node="node", host_script=str(host_root / "host-one.mjs"),
            extension=str(package), source_dir=str(host_root),
            tool_id=real[0], arguments={}, timeout=args.timeout,
            data_dir=str(host_data_dir), extension_id=ext_id)
        return retry, real[0]

    async def probe_loaded(sid):
        """没有工具的包：用 list_tools 确认宿主认不认它。

        返回 (verdict, 说明)：verdict 是 ok / ran-blocked / no-tool / load-failed 之一。
        · 宿主 ok=True              → ok（纯提示词 / 纯 hook / 纯 provider，已加载）
        · 宿主 ok=False 且是业务拒绝 → ran-blocked（如 account-pool「账号池是空的」）
        · 宿主 ok=False 且是加载类错 → load-failed
        """
        package = extensions / sid
        try:
            listed = await extension_host.list_tools(
                node="node", host_script=str(host_root / "host-one.mjs"),
                extension=str(package), source_dir=str(host_root),
                timeout=args.timeout, data_dir=str(host_data_dir),
                extension_id=live_prefix(sid))
        except Exception as exc:  # noqa: BLE001
            return "load-failed", f"{type(exc).__name__}: {exc}"
        if listed.get("ok"):
            return "ok", "无工具包（纯提示词 / 纯 hook / 纯 provider），宿主已加载"
        err = str(listed.get("error") or "")
        # 加载类错误：模块找不到、清单非法、入口缺失、依赖缺失/未启用、逃逸运行根
        for token in ("Cannot find module", "ERR_MODULE_NOT_FOUND", "SyntaxError",
                      "manifest-invalid", "entry-missing", "extension-invalid",
                      "dependency-", "escape-run-root", "load-failed", "no-entry",
                      "no-manifest", "宿主配置未启用"):
            if token in err:
                return "load-failed", err
        return "ran-blocked", err or "宿主拒绝加载（业务前置未满足）"

    async def run_all():
        rows = []
        for sid in installed:
            tool = first_tool.get(sid, "")
            row = {"skill": sid, "tool": tool, "registry": sid in enabled,
                   "hostConfig": cfg.get(sid), "ok": False, "verdict": "", "error": ""}
            if not tool:
                # 有一类包天生没有工具、但注册后照样生效：纯提示词（force-send）、
                # 纯 hook（topic-guard）、纯 provider（video-frames / account-pool）。
                # 判它们「没工具 = 没装好」是错的，改用 list_tools 看宿主是否真的认这个包。
                verdict, why = await probe_loaded(sid)
                row["verdict"] = verdict
                row["ok"] = verdict == "ok"
                row["error"] = "" if verdict == "ok" else why
                if verdict == "ok":
                    row["preview"] = why
                rows.append(row)
                continue
            try:
                out, used = await call_one(sid, tool)
            except Exception as exc:  # noqa: BLE001
                row["verdict"] = "load-failed"
                row["error"] = f"{type(exc).__name__}: {exc}"
                rows.append(row)
                continue

            ok = bool(out.get("ok"))
            err = str(out.get("error") or "")
            value = out.get("value") or {}
            text = ""
            if isinstance(value, dict):
                content = value.get("content")
                if isinstance(content, list) and content:
                    first = content[0] if isinstance(content[0], dict) else {}
                    text = str(first.get("text") or "")
                elif isinstance(content, str):
                    text = content
                if not text:
                    text = str(value.get("content") or value.get("text") or "")
            text = text.strip()
            row.update(ok=ok, durationMs=out.get("duration_ms"), error=err,
                       preview=text[:160])
            if used != tool:
                row["usedTool"] = used
            if ok:
                row["verdict"] = "ok"
            elif err and "不属于" in err:
                # 清单里的工具名与运行期注册的名字对不上 —— 这是真问题，不是业务前置
                row["verdict"] = "load-failed"
            elif err:
                # 子进程正常跑完、业务层报错 —— 不是加载失败
                row["verdict"] = "ran-blocked"
            else:
                row["verdict"] = "ok"
            rows.append(row)
        return rows

    rows = asyncio.run(run_all())

    print("")
    print(f"{'skill':<22}{'registry':<10}{'hostCfg':<9}{'verdict':<14}ms")
    print("-" * 70)
    for row in rows:
        print(f"{row['skill']:<22}{str(row['registry']):<10}{str(row['hostConfig']):<9}"
              f"{row['verdict']:<14}{row.get('durationMs') or ''}")

    bad = [r for r in rows if r["verdict"] == "load-failed"]
    ok = [r for r in rows if r["verdict"] == "ok"]
    blocked = [r for r in rows if r["verdict"] == "ran-blocked"]
    no_tool = [r for r in rows if r["verdict"] == "no-tool"]

    print("")
    print(f"ok {len(ok)} / ran-blocked {len(blocked)} / no-tool {len(no_tool)} / "
          f"load-failed {len(bad)}")
    for row in bad:
        print(f"  加载失败 {row['skill']}: {row['error'][:150]}")
    for row in blocked:
        print(f"  业务阻塞 {row['skill']}: {row['error'][:120]}")
    for row in no_tool:
        print(f"  无工具   {row['skill']}: {row['error'][:100]}")

    if args.json:
        Path(args.json).write_text(
            json.dumps({"rows": rows, "counts": {
                "ok": len(ok), "ranBlocked": len(blocked),
                "noTool": len(no_tool), "loadFailed": len(bad)}},
                ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n结果写到 {args.json}")

    print("")
    print("结论：" + ("通过" if not bad else "有加载失败"))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
