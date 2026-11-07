#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qqplugin 一键自检：把四套产物都验一遍，不写任何文件。

用户在仓库根跑这一条就够：

    python selfcheck.py                  # 只读，全部跑一遍
    python selfcheck.py --quick          # 跳过 skills 的真跑（省 10 分钟）
    python selfcheck.py --host-root D:\\qq机器人5.0

检查内容（与 README 的「实测结论」表一一对应）：

  1. 结构     —— 四套产物的文件/条目数、INDEX 条数、zip 内根级脚本与磁盘一致
  2. 插件包   —— 66 个：`plugins/verify.py`（逐包隔离 + 全量共存 + 清单校验）
  3. 技能包   —— 373 个：`skills/verify.py`（真跑，默认全量）
  4. 市场包   —— 42 个：`market/tools/verify_market.py`
  5. 心情插件 —— `heart/verify.py`

退出码：全过 0，否则 1。**只读**：不装、不改、不删任何东西。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OK = "  ok  "
BAD = " FAIL "
SKIP = " skip "

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def default_python() -> str:
    """优先用宿主自带 venv（真跑要它的依赖），其次当前解释器。"""
    root = os.environ.get("QQ_HOST_ROOT", r"D:\qq机器人5.0")
    cand = Path(root) / ".venv-qq" / "Scripts" / "python.exe"
    return str(cand) if cand.is_file() else sys.executable


def default_host() -> Path:
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
    return dev


def count_index(path: Path) -> int:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return -1
    if isinstance(data, list):
        return len(data)
    for key in ("plugins", "skills", "items"):
        if isinstance(data.get(key), list):
            return len(data[key])
    return -1


def check_structure(rows: list) -> None:
    """纯静态：条目数、INDEX 条数、zip 根级脚本一致性。"""
    def add(name, ok, detail):
        rows.append((name, ok, detail))

    # 插件包
    idx = count_index(HERE / "plugins" / "INDEX.json")
    add("plugins/INDEX.json 66 条", idx == 66, idx)
    allzip = HERE / "plugins" / "dist" / "qq-plugin-packs-all.zip"
    if allzip.is_file():
        with zipfile.ZipFile(allzip) as zf:
            names = zf.namelist()
            add("插件合集 139 条目", len(names) == 139, len(names))
            add("插件合集无 __pycache__",
                not any("__pycache__" in n or n.endswith(".pyc") for n in names), "clean")
            mism = []
            for n in names:
                rel = n.split("qq-plugin-packs/", 1)[-1]
                src = HERE / "plugins" / rel
                if src.is_file() and hashlib.sha256(zf.read(n)).digest() != \
                        hashlib.sha256(src.read_bytes()).digest():
                    mism.append(rel)
            add("插件合集与源一致", not mism, mism[:3] or "ok")
    else:
        add("插件合集存在", False, "缺 dist/qq-plugin-packs-all.zip")

    # 技能包
    sidx = count_index(HERE / "skills" / "INDEX.json")
    add("skills/INDEX.json 373 条", sidx == 373, sidx)
    rzip = HERE / "skills" / "dist" / "ready-all.zip"
    root8 = ["install.py", "verify.py", "hostfix.py", "guard_host.py",
             "README.md", "REPORT.md", "INDEX.json", "INDEX.md"]
    if rzip.is_file():
        with zipfile.ZipFile(rzip) as zf:
            names = zf.namelist()
            add("技能全量包 1572 条目", len(names) == 1572, len(names))
            bad8 = [f for f in root8 if f in names and
                    hashlib.sha256(zf.read(f)).digest() !=
                    hashlib.sha256((HERE / "skills" / f).read_bytes()).digest()]
            add("技能包根级 8 脚本与仓库一致", not bad8, bad8 or "ok")
    else:
        add("技能全量包存在", False, "缺 skills/dist/ready-all.zip")

    # 市场包
    midx = HERE / "market" / "index.json"
    mcount = count_index(midx)
    add("market/index.json 42 条", mcount == 42, mcount)
    if midx.is_file():
        m = json.loads(midx.read_text(encoding="utf-8"))
        bad = []
        for e in m.get("plugins", []):
            p = HERE / "market" / "packages" / e["file"]
            if not p.is_file():
                bad.append(f"{e['id']}:缺 zip")
                continue
            blob = p.read_bytes()
            if len(blob) != e["bytes"] or hashlib.sha256(blob).hexdigest() != e["sha256"]:
                bad.append(f"{e['id']}:sha 不符")
                continue
            with zipfile.ZipFile(p) as zf:
                if "plugin.json" not in zf.namelist():
                    bad.append(f"{e['id']}:无 plugin.json")
                    continue
                manifest = json.loads(zf.read("plugin.json"))
            if manifest.get("api_version") != 1:
                bad.append(f"{e['id']}:缺 api_version")
        add("市场包 sha/字节/api_version", not bad, bad[:3] or "ok")

    # 心情插件
    hzip = HERE / "heart" / "dsh-heart-qq-0.1.0.zip"
    if hzip.is_file():
        with zipfile.ZipFile(hzip) as zf:
            names = zf.namelist()
            add("心情插件 zip 8 条目", len(names) == 8, len(names))
            bad = [n for n in names
                   if n.endswith((".py", ".md", ".json", ".html"))
                   and (HERE / "heart" / n).is_file()
                   and hashlib.sha256(zf.read(n)).digest() !=
                   hashlib.sha256((HERE / "heart" / n).read_bytes()).digest()]
            add("心情插件 zip 与磁盘一致", not bad, bad or "ok")
    else:
        add("心情插件 zip 存在", False, "缺 heart/dsh-heart-qq-0.1.0.zip")


