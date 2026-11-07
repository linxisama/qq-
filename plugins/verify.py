"""把打包产物按真实宿主路径验证一遍。

四轮：
  A. 逐包隔离挂载：每个包单独一个 data_dir，确认只挂自己、通道判定与实测一致。
  B. 全量共存：66 个包同时装进一个 data_dir，确认互不冲突、无一被拒载。
  C. 门面回归：给每个插件喂一个**形状接近 QQRuntime** 的替身，经
     `manager._call_mod_hook` 走真实调用路径（目录 mod 会套 ModRuntime 门面 + 2 秒超时）。
     目录 mod 包里只要有一条钩子抛 ModRuntime AttributeError，就是通道判定错了。
  D. 清单校验：用宿主自带的 `src.plugin_packs` 只读校验器过一遍每个目录包。

C 轮的意义：静态扫描会保守（宁可多判 override），这一轮用真门面跑一遍，
把「判成 mod 但其实会炸」的漏网之鱼抓出来——那才是必须修的问题。
"""
from __future__ import annotations

import asyncio
import inspect
import json
import shutil
import sys
import time
import traceback
from pathlib import Path

HOST = Path(r"D:\qq机器人5.0")
ROOT = Path(r"D:\插件\qq-plugin-packs")
sys.path.insert(0, str(HOST))

from src.plugins.manager import PluginManager  # noqa: E402
from src import plugin_packs  # noqa: E402

TMP = ROOT / ".verify"
INDEX = json.loads((ROOT / "INDEX.json").read_text(encoding="utf-8"))

MSG = {"id": 1, "key": "k1", "kind": "group", "text": "你好呀，今天怎么样",
       "sender_id": 10001, "target": 20002, "sender_name": "测试", "msg_id": 1,
       "time": time.time(), "images": [], "faces": [], "at_me": False, "is_group": True,
       "self_id": 30003, "notice": "", "raw": {}}


class _ChatState:
    """`runtime.chat_state` 的替身：返回空数据，不返回 `_Anything`。

    `conversation_memory.on_pre_ai` 把 `state.recall(...)` 的结果直接
    `json.dumps` 进提示词，返回 `_Anything` 会炸
    `TypeError: Object of type _Anything is not JSON serializable`——夹具的错。
    """

    def recall(self, *a, **kw):
        return []

    def ambient(self, *a, **kw):
        return ""


class _PluginHost:
    """`runtime.plugins` 的替身。

    宿主里它是 PluginManager，插件最常摸的是 `runtime.plugins._plugins[id]`
    （`src/chat_state.py:scope_of` 就这么取 archive_isolation）。返回 `_Anything`
    会让 `scope_of` 返回一个非字符串、被插件当 dict key 用时炸出
    `TypeError: keys must be str...`——那是夹具的错。
    """

    _plugins = {}


class _Anything:
    """万能替身：任何属性访问都返回自己，调用也返回自己。"""

    def __getattr__(self, name):
        return self

    def __call__(self, *a, **kw):
        return self

    def __bool__(self):
        return True

    def __iter__(self):
        return iter(())

    def __getitem__(self, k):
        return self

    def __eq__(self, other):
        return False

    def __hash__(self):
        return id(self)

    def __str__(self):
        return ""


