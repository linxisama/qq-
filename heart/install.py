#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 dsh-heart-qq 心情插件装进 WhaleGirlQQ（QQ 控制台）。

两件事必须一起做：

1. **插件包** → <custom_plugins>/dsh-heart-qq/。目录名必须等于 plugin.json 的 id，
   否则管理器以 id_mismatch 拒载；目录包不需要登记 custom_plugins.json。
2. **宿主侧路由** → 插件层没有注册 HTTP 路由的钩子（register_tool 注册的是 AI 工具），
   面板的 /heart 与 /api/heart/* 只能由宿主提供：新增 src/heart_api.py，并在
   qq_app.py / qq.html / qq.js 各插一小段。

不做第 2 步插件照常算数值、照常注入提示词，只是没有面板。

所有改动都是幂等的：已经打过的补丁会被识别并跳过，重复执行不会插两遍。

用法：
    python install.py                      # 预演，只打印将要做什么
    python install.py --apply              # 真装
    python install.py --apply --overwrite  # 覆盖已存在的插件目录（先备份）
    python install.py --apply --uninstall  # 反向卸载（保留心情存档）
    python install.py --dir  <custom_plugins 路径>
    python install.py --host-dir <宿主源码根>

安全约定：默认只预演；--apply 才动磁盘；覆盖任何文件前先备份成 <名>.bak-dsh-heart-<8位>。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
PLUGIN_ID = 'dsh-heart-qq'
PLUGIN_SRC = ROOT / PLUGIN_ID
HOST_MODULE = ROOT / 'host' / 'heart_api.py'
DEFAULT_URL = 'http://127.0.0.1:8090'
BACKUP_TAG = '.bak-dsh-heart-'


# --------------------------------------------------------------------------- #
# 宿主补丁表
#
# 每条都是「干净文件里的唯一锚点 + 要插入/替换成的文本」。marker 用于判断这条
# 补丁是否已经打过 —— 打过就跳过，所以重复执行安全。
# --------------------------------------------------------------------------- #
PATCHES = [
    {
        'label': 'qq_app.py：装配 /heart 路由',
        'rel': 'src/qq_app.py',
        'kind': 'after',
        'old': '    install_log_routes(app)',
        'marker': 'install_heart_routes(app)',
        'lines': [
            '    # 心情系统面板（/heart + /api/heart/*）：页面留在插件包里，这里只发文件与转发动作。',
            '    from .heart_api import register as install_heart_routes',
            '    install_heart_routes(app)',
        ],
    },
    {
        'label': 'qq.html：面板样式 .heart-frame',
        'rel': 'src/web/static/qq.html',
        'kind': 'after',
        'old': '.tab-panel{display:none}.tab-panel.active{display:block}',
        'marker': '.heart-frame{',
        'lines': [
            '/* Heart panel */',
            '.heart-frame{display:block;width:100%;height:calc(100vh - 300px);min-height:620px;'
            'border:1px solid #273750;border-radius:12px;background:#0b1220}',
        ],
    },
    {
        'label': 'qq.html：标签栏第 6 个「🫀 心情」',
        'rel': 'src/web/static/qq.html',
        'kind': 'after',
        'old': '    <button class="tab-btn" onclick="switchTab(\'logs\')">📋 日志</button>',
        'marker': 'data-tab="heart"',
        'lines': [
            '    <button class="tab-btn" data-tab="heart" onclick="switchTab(\'heart\')">🫀 心情</button>',
        ],
    },
    {
        'label': 'qq.html：插件页的「打开心情面板」按钮',
        'rel': 'src/web/static/qq.html',
        'kind': 'replace',
        'old': '      <p>🫀 <a href="/heart" target="_blank" rel="noopener">心情面板</a> —— 14 项情绪数值、'
               '模式开关、睡眠闸门与五维滑杆（由 dsh-heart-qq 插件提供）。</p>',
        'new': '      <p>🫀 <button class="secondary" onclick="switchTab(\'heart\')">打开心情面板</button> —— '
               '14 项情绪数值、模式开关、睡眠闸门与五维滑杆（由 dsh-heart-qq 插件提供，也可'
               '<a href="/heart" target="_blank" rel="noopener">在新标签页打开</a>）。</p>',
        'marker': '打开心情面板',
    },
    {
        'label': 'qq.html：第 6 个面板 tab-heart（iframe）',
        'rel': 'src/web/static/qq.html',
        'kind': 'before',
        'old': '</main>',
        'marker': 'id="tab-heart"',
        'lines': [
            '',
            '  <!-- Heart Tab -->',
            '  <div id="tab-heart" class="tab-panel">',
            '    <div class="card">',
            '      <h2>🫀 心情系统</h2>',
            '      <p>14 项情绪数值、模式开关、睡眠闸门与五维滑杆。面板由 dsh-heart-qq 插件提供，改完立刻生效。</p>',
            '      <p class="hint">这里空白说明插件没加载，或插件设置里「网页面板」关着 —— 到「插件」页检查。</p>',
            '      <iframe id="heart-frame" class="heart-frame" title="心情面板" src="about:blank"></iframe>',
            '      <div class="row" style="margin-top:12px">',
            '        <button id="heart-reload" class="secondary">↻ 重新加载面板</button>',
            '        <a href="/heart" target="_blank" rel="noopener" style="align-self:center">在新标签页打开</a>',
            '      </div>',
            '    </div>',
            '  </div>',
        ],
    },
    {
        'label': 'qq.js：heartLoaded 标志',
        'rel': 'src/web/static/qq.js',
        'kind': 'after',
        'old': 'let polling = true;',
        'marker': 'let heartLoaded = false;',
        'lines': [
            'let heartLoaded = false;   // 心情面板 iframe 首次打开才加载',
        ],
    },
    {
        'label': 'qq.js：switchTab 支持 data-tab',
        'rel': 'src/web/static/qq.js',
        'kind': 'replace',
        'old': "    b.classList.toggle('active', panels[i] === name);",
        'new': '    // 带 data-tab 的按钮自己声明页签名（新标签不用改这张下标表），老按钮仍按下标对齐。\n'
               '    const key = (b.dataset && b.dataset.tab) ? b.dataset.tab : panels[i];\n'
               "    b.classList.toggle('active', key === name);",
        'marker': 'b.dataset.tab',
    },
    {
        'label': 'qq.js：切到心情页时懒加载 iframe',
        'rel': 'src/web/static/qq.js',
        'kind': 'after',
        'old': "  if (name === 'persona') loadPersona();",
        'marker': "if (name === 'heart') enterHeart();",
        'lines': [
            "  if (name === 'heart') enterHeart();",
        ],
    },
    {
        'label': 'qq.js：enterHeart()',
        'rel': 'src/web/static/qq.js',
        'kind': 'before',
        'old': '// ── Settings ──────────────────────────────────────────────────────────────────',
        'marker': 'function enterHeart()',
        'lines': [
            '// ── Heart ─────────────────────────────────────────────────────────────────────',
            'function enterHeart() {',
            "  const frame = $('heart-frame');",
            '  if (!frame) return;',
            '  // 首次进入才请求 /heart，避免控制台每次打开都多一次面板渲染。',
            '  if (!heartLoaded) {',
            '    heartLoaded = true;',
            "    frame.src = '/heart?embed=1';",
            '  }',
            '}',
            '',
        ],
    },
    {
        'label': 'qq.js：「重新加载面板」按钮',
        'rel': 'src/web/static/qq.js',
        'kind': 'before',
        'old': "if ($('log-level'))",
        'marker': "$('heart-reload')",
        'lines': [
            "if ($('heart-reload')) $('heart-reload').addEventListener('click', () => {",
            "  const frame = $('heart-frame');",
            '  if (!frame) return;',
            '  heartLoaded = true;',
            '  // 加时间戳绕过缓存，面板里的 fetch 本身是 no-store 的。',
            "  frame.src = '/heart?embed=1&t=' + Date.now();",
            '});',
            '',
        ],
    },
]


