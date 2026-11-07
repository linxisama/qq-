"""把 `packs/` 与 `overrides/` 里的产物装进 QQ 工作台的插件库。

两条通道，落点都是同一个 `custom_plugins` 目录：

* 目录 mod 包 → 整个 `pack_xxx/` 目录复制进去。以磁盘 `plugin.json` 为唯一事实，
  **不需要**登记 `custom_plugins.json`。
* 裸 .py 覆盖包 → `<id>.py` 复制进去，**必须**写进 `custom_plugins.json` 的
  `{"plugins": [...]}`，否则宿主根本不会 import 它。

目标目录的判定顺序：
  1. `--dir` 显式指定；
  2. 宿主控制台在线时问 `GET /api/plugins/custom`（`--url` 可改，默认 127.0.0.1:8099）；
  3. 已知的安装版/源码态默认路径，挑存在且有内容的那个。

用法：
    python install.py                 # 预演，只打印将要做什么
    python install.py --apply         # 真装
    python install.py --apply --enable        # 顺带把插件设为启用
    python install.py --apply --only sleep_mode,qqagent_bridge
    python install.py --apply --channel mod   # 只装目录包（或 override）
    python install.py --apply --overwrite     # 覆盖同名已有文件/目录
    python install.py --apply --uninstall     # 反向卸载本套产物

安全约定：默认只预演；`--apply` 才动磁盘；覆盖已有文件前先备份成 `.bak-<uuid>`。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = json.loads((ROOT / "INDEX.json").read_text(encoding="utf-8"))

DEFAULT_URL = "http://127.0.0.1:8090"


# --------------------------------------------------------------------------- #
# 目标目录
# --------------------------------------------------------------------------- #
def candidates() -> list[Path]:
    """已知的 custom_plugins 落点，按可能性排序。"""
    out: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        out.append(Path(local) / "WhaleGirlQQ" / "data" / "qq-only" / "custom_plugins")
    out.append(Path(r"D:\qq机器人5.0") / "data" / "qq-only" / "custom_plugins")
    out.append(Path.home() / "WhaleGirlQQ" / "data" / "qq-only" / "custom_plugins")
    return out


def from_api(url: str, timeout: float = 3.0) -> Path | None:
    """问宿主自己插件库在哪——这是唯一权威答案，避免猜错账号目录。"""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/plugins/custom",
                                    timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None
    raw = str(payload.get("dir") or "").strip()
    return Path(raw) if raw else None


def resolve_dir(explicit: str | None, url: str) -> tuple[Path, str]:
    if explicit:
        return Path(explicit).expanduser(), "--dir 指定"
    found = from_api(url)
    if found:
        return found, f"控制台 {url}"
    for path in candidates():
        if path.is_dir() and any(path.iterdir()):
            return path, "已存在的默认路径"
    for path in candidates():
        if path.is_dir():
            return path, "已存在的空默认路径"
    return candidates()[0], "默认路径（尚不存在，将创建）"


# --------------------------------------------------------------------------- #
# 计划
# --------------------------------------------------------------------------- #
def select(entries: list[dict], only: set[str], channel: str) -> list[dict]:
    out = []
    for e in entries:
        if only and e["id"] not in only and e["pack_id"] not in only:
            continue
        if channel != "all" and e["channel"] != channel:
            continue
        out.append(e)
    return out


def plan(target: Path, entries: list[dict], overwrite: bool) -> list[dict]:
    steps = []
    for e in entries:
        if e["channel"] == "mod":
            src = ROOT / "packs" / e["pack_id"]
            dst = target / e["pack_id"]
        else:
            src = ROOT / "overrides" / f"{e['id']}.py"
            dst = target / f"{e['id']}.py"
        exists = dst.exists()
        steps.append({"entry": e, "src": src, "dst": dst,
                      "exists": exists,
                      "action": "覆盖" if exists and overwrite else
                                ("跳过（已存在）" if exists else "安装")})
    return steps


# --------------------------------------------------------------------------- #
# 落盘
# --------------------------------------------------------------------------- #
def backup(path: Path) -> Path:
    bak = path.with_name(path.name + f".bak-{uuid.uuid4().hex[:8]}")
    if path.is_dir():
        shutil.copytree(path, bak)
    else:
        shutil.copy2(path, bak)
    return bak


def copy_item(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        tmp = dst.with_name(dst.name + f".{uuid.uuid4().hex[:8]}.tmp")
        shutil.copy2(src, tmp)
        tmp.replace(dst)


def read_custom(path: Path) -> list[str]:
    try:
        raw = json.loads(path.read_text("utf-8"))
    except Exception:
        return []
    if isinstance(raw, dict):
        raw = raw.get("plugins")
    return [str(x) for x in raw if isinstance(x, str)] if isinstance(raw, list) else []


def write_custom(path: Path, ids: list[str]) -> None:
    path.write_text(json.dumps({"plugins": sorted(set(ids))},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_steps(target: Path, steps: list[dict], overwrite: bool) -> dict:
    target.mkdir(parents=True, exist_ok=True)
    custom_path = target.parent / "custom_plugins.json"
    done, skipped, backed = [], [], []
    for s in steps:
        if s["action"].startswith("跳过"):
            skipped.append(s["entry"]["id"])
            continue
        if s["exists"] and overwrite:
            backed.append(str(backup(s["dst"])))
            if s["dst"].is_dir():
                shutil.rmtree(s["dst"])
            else:
                s["dst"].unlink()
        copy_item(s["src"], s["dst"])
        done.append(s["entry"]["id"])
        if s["entry"]["channel"] == "override":
            ids = read_custom(custom_path)
            if s["entry"]["id"] not in ids:
                write_custom(custom_path, ids + [s["entry"]["id"]])
    return {"installed": done, "skipped": skipped, "backups": backed,
            "custom_manifest": str(custom_path)}


def uninstall(target: Path, entries: list[dict]) -> dict:
    removed, missing = [], []
    custom_path = target.parent / "custom_plugins.json"
    ids = read_custom(custom_path)
    touched = False
    for e in entries:
        path = (target / e["pack_id"]) if e["channel"] == "mod" else (target / f"{e['id']}.py")
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(str(path))
        elif path.is_file():
            path.unlink()
            removed.append(str(path))
        else:
            missing.append(str(path))
        if e["channel"] == "override" and e["id"] in ids:
            ids = [x for x in ids if x != e["id"]]
            touched = True
    if touched:
        write_custom(custom_path, ids)
    return {"removed": removed, "missing": missing}


# --------------------------------------------------------------------------- #
# 启用（可选）
# --------------------------------------------------------------------------- #
def enable_via_api(url: str, plugin_ids: list[str]) -> dict:
    """宿主在线时改设置；离线时只提示，让用户在控制台勾。

    端点是 `POST /api/plugins/{plugin_id}`（`src/qq_app.py:6269`），
    body 就是设置字典本身（`{"enabled": true}`），不是包一层的对象。
    """
    result = {"ok": False, "url": url, "enabled": [], "errors": []}
    for pid in plugin_ids:
        body = json.dumps({"enabled": True}).encode("utf-8")
        req = urllib.request.Request(f"{url.rstrip('/')}/api/plugins/{pid}",
                                     data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
            result["enabled"].append(pid)
        except Exception as exc:  # 端点可能不存在，离线/版本差异都算失败
            result["errors"].append(f"{pid}: {type(exc).__name__}: {exc}")
    result["ok"] = not result["errors"]
    return result


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="把 qq-plugin-packs 装进 QQ 工作台")
    ap.add_argument("--dir", help="custom_plugins 目录（默认自动判定）")
    ap.add_argument("--url", default=DEFAULT_URL, help=f"控制台地址，默认 {DEFAULT_URL}")
    ap.add_argument("--apply", action="store_true", help="真的写盘（默认只预演）")
    ap.add_argument("--overwrite", action="store_true", help="覆盖同名已有项（先备份）")
    ap.add_argument("--uninstall", action="store_true", help="卸载本套产物")
    ap.add_argument("--enable", action="store_true", help="安装后尝试通过控制台启用")
    ap.add_argument("--only", default="", help="只处理这些 id，逗号分隔")
    ap.add_argument("--channel", choices=("all", "mod", "override"), default="all")
    args = ap.parse_args(argv)

    target, how = resolve_dir(args.dir, args.url)
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    entries = select(INDEX["plugins"], only, args.channel)

    print(f"宿主版本 {INDEX['host_version']}｜产物 {INDEX['total']} 个"
          f"（目录 mod {INDEX['mod']}／裸 .py {INDEX['override']}）")
    print(f"目标目录 {target}  ← {how}")
    print(f"本次选中 {len(entries)} 个｜通道 {args.channel}"
          f"{'｜覆盖' if args.overwrite else ''}")
    print()

    if args.uninstall:
        if not args.apply:
            for e in entries:
                p = (target / e["pack_id"]) if e["channel"] == "mod" else (target / f"{e['id']}.py")
                print(f"  将删除 {p}  {'（存在）' if p.exists() else '（不存在）'}")
            print("\n预演结束；加 --apply 才会真的删除。")
            return 0
        out = uninstall(target, entries)
        for p in out["removed"]:
            print(f"  已删除 {p}")
        for p in out["missing"]:
            print(f"  未找到 {p}")
        print(f"\n卸载完成：删除 {len(out['removed'])} 项，"
              f"未找到 {len(out['missing'])} 项。重启宿主生效。")
        return 0

    steps = plan(target, entries, args.overwrite)
    for s in steps:
        print(f"  [{s['entry']['channel']:8}] {s['action']:12} "
              f"{s['entry']['id']:22} → {s['dst']}")

    if not args.apply:
        print(f"\n预演结束：将装 {sum(1 for s in steps if s['action'] != '跳过（已存在）')} 个，"
              f"跳过 {sum(1 for s in steps if s['action'].startswith('跳过'))} 个。")
        print("加 --apply 才会真的写盘。")
        return 0

    out = apply_steps(target, steps, args.overwrite)
    print(f"\n已安装 {len(out['installed'])} 个，跳过 {len(out['skipped'])} 个。")
    if out["backups"]:
        print(f"覆盖前备份 {len(out['backups'])} 份：")
        for b in out["backups"]:
            print(f"  {b}")
    print(f"裸 .py 登记清单：{out['custom_manifest']}")

    if args.enable:
        ids = [e["id"] for e in entries]
        res = enable_via_api(args.url, ids)
        if res["enabled"]:
            print(f"已通过控制台启用 {len(res['enabled'])} 个。")
        if res["errors"]:
            print("以下没启用成功，请到控制台「插件」里手动勾：")
            for e in res["errors"][:10]:
                print(f"  {e}")

    print("\n重启 QQ 工作台后生效。目录 mod 走「插件 → 本地插件包」，"
          "裸 .py 走「插件 → 自定义插件」。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
