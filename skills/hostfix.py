#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""给 QQ 工作台宿主打 skill 清单 / 注册闸门补丁（可回滚）。

## 为什么需要它

宿主的 skill 注册链上有一串**静态闸门**，其中绝大多数经实测是**误判**：它们把
「扫描到的字面量」当成「运行时硬依赖」，而真实 skill 的写法是防御式的
（`ctx?.sender && typeof ctx.sender.sendImage === 'function'`），宿主不给就走降级分支。

实测数据（`D:\插件\_audit\` 下的 probe，全部真跑，不是推断）：

| 阶段 | 可注册 | 工具 |
| --- | --- | --- |
| 原始生产 | 53 | 143 |
| 去 T4 闸 | 72 | 190 |
| 去 T4 + hostImports | 89 | 234 |
| 再去 ctx 闸 | 226 | 601 |
| 再剥注释 | 245 | 659 |
| 再补 node 内置模块政策 | 331 | 1029 |
| 再补 loose 兜底扫描 | 354 | 1027 |
| 再修 `_IMPORT` 捕获组 | 361 | 1136 |
| 再按宿主 node_modules 实查 npm 包 | 365 | 1165 |
| 再修包根解析（第九组 I） | 366 | 1171 |
| 再让 requires 认已安装提供方（第十组 J） | 367 | 1175 |
| 再放行纯提示词/钩子/能力型包（第十一~十三组 K/L/M） | 371 | 1175 |
| 再解除 onebot/qq_sticker 的 T3 误判（第十四组 N） | **373** | **1179** |

最终交叉验证：373 个里 **334 真跑 ok / 39 缺本机配置 / 0 加载失败**。

## 各组闸与对应补丁

### 第一组（原 hostfix，修「装了不生效」）

**A1/A2/A3 工具名前缀**：`classify()` 用 `posixpath.basename(root)` 当 skill_id，
扁平布局（`<extensions>/<id>/skill.json`）下 `_package_root()` 返回 `''` →
不加 `<id>__` 前缀 → 清单里存裸名 `nav` → `_skill_plan()` 判「缺 __」→ 整个 skill 不注册。

**B 相对路径**：`ensure_manifest()` 把 `runtime` 丢了 → `extensions_dir(None)` 返回
`Path('.')` → 相对路径 `data/qq-only/skill_extensions`，依赖 CWD。生产 `start.bat` 有
`cd /d "%~dp0"`，CWD 恰好等于 data_root，所以这个相对路径**恰好命中** → 触发上面的 Bug A。

### 第二组（本次新增，修「能跑却判死」）

**C1 剥 JS 注释**：`_scan_reader()` 对**原始文本**跑 `_MEMBER` 正则，注释里的
`// api.bilibili.com`、`// 缺 api.baseUrl 或 api.apiKey` 全被当成宿主成员依赖。
实测：剥注释后多解锁 19 个。

**C2 `api.X` 不算 ctx 成员**：`_MEMBER = r"\b(?:ctx|api)\s*..."` 把 `ctx.X` 和 `api.X`
混为一谈。但宿主**只提供 `ctx`**，从不提供 `api` —— 那是 QQ Agent 老插件
`setup(api)` 的形参，或包内局部变量。实测：14 个 skill 仅由 `api.X` 触发误判。

**C3 去 T4 闸**：`if host_imports: return result("T4-host-source")` —— 只要有 `../`
就判死，从不看深度、从不看文件是否存在。但 `host-one.mjs:204` 把包拷到
`<source>/skills-host-<pid>/0000-<id>/`，那里 `../../src/config.js` 正好解析到
`<source>/src/config.js`，**文件真实存在**。实测 89/89 能加载、83 真跑 ok。

**C4 去 hostImports 闸**：`_skill_plan()` 里有第二道一模一样的闸，拆了 C3 不拆它，
89 个全部落在这里。

**C5 node 内置模块政策补齐**：
- `node:module`（11 个，`import { createRequire } from 'node:module'`）→ 纯计算，归 SAFE
- `node:timers/promises`（1 个，`setTimeout as delay`）→ 归 SAFE
- `node:dns` / `node:dns/promises`（4 个，真的查 DNS）→ 归 ACCOUNTED（出网但记账）
- `node:net/http/https/tls` 原在 GATED，要求声明 `network` 权限，而真实市场 379 个 zip
  里**没有任何包声明过它**（源码注释自己写了「这条闸今天在市场上一次都不会触发」）
  → 不是放行主力，是永久阻断。改归 ACCOUNTED。

### 第三组（可选，改善实际生效数量）

**D SKILL_LIMIT**：`src/agent_tools.py:34 SKILL_LIMIT = 20`，
`register_skills(runtime, limit=20)` 按 id 字母序只注册前 20 个 —— 可能截掉有用的、
留下缺配置的（前 20 里有 ai-vent / ai-voice 这种本机没配的）。改成 60。

### 第四~第八组（修「工具名对不上」与「误报缺包」）

- **E1 ctx 闸只审计不拦截**：`_skill_plan()` 里 `blocked` 非空即拒。实测 276 个被 ctx 挡的里
  242 个真跑 ok、源码全是防御式写法 → 只对 `node:` / `npm:` 前缀硬拦，其余记账放行。
- **F1 常量表内联**：`registerTool({ id: TOOL.list, … })` 的标识符引用解不出 → `id` 键被丢弃
  → 退回中文 `name` 当 id。解析前把 `const TOOL = {list:'list'}` 内联进源码。
- **F2 注册比对清洗口径**：`reply-meme_1.2.0` 的点号被 `_clean_name` 洗成 `_`，实际注册成功却误报。
- **F3 运行期前缀回拼**：宿主 `sanitize` 后 skillId 截 24 位、toolId 截 38 位，清单存原样拼法
  → 调用必报「tool 不属于被选扩展」。用 `KNOWN_PREFIX_MISMATCH` 回拼。
- **G1/G2 loose 兜底扫描**：`registerTool(fn())` / 表驱动 for-of / 位置参数 `register(...)` /
  包装函数四类写法静态解析不出，**只在严格路径返回空时**跑宽松扫描。
- **H1 `_IMPORT` 捕获组加白名单**：停用词数组里的 `from', '` 被当 import，抓出 `, ` 这种假模块名。
- **H2a~H2e npm 包按宿主 node_modules 实查**：`blocked_capabilities()` 对 `npm:` 一律判死，
  从不查盘。实测 `ws` / `js-yaml` / `undici` 宿主本来就装着。

### 第九组（本次新增，修「双层嵌套包被判 no-entry」）

**I 包根解析**：`_package_root()` 取「**最浅**的 skill.json / plugin.json 所在目录」当包根。
市场里有一批包是双层嵌套（真例 `<id>/<id>/index.js`）：外层只放了清单副本，真包在内层。
于是 `_package_entry()` 拼出 `<id>/index.js` —— 文件不存在 → `entry=""` → 整包被判
`T6-disabled / no-entry`，明明能跑却一个工具都注册不上。

改法：包根优先选「**同时**含清单与入口」的那层（按层数从浅到深找，最多不过度下潜）；
所有候选层都没有入口时才退回原来的「最浅清单目录」。清单与入口同层的正常包
（379 个里的绝大多数）结果完全不变。

实测：`jujutsu-phantom-parade` 手工扁平化内层后 `list_tools ok=True`，6 个工具
（`card_info` / `kb_search` / `tier_list` / `skill_search` / `glossary` / `dfhy_live`）
全部注册、`call card_info` / `call kb_search` 都 ok；只差这一处包根解析。

注意：Node 侧加载器（`runtime/qqagent-host/src/plugin-loader.js` 的 `readManifest`）
同样只看目录本层、`pickEntryFallback` 也只在本层找，**不会自动下潜**；而
`skill_tools.install_skill()` 装包时会把「清单所在层」整个搬成 `<id>/`，装完就是扁平的
—— 所以修在包根这一层，和安装/加载两边口径一致。

## 用法

    python -X utf8 hostfix.py --check              # 只看状态
    python -X utf8 hostfix.py --apply              # 打全部补丁（自动备份）
    python -X utf8 hostfix.py --apply --no-limit   # 不打 SKILL_LIMIT 那处
    python -X utf8 hostfix.py --revert             # 从备份全部回滚

默认宿主根 `D:\qq机器人5.0`，用 `--root` 改。

## 安全设计