def run(cmd: list, timeout: int) -> tuple:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout, cwd=str(HERE))
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out
    except subprocess.TimeoutExpired:
        return 124, f"超时（>{timeout}s）"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="qqplugin 一键自检（只读）")
    ap.add_argument("--quick", action="store_true",
                    help="跳过技能包真跑（省 10 分钟左右）")
    ap.add_argument("--host-root", default="", help="宿主根，默认自动探测")
    ap.add_argument("--python", default="", help="跑真跑用的 python，默认宿主 venv")
    args = ap.parse_args(argv)

    host = Path(args.host_root) if args.host_root else default_host()
    py = args.python or default_python()
    rows: list = []

    print("=" * 62)
    print("qqplugin 自检")
    print("=" * 62)
    print(f"仓库     : {HERE}")
    print(f"宿主根   : {host}")
    print(f"python   : {py}")
    print()

    # 1. 结构
    check_structure(rows)

    # 2. 插件包
    code, out = run([py, "-X", "utf8", "plugins/verify.py"], 300)
    mounted = ""
    for line in out.splitlines():
        if "mounted=" in line:
            mounted = line.strip()
    rows.append(("插件包 66 个真装挂载", code == 0, mounted or f"exit={code}"))

    # 3. 技能包
    if args.quick:
        rows.append(("技能包真跑", True, "skip（--quick）"))
    else:
        cmd = [py, "-X", "utf8", "skills/verify.py", "--root", str(host)]
        code, out = run(cmd, 3600)
        summary = ""
        for line in out.splitlines():
            if line.startswith("ok ") and "ran-blocked" in line:
                summary = line.strip()
        rows.append(("技能包 373 个真跑", code == 0, summary or f"exit={code}"))

    # 4. 市场包
    code, out = run([py, "-X", "utf8", "market/tools/verify_market.py",
                     "--console", str(host)], 600)
    total = ""
    for line in out.splitlines():
        if "总计" in line:
            total = line.strip()
    rows.append(("市场包 42 个", code == 0, total or f"exit={code}"))

    # 5. 心情插件
    code, out = run([py, "-X", "utf8", "heart/verify.py", "--host-dir", str(host)], 300)
    rows.append(("心情插件", code == 0, "全部通过" if code == 0 else f"exit={code}"))

    print()
    print("=" * 62)
    bad = 0
    for name, ok, detail in rows:
        tag = OK if ok else BAD
        if not ok:
            bad += 1
        print(f"{tag}{name:30} {detail}")
    print("=" * 62)
    print(f"检查 {len(rows)} 项，通过 {len(rows) - bad} 项，不通过 {bad} 项")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