class LiveRuntime:
    """尽量贴近 QQRuntime 的替身，让插件的正常分支能跑起来。

    成员表照 `src/qq_app.py:455 class QQRuntime` 抄：`mode` 是 property，
    `account(mode)` 是方法，`recent_chats/last_interaction/last_outbound/
    has_plugin_outgoing/queue_plugin_outgoing/outgoing_exists/can_send_proactive/
    queue_outgoing/set_persona` 都是方法，不是属性——写成属性会得到
    `TypeError: 'str' object is not callable`，那是夹具的错，不是插件的错。

    目录 mod 走门面时这些成员会被 ModRuntime 挡掉——这正是 C 轮要抓的。
    """

    running = True
    self_id = 30003
    style = _Anything()
    ai = _Anything()
    ai_lock = None            # 在 __init__ 里按需建，避免绑定到错误的 loop
    db = _Anything()
    onebot = _Anything()
    bridge = _Anything()
    pc = _Anything()
    plugins = _PluginHost()
    config = {"qq_only.mode": "onebot"}
    reply_meta = {}
    chat_state = _ChatState()
    stickers = _Anything()
    admin = _Anything()
    local_agent_console = _Anything()
    audio_gateway = _Anything()

    def __init__(self):
        if LiveRuntime.ai_lock is None:
            LiveRuntime.ai_lock = asyncio.Lock()

    @property
    def mode(self):
        return "onebot"

    def account(self, mode=None):
        return "30003"

    def note(self, msg):
        pass

    def secret(self, key):
        return ""

    def recent_messages(self, *a, **kw):
        return []

    def recent_chats(self, *a, **kw):
        return []

    def last_interaction(self, *a, **kw):
        return 0.0

    def last_outbound(self, *a, **kw):
        return 0.0

    def has_plugin_outgoing(self, *a, **kw):
        return False

    def queue_plugin_outgoing(self, *a, **kw):
        return None

    def outgoing_exists(self, *a, **kw):
        return False

    def can_send_proactive(self, *a, **kw):
        return False

    def queue_outgoing(self, *a, **kw):
        return None

    def set_persona(self, *a, **kw):
        return None


HOOK_CASES = [
    ("on_ingest", lambda rt: (MSG, rt)),
    ("on_block", lambda rt: (MSG, rt)),
    ("wants_reply", lambda rt: (MSG, rt)),
    ("on_pre_ai", lambda rt: (MSG, [], rt)),
    ("volatile_hint", lambda rt: ("提示文本", rt)),
    ("on_sent", lambda rt: (MSG, "回复内容", rt)),
    ("on_post_reply", lambda rt: (MSG, "回复内容", rt)),
    ("on_prepare", lambda rt: (MSG, rt)),
    ("tick", lambda rt: (rt,)),
]


def run_hook(inst, hook, rt):
    fn = getattr(type(inst), hook, None)
    if fn is None:
        return None
    res = getattr(inst, hook)(*HOOK_CASES[[c[0] for c in HOOK_CASES].index(hook)][1](rt))
    if inspect.iscoroutine(res):
        asyncio.run(asyncio.wait_for(res, 8.0))
    return res


def call_through_manager(mgr, pid, rt):
    """经 manager 的真实调用路径跑一遍：目录 mod 会套门面 + 超时围栏。"""
    inst = mgr._plugins.get(pid)
    errors = []
    for hook, _ in HOOK_CASES:
        if getattr(type(inst), hook, None) is None:
            continue
        try:
            mgr._call_mod_hook(inst, hook, lambda *a, _h=hook, _i=inst: run_hook(_i, _h, *a), rt)
        except Exception as exc:
            text = f"{hook}: {type(exc).__name__}: {exc}"
            errors.append(text)
    return errors


def fresh(name: str) -> Path:
    d = TMP / name
    if d.exists():
        shutil.rmtree(d)
    (d / "custom_plugins").mkdir(parents=True)
    return d


def install_one(cp: Path, e: dict) -> None:
    if e["channel"] == "mod":
        shutil.copytree(ROOT / "packs" / e["pack_id"], cp / e["pack_id"])
    else:
        shutil.copy2(ROOT / "overrides" / f"{e['id']}.py", cp / f"{e['id']}.py")