- 任一处补丁 `missing`（原文找不到）→ **整体中止，一个文件都不改**
- 写盘前 `compile()` 语法检查
- 每个文件首次 apply 自动备份 `<name>.dsh-bak`，`--revert` 从备份还原
- 幂等：已应用的补丁跳过
"""
import argparse
import shutil
import sys
from pathlib import Path

DEFAULT_ROOT = r"D:\qq机器人5.0"
BACKUP_SUFFIX = ".dsh-bak"

# ── 剥注释辅助函数（作为补丁内容插进 skill_tools.py）────────────────────────
STRIP_HELPER = '''

def _strip_js_comments(text):
    """去掉 // 行注释与 /* */ 块注释，保留字符串/模板字面量内容。

    扫描器原来直接对原始文本跑正则，于是注释里的 `api.bilibili.com`、
    `缺 api.baseUrl` 都被当成宿主成员依赖。这里只剥注释，不动字符串内容
    （模板字符串里的 URL 仍然算数，那是真依赖）。
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            while i < n and text[i] not in "\\r\\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i = min(i + 2, n)
            continue
        if ch in "'\\"`":
            quote = ch
            out.append(ch)
            i += 1
            while i < n:
                c = text[i]
                out.append(c)
                if c == "\\\\" and i + 1 < n:
                    out.append(text[i + 1])
                    i += 2
                    continue
                i += 1
                if c == quote:
                    break
            continue
        out.append(ch)
        i += 1
    return "".join(out)
'''

# ── 常量表辅助函数（作为补丁内容插进 tool_schema.py）────────────────────────
# 为什么需要：市场里大量 skill 写的是 `api.registerTool({ id: TOOL.list, name: '表情包清单' })`。
# 解析器对标识符一律返回 _UNKNOWN，`id` 键被丢弃 → _normalise 退回 ID_KEYS 取到中文
# `name` 当 id → 清单写成 `sticker-admin__表情包清单`，而运行期宿主用 def.id 拼
# `sticker-admin__list`，两边对不上 → 注册失败。
# 做法：不改解析器，改成「解析前把常量内联进源码文本」，只替换两处位置，避免误伤声明本身。
CONST_HELPER = r'''

_CONST_DECL_RE = re.compile(r'\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*')
_OBJ_ENTRY_RE = re.compile(
    r"""(?:([A-Za-z_$][\w$]*)|'([^']*)'|"([^"]*)")\s*:\s*(?:'([^']*)'|"([^"]*)")""")
_MAX_CONSTS = 240


def _js_str(value):
    """把一个 Python 字符串写成 JS 单引号字面量。"""
    body = str(value).replace('\\', '\\\\').replace("'", "\\'")
    return "'" + body + "'"


def _object_span(text, start):
    """从 start 处的 '{' 找到配对 '}'，返回 (起, 止)；找不到返回 None。

    用 _mask 判断代码区：字符串与注释里的花括号不算数。
    """
    try:
        masked = _mask(text)
    except Exception:
        return None
    depth = 0
    index = start
    total = len(masked)
    while index < total:
        char = masked[index]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return start, index + 1
        index += 1
    return None


def _const_table(text, budget=0.02):
    """收集 `const X = 'str'` 与 `const X = { k: 'v', ... }` 的简单字面量值。

    只认一层：对象内部再引用别的常量时不追（实测市场里没有这种写法）。
    有 20ms 预算，超了就停 —— 静态提取宁可少解，不许拖慢清单重建。
    """
    consts = {}
    if not isinstance(text, str) or not text:
        return consts
    started = time.monotonic()
    for index, match in enumerate(_CONST_DECL_RE.finditer(text)):
        if index >= _MAX_CONSTS or time.monotonic() - started > budget:
            break
        name = match.group(1)
        pos = match.end()
        while pos < len(text) and text[pos] in ' \t\r\n':
            pos += 1
        if pos >= len(text):
            break
        char = text[pos]
        if char in '\'"':
            end = _quote_end(text, pos, char, True)
            if end > pos:
                consts[name] = _unquote(text[pos:end + 1])
        elif char == '{':
            span = _object_span(text, pos)
            if not span:
                continue
            inner = {}
            for entry in _OBJ_ENTRY_RE.finditer(text[span[0]:span[1]]):
                key = entry.group(1) or entry.group(2) or entry.group(3)
                val = entry.group(4) if entry.group(4) is not None else entry.group(5)
                if key and val is not None:
                    inner[key] = val
            if inner:
                consts[name] = inner
    return consts


def _inline_consts(text, consts):
    """把 `id: TOOL.list` / `id: TOOL_ID` 就地换成字面量。

    只替换两类位置，避免误伤声明本身：
      1. `NAME.attr` / `NAME['attr']` → 'value'（属性引用，全文替换也安全）
      2. `id|toolId|tool_id|key: NAME` → `...: 'value'`（标量常量）
    """
    out = text
    for name, value in consts.items():
        ident = re.escape(name)
        if isinstance(value, dict):
            for key, sub in value.items():
                literal = _js_str(sub)
                out = re.sub(r'\b%s\s*\.\s*%s\b' % (ident, re.escape(key)), literal, out)
                out = re.sub(r"""\b%s\s*\[\s*['"]%s['"]\s*\]""" % (ident, re.escape(key)),
                             literal, out)
        elif isinstance(value, str):
            out = re.sub(r'\b(id|toolId|tool_id|key)(\s*:\s*)%s\b' % ident,
                         lambda m, lit=_js_str(value): m.group(1) + m.group(2) + lit, out)
    return out
'''

CODE_TOOLS_OLD = '''def _code_tools(text: str) -> List[dict]:
    found: Dict[str, dict] = {}
    for start in _call_sites(text):
        obj = _parse_js_object(text, start)
        tool = _normalise(obj, 'code') if obj else None
        if not tool:
            continue
        old = found.get(tool['id'])
        if old is None or (not old['parameters'] and tool['parameters']):
            found[tool['id']] = tool
    return list(found.values())
'''

CODE_TOOLS_NEW = CONST_HELPER + '''

def _code_tools(text: str) -> List[dict]:
    """先走原路径；只有某个调用点解不出 id 时才建常量表、内联后重跑全文。

    无条件建表会把 extract_tools 的 TIME_BUDGET 挤爆（实测 pai-skills 掉 3 个工具），
    所以按需触发：绝大多数包一次都不用。
    """
    found: Dict[str, dict] = {}
    consts = None
    work = text
    for start in _call_sites(work):
        obj = _parse_js_object(work, start)
        if isinstance(obj, dict) and 'id' not in obj and consts is None:
            consts = _const_table(text)
            if consts:
                work = _inline_consts(text, consts)
                break
        tool = _normalise(obj, 'code') if obj else None
        if not tool:
            continue
        old = found.get(tool['id'])
        if old is None or (not old['parameters'] and tool['parameters']):
            found[tool['id']] = tool
    if work is text:
        return list(found.values())
    found = {}
    for start in _call_sites(work):
        obj = _parse_js_object(work, start)
        tool = _normalise(obj, 'code') if obj else None
        if not tool:
            continue
        old = found.get(tool['id'])
        if old is None or (not old['parameters'] and tool['parameters']):
            found[tool['id']] = tool
    return list(found.values())
'''

LOOSE_HELPER = r'''
_LOOSE_ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


def _loose_object_tools(text, limit=600):
    """兜底 A：全文找形如工具定义的对象字面量 { id, name, ..., execute }。"""
    found = {}
    try:
        masked = _mask(text)
    except Exception:
        return found
    index = 0
    budget = 0
    while True:
        index = masked.find('{', index)
        if index < 0 or budget >= limit:
            break
        budget += 1
        obj = _parse_js_object(text, index)
        if isinstance(obj, dict):
            ident = obj.get('id')
            runnable = any(k in obj for k in ('execute', 'run', 'handler'))
            described = 'description' in obj or 'parameters' in obj
            named = 'name' in obj
            if (isinstance(ident, str) and _LOOSE_ID.match(ident)
                    and (runnable or (named and described) or ('parameters' in obj and 'description' in obj))):
                tool = _normalise(obj, 'code')
                if tool:
                    old = found.get(tool['id'])
                    if old is None or (not old['parameters'] and tool['parameters']):
                        found[tool['id']] = tool
        index += 1
    return found


def _loose_array_tools(text, limit=400):
    """兜底 B：`const defs = [['id', '名称', '描述', {...}], ...]` 这类表驱动定义。

    真例：admin-mute / qq-self 用
        for (const [id, name, description, properties] of defs) api.registerTool({ id, ... })
    对象的 id 是解构变量，静态解析看不到字面量，只能从 defs 数组回填。
    """
    found = {}
    for match in re.finditer(r'(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*\[', text):
        start = match.end() - 1
        try:
            masked = _mask(text)
        except Exception:
            return found
        depth = 0
        index = start
        end = -1
        while index < len(masked):
            char = masked[index]
            if char == '[':
                depth += 1
            elif char == ']':
                depth -= 1
                if depth == 0:
                    end = index
                    break
            index += 1
        if end < 0:
            continue
        cursor = start + 1
        count = 0
        while cursor < end and count < limit:
            while cursor < end and masked[cursor] in ' \t\r\n,':
                cursor += 1
            if cursor >= end or masked[cursor] != '[':
                break
            cursor += 1
            count += 1
            fields = []
            for _ in range(2):
                while cursor < end and masked[cursor] in ' \t\r\n,':
                    cursor += 1
                if cursor < end and masked[cursor] in '\'"`':
                    quote = masked[cursor]
                    close = text.find(quote, cursor + 1)
                    if close < 0:
                        break
                    fields.append(text[cursor + 1:close])
                    cursor = close + 1
                else:
                    break
            if len(fields) == 2 and _LOOSE_ID.match(fields[0]) and fields[1].strip():
                tool = _normalise({'id': fields[0], 'name': fields[1]}, 'code')
                if tool and tool['id'] not in found:
                    found[tool['id']] = tool
            # 跳到下一个顶层元素
            depth = 1
            while cursor < end:
                char = masked[cursor]
                if char in '[{(':
                    depth += 1
                elif char in ']})':
                    depth -= 1
                    if depth == 0:
                        cursor += 1
                        break
                cursor += 1
    return found


