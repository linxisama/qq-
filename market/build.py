# -*- coding: utf-8 -*-
"""从 plugins/ 重新同步 market/packages/ 里的 42 个市场包。

**为什么只换 .py**：market 包是「whale-plugin」格式，plugin.json 里带 `config` 数组
（每个设置项的 label/type/default/description），这是从插件类里 `FieldSchema` 反解出来的；
plugins/ 侧要么是裸 .py（没有 plugin.json），要么是 build.py 生成的另一种清单。
所以这里**保留 zip 里原有的 plugin.json 与 使用说明.md**，只把 `<id>.py` 换成 plugins/ 的最新源码。

**修的是什么**：plugins 侧修了 5 个插件（image_library 的注入预算、icebreaker/proactive_chat/
silence_ping 的会话绑定人设、voice_reply 的截断提示），market 里还是旧版 ——
用户从「插件中心」装到的是没修的代码。实测 42 个里 5 个落后：

    image_library   9722 vs 15614
    mention_gate   13827 vs 13825
    proactive_chat  9811 vs 10672
    silence_ping    8568 vs 9044
    icebreaker     16878 vs 17454

用法：
    python build.py            # 预演，只报告哪些包落后
    python build.py --apply    # 真写：重打 zip + 更新 index.json 的 sha256/bytes
    python build.py --apply --bundle   # 再把 42 个包打成 qq插件-市场-<ver>.zip
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PLUGINS = REPO / "plugins"
PACKAGES = HERE / "packages"
INDEX = HERE / "index.json"
# 可复现：时间戳固定，与 plugins/build.py 同口径
_EPOCH = (2020, 1, 1, 0, 0, 0)


def _entry(zf, name, data):
    info = zipfile.ZipInfo(name, date_time=_EPOCH)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    zf.writestr(info, data)


def source_of(entry):
    """plugins/ 侧这个 id 的源码路径。"""
    if entry["channel"] == "override":
        return PLUGINS / "overrides" / f"{entry['id']}.py"
    base = PLUGINS / "packs" / entry["pack_id"]
    src = base / f"{entry['id']}.py"
    if not src.is_file():
        cands = sorted(base.glob("*.py"))
        if cands:
            return cands[0]
    return src


def norm(b):
    return b.replace(b"\r\n", b"\n")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    apply = "--apply" in argv
    bundle = "--bundle" in argv

    pidx = json.loads((PLUGINS / "INDEX.json").read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in pidx["plugins"]}
    m = json.loads(INDEX.read_text(encoding="utf-8"))

    stale, missing, changed = [], [], []
    for e in m["plugins"]:
        pid = e["id"]
        pe = by_id.get(pid)
        dest = PACKAGES / e["file"]
        if not pe:
            missing.append(f"{pid}（plugins 里没有）")
            continue
        src = source_of(pe)
        if not src.is_file():
            missing.append(f"{pid}（源码缺失）")
            continue
        if not dest.is_file():
            missing.append(f"{pid}（market 里没有 zip）")
            continue

        with zipfile.ZipFile(dest) as zf:
            items = [(i.filename, zf.read(i.filename)) for i in zf.infolist()]
        cur = dict(items)
        py_names = [n for n in cur if n.endswith(".py")]
        if not py_names:
            missing.append(f"{pid}（zip 里没有 .py）")
            continue
        if norm(cur[py_names[0]]) == norm(src.read_bytes()):
            continue
        stale.append(pid)
        if not apply:
            continue

        # 只替换 .py，其余（plugin.json / 使用说明.md）原样保留
        payload = [(py_names[0], src.read_bytes())]
        payload += [(n, d) for n, d in items if n not in py_names]
        tmp = dest.with_suffix(".zip.tmp")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in payload:
                _entry(zf, name, data)
        tmp.replace(dest)
        blob = dest.read_bytes()
        e["sha256"] = hashlib.sha256(blob).hexdigest()
        e["bytes"] = len(blob)
        changed.append(pid)

    print(f"落后于 plugins 的包：{len(stale)} 个 -> {stale}")
    if missing:
        print(f"处理不了：{missing}")
    if not apply:
        print("（预演，加 --apply 才写盘）")
        return 0 if not missing else 1

    if changed:
        INDEX.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")
        print(f"已重打 {len(changed)} 个，index.json 的 sha256/bytes 已更新")
    else:
        print("无需改动")

    if bundle:
        ver = m["plugins"][0]["version"]
        out = HERE / f"qq插件-市场-{ver}.zip"
        names = ["index.json", "README-插件市场.md"]
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in names:
                if (HERE / name).is_file():
                    _entry(zf, name, (HERE / name).read_bytes())
            for e in m["plugins"]:
                _entry(zf, f"packages/{e['file']}", (PACKAGES / e["file"]).read_bytes())
                doc = HERE / "使用说明" / f"{e['name']}-{e['id']}.md"
                if doc.is_file():
                    _entry(zf, f"使用说明/{doc.name}", doc.read_bytes())
        print(f"整包重打：{out.name} {out.stat().st_size} B")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