# --------------------------------------------------------------------------- #
# 目标目录
# --------------------------------------------------------------------------- #
def from_api(url: str, timeout: float = 3.0):
    """问宿主插件库在哪 —— 唯一权威答案，避免猜错账号目录。"""
    try:
        with urllib.request.urlopen(url.rstrip('/') + '/api/plugins/custom',
                                    timeout=timeout) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None
    raw = str(payload.get('dir') or '').strip()
    return Path(raw) if raw else None


def custom_candidates():
    import os
    out = []
    local = os.environ.get('LOCALAPPDATA')
    if local:
        out.append(Path(local) / 'WhaleGirlQQ' / 'data' / 'qq-only' / 'custom_plugins')
    out.append(Path(r'D:\qq机器人5.0') / 'data' / 'qq-only' / 'custom_plugins')
    out.append(Path.home() / 'WhaleGirlQQ' / 'data' / 'qq-only' / 'custom_plugins')
    return out


def resolve_custom(explicit, url):
    if explicit:
        return Path(explicit).expanduser(), '--dir 指定'
    found = from_api(url)
    if found:
        return found, '控制台 %s' % url
    candidates = custom_candidates()
    # 安装版会在 %LOCALAPPDATA%/WhaleGirlQQ 下建一个空目录，源码态用的却是仓库里的
    # 那个 —— 空目录优先会把插件装到一个没人读的地方，所以先挑真有插件的那一个。
    for path in candidates:
        try:
            if path.is_dir() and any(path.iterdir()):
                return path, '已存在的默认路径'
        except OSError:
            continue
    for path in candidates:
        if path.is_dir():
            return path, '已存在的空默认路径'
    return candidates[0], '默认路径（尚不存在，将创建）'