def _loose_call_tools(text, limit=200):
    """兜底 C：`register('id', '名称', '描述', {...})` 这类位置参数注册函数。

    真例：mooncell 用 const register = (id, name, description, parameters, method) => api.registerTool({id, ...})。
    """
    found = {}
    for match in re.finditer(r'\b([A-Za-z_$][\w$]*)\s*\(\s*([\'"])([A-Za-z0-9_-]{1,64})\2\s*,\s*([\'"])', text):
        name = match.group(1)
        if not re.search(r'register|tool', name, re.I):
            continue
        ident = match.group(3)
        start = match.start(4) + 1
        close = text.find(match.group(4), start)
        if close < 0 or close - start > 200:
            continue
        label = text[start:close].strip()
        if not label:
            continue
        tool = _normalise({'id': ident, 'name': label}, 'code')
        if tool and tool['id'] not in found:
            found[tool['id']] = tool
        if len(found) >= limit:
            break
    return found


def _loose_tools(text):
    """兜底：严格路径一个工具都没解出来时，用三种宽松扫描合并。"""
    merged = {}
    for table in (_loose_object_tools(text), _loose_array_tools(text), _loose_call_tools(text)):
        for key, value in table.items():
            if key not in merged:
                merged[key] = value
    return list(merged.values())


def _loose_from_dir(root):
    """对一个包做兜底扫描（只在严格路径返回空时调用）。"""
    found = {}
    try:
        for path in sorted(root.rglob('*.js')):
            if path.stat().st_size > 400000:
                continue
            text = _read_text(path, MAX_FILE_BYTES)
            if not text:
                continue
            for tool in _loose_tools(text):
                old = found.get(tool['id'])
                if old is None or (not old['parameters'] and tool['parameters']):
                    found[tool['id']] = tool
    except Exception as exc:
        _log.debug('loose scan failed on %s: %s', root, exc)
    return list(found.values())
'''

# (文件, 名字, 原文, 替换, 说明, 是否属于 limit 组, 已应用标记)
# 已应用标记：应用后文件里必然出现、且别处不会出现的字符串。
# 纯删除型补丁（替换为空）没有可依赖的「新内容」，插入型补丁的原文又可能被后续补丁改掉，
# 所以必须显式给出标记，否则 --check 会把已应用的判成 missing。
NODE_MODULES_HELPER = r'''_NODE_MODULES_CACHE: Dict[str, Optional[Path]] = {}


def host_node_modules(runtime=None) -> Optional[Path]:
    """推出宿主根下的 node_modules（宿主 require 时真正会命中的那个）。

    宿主把 skill 包拷到 <source>/skills-host-<pid>/0000-<id>/ 再加载，Node 的
    require 会逐级向上找 node_modules，所以 <source>/node_modules 就是可见范围。
    找不到返回 None —— 调用方按旧行为处理（不查 node_modules）。
    """
    try:
        base = str(data_dir(runtime))
    except Exception:
        return None
    if base in _NODE_MODULES_CACHE:
        return _NODE_MODULES_CACHE[base]
    found: Optional[Path] = None
    try:
        from . import qqagent_host as _qqagent_host
        candidate = Path(_qqagent_host.default_host_root(base)) / 'node_modules'
        if candidate.is_dir():
            found = candidate
    except Exception:
        found = None
    if found is None:
        guess = Path(base) / 'qqagent_host' / 'node_modules'
        found = guess if guess.is_dir() else None
    _NODE_MODULES_CACHE[base] = found
    return found


def npm_available(token: str, modules: Optional[Path]) -> bool:
    """npm:<包名> 是否真在宿主 node_modules 里。modules 为 None 时一律当作不可知。"""
    name = str(token or '')[4:].strip()
    if not name or modules is None:
        return False
    if name.startswith('@'):
        parts = name.split('/')
        if len(parts) < 2:
            return False
        target = modules / parts[0] / parts[1]
    else:
        target = modules / name.split('/')[0]
    try:
        return target.exists()
    except OSError:
        return False


def blocked_capabilities(usage: Iterable[str], permissions: Iterable[str] = (),
                         modules: Optional[Path] = None) -> set:
    """算出「宿主给不了」的成员：真缺的 ctx 成员、需授权而未授权的内置模块、缺的 npm 包。

    内置模块按三档判：NODE_BUILTIN_SAFE 与 NODE_BUILTIN_ACCOUNTED（如 node:child_process）
    都不算阻断，区别只在后者会被记进注册审计的 released 字段；NODE_BUILTIN_GATED 只有
    skill 自己的 permissions 里有对应权限名才放行（GATED_BY_PERMISSION）。ctx 成员与 npm
    包：npm 包会先看宿主 node_modules 里到底有没有（modules 为 None 时退回旧行为）。
    """
    perms = {str(item).strip().lower() for item in permissions or ()}
    blocked = set()
    for token in usage or ():
        if (token in HOST_SUPPORTED_CTX or token in NODE_BUILTIN_SAFE
                or token in NODE_BUILTIN_ACCOUNTED):
            continue
        gate = GATED_BY_PERMISSION.get(token)
        if gate and gate in perms:
            continue
        if str(token).startswith('npm:') and npm_available(token, modules):
            continue
        blocked.add(token)
    return blocked