def round_a() -> list[dict]:
    results = []
    for e in INDEX["plugins"]:
        d = fresh(f"a_{e['pack_id']}")
        install_one(d / "custom_plugins", e)
        mgr = PluginManager(d)
        inst = mgr._plugins.get(e["id"])
        problems = []
        if inst is None:
            problems.append(f"未挂载（refusals={mgr._mod_refusals} "
                            f"last_error={getattr(mgr, '_last_import_error', None)}）")
        else:
            is_mod = mgr._is_mod(inst)
            if e["channel"] == "mod" and not is_mod:
                problems.append("判定为目录 mod，实际走的不是目录 mod 通道")
            if e["channel"] == "override" and is_mod:
                problems.append("判定为裸 .py，实际被当成目录 mod 加载")
            if is_mod and e["pack_id"] not in mgr._mod_plugins.values():
                problems.append("manager 的 mod 记账里没有这个包")
            problems += call_through_manager(mgr, e["id"], LiveRuntime())
        results.append({"pack": e["pack_id"], "channel": e["channel"], "problems": problems})
    return results


def round_b() -> dict:
    d = fresh("b_all")
    cp = d / "custom_plugins"
    for e in INDEX["plugins"]:
        install_one(cp, e)
    t0 = time.perf_counter()
    mgr = PluginManager(d)
    elapsed = time.perf_counter() - t0
    missing = [e["id"] for e in INDEX["plugins"] if e["id"] not in mgr._plugins]
    wrong_channel = []
    for e in INDEX["plugins"]:
        inst = mgr._plugins.get(e["id"])
        if inst is None:
            continue
        if bool(mgr._is_mod(inst)) != (e["channel"] == "mod"):
            wrong_channel.append(e["id"])
    return {
        "mounted": len(mgr._plugins),
        "expected": len(INDEX["plugins"]),
        "missing": missing,
        "wrong_channel": wrong_channel,
        "refusals": dict(mgr._mod_refusals),
        "problems": list(getattr(mgr, "_load_problems", []) or []),
        "last_import_error": getattr(mgr, "_last_import_error", None),
        "mod_plugins": dict(mgr._mod_plugins),
        "load_seconds": round(elapsed, 2),
    }


def round_d() -> list[dict]:
    out = []
    host_version = (HOST / "version.txt").read_text(encoding="utf-8").strip()
    for e in INDEX["plugins"]:
        if e["channel"] != "mod":
            continue
        pack_dir = ROOT / "packs" / e["pack_id"]
        info = plugin_packs.inspect_dir(pack_dir, host_version_text=host_version)
        errs = [i for i in info.get("issues", []) if i.get("level") == "error"]
        out.append({"pack": e["pack_id"], "ok": info.get("ok"), "errors": errs,
                    "issues": info.get("issues", [])})
    return out


if __name__ == "__main__":
    t0 = time.perf_counter()
    a = round_a()
    bad = [r for r in a if r["problems"]]
    print(f"=== A 逐包隔离: {len(a)} 个包，有问题 {len(bad)} 个 ===")
    for r in bad:
        print(f"  {r['pack']} [{r['channel']}]")
        for p in r["problems"]:
            print(f"    - {p}")

    b = round_b()
    print(f"\n=== B 全量共存: mounted={b['mounted']}/{b['expected']} "
          f"（{b['load_seconds']}s）===")
    print(f"  missing={b['missing']}")
    print(f"  wrong_channel={b['wrong_channel']}")
    print(f"  refusals={b['refusals']}")
    print(f"  last_import_error={b['last_import_error']!r}")
    for p in b["problems"]:
        print(f"  load_problem: {p}")

    d = round_d()
    dbad = [r for r in d if not r["ok"]]
    print(f"\n=== D 清单校验: {len(d)} 个目录包，不合格 {len(dbad)} 个 ===")
    for r in dbad:
        print(f"  {r['pack']}: {r['errors']}")

    report = {"per_pack": a, "all": b, "manifests": d,
              "elapsed": round(time.perf_counter() - t0, 1)}
    (TMP / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = not bad and not b["missing"] and not b["wrong_channel"] and not dbad
    print(f"\n总耗时 {report['elapsed']}s，结论：{'通过' if ok else '有问题，见上'}")
    sys.exit(0 if ok else 1)