def looks_like_host(path: Path) -> bool:
    return ((path / 'src' / 'qq_app.py').is_file()
            and (path / 'src' / 'web' / 'static' / 'qq.html').is_file())


def resolve_host(explicit, custom_dir):
    if explicit:
        return Path(explicit).expanduser(), '--host-dir 指定'
    tried = []
    # <root>/data/qq-only/custom_plugins → parents[2] 就是宿主根
    try:
        guess = custom_dir.parents[2]
        tried.append(guess)
        if looks_like_host(guess):
            return guess, '由插件库位置推出'
    except IndexError:
        pass
    for guess in (Path(r'D:\qq机器人5.0'), Path.cwd()):
        tried.append(guess)
        if looks_like_host(guess):
            return guess, '已知宿主源码路径'
    return None, '找不到宿主源码（试过：%s）' % '、'.join(str(p) for p in tried)


# --------------------------------------------------------------------------- #
# 补丁
# --------------------------------------------------------------------------- #
def detect_eol(text: str) -> str:
    return '\r\n' if '\r\n' in text else '\n'


def patched_text(patch, eol):
    """这条补丁打完之后，那段区域应该长什么样。"""
    old = patch['old']
    if patch['kind'] == 'after':
        return old + eol + eol.join(patch['lines'])
    if patch['kind'] == 'before':
        return eol.join(patch['lines']) + eol + old
    return patch['new'].replace('\n', eol)


def patch_state(text, patch):
    if patch['marker'] in text:
        return 'applied'
    if text.count(patch['old']) == 1:
        return 'pending'
    return 'conflict'


def backup(path: Path) -> Path:
    bak = path.with_name(path.name + BACKUP_TAG + uuid.uuid4().hex[:8])
    shutil.copy2(path, bak)
    return bak


# --------------------------------------------------------------------------- #
# 计划
# --------------------------------------------------------------------------- #
def _same_text(a: Path, b: Path) -> bool:
    """按文本比而不是按字节比：只差换行不算「内容不同」。

    装过的文件是 LF、包内是 CRLF 时逐字节比永远不等，会把用户可能手工改过的
    文件无声覆盖掉。归一化 CRLF 之后再比。
    """
    try:
        left = a.read_bytes().replace(b'\r\n', b'\n')
        right = b.read_bytes().replace(b'\r\n', b'\n')
    except OSError:
        return False
    return left == right


