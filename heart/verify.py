#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 dsh-heart-qq 是否装好了。

只读，不改任何文件。三个层次：

1. **文件层** —— 插件目录四件齐、plugin.json 的 id 与目录名一致、宿主模块内容一致。
2. **补丁层** —— 复用 install.py 的 PATCHES 表，逐条确认 marker 在文件里。
3. **运行层** —— 给 --url 就真的去问控制台：/heart 与 /api/heart/state 是否 200。

用法：
    python verify.py                       # 只查文件与补丁
    python verify.py --url http://127.0.0.1:8090   # 再探一次运行中的控制台

退出码：全过 0，有问题 1。
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8')
    except Exception:
        pass

import install as I  # 同目录，复用目标解析与补丁表

OK = '  ok  '
BAD = ' FAIL '
WARN = ' warn '


def _same_text(a: Path, b: Path) -> bool:
    """按文本比而不是按字节比。

    install.py 写盘时会把 CRLF 归一成 LF（包内 17/663/330 个 CRLF，安装后 0 个），
    直接比字节就会把「只差换行」报成「安装后被改过」——实测三个文件逐行 diff 都是 0 行。
    """
    try:
        left = a.read_bytes().replace(b'\r\n', b'\n')
        right = b.read_bytes().replace(b'\r\n', b'\n')
    except OSError:
        return False
    return left == right


def check_plugin(custom_dir: Path, problems: list, warns: list):
    dst = custom_dir / I.PLUGIN_ID
    if not dst.is_dir():
        problems.append('插件目录不存在：%s' % dst)
        return
    for name in ('plugin.json', 'heart_qq.py', 'README.md', 'web/heart.html'):
        if not (dst / name).is_file():
            problems.append('插件缺文件：%s' % (dst / name))
    manifest = dst / 'plugin.json'
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding='utf-8'))
        except ValueError as exc:
            problems.append('plugin.json 不是合法 JSON：%s' % exc)
        else:
            if data.get('id') != dst.name:
                problems.append('plugin.json 的 id（%r）与目录名（%r）不一致，管理器会以 '
                                'id_mismatch 拒载' % (data.get('id'), dst.name))
            if data.get('entry') != 'heart_qq.py':
                warns.append('plugin.json 的 entry 是 %r，预期 heart_qq.py' % data.get('entry'))
    src = I.PLUGIN_SRC
    if src.is_dir():
        for name in ('plugin.json', 'heart_qq.py', 'web/heart.html'):
            a, b = dst / name, src / name
            if a.is_file() and b.is_file() and not _same_text(a, b):
                warns.append('已安装的 %s 与包内版本不同（安装后被改过？）' % name)


def check_module(host_root: Path, problems: list, warns: list):
    dst = host_root / 'src' / 'heart_api.py'
    if not dst.is_file():
        problems.append('宿主模块缺失：%s（面板会 404）' % dst)
    elif not _same_text(dst, I.HOST_MODULE):
        warns.append('src/heart_api.py 与包内 host/heart_api.py 不同')


def check_patches(host_root: Path, problems: list):
    cache = {}
    for patch in I.PATCHES:
        path = host_root / patch['rel']
        if path not in cache:
            try:
                cache[path] = path.read_bytes().decode('utf-8')
            except OSError as exc:
                cache[path] = None
                problems.append('%s：读不到（%s）' % (patch['rel'], exc))
        text = cache[path]
        if text is None:
            continue
        state = I.patch_state(text, patch)
        if state == 'applied':
            print('%s %s' % (OK, patch['label']))
        elif state == 'pending':
            problems.append('%s：没打上（锚点在，但 marker 不在）' % patch['label'])
        else:
            problems.append('%s：锚点不唯一或缺失（宿主版本可能不是 5.2.112）' % patch['label'])


def probe(url: str, problems: list, warns: list):
    base = url.rstrip('/')
    for path, want in (('/heart', 200), ('/api/heart/state', 200)):
        target = base + path
        try:
            with urllib.request.urlopen(target, timeout=5) as resp:
                code = resp.status
                body = resp.read(400)
        except urllib.error.HTTPError as exc:
            code = exc.code
            body = exc.read(400)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            warns.append('%s 连不上（%s）—— 控制台没在跑？' % (target, exc))
            return
        if code == want:
            print('%s GET %-22s %d' % (OK, path, code))
        elif code == 503:
            problems.append('GET %s → 503：插件实例没找到，控制台需要重启' % path)
        elif code == 403:
            problems.append('GET %s → 403：本机校验没过（或不是从 127.0.0.1 访问）' % path)
        else:
            problems.append('GET %s → %d：%s' % (path, code, body[:120].decode('utf-8', 'replace')))
    try:
        with urllib.request.urlopen(base + '/api/heart/state', timeout=5) as resp:
            state = json.loads(resp.read().decode('utf-8'))
        # /api/heart/state 的形状是 {'ok': True, 'state': {...}}，gauges 在内层。
        panel = state.get('state') if isinstance(state.get('state'), dict) else state
        gauges = panel.get('gauges') or []
        if len(gauges) == 14:
            print('%s 面板数据：14 项数值，时钟 %s' % (OK, (panel.get('clock') or {}).get('text', '?')))
        else:
            problems.append('/api/heart/state 返回的 gauges 是 %d 项，预期 14' % len(gauges))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description='检查 dsh-heart-qq 装好了没（只读）。')
    ap.add_argument('--dir', help='custom_plugins 目录')
    ap.add_argument('--host-dir', help='宿主源码根（含 src/qq_app.py）')
    ap.add_argument('--url', help='控制台地址，给了就额外探测运行层')
    args = ap.parse_args(argv)

    if not I.HOST_MODULE.is_file():
        print('包里缺 host/heart_api.py，先重新解压包。')
        return 1

    custom_dir, how = I.resolve_custom(args.dir, args.url or I.DEFAULT_URL)
    print('插件库：%s（%s）' % (custom_dir, how))
    host_root, how = I.resolve_host(args.host_dir, custom_dir)
    if host_root is None:
        print('宿主源码：%s' % how)
        print('提示：用 --host-dir 指定源码根（例如 D:\\qq机器人5.0）。')
        return 1
    print('宿主源码：%s（%s）' % (host_root, how))
    print()

    problems, warns = [], []
    print('文件层：')
    check_plugin(custom_dir, problems, warns)
    check_module(host_root, problems, warns)
    if not problems:
        print('%s 插件四件齐、plugin.json id 与目录名一致、宿主模块在位' % OK)

    print()
    print('补丁层：')
    check_patches(host_root, problems)

    if args.url:
        print()
        print('运行层：')
        probe(args.url, problems, warns)

    print()
    for w in warns:
        print('%s %s' % (WARN, w))
    if problems:
        print('有 %d 个问题：' % len(problems))
        for p in problems:
            print('%s %s' % (BAD, p))
        return 1
    print('全部通过。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