'''

PATCHES = [
    # ── 第一组：修「装了不生效」────────────────────────────────────────────
    (
        "src/skill_manifest.py",
        "A1 classify 接受 skill_id",
        'def classify(reader, tools=None):',
        'def classify(reader, tools=None, skill_id=""):',
        "给 classify 加可选 skill_id 参数，默认行为不变",
        False,
    ),
    (
        "src/skill_manifest.py",
        "A2 工具名用 skill_id 补前缀",
        '    tool_list = _tool_entries(tools, posixpath.basename(root) if root else "")',
        '    tool_list = _tool_entries(tools, skill_id or (posixpath.basename(root) if root else ""))',
        "扁平布局下 root 为空，改用具名 skill_id",
        False,
    ),
    (
        "src/skill_manifest.py",
        "A3 _skill_entry 把 skill_id 传进去",
        '        info = classify(reader, tools=tools)',
        '        info = classify(reader, tools=tools, skill_id=skill_id)',
        "_skill_entry 本来就有 skill_id，只是没传",
        False,
    ),
    (
        "src/skill_manifest.py",
        "B ensure_manifest 用 runtime 派生目录",
        '        manifest = build_manifest(market_dir=market_dir, extensions_root=extensions_root)',
        '        if extensions_root is None:\n'
        '            try:\n'
        '                extensions_root = skill_tools.extensions_dir(runtime)\n'
        '            except Exception:\n'
        '                extensions_root = None\n'
        '        if market_dir is None:\n'
        '            try:\n'
        '                market_dir = skill_tools.market_dir(runtime=runtime)\n'
        '            except Exception:\n'
        '                market_dir = None\n'
        '        manifest = build_manifest(market_dir=market_dir, extensions_root=extensions_root)',
        "不再依赖 CWD 的相对路径，改用 runtime 的绝对路径",
        False,
    ),
    # ── 第二组：修「能跑却判死」────────────────────────────────────────────
    (
        "src/skill_tools.py",
        "C1a 插入 _strip_js_comments 辅助函数",
        '_MEMBER = re.compile(r"\\b(?:ctx|api)\\s*(?:\\?\\.|\\.)\\s*([A-Za-z_$][\\w$]*)")',
        '_MEMBER = re.compile(r"\\b(?:ctx|api)\\s*(?:\\?\\.|\\.)\\s*([A-Za-z_$][\\w$]*)")' + STRIP_HELPER,
        "扫描前剥注释，注释里的 api.xxx 不是依赖",
        False,
        "def _strip_js_comments(text):",
    ),
    (
        "src/skill_tools.py",
        "C1b _scan_reader 剥注释后再扫",
        '        text = reader.read(name)\n'
        '        if text is None:\n'
        '            continue\n'
        '        seen.append(name)',
        '        text = reader.read(name)\n'
        '        if text is None:\n'
        '            continue\n'
        '        text = _strip_js_comments(text)\n'
        '        seen.append(name)',
        "只剥注释，不改扫描范围与 import 闭包",
        False,
    ),
    (
        "src/skill_manifest.py",
        "C3 T4-host-source 只看入口文件的逃逸深度",
        '    if requires:\n',
        '    if host_imports:\n'
        '        _above = sorted(set(escape_above))\n'
        '        if _above:\n'
        '            return result("T4-host-source", "host-source:%s" % _above[0])\n'
        '    if requires:\n',
        "host_imports 只是「有 ../」，不等于加载不到。包运行期被拷到 "
        "<source>/skills-host-<pid>/0000-<id>/，从包根上溯 2 层正好是 <source>/，"
        "所以 '../../src/config.js' 解析到 <source>/src/config.js —— 实测 node import 成功"
        "（keys=CONFIG_FILE,DATA_DIR,DEFAULT_PRICE,...）。"
        "2026-11-07 全量核算（_audit/host_import_gate_matrix.txt）：92 个声明 hostImports 的包里"
        "89 个全部落在 2 层内且真跑 ok 84 个，只有 anon-qa 的入口写 '../../../src/config.js' "
        "（3 层，越过 <source>）真解析不到 —— 那个包已被 escape_above 判 T6。"
        "所以 T4 只看 escape_above（入口自己的逃逸深度），不看「有没有 ../」。",
        False,
        '_above = sorted(set(escape_above))',
    ),
    (
        "src/skill_tools.py",
        "C4b _skill_plan 的 hostImports 闸按入口逃逸深度判（5.2.112 措辞版本）",
        "    if reader is None:\n"
        "        return None, '既没安装、市场里也没有这个 zip，扫不到源码'\n",
        "    declared_host = [str(item) for item in (skill.get('hostImports') or []) if str(item).strip()]\n"
        "    if declared_host and not forced and reader is None:\n"
        "        # 只有「没有源码可扫」时才拿清单声明的 hostImports 兜底判死（fail-closed）。\n"
        "        # 有源码时不能按清单判：classify() 已经把「入口文件自己上溯 >=3 层」判成\n"
        "        # T6 escape-run-root，而声明里的 3~4 层上溯大多出现在非入口文件里（永远不加载），\n"
        "        # 实测 bili / machine-work / pai-skills 等 7 个包都属这类，真跑 ok。\n"
        "        # 包运行期被拷到 <source>/skills-host-<pid>/0000-<id>/，2 层正好回到 <source>/，\n"
        "        # '../../src/config.js' 实测能 import。\n"
        "        return None, ('宿主源码模块：清单声明了 %s，运行期 require 不到 0.4 宿主源码树，'\n"
        "                      '不加载' % ', '.join(declared_host[:3]))\n"
        "    if reader is None:\n"
        "        return None, '既没安装、市场里也没有这个 zip，扫不到源码'\n",
        "5.2.112 把这处闸改写成了 declared_host 版本。判据与 classify() 的 escape_above 同一口径："
        "只看上溯层数，不看「有没有 ../」。实测 92 个声明 hostImports 的包里 89 个是 2 层（真跑 ok 84 个），"
        "只有 anon-qa 是 3 层。old 只取代码行、不取注释 —— 这台机器上别的会话会往这段加注释，"
        "把注释写进 old 会导致下次定位失败（已踩过 2 次）",
        False,
        "if declared_host and not forced and reader is None:",
    ),
    (
        "src/skill_tools.py",
        "C4c 插入 _host_escape_depth 辅助函数",
        "def _split_full_name(full: str) -> tuple:\n",
        "def _host_escape_depth(spec) -> int:\n"
        '    """数一条相对 import 上溯了几层：\'../../src/config.js\' -> 2。\n'
        "\n"
        "    包运行期被拷到 <source>/skills-host-<pid>/0000-<id>/，从包根上溯 2 层正好是\n"
        "    <source>/（0.4 宿主源码目录），所以 2 层能解析、3 层越过它。判据与\n"
        "    src/skill_manifest.py:363 的 escape_above 同一口径。\n"
        '    """\n'
        "    depth = 0\n"
        "    rest = str(spec or '')\n"
        "    while rest.startswith('../'):\n"
        "        rest = rest[3:]\n"
        "        depth += 1\n"
        "    return depth\n"
        "\n"
        "\n"
        "def _split_full_name(full: str) -> tuple:\n",
        "C4b 依赖这个辅助函数：数一条相对 import 上溯了几层。",
        False,
        "def _host_escape_depth(spec) -> int:",
    ),
    (
        "src/skill_tools.py",
        "C5a node 内置模块：module/timers-promises 归 SAFE",
        "NODE_BUILTIN_SAFE = frozenset({\n"
        "    'node:path', 'node:url', 'node:os', 'node:crypto', 'node:util', 'node:querystring',\n"
        "    'node:string_decoder', 'node:buffer', 'node:events', 'node:assert', 'node:zlib',\n"
        "    'node:stream', 'node:timers', 'node:readline', 'node:perf_hooks',\n"
        "    'node:fs', 'node:fs/promises',\n"
        "})",
        "NODE_BUILTIN_SAFE = frozenset({\n"
        "    'node:path', 'node:url', 'node:os', 'node:crypto', 'node:util', 'node:querystring',\n"
        "    'node:string_decoder', 'node:buffer', 'node:events', 'node:assert', 'node:zlib',\n"
        "    'node:stream', 'node:timers', 'node:readline', 'node:perf_hooks',\n"
        "    'node:fs', 'node:fs/promises',\n"
        "    # 纯计算，无宿主外副作用：createRequire / setTimeout as delay / 常量表\n"
        "    'node:module', 'node:timers/promises', 'node:constants', 'node:process',\n"
        "})",
        "11 个包只用 createRequire，1 个只用 setTimeout as delay",
        False,
    ),
    (
        "src/skill_tools.py",
        "C5b node 出网模块改归 ACCOUNTED（放行但记账）",
        "NODE_BUILTIN_ACCOUNTED = frozenset({'node:child_process'})",
        "NODE_BUILTIN_ACCOUNTED = frozenset({\n"
        "    'node:child_process',\n"
        "    # 出网/线程/vm：原来在 GATED，要求声明 network/worker_threads/vm 权限，\n"
        "    # 但真实市场 379 个 zip 里没有任何包声明过这些名字 —— 那道闸一次都不会触发，\n"
        "    # 等于永久阻断。宿主本身就是 Node，注册期挡不住代码自己 import()，\n"
        "    # 所以改归 ACCOUNTED：放行，但每一次放行都在注册审计里留 released 痕迹。\n"
        "    'node:net', 'node:http', 'node:https', 'node:tls', 'node:dgram',\n"
        "    'node:dns', 'node:dns/promises', 'node:worker_threads', 'node:vm',\n"
        "})",
        "13 个 node:net / 6 个 node:http / 3 个 node:https / 4 个 node:dns",
        False,
    ),
    (
        "src/skill_tools.py",
        "C5c GATED 清空（已全部并入 ACCOUNTED）",
        "NODE_BUILTIN_GATED = {\n"
        "    'node:net': 'network',\n"
        "    'node:http': 'network',\n"
        "    'node:https': 'network',\n"
        "    'node:dgram': 'network',\n"
        "    'node:tls': 'network',\n"
        "    'node:dns': 'network',\n"
        "    'node:dns/promises': 'network',\n"
        "    'node:worker_threads': 'worker_threads',\n"
        "    'node:vm': 'vm',\n"
        "}",
        "NODE_BUILTIN_GATED = {}",
        "上面已整体并入 ACCOUNTED；留着会重复挡一次。"
        "old 按宿主 5.2.112 现场原文写（已含 node:dns 两项）",
        False,
    ),
    # ── 第三组：实际生效数量 ───────────────────────────────────────────────
    (
        "src/agent_tools.py",
        "D SKILL_LIMIT 20 → 60",
        "SKILL_LIMIT = 20",
        "SKILL_LIMIT = 60",
        "按 id 字母序只注册前 20 个，会截掉有用的、留下缺配置的",
        True,
    ),
    # ── 第四组：ctx 成员闸（最大的一道，实测也是误判）──────────────────────
    (
        "src/skill_tools.py",
        "E1 ctx 成员只审计不拦截",
        "    blocked = blocked_capabilities(scan['members'], skill.get('permissions'))\n"
        "    if blocked and not forced:\n"
        "        return None, 'ctx/宿主 API 用到宿主不提供的成员：%s' % ', '.join(sorted(blocked)[:8])\n",
        "    blocked = blocked_capabilities(scan['members'], skill.get('permissions'))\n"
        "    # ctx 成员不再拦截，只记进审计的 blocked/released 字段。\n"
        "    # 实测依据：276 个被这道闸挡住的 skill 里 242 个真跑 ok（工具 836 个），\n"
        "    # 源码全是防御式写法（ctx?.sender && typeof ctx.sender.sendImage === 'function'），\n"
        "    # 宿主不给就走降级分支。node:/npm: 的真缺仍由 blocked_capabilities 判。\n"
        "    hard = {t for t in blocked if str(t).startswith(('node:', 'npm:'))}\n"
        "    if hard and not forced:\n"
        "        return None, '缺宿主内置模块或 npm 包：%s' % ', '.join(sorted(hard)[:8])\n",
        "242/276 被 ctx 闸挡住的 skill 真跑 ok，源码是防御式写法，不是硬依赖",
        False,
        "hard = {t for t in blocked if str(t).startswith(('node:', 'npm:'))}",
    ),
    # ── 第五组：工具 id 是常量引用（中文显示名被当成 id）────────────────────
    (
        "src/tool_schema.py",
        "F1 _code_tools 解析前内联常量",
        CODE_TOOLS_OLD,
        CODE_TOOLS_NEW,
        "`id: TOOL.list` 解不出 → id 键被丢弃 → 退回中文 name → 清单名与运行期名对不上",
        False,
        "def _inline_consts(text, consts):",
    ),
    # ── 第六组：比对口径不一致（id 带点号的 skill 被误报失败）──────────────
    (
        "src/skill_tools.py",
        "F2 注册后比对用同一套清洗口径",
        "            registered_names = tool_loop.registry_for(runtime).names()\n"
        "            for tool in tools:\n"
        "                if tool['full'] in registered_names:\n"
        "                    names.append(tool['full'])\n",
        "            registered_names = tool_loop.registry_for(runtime).names()\n"
        "            for tool in tools:\n"
        "                # 工具表里的键是 _clean_name(source + '__' + raw_name)，点号等会被洗成下划线\n"
        "                # （reply-meme_1.2.0 → reply-meme_1_2_0）；清单里的 full 是原始拼法。\n"
        "                # 两边必须用同一口径比，否则这类 skill 明明注册成功也会被记成失败。\n"
        "                if tool_loop._clean_name(tool['full']) in registered_names:\n"
        "                    names.append(tool['full'])\n",
        "清单名 reply-meme_1.2.0__x 与工具表键 reply-meme_1_2_0__x 不同，按清单名比永远失败",
        False,
        "if tool_loop._clean_name(tool['full']) in registered_names:",
    ),
    # ── 第七组：清单前缀与运行期前缀不一致 ────────────────────────────────
    (
        "src/skill_tools.py",
        "F3 用运行期前缀替换清单前缀",
        "    for tool in skill.get('tools') or []:\n"
        "        prefix, rest = _split_full_name(tool['name'])\n"
        "        if not prefix or not rest:\n"
        "            odd.append(str(tool.get('name')))\n"
        "            continue\n"
        "        tools.append({'full': tool['name'], 'prefix': prefix, 'raw': rest,\n"
        "                      'description': (tool.get('description') or skill.get('summary')\n"
        "                                      or tool['name'])})\n",
        "    for tool in skill.get('tools') or []:\n"
        "        prefix, rest = _split_full_name(tool['name'])\n"
        "        if not prefix or not rest:\n"
        "            odd.append(str(tool.get('name')))\n"
        "            continue\n"
        "        # 运行期前缀可能被宿主 sanitize/截断（skillId 截到 24 位、点号换成下划线），\n"
        "        # 清单里存的是 skill id 的拼法。host-one 的 owned() 要求 tool.id 与 skillId\n"
        "        # 都对得上，所以这里必须换成运行期前缀，否则每次调用都报「tool 不属于被选扩展」。\n"
        "        live_prefix = KNOWN_PREFIX_MISMATCH.get(prefix) or prefix\n"
        "        full = tool['name'] if live_prefix == prefix else live_prefix + '__' + rest\n"
        "        tools.append({'full': full, 'prefix': live_prefix, 'raw': rest,\n"
        "                      'description': (tool.get('description') or skill.get('summary')\n"
        "                                      or tool['name'])})\n",
        "清单前缀 global-short-memory-lookup / reply-meme_1.2.0 与运行期前缀被截断/清洗后不同，"
        "调用必报 tool 不属于被选扩展",
        False,
        "live_prefix = KNOWN_PREFIX_MISMATCH.get(prefix) or prefix",
    ),
    # ── 第八组：静态解析解不出工具定义（整包被判「无工具」）─────────────────
    (
        "src/tool_schema.py",
        "G1 加入 loose 兜底扫描函数",
        "def extract_tools(extension_dir, entry_files=None) -> Dict[str, dict]:",
        LOOSE_HELPER + "def extract_tools(extension_dir, entry_files=None) -> Dict[str, dict]:",
        "registerTool(fn()) / 表驱动 / 位置参数注册三类写法解析不出工具，整包被判无工具",
        False,
        "def _loose_from_dir(root):",
    ),
    (
        "src/tool_schema.py",
        "G2 严格路径为空时跑 loose 兜底",
        "    except Exception as exc:\n"
        "        _log.debug('extract_tools failed on %s: %s', extension_dir, exc)\n"
        "    return result\n",
        "    except Exception as exc:\n"
        "        _log.debug('extract_tools failed on %s: %s', extension_dir, exc)\n"
        "    if not result:\n"
        "        # 兜底：严格路径一个工具都没解出来时，用宽松扫描再试一次。\n"
        "        # 只在「空结果」时触发，正常包完全不受影响（实测 331 包工具数不变）。\n"
        "        try:\n"
        "            loose_root = Path(extension_dir)\n"
        "            if loose_root.is_dir():\n"
        "                for tool in _loose_from_dir(loose_root):\n"
        "                    result.setdefault(tool['id'], tool)\n"
        "        except Exception as exc:\n"
        "            _log.debug('loose scan failed on %s: %s', extension_dir, exc)\n"
        "    return result\n",
        "22 个「无工具」skill 里 19 个其实有 67 个工具，只是静态解析解不出",
        False,
        "for tool in _loose_from_dir(loose_root):",
    ),
    # ── 第四组：修「明明没依赖 npm 包却报缺」──────────────────────────────
    (
        "src/skill_tools.py",
        "H1 _IMPORT 只认合法模块说明符",
        '_IMPORT = re.compile(r"(?:from\\s*[\'\\"]([^\'\\"]+)[\'\\"]|'
        'require\\(\\s*[\'\\"]([^\'\\"]+)[\'\\"]\\s*\\))")',
        '_IMPORT = re.compile(r"(?:from\\s*[\'\\"]([^\'\\"\\s,;()\\[\\]{}]+)[\'\\"]|'
        'require\\(\\s*[\'\\"]([^\'\\"\\s,;()\\[\\]{}]+)[\'\\"]\\s*\\))")',
        "停用词数组里的 'from', ' 会被当成 import 语句，抓出 ', ' 这种假模块名；"
        "把捕获组限制成合法说明符字符集",
        False,
        '[^\'\\"\\s,;()\\[\\]{}]+)[\'\\"]|require',
    ),
    # ── 第五组：修「宿主 node_modules 里明明有这个包却报缺」──────────────
    (
        "src/skill_tools.py",
        "H2a npm 包按宿主 node_modules 实查",
        'def blocked_capabilities(usage: Iterable[str], permissions: Iterable[str] = ()) -> set:\n    """算出「宿主给不了」的成员：真缺的 ctx 成员、需授权而未授权的内置模块、缺的 npm 包。\n\n    内置模块按三档判：NODE_BUILTIN_SAFE 与 NODE_BUILTIN_ACCOUNTED（如 node:child_process）\n    都不算阻断，区别只在后者会被记进注册审计的 released 字段；NODE_BUILTIN_GATED 只有\n    skill 自己的 permissions 里有对应权限名才放行（GATED_BY_PERMISSION）。ctx 成员与 npm\n    包的判定与旧版逐字一致（npm 包不在宿主 node_modules 里就是真缺）。\n    """\n    perms = {str(item).strip().lower() for item in permissions or ()}\n    blocked = set()\n    for token in usage or ():\n        if (token in HOST_SUPPORTED_CTX or token in NODE_BUILTIN_SAFE\n                or token in NODE_BUILTIN_ACCOUNTED):\n            continue\n        gate = GATED_BY_PERMISSION.get(token)\n        if gate and gate in perms:\n            continue\n        blocked.add(token)\n    return blocked\n',
        NODE_MODULES_HELPER + '',
        "blocked_capabilities 对 npm: 前缀的 token 一律判死，从不看宿主 node_modules；"
        "实测 ws/js-yaml/undici 都在宿主 node_modules 里（只有 electron 真缺），"
        "4 个 skill 因此被误判",
        False,
        "def npm_available(token: str, modules: Optional[Path]) -> bool:",
    ),
    (
        "src/skill_tools.py",
        "H2b _skill_plan 接收宿主 node_modules",
        'def _skill_plan(skill: dict, reader, source: str, forced: bool) -> tuple:',
        'def _skill_plan(skill: dict, reader, source: str, forced: bool,\n                modules: Optional[Path] = None) -> tuple:',
        "把宿主 node_modules 传进 _skill_plan",
        False,
        "def _skill_plan(skill: dict, reader, source: str, forced: bool,",
    ),
    (
        "src/skill_tools.py",
        "H2c _skill_plan 调 blocked_capabilities 时带上 modules",
        "    blocked = blocked_capabilities(scan['members'], skill.get('permissions'))",
        "    blocked = blocked_capabilities(scan['members'], skill.get('permissions'), modules)",
        "把 modules 交给 blocked_capabilities",
        False,
        "skill.get('permissions'), modules)",
    ),
    (
        "src/skill_tools.py",
        "H2d eligible_skills 先算一次宿主 node_modules",
        '    eligible, skipped = [], []\n    by_tier: Dict[str, int] = {}',
        '    modules = host_node_modules(runtime)\n    eligible, skipped = [], []\n    by_tier: Dict[str, int] = {}',
        "整个清单算一次即可（探测 200 次 iterdir 只花 11.4 ms）",
        False,
        "modules = host_node_modules(runtime)",
    ),
    (
        "src/skill_tools.py",
        "H2e 调用点传入 modules",
        '            plan, reason = _skill_plan(skill, reader, source, ident in allow_set)',
        '            plan, reason = _skill_plan(skill, reader, source, ident in allow_set, modules)',
        "把 modules 传给 _skill_plan",
        False,
        "ident in allow_set,",
    ),
    # ── 第九组：修「双层嵌套包被判 no-entry」──────────────────────────────
    (
        "src/skill_manifest.py",
        "I 包根优先选同时含入口的那层",
        'def _package_root(names):\n'
        '    """包根 = 最浅的 skill.json / plugin.json 所在目录（无清单返回 None）。"""\n'
        '    manifests = [name for name in names if posixpath.basename(name) in MANIFEST_NAMES]\n'
        '    if not manifests:\n'
        '        return None\n'
        '    return posixpath.dirname(min(manifests, key=lambda name: name.count("/")))\n',
        'def _package_root(names):\n'
        '    """包根 = 最浅的「既有清单、又有入口」的目录；都没有入口时退回最浅清单目录。\n'
        '\n'
        '    市场里有一批包是双层嵌套（真例 <id>/<id>/index.js）：外层只放了\n'
        '    skill.json / plugin.json 副本，真包在内层。按「最浅清单目录」取根会把\n'
        '    entry 拼成 <id>/index.js 而文件根本不存在，整包被判 no-entry。\n'
        '    """\n'
        '    manifests = [name for name in names if posixpath.basename(name) in MANIFEST_NAMES]\n'
        '    if not manifests:\n'
        '        return None\n'
        '    name_set = set(names)\n'
        '    dirs = sorted({posixpath.dirname(name) for name in manifests},\n'
        '                  key=lambda item: (item.count("/") if item else -1, item))\n'
        '    for root in dirs:\n'
        '        for entry in ENTRY_NAMES:\n'
        '            if (posixpath.join(root, entry) if root else entry) in name_set:\n'
        '                return root\n'
        '    return dirs[0]\n',
        "双层嵌套包的 entry 拼在外层、文件不存在 → 整包被判 no-entry（jujutsu-phantom-parade "
        "实测扁平化后 6 个工具全注册）；改成优先选同时含清单与入口的那层，"
        "正常包（清单与入口同层）结果完全不变",
        False,
        "for root in dirs:",
    ),
    # ── 第十组：修「requires 有提供方也被无条件判死」──────────────────────
    (
        "src/skill_tools.py",
        "J1 能力提供方索引 helper",
        "def _skill_plan(skill: dict, reader, source: str, forced: bool,\n"
        "                modules: Optional[Path] = None) -> tuple:\n",
        'def capability_providers(runtime=None) -> Dict[str, List[str]]:\n'
        '    """扫描已安装扩展的清单，算出「能力名 → 提供它的扩展 id」索引。\n'
        '\n'
        '    宿主的依赖判定（runtime/qqagent-host/host-one.mjs:162-183 planDependencies）\n'
        '    只要求「提供方已安装且已启用」，不要求消费方自己声明什么。而这里的\n'
        '    _skill_plan 原来对任何非空 requires 一律判死（「requires 未满足」），\n'
        '    把 better-notes 这种「依赖市场里另一个扩展」的包全锁在外面 ——\n'
        '    实测把 shared-memory 的 id 放进 QQ_AGENT_DEPENDENCY_IDS 后，\n'
        '    better-notes 的 4 个工具全部正常注册。\n'
        '    """\n'
        '    index: Dict[str, List[str]] = {}\n'
        '    try:\n'
        '        base = extensions_dir(runtime)\n'
        '        if not base.is_dir():\n'
        '            return index\n'
        '        for item in base.iterdir():\n'
        '            if not item.is_dir():\n'
        '                continue\n'
        '            raw = None\n'
        '            for name in ("skill.json", "plugin.json"):\n'
        '                candidate = item / name\n'
        '                if not candidate.is_file():\n'
        '                    continue\n'
        '                try:\n'
        '                    raw = json.loads(candidate.read_text(encoding="utf-8-sig"))\n'
        '                except Exception:\n'
        '                    raw = None\n'
        '                break\n'
        '            if not isinstance(raw, dict):\n'
        '                continue\n'
        '            ident = str(raw.get("id") or item.name)\n'
        '            caps = raw.get("capabilities")\n'
        '            for cap in (caps if isinstance(caps, list) else []):\n'
        '                text = str(cap or "").strip()\n'
        '                if text:\n'
        '                    index.setdefault(text, []).append(ident)\n'
        '    except Exception:\n'
        '        return index\n'
        '    return index\n'
        '\n'
        '\n'
        "def _skill_plan(skill: dict, reader, source: str, forced: bool,\n"
        "                modules: Optional[Path] = None,\n"
        "                providers: Optional[Dict[str, List[str]]] = None) -> tuple:\n",
        "requires 有已安装提供方时应当放行（宿主 planDependencies 就是这么判的），"
        "新增 capability_providers() 扫已安装扩展的 capabilities",
        False,
        "def capability_providers(runtime=None) -> Dict[str, List[str]]:",
    ),
    (
        "src/skill_tools.py",
        "J2 requires 只在真缺提供方时判死",
        "    if skill.get('requires'):\n"
        "        return None, 'requires 未满足：%s' % ', '.join(skill['requires'][:4])\n",
        "    wanted = [str(cap) for cap in (skill.get('requires') or []) if str(cap).strip()]\n"
        "    if wanted:\n"
        "        index = providers if providers is not None else {}\n"
        "        missing = [cap for cap in wanted if not index.get(cap)]\n"
        "        if missing and not forced:\n"
        "            return None, 'requires 没有提供方：%s' % ', '.join(missing[:4])\n",
        "原来的 if skill.get('requires') 是无条件判死，从不看市场里有没有提供方；"
        "改成只对「真缺提供方」的能力判死（forced 时仍放行）",
        False,
        "requires 没有提供方：",
    ),
    (
        "src/skill_tools.py",
        "J3 eligible_skills 先算一次能力索引",
        '    modules = host_node_modules(runtime)\n    eligible, skipped = [], []',
        '    modules = host_node_modules(runtime)\n    providers = capability_providers(runtime)\n'
        '    eligible, skipped = [], []',
        "能力索引整个清单只算一次（与 modules 同口径）",
        False,
        "providers = capability_providers(runtime)",
    ),
    (
        "src/skill_tools.py",
        "J4 调用点传入 providers",
        '            plan, reason = _skill_plan(skill, reader, source, ident in allow_set, modules)',
        '            plan, reason = _skill_plan(skill, reader, source, ident in allow_set,\n'
        '                                       modules, providers)',
        "把 providers 传给 _skill_plan",
        False,
        "modules, providers)",
    ),
    # ── 第十一组：修「T5 的依赖其实有提供方却因 tier 闸先被拦」────────────
    (
        "src/skill_tools.py",
        "K1 T5 且提供方齐备时按依赖满足处理",
        "    if tier not in DEFAULT_TIERS and not forced:\n"
        "        return None, 'tier %s 默认不放行（只放 %s；要放行请把它列进 allow）' % (\n"
        "            tier or '未标注', '/'.join(DEFAULT_TIERS))\n",
        "    if tier not in DEFAULT_TIERS and not forced:\n"
        "        # T5-depends-other：tier 闸比 requires 闸更早，所以「依赖其实有提供方」\n"
        "        # 的包会先被这里拦掉、永远走不到后面的 requires 判断。宿主自己的\n"
        "        # planDependencies（host-one.mjs:162-183）只要求提供方已安装且已启用，\n"
        "        # 所以这里对 T5 多给一次机会：全部 requires 都有已安装提供方就继续往下判。\n"
        "        # 实测依据：better-notes 的 shared-memory.* 由 shared-memory 提供，\n"
        "        # 把它的 id 放进 QQ_AGENT_DEPENDENCY_IDS 后 4 个工具全部注册成功。\n"
        "        _wanted = [str(cap) for cap in (skill.get('requires') or []) if str(cap).strip()]\n"
        "        _index = providers if providers is not None else {}\n"
        "        _satisfied = bool(_wanted) and all(_index.get(cap) for cap in _wanted)\n"
        "        if tier != 'T5-depends-other' or not _satisfied:\n"
        "            return None, 'tier %s 默认不放行（只放 %s；要放行请把它列进 allow）' % (\n"
        "                tier or '未标注', '/'.join(DEFAULT_TIERS))\n",
        "T5-depends-other 在 tier 闸就被拦掉，走不到 requires 判断；"
        "改成「requires 全都有已安装提供方」时放行继续往下判",
        False,
        "_satisfied = bool(_wanted) and all(_index.get(cap) for cap in _wanted)",
    ),
    # ── 第十二组：修「纯提示词 / 纯 hook / 纯 provider 型包被判无工具」────
    (
        "src/skill_tools.py",
        "L1 无工具但有提示词/钩子/能力的包也放行",
        "    if not tools:\n"
        "        return None, '清单里的工具名不是运行时全名（缺 __），无法按宿主输出的名字注册：%s' % (\n"
        "            ', '.join(odd[:3]) or '无工具')\n",
        "    if not tools:\n"
        "        # 有一类包天生没有工具，但必须注册才生效：\n"
        "        #   ① 纯提示词型（force-send）：功能全在 skill.json 的 prompt.sections 里，\n"
        "        #      宿主 getPromptSections()（runtime/qqagent-host/src/skills/manager.js:440）\n"
        "        #      遍历已注册 skill 时才读得到；\n"
        "        #   ② 纯 hook 型（topic-guard）：只导出 hooks，靠 on_before_tool 硬拦；\n"
        "        #   ③ 纯 provider 型（video-frames / account-pool）：只导出 providers，\n"
        "        #      给核心提供 video.frames / llm.endpoint-pick 等能力。\n"
        "        # 这三种都没有工具，原判「无工具就不注册」会把它们全挡死。\n"
        "        # 判据：源码里出现 hooks / providers / promptSections 导出，或清单里有 prompt.sections。\n"
        "        # 注意：清单里的 prompt 不在 skill 条目上（skill 是 skill-tools.json 的摘要），\n"
        "        # 必须回 reader 读原始清单才拿得到。\n"
        "        _decl = skill.get('prompt') if isinstance(skill.get('prompt'), dict) else {}\n"
        "        _has_prompt = bool((_decl.get('sections') or [])) if _decl else False\n"
        "        if not _has_prompt:\n"
        "            try:\n"
        "                _all_names = reader.names() or []\n"
        "                for _mn in MANIFEST_NAMES:\n"
        "                    if _mn not in _all_names:\n"
        "                        continue\n"
        "                    _meta = json.loads(reader.read(_mn) or '{}')\n"
        "                    if isinstance(_meta, dict):\n"
        "                        _p = _meta.get('prompt')\n"
        "                        if isinstance(_p, dict) and (_p.get('sections') or []):\n"
        "                            _has_prompt = True\n"
        "                            break\n"
        "            except Exception:\n"
        "                pass\n"
        "        _code = ''\n"
        "        try:\n"
        "            for _name in (scan.get('files') or []):\n"
        "                _text = reader.read(_name)\n"
        "                if _text:\n"
        "                    _code += _strip_js_comments(_text)\n"
        "        except Exception:\n"
        "            _code = ''\n"
        "        _side = any(token in _code for token in\n"
        "                    ('export function hooks', 'export const hooks',\n"
        "                     'export function providers', 'export const providers',\n"
        "                     'export function promptSections', 'export const promptSections',\n"
        "                     'hooks:', 'providers:'))\n"
        "        if not (_has_prompt or _side):\n"
        "            return None, '清单里的工具名不是运行时全名（缺 __），无法按宿主输出的名字注册：%s' % (\n"
        "                ', '.join(odd[:3]) or '无工具')\n",
        "纯提示词型（force-send）/ 纯 hook 型（topic-guard）/ 纯 provider 型（video-frames、"
        "account-pool）本来就没有工具，但必须注册才生效；原来「无工具就不注册」把它们全挡死",
        False,
        "_has_prompt = bool((_decl.get('sections') or [])) if _decl else False",
    ),
    # ── 第十三组：classify 也放行「无工具但有提示词/钩子/能力」的包 ────────
    (
        "src/skill_manifest.py",
        "M1 classify 不再把纯提示词/钩子/能力型包判 no-tools",
        "    if register_sites == 0 and not tool_list:\n"
        "        return result(\"T6-disabled\", \"no-tools\")\n",
        "    if register_sites == 0 and not tool_list:\n"
        "        # 有一类包天生没有工具、但必须注册才生效（纯提示词 / 纯 hook / 纯 provider）：\n"
        "        #   · force-send   —— 功能全在 skill.json 的 prompt.sections，\n"
        "        #                    宿主 getPromptSections()（src/skills/manager.js:440）\n"
        "        #                    遍历**已注册** skill 时才读得到；\n"
        "        #   · topic-guard  —— 只导出 hooks，靠 on_before_tool 硬拦；\n"
        "        #   · video-frames —— 只导出 providers，给核心提供 video.frames；\n"
        "        #   · account-pool —— 只导出 providers，提供 llm.endpoint-pick 等。\n"
        "        # 它们都没有工具，原判「无工具就不注册」把整类包判成结构性残缺。\n"
        "        _side = False\n"
        "        _decl2 = declaration if isinstance(declaration, dict) else {}\n"
        "        _prompt = _decl2.get(\"prompt\") if isinstance(_decl2.get(\"prompt\"), dict) else {}\n"
        "        if _prompt.get(\"sections\"):\n"
        "            _side = True\n"
        "        if not _side:\n"
        "            for _n in names:\n"
        "                if not _n.endswith(JS_EXTS):\n"
        "                    continue\n"
        "                _t = _read(reader, _n)\n"
        "                if not _t:\n"
        "                    continue\n"
        "                _c = _strip_comments(_t)\n"
        "                if any(_tok in _c for _tok in (\n"
        "                        \"export function hooks\", \"export const hooks\",\n"
        "                        \"export function providers\", \"export const providers\",\n"
        "                        \"export function promptSections\", \"export const promptSections\",\n"
        "                        \"hooks:\", \"providers:\")):\n"
        "                    _side = True\n"
        "                    break\n"
        "        if not _side:\n"
        "            return result(\"T6-disabled\", \"no-tools\")\n",
        "纯提示词型（force-send）/ 纯 hook 型（topic-guard）/ 纯 provider 型（video-frames、"
        "account-pool）本来就没有工具，但必须注册才生效；classify 原来直接判 no-tools",
        False,
        "_decl2 = declaration if isinstance(declaration, dict) else {}",
    ),
    # ── 第十四组：修「T3-extra-api 把宿主真给了的能力当额外 API」────────────
    (
        "src/skill_manifest.py",
        "N1 onebot / qq_sticker 不是「额外 API」，宿主本来就给",
        '    extra = sorted(set(permissions) & EXTRA_APIS)\n'
        '    if extra:\n'
        '        return result("T3-extra-api", "extra-api:%s" % extra[0])\n',
        '    # onebot / qq_sticker 曾被视为「宿主没开放的额外 API」，实测宿主本来就给：\n'
        '    #   ctx.onebot  —— runtime/qqagent-host/src/orchestrator.js:958 `onebot: this.onebot`\n'
        '    #   ctx.stickers —— orchestrator.js:961 `stickers: this.stickers`\n'
        '    # 工具执行时 ctx 由 tools.js:131-134 的注释明确列出（onebot, store, memory, stickers,\n'
        '    # sender, session 都在里面）。self-profile 实测 list_tools ok + set_profile 能跑\n'
        '    # （只因为测试时没有 QQ 上下文才回「拿不到请求者 QQ 号」）。\n'
        '    # 所以这两个权限不再降级到 T3；真需要额外 API 的包另说。\n',
        "onebot / qq_sticker 由宿主 ctx 直接提供（orchestrator.js:958/961），"
        "self-profile 实测可加载可运行；原来把它们当「额外 API」降级到 T3 是误判",
        False,
        "onebot / qq_sticker 曾被视为",
    ),
]


def _fields(patch):
    """把补丁元组归一成 7 元组，兼容旧的 6 元组写法。"""
    rel, name, old, new, note, is_limit = patch[:6]
    marker = patch[6] if len(patch) > 6 else ""
    return rel, name, old, new, note, is_limit, marker


def _applied(text: str, old: str, new: str, marker: str) -> bool:
    """判断这处补丁是否已经应用。

    普通补丁：替换后的内容在文件里就算已应用。
    删除型补丁（new 为空）没有可依赖的新内容，必须用 marker 判：
    marker 以 "!" 开头表示「这串必须已消失」，否则表示「这串必须已出现」。

    但 marker 会骗人：正向 marker 若是一行**注释**，别的进程把被删的代码塞回去时
    注释会留下来（实测：C4b 的 `# hostImports 闸已拆…` 还在，闸的 4 行代码又被插回
    `if reader is None:` 之后），于是 marker 命中、补丁被跳过、代码却回来了。
    所以先看 old：**old 原样还在文件里就一定没应用**，不管 marker 说什么。

    只对「替换型」补丁这么做 —— 插入型补丁（old 是 new 的子串，如 B/C1a/G1/H2d）
    old 本来就该还在，拿 old 判会重复插入。
    """
    replaced = bool(old) and bool(new) and old not in new
    if replaced and old in text:
        return False
    if marker:
        if marker.startswith("!"):
            return marker[1:] not in text
        return marker in text
    if new:
        return new in text
    return False


def inspect(root: Path):
    """返回 [(文件, 名字, 状态, 说明)]，状态 ∈ applied / pending / missing。"""
    out = []
    for patch in PATCHES:
        rel, name, old, new, note, _is_limit, marker = _fields(patch)
        target = root / rel
        if not target.is_file():
            out.append((rel, name, "missing", "找不到文件"))
            continue
        text = target.read_text(encoding="utf-8")
        if _applied(text, old, new, marker):
            state = "applied"
        elif old in text:
            state = "pending"
        else:
            state = "missing"
        out.append((rel, name, state, note))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="给 QQ 工作台宿主打 skill 注册闸门补丁")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="宿主仓库根（默认 %s）" % DEFAULT_ROOT)
    ap.add_argument("--check", action="store_true", help="只看状态，不改文件")
    ap.add_argument("--apply", action="store_true", help="打补丁")
    ap.add_argument("--revert", action="store_true", help="从备份回滚")
    ap.add_argument("--no-limit", action="store_true",
                    help="不打 SKILL_LIMIT 那处（只修判死逻辑，不改上限）")
    args = ap.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print("找不到宿主根 %s" % root, file=sys.stderr)
        return 2

    print("宿主根：%s" % root)
    print()

    # ── 回滚 ────────────────────────────────────────────────────────────────
    if args.revert:
        done = 0
        for rel in sorted({p[0] for p in PATCHES}):
            target = root / rel
            backup = target.with_name(target.name + BACKUP_SUFFIX)
            if backup.is_file():
                shutil.copyfile(backup, target)
                print("已回滚：%s ← %s" % (rel, backup.name))
                done += 1
            else:
                print("无备份，跳过：%s" % rel)
        print()
        print("回滚 %d 个文件" % done)
        return 0

    rows = inspect(root)
    cur = None
    for rel, name, state, note in rows:
        if rel != cur:
            print("── %s" % rel)
            cur = rel
        mark = {"applied": "已修", "pending": "待修", "missing": "找不到"}[state]
        print("  [%s] %s — %s" % (mark, name, note))
    print()

    if args.check or not args.apply:
        pending = sum(1 for r in rows if r[2] == "pending")
        missing = sum(1 for r in rows if r[2] == "missing")
        if missing:
            print("有 %d 处定位失败（宿主版本可能不同），未做任何修改" % missing)
            return 1
        if pending:
            print("有 %d 处待修，加 --apply 打补丁" % pending)
        else:
            print("全部已修，无需操作")
        return 0

    # ── 打补丁 ──────────────────────────────────────────────────────────────
    todo = [r for r in rows if r[2] == "pending"]
    if args.no_limit:
        todo = [r for r in todo if r[0] != "src/agent_tools.py"]
    if not todo:
        print("没有待修项，无需操作")
        return 0

    bad = [r[1] for r in rows if r[2] == "missing"]
    if bad:
        print("以下补丁定位失败，为安全起见**不做任何修改**：", file=sys.stderr)
        for name in bad:
            print("  - %s" % name, file=sys.stderr)
        return 1

    # 按文件分组
    by_file = {}
    for rel, name, state, note in todo:
        by_file.setdefault(rel, []).append(name)

    for rel, names in by_file.items():
        target = root / rel
        backup = target.with_name(target.name + BACKUP_SUFFIX)
        text = target.read_text(encoding="utf-8")

        if not backup.is_file():
            shutil.copyfile(target, backup)
            print("已备份 → %s" % backup.name)

        new_text = text
        for patch in PATCHES:
            pref, name, old, new, note, _is_limit, marker = _fields(patch)
            if pref != rel or name not in names:
                continue
            if _applied(new_text, old, new, marker):
                continue
            if old not in new_text:
                print("补丁 %s 定位失败，已中止（文件未改）" % name, file=sys.stderr)
                return 1
            new_text = new_text.replace(old, new, 1)
            print("  已应用：%s" % name)

        try:
            compile(new_text, str(target), "exec")
        except SyntaxError as exc:
            print("补丁后语法检查失败，已中止（%s 未改）：%s" % (rel, exc), file=sys.stderr)
            return 1

        # 残块检查：替换型补丁（old 不是 new 的子串）打完以后，old 不应再出现在文件里。
        # 曾踩过：C4b 的闸体改过两次，旧块留在 live 里，_applied() 因为 marker 命中
        # 而跳过，结果 _skill_plan 里同时有两个 declared_host 段，前一个继续拦掉 7 个包。
        leftover = []
        for patch in PATCHES:
            pref, name, old, new, _note, _is_limit, _marker = _fields(patch)
            if pref != rel or name not in names:
                continue
            if not (old and new) or old in new:
                continue
            if old in new_text:
                leftover.append(name)
        if leftover:
            print("补丁后仍有残块，已中止（%s 未改）：%s" % (rel, ", ".join(leftover)), file=sys.stderr)
            return 1

        target.write_text(new_text, encoding="utf-8")
        print("  已写入 %s" % rel)

    print()
    print("回滚：python -X utf8 hostfix.py --revert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