def build_plan(custom_dir: Path, host_root: Path, overwrite: bool):
    steps = []

    dst_plugin = custom_dir / PLUGIN_ID
    steps.append({
        'kind': 'plugin',
        'label': '插件包 %s' % PLUGIN_ID,
        'dst': dst_plugin,
        'src': PLUGIN_SRC,
        'exists': dst_plugin.exists(),
        'action': ('跳过（已存在，加 --overwrite 覆盖）' if dst_plugin.exists() and not overwrite
                   else ('覆盖' if dst_plugin.exists() else '安装')),
    })

    dst_api = host_root / 'src' / 'heart_api.py'
    same = _same_text(dst_api, HOST_MODULE) if dst_api.is_file() else False
    steps.append({
        'kind': 'module',
        'label': '宿主模块 src/heart_api.py',
        'src': HOST_MODULE,
        'dst': dst_api,
        'exists': dst_api.exists(),
        'action': '跳过（内容已一致）' if same else ('覆盖' if dst_api.exists() else '安装'),
    })

    cache = {}
    for patch in PATCHES:
        path = host_root / patch['rel']
        if path not in cache:
            try:
                cache[path] = path.read_bytes().decode('utf-8')
            except OSError as exc:
                cache[path] = None
                steps.append({'kind': 'patch', 'label': patch['label'], 'path': path,
                              'state': 'conflict', 'action': '跳过（读不到文件：%s）' % exc,
                              'patch': patch})
                continue
        text = cache[path]
        state = patch_state(text, patch) if text is not None else 'conflict'
        steps.append({
            'kind': 'patch',
            'label': patch['label'],
            'path': path,
            'patch': patch,
            'state': state,
            'action': {'applied': '跳过（已打过）',
                       'pending': '打补丁',
                       'conflict': '跳过（锚点不唯一或缺失，需人工看）'}[state],
        })
    return steps


def build_uninstall_plan(custom_dir: Path, host_root: Path):
    steps = []
    dst_plugin = custom_dir / PLUGIN_ID
    steps.append({'kind': 'plugin', 'label': '插件包 %s' % PLUGIN_ID, 'dst': dst_plugin,
                  'exists': dst_plugin.exists(),
                  'action': '删除' if dst_plugin.exists() else '跳过（不存在）'})
    dst_api = host_root / 'src' / 'heart_api.py'
    steps.append({'kind': 'module', 'label': '宿主模块 src/heart_api.py', 'dst': dst_api,
                  'exists': dst_api.exists(),
                  'action': '删除（先备份）' if dst_api.exists() else '跳过（不存在）'})
    cache = {}
    for patch in PATCHES:
        path = host_root / patch['rel']
        if path not in cache:
            try:
                cache[path] = path.read_bytes().decode('utf-8')
            except OSError:
                cache[path] = None
        text = cache[path]
        state = 'conflict'
        if text is not None:
            eol = detect_eol(text)
            state = 'applied' if text.count(patched_text(patch, eol)) == 1 else 'pending'
        steps.append({'kind': 'patch', 'label': patch['label'], 'path': path, 'patch': patch,
                      'state': state,
                      'action': {'applied': '回滚', 'pending': '跳过（没打过）',
                                 'conflict': '跳过（找不到补丁块）'}[state]})
    return steps


def print_plan(steps, title):
    print(title)
    for step in steps:
        print('  - %-34s %s' % (step['label'], step['action']))
    print()


