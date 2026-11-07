# -*- coding: utf-8 -*-
"""QQ 插件市场校验器：用控制台真实安装器把每个包逐个装进独立临时目录，
并确认能被 PluginManager 以 source=custom 注册、重启后仍在插件表内。

判据与控制台真实链路一致（src/plugin_install_service.py finish_install）：
inspect_local -> install_from_file -> finish_install -> 新建 PluginManager 重启 -> 必须在 _plugins 里。

用法：
    python tools/verify_market.py --console <控制台源码根>
    QQ_CONSOLE_ROOT=<控制台源码根> python tools/verify_market.py

退出码：全部 PASS 为 0，任一 FAIL 为 1。
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True

MARKET = Path(__file__).resolve().parents[1]
ENV_CONSOLE = 'QQ_CONSOLE_ROOT'


def load_index(market: Path) -> dict:
    path = market / 'index.json'
    if not path.is_file():
        raise SystemExit('找不到 index.json：本目录不完整')
    return json.loads(path.read_text('utf-8'))


def check_one(installer, finish_install, manager_cls, zip_path: Path, entry: dict, work: Path) -> str:
    """返回空串表示通过，否则返回失败原因。"""
    data = zip_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry['sha256'] or len(data) != entry['bytes']:
        return 'sha256/字节数不符'
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        meta = json.loads(z.read('plugin.json').decode('utf-8'))
    if names != {entry['id'] + '.py', 'plugin.json', '使用说明.md'}:
        return '包内成员不符：' + ', '.join(sorted(names))
    if meta.get('id') != entry['id']:
        return 'manifest id 不符：' + str(meta.get('id'))

    info = installer.inspect_local(zip_path)
    if not info['ok']:
        return '预检不通过：' + '；'.join(info['problems'])
    if info['plugin_id'] != entry['id']:
        return '识别出的插件标识不符：' + str(info['plugin_id'])

    # A 档：模块表置空，只加载 zip 里的自定义文件（验证包本身自足）
    with patch('src.plugins.manager.PLUGIN_MODULES', []):
        manager = manager_cls(work / 'a')
        result = installer.install_from_file(zip_path, manager.custom_plugins_dir, confirmed=True)
        finish_install(manager, result, enable=True)
        restarted = manager_cls(manager.data_dir)
        if entry['id'] not in restarted._plugins:
            return 'A 档：重启后未加载'
        if not restarted._plugins[entry['id']].enabled:
            return 'A 档：重启后未启用'

    # B 档：保留内置模块表（真实控制台的自定义优先覆盖路径）
    manager = manager_cls(work / 'b')
    result = installer.install_from_file(zip_path, manager.custom_plugins_dir, confirmed=True)
    finish_install(manager, result, enable=True)
    restarted = manager_cls(manager.data_dir)
    if entry['id'] not in restarted._plugins:
        return 'B 档：重启后未加载'
    if restarted._plugins[entry['id']].META.id != entry['id']:
        return 'B 档：META.id 不一致'
    problems = [p for p in restarted._load_problems if entry['id'] in str(p)]
    if problems:
        return 'B 档：加载告警 ' + str(problems)
    return ''


def main() -> int:
    parser = argparse.ArgumentParser(description='用真实安装器校验 QQ 插件市场')
    parser.add_argument('--console', default=os.environ.get(ENV_CONSOLE, ''),
                        help='控制台源码根（含 src/plugin_installer.py 的目录）')
    parser.add_argument('--market', default=str(MARKET), help='插件市场目录，默认本脚本的上级目录')
    parser.add_argument('--work', default='', help='临时工作目录（默认系统临时目录；受限环境下可指到可写目录）')
    args = parser.parse_args()

    console = Path(args.console).expanduser() if args.console else None
    if not console or not (console / 'src' / 'plugin_installer.py').is_file():
        raise SystemExit('请用 --console 指定控制台源码根（该目录下应有 src/plugin_installer.py）')
    sys.path.insert(0, str(console))
    from src import plugin_installer as installer
    from src.plugin_install_service import finish_install
    from src.plugins.manager import PluginManager

    market = Path(args.market).resolve()
    index = load_index(market)
    packages = sorted((market / 'packages').glob('*.zip'))
    fails = []
    if len(packages) != index['total']:
        fails.append({'stage': 'index', 'error': 'index.json 记 %d 个，packages 里 %d 个'
                      % (index['total'], len(packages))})

    work_root = Path(args.work).expanduser() if args.work else Path(tempfile.gettempdir())
    work_root.mkdir(parents=True, exist_ok=True)
    # 不用 mkdtemp：Windows 上它建出的目录带受限 ACL，某些受限环境里无法在其下再建子目录
    temp = work_root / ('qq-market-' + uuid.uuid4().hex[:8])
    temp.mkdir(parents=True, exist_ok=False)
    try:
        for i, entry in enumerate(index['plugins']):
            zip_path = market / 'packages' / entry['file']
            if not zip_path.is_file():
                fails.append({'id': entry['id'], 'file': entry['file'], 'error': '文件不存在'})
                continue
            work = temp / ('p' + str(i))
            try:
                error = check_one(installer, finish_install, PluginManager, zip_path, entry, work)
            except Exception as exc:
                error = type(exc).__name__ + ': ' + str(exc)
            if error:
                fails.append({'id': entry['id'], 'file': entry['file'], 'error': error})
            else:
                print('PASS  %-22s %s' % (entry['id'], entry['file']))
    finally:
        shutil.rmtree(temp, ignore_errors=True)

    total = len(index['plugins'])
    print('')
    print('总计 %d 个，通过 %d 个，失败 %d 个' % (total, total - len(fails), len(fails)))
    for item in fails:
        print('FAIL  %s' % json.dumps(item, ensure_ascii=False))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
