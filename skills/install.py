# -*- coding: utf-8 -*-
"""把 ready/ 里的 skill 装到 QQ Agent 宿主，并登记两层启用态。

它做三件事：
  1. 把每个 skill 目录复制到 <data>/qq-only/skill_extensions/<id>/
  2. 调 extension_registry.set_enabled(<id>, True) —— 写 qqagent_extensions.json，
     内部还会 _mirror_host_enabled 同步到 <host_root>/data-host-one/config.json
  3. 重建 skill-tools 清单（skill_manifest.ensure_manifest），让工具立刻可注册

前提：宿主根已经 materialize（`qqagent_host.materialize_host_root()` 或控制台点一次
「准备运行时」）。没 materialize 的话第 2 步的镜像会落到一个还不存在的目录，宿主读不到。

用法（在装有宿主依赖的 python 下跑，即 D:\\qq机器人5.0\\.venv-qq\\Scripts\\python.exe）：

    # 预演（默认，不写盘）
    python install.py

    # 真装
    python install.py --apply

    # 只装几个
    python install.py --apply --only kaomoji,csgo-5e

    # 装到指定数据根（默认 D:\\qq机器人5.0）
    python install.py --apply --root "D:\\qq机器人5.0"

    # 卸载
    python install.py --apply --uninstall
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
READY = HERE / "ready"
BUNDLE_ZIP = HERE / "dist" / "ready-all.zip"

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


def ensure_ready() -> Path:
    """返回可用的 ready/ 目录。

    分发包里不放 75.6 MB 的散文件，只带 dist/ready-all.zip；第一次跑时把它
    解到本地 ready/（zip 内顶层就是 ready/，所以解压目标是 HERE）。
    """
    if READY.is_dir():
        return READY
    if not BUNDLE_ZIP.is_file():
        raise SystemExit(
            f"找不到 {READY}，也没有 {BUNDLE_ZIP}；\n"
            f"  有源码的话先跑 build.py，否则确认 dist/ready-all.zip 没被删。")
    print(f"ready/ 不存在，从 {BUNDLE_ZIP.name} 解压（{human(BUNDLE_ZIP.stat().st_size)}）…")
    with zipfile.ZipFile(BUNDLE_ZIP) as zf:
        zf.extractall(HERE)
    if not READY.is_dir():
        raise SystemExit(f"解压后仍然没有 {READY}；zip 结构不对")
    print(f"  解压完成：{len(list(READY.iterdir()))} 个 skill\n")
    return READY


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="把 ready/ 里的 skill 装到宿主")
    parser.add_argument("--root", default=str(DEFAULT_HOST),
                        help="QQ Agent 仓库根（默认 D:\\qq机器人5.0）")
    parser.add_argument("--data-root", default="",
                        help="数据根，skill 装到 <data-root>/data/qq-only/skill_extensions；"
                             "默认与 --root 相同。多账号/测试时用它指向别的目录")
    parser.add_argument("--apply", action="store_true", help="真的写盘（默认只预演）")
    parser.add_argument("--only", default="", help="逗号分隔的 skill id，只处理这些")
    parser.add_argument("--uninstall", action="store_true", help="反向操作：删掉这些 skill")
    parser.add_argument("--force", action="store_true", help="目标已存在也覆盖")
    parser.add_argument("--no-enable", action="store_true", help="只复制文件，不登记启用态")
    parser.add_argument("--no-prepare-host", action="store_true",
                        help="不自动 materialize 宿主根（默认会自动准备，否则启用态镜像写不进去）")
    parser.add_argument("--fix-host", action="store_true",
                        help="先给宿主打 skill 清单补丁（见 hostfix.py），否则已安装的 skill 注册不上")
    parser.add_argument("--no-check-host", action="store_true",
                        help="跳过宿主补丁检查（明知宿主已修过时用）")
    parser.add_argument("--no-deps", action="store_true",
                        help="不把 requires 的提供方复制到 <host_root>/plugins/"
                             "（宿主 host-one.mjs 只看那里，不复制的话依赖型包会报缺提供方）")
    return parser.parse_args(argv)


def host_patch_state(root: Path):
    """宿主 skill 清单补丁的状态；返回 (是否已修, 待修数, 定位失败数)。

    hostfix.inspect() 的签名是 inspect(root) —— 传宿主根，返回
    [(相对路径, 补丁名, 状态, 说明)]，状态 ∈ applied / pending / missing。
    """
    if not (root / "src").is_dir():
        return False, 0, 0
    try:
        sys.path.insert(0, str(HERE))
        from hostfix import inspect as inspect_patches
    except Exception:
        return False, 0, 0
    finally:
        try:
            sys.path.remove(str(HERE))
        except ValueError:
            pass
    try:
        rows = inspect_patches(root)
    except Exception:
        return False, 0, 0
    pending = sum(1 for row in rows if row[2] == "pending")
    missing = sum(1 for row in rows if row[2] == "missing")
    return pending == 0 and missing == 0, pending, missing


def load_host(root: Path):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from src import extension_registry, skill_manifest, skill_tools
    except Exception as exc:  # pragma: no cover - 环境问题
        raise SystemExit(
            f"导入宿主模块失败（{exc}）。请用宿主自己的 venv python 跑：\n"
            f"  {root}\\.venv-qq\\Scripts\\python.exe -X utf8 install.py ...")
    return extension_registry, skill_manifest, skill_tools


def skill_ids(only: str) -> list[str]:
    ready = ensure_ready()
    found = sorted(p.name for p in ready.iterdir() if p.is_dir())
    if not only:
        return found
    wanted = [s.strip() for s in only.split(",") if s.strip()]
    unknown = [s for s in wanted if s not in found]
    if unknown:
        raise SystemExit(f"ready/ 里没有这些 skill：{unknown}")
    return wanted


def human(n: int) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


def link_dependencies(ids, extensions: Path, host_root: Path) -> list:
    """把 requires 的提供方复制到 <host_root>/plugins/<id>/，让宿主的 installedCandidates 看得到。

    宿主 host-one.mjs 只扫 <source>/plugins 和 <source>/skills，看不到 skill_extensions/。
    返回已链接的说明行；任何一步失败都不抛（依赖本来就只是尽力而为）。
    """
    import json as _json
    import shutil as _shutil

    # 1) 扫所有已装扩展的 capabilities，建「能力名 → 提供方目录」索引
    providers = {}
    for pkg in extensions.iterdir():
        if not pkg.is_dir():
            continue
        for name in ("skill.json", "plugin.json"):
            mf = pkg / name
            if not mf.is_file():
                continue
            try:
                raw = _json.loads(mf.read_text(encoding="utf-8-sig"))
            except Exception:
                break
            caps = raw.get("capabilities")
            if isinstance(caps, list):
                for cap in caps:
                    if isinstance(cap, str) and cap.strip():
                        providers.setdefault(cap.strip(), pkg)
            break

    # 2) 看这次装的这些包里，谁 requires 了谁
    plugins = host_root / "plugins"
    linked = []
    for ident in ids:
        pkg = extensions / ident
        if not pkg.is_dir():
            continue
        needs = []
        for name in ("skill.json", "plugin.json"):
            mf = pkg / name
            if not mf.is_file():
                continue
            try:
                raw = _json.loads(mf.read_text(encoding="utf-8-sig"))
            except Exception:
                break
            reqs = raw.get("requires")
            if isinstance(reqs, list):
                needs = [str(c).strip() for c in reqs if str(c).strip()]
            break
        for cap in needs:
            src = providers.get(cap)
            if src is None or src.name == ident:
                continue
            dest = plugins / src.name
            if dest.is_dir():
                continue
            try:
                plugins.mkdir(parents=True, exist_ok=True)
                _shutil.copytree(src, dest)
                linked.append(f"{src.name}（{ident} 需要 {cap}）")
            except Exception as exc:
                linked.append(f"{src.name} 复制失败：{exc}")
    return linked


def main(argv=None) -> int:
    args = parse_args(argv)
    root = Path(args.root).expanduser()
    if not (root / "src" / "skill_tools.py").is_file():
        raise SystemExit(f"{root} 看起来不是 QQ Agent 仓库根（缺 src/skill_tools.py）")

    ids = skill_ids(args.only)
    extension_registry, skill_manifest, skill_tools = load_host(root)

    # 生产链路里 PluginManager.data_dir = <data_root>/data/qq-only，
    # skill_tools.data_dir(runtime) 依赖 runtime.data_root，这里直接用数据根当 runtime。
    data_root = Path(args.data_root).expanduser() if args.data_root else root
    root_text = str(data_root)

    class _RT:
        data_root = root_text

    data_dir = skill_tools.data_dir(_RT())            # <root>/data/qq-only
    extensions = skill_tools.extensions_dir(_RT())     # <root>/data/qq-only/skill_extensions
    registry_data = data_dir.parent                    # <root>/data
    # 宿主根的 plugins/ 目录：host-one.mjs 的 installedCandidates() 只扫这里和 skills/，
    # 看不到 skill_extensions/ —— 依赖型包必须把提供方复制进来（见 link_dependencies）。
    from src import qqagent_host as _qh
    host_root = Path(_qh.default_host_root(data_dir))

    print(f"宿主根   : {root}")
    print(f"skill 目录: {extensions}")
    print(f"注册表   : {extension_registry.state_path(registry_data)}")
    print(f"处理     : {len(ids)} 个 skill{'（卸载）' if args.uninstall else ''}")
    print("")

    # ── 宿主补丁检查 ────────────────────────────────────────────────────────
    # 没打补丁的话，装完的 skill 在清单里是裸工具名，_skill_plan() 判「缺 __」，
    # 结果是 eligible=0、一个都注册不上。这不是安装问题，是宿主 bug。
    if not args.no_check_host and not args.uninstall:
        fixed, pending, missing = host_patch_state(root)
        if not fixed:
            print("宿主检查: 未修复")
            if missing:
                print(f"  有 {missing} 处补丁定位失败（宿主版本可能不同），请手工核对 hostfix.py")
            if pending:
                print(f"  有 {pending} 处待修：装好的 skill 会因为工具名缺 __ 前缀而注册不上。")
                if args.fix_host:
                    print("  正在打补丁 ...")
                    import hostfix
                    code = hostfix.main(["--root", str(root), "--apply"])
                    if code != 0:
                        print("  补丁失败，中止。先修好宿主再装。")
                        return code
                else:
                    print("  加 --fix-host 自动修，或先单独跑：python -X utf8 hostfix.py --apply")
                    if args.apply:
                        print("  （仍继续安装：文件会装好，但要等宿主修好才会生效）")
            print("")
        else:
            print("宿主检查: 已修复")
            print("")

    if not args.apply:
        print("[预演] 下面这些操作不会真的执行；加 --apply 才写盘")
        print("")

    if args.apply and not args.no_enable and not args.uninstall and not args.no_prepare_host:
        # 启用态要镜像到 <host_root>/data-host-one/config.json，宿主根不存在的话镜像会丢。
        # 生产上这一步由控制台「准备运行时」做，这里替用户做掉。
        try:
            from src import qqagent_host
            prepared = qqagent_host.materialize_host_root(str(data_dir), smoke=False)
            print(f"宿主根准备: ok={prepared.get('ok')} reused={prepared.get('reused')} "
                  f"root={prepared.get('root')}")
            if not prepared.get("ok"):
                print(f"  警告：宿主根没准备好（{json.dumps(prepared.get('error'), ensure_ascii=False)[:200]}）；"
                      f"启用态只会写进注册表，宿主读不到")
        except Exception as exc:
            print(f"  警告：准备宿主根失败（{exc}）；继续，只写注册表")
        print("")

    done, skipped, failed = [], [], []
    ready = ensure_ready()
    for ident in ids:
        src = ready / ident
        dest = extensions / ident

        if args.uninstall:
            if not dest.is_dir():
                skipped.append((ident, "没装"))
                continue
            print(f"  - {ident:<22} 删除 {dest}")
            if args.apply:
                shutil.rmtree(dest, ignore_errors=True)
                if not args.no_enable:
                    try:
                        extension_registry.set_enabled(
                            ident, False, registry_data, source="market", note="卸载")
                    except Exception as exc:
                        failed.append((ident, f"登记停用失败：{exc}"))
                        continue
            done.append(ident)
            continue

        if dest.is_dir() and not args.force:
            skipped.append((ident, "已存在（--force 覆盖）"))
            continue

        size = sum(p.stat().st_size for p in src.rglob("*") if p.is_file())
        print(f"  + {ident:<22} {human(size):>8}  -> {dest.name}")
        if not args.apply:
            done.append(ident)
            continue
        try:
            extensions.mkdir(parents=True, exist_ok=True)
            if dest.is_dir():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
        except Exception as exc:
            failed.append((ident, f"复制失败：{exc}"))
            continue

        if not args.no_enable:
            try:
                extension_registry.set_enabled(
                    ident, True, registry_data, source="market", note="独立包安装")
            except Exception as exc:
                failed.append((ident, f"登记启用失败：{exc}"))
                continue
        done.append(ident)

    # ── 依赖型包：把提供方也放进宿主能看见的位置 ──────────────────────────
    # 宿主 host-one.mjs 的 installedCandidates() 只扫 <source>/plugins 和 <source>/skills，
    # 而本脚本把包装在 <data>/qq-only/skill_extensions/ —— 宿主从那里加载「被调用的那个包」，
    # 但**看不见**同目录下的其它包。于是 better-notes 这类 requires 别的包的，
    # 会报「缺少已安装的能力提供者：shared-memory.check」，即使 shared-memory 就在隔壁。
    # 修法：装完之后，把每个「被 require 的能力」的提供方复制一份到 <host_root>/plugins/<id>/。
    # 这些包只是被 require 读取清单和 provider，不参与工具调用，多一份副本是安全的。
    if args.apply and done and not args.uninstall and not args.no_deps:
        try:
            linked = link_dependencies(ids, extensions, host_root)
            if linked:
                print("")
                print("依赖提供方已放进宿主可见目录：")
                for item in linked:
                    print(f"  ~ {item}")
        except Exception as exc:
            print(f"  依赖链接失败（不影响已装文件）：{exc}")

    print("")
    print(f"完成 {len(done)} 个，跳过 {len(skipped)} 个，失败 {len(failed)} 个")
    for ident, why in skipped:
        print(f"  跳过 {ident}：{why}")
    for ident, why in failed:
        print(f"  失败 {ident}：{why}")

    if args.apply and done and not args.no_enable and not args.uninstall:
        print("")
        print("重建 skill-tools 清单 ...")
        try:
            report = skill_manifest.ensure_manifest(_RT(), 0, True)
            print(f"  {json.dumps(report, ensure_ascii=False)[:400]}")
        except Exception as exc:
            print(f"  重建失败（不影响已装文件，下次宿主启动会自己重建）：{exc}")

        print("")
        print("启用态：")
        try:
            state = extension_registry.load(registry_data)
            enabled = sorted(k for k, v in (state.get("extensions") or {}).items()
                             if isinstance(v, dict) and v.get("enabled"))
            print(f"  registry 启用 {len(enabled)} 个：{enabled[:10]}{' ...' if len(enabled) > 10 else ''}")
        except Exception as exc:
            print(f"  读注册表失败：{exc}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