# --------------------------------------------------------------------------- #
# 执行
# --------------------------------------------------------------------------- #
def apply_install(steps):
    for step in steps:
        if step['kind'] == 'plugin':
            if step['action'] == '安装':
                step['dst'].parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(step['src'], step['dst'],
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            elif step['action'] == '覆盖':
                bak = step['dst'].with_name(step['dst'].name + BACKUP_TAG + uuid.uuid4().hex[:8])
                shutil.move(str(step['dst']), str(bak))
                shutil.copytree(step['src'], step['dst'],
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                print('  备份旧插件目录 → %s' % bak.name)
        elif step['kind'] == 'module':
            if step['action'] in ('安装', '覆盖'):
                if step['dst'].is_file():
                    print('  备份 → %s' % backup(step['dst']).name)
                step['dst'].parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(step['src'], step['dst'])

    # 补丁按文件分组，一次读一次写，避免同一文件被反复覆盖。
    by_file = {}
    for step in steps:
        if step['kind'] == 'patch' and step['state'] == 'pending':
            by_file.setdefault(step['path'], []).append(step['patch'])
    for path, patches in by_file.items():
        text = path.read_bytes().decode('utf-8')
        eol = detect_eol(text)
        for patch in patches:
            text = text.replace(patch['old'], patched_text(patch, eol), 1)
        print('  备份 → %s' % backup(path).name)
        path.write_bytes(text.encode('utf-8'))
        print('  打补丁 → %s（%d 处）' % (path, len(patches)))


def apply_uninstall(steps):
    by_file = {}
    for step in steps:
        if step['kind'] == 'patch' and step['state'] == 'applied':
            by_file.setdefault(step['path'], []).append(step['patch'])
    for path, patches in by_file.items():
        text = path.read_bytes().decode('utf-8')
        eol = detect_eol(text)
        for patch in patches:
            text = text.replace(patched_text(patch, eol), patch['old'], 1)
        print('  备份 → %s' % backup(path).name)
        path.write_bytes(text.encode('utf-8'))
        print('  回滚 → %s（%d 处）' % (path, len(patches)))

    for step in steps:
        if step['kind'] == 'module' and step['exists']:
            print('  备份 → %s' % backup(step['dst']).name)
            step['dst'].unlink()
        elif step['kind'] == 'plugin' and step['exists']:
            shutil.rmtree(step['dst'])
            print('  删除插件目录 → %s' % step['dst'])


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='把 dsh-heart-qq 心情插件装进 WhaleGirlQQ（QQ 控制台）。')
    ap.add_argument('--apply', action='store_true', help='真写盘；不加只预演')
    ap.add_argument('--uninstall', action='store_true', help='反向卸载（保留心情存档）')
    ap.add_argument('--overwrite', action='store_true', help='覆盖已存在的插件目录（先备份）')
    ap.add_argument('--dir', help='custom_plugins 目录')
    ap.add_argument('--host-dir', help='宿主源码根（含 src/qq_app.py）')
    ap.add_argument('--url', default=DEFAULT_URL, help='控制台地址，默认 %s' % DEFAULT_URL)
    args = ap.parse_args(argv)

    if not PLUGIN_SRC.is_dir():
        print('找不到插件目录：%s' % PLUGIN_SRC)
        return 2
    if not HOST_MODULE.is_file():
        print('找不到宿主模块：%s' % HOST_MODULE)
        return 2

    custom_dir, how = resolve_custom(args.dir, args.url)
    print('插件库：%s（%s）' % (custom_dir, how))
    host_root, how = resolve_host(args.host_dir, custom_dir)
    if host_root is None:
        print('宿主源码：%s' % how)
        print('提示：用 --host-dir 指定源码根（例如 D:\\qq机器人5.0）。')
        return 2
    print('宿主源码：%s（%s）' % (host_root, how))
    print()

    if args.uninstall:
        steps = build_uninstall_plan(custom_dir, host_root)
        print_plan(steps, '将执行（卸载）：')
        if not args.apply:
            print('预演结束。加 --apply 才真删。')
            return 0
        apply_uninstall(steps)
        print()
        print('已卸载。心情存档 data/qq-only/plugin_state/dsh_heart/ 保留，删掉它等于重置。')
        print('重启控制台后标签页与 /heart 才会消失。')
        return 0

    steps = build_plan(custom_dir, host_root, args.overwrite)
    print_plan(steps, '将执行（安装）：')
    conflicts = [s for s in steps if s.get('state') == 'conflict']
    if conflicts:
        print('有 %d 处锚点不匹配，这些会跳过。宿主版本可能不是 5.2.112，' % len(conflicts))
        print('装完请手动确认 /heart 是否 200。')
        print()
    if not args.apply:
        print('预演结束。加 --apply 才真写盘。')
        return 0
    apply_install(steps)
    print()
    print('装完。下一步：')
    print('  1. 重启控制台（qq_main.py），插件与路由都是启动时装配的。')
    print('  2. 打开 http://127.0.0.1:8090/ ，点标签栏的「🫀 心情」。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
