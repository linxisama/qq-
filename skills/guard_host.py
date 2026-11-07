# -*- coding: utf-8 -*-
r"""宿主补丁守护：检测 src/ 是否被还原，还原了就自动重打。

用途：这台机器上有别的会话会改 D:\qq机器人5.0\src（已实测 3 次），
每次都要手工跑 hostfix.py --apply。这个脚本把「检测 + 重打 + 复验」做成一条命令。

用法：
    python -X utf8 guard_host.py            # 检查 + 自动修复
    python -X utf8 guard_host.py --check    # 只看，不改
"""
import subprocess
import sys
from pathlib import Path

PY = r"D:\qq机器人5.0\.venv-qq\Scripts\python.exe"
PACKS = Path(r"D:\插件\qq-skill-packs")
HOSTFIX = PACKS / "hostfix.py"
ROOT = r"D:\qq机器人5.0"

# 这些串出现 = 补丁被回滚（与 check_all.py 的 patch_gone 同口径）
GONE = {
    "src/skill_tools.py": [
        r"\b(?:ctx|api)\s*(?:\?\.|\.)",
        "宿主源码模块：清单声明了",
        "依赖宿主源码模块：",
    ],
    "src/skill_manifest.py": [
        '"T4-host-source", "host-source:',
        "if host_imports:",
    ],
}


def rolled_back() -> list:
    hits = []
    for rel, needles in GONE.items():
        path = Path(ROOT) / rel
        if not path.is_file():
            hits.append((rel, "<文件不存在>"))
            continue
        text = path.read_bytes().decode("utf-8", "replace")
        for n in needles:
            if n in text:
                hits.append((rel, n))
    return hits


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    check_only = "--check" in argv

    hits = rolled_back()
    if not hits:
        print("[守护] 宿主补丁在位，无需处理")
        return 0

    print("[守护] 检测到补丁被回滚：")
    for rel, needle in hits:
        print("  %-26s %s" % (rel, needle))
    if check_only:
        print("\n（--check 模式，未修改）")
        return 1

    print("\n[守护] 正在重打补丁 ...")
    proc = subprocess.run([PY, "-X", "utf8", str(HOSTFIX), "--root", ROOT, "--apply"],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(PACKS))
    print(proc.stdout[-1500:])
    if proc.returncode != 0:
        print("[守护] hostfix 失败，退出码", proc.returncode)
        print(proc.stderr[-800:])
        return proc.returncode

    hits2 = rolled_back()
    if hits2:
        print("[守护] 重打后仍有残留：", hits2)
        return 1
    print("[守护] 已修复，补丁全部回位")
    return 0


if __name__ == "__main__":
    sys.exit(main())
