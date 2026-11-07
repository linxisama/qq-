"""dsh-heart-qq — 心情系统（QQ 控制台版）。

移植自 D:/插件/dsh-heart：数值引擎 + 提示词注入 + 网页面板三件套。
目录 mod 的 entry 只能是单个 .py（兄弟模块无法按包导入），所以全部写在这里。

数值只是"这一轮说话的脸色"，不改人设、不改事实、不推掉该做的事。
"""

from __future__ import annotations

import json
import math
import os
import threading
import time

from . import FieldSchema, PluginBase, PluginMeta

STATE_VERSION = 1
MAX_DEFAULT = 100.0
MAX_MSG_DELTA = 8.0

# ── 数值表 ───────────────────────────────────────────────────────────────────
# tiers 从高到低，命中第一个 value >= min 的档。
GAUGES = [
    {"key": "happy", "label": "开心", "base": 30.0, "rate": 0.25, "group": "core",
     "tiers": [(80, "极度开心"), (60, "开心"), (40, "平静"), (20, "有点闷"), (0, "低落")]},
    {"key": "excited", "label": "兴奋", "base": 12.0, "rate": 0.5, "group": "core",
     "tiers": [(80, "亢奋"), (55, "兴奋"), (30, "有点来劲"), (0, "平静")]},
    {"key": "anger", "label": "愤怒", "base": 4.0, "rate": 0.6, "group": "core",
     "tiers": [(80, "暴怒"), (55, "生气"), (30, "有点烦"), (0, "平静")]},
    {"key": "jealous", "label": "吃醋", "base": 4.0, "rate": 0.4, "group": "core",
     "tiers": [(70, "醋劲很大"), (40, "吃醋"), (10, "有点吃醋"), (0, "平静")]},
    {"key": "sad", "label": "难过", "base": 6.0, "rate": 0.3, "group": "core",
     "tiers": [(70, "很不好受"), (40, "低落"), (15, "有点闷"), (0, "平静")]},
    {"key": "affection", "label": "情爱值", "base": 20.0, "rate": 0.2, "group": "love",
     "tiers": [(80, "满溢"), (50, "有点黏"), (20, "平静"), (0, "淡")]},
    {"key": "libido", "label": "性欲值", "base": 8.0, "rate": 0.25, "group": "lust",
     "tiers": [(80, "压不住"), (50, "有点想"), (10, "平静"), (0, "淡")]},
    {"key": "lust", "label": "色色兴奋", "base": 4.0, "rate": 0.3, "group": "lust",
     "tiers": [(95, "临界"), (70, "上头"), (35, "有点"), (0, "平静")]},
    {"key": "quarrel", "label": "吵架速度", "base": 0.0, "rate": 0.5, "group": "core",
     "tiers": [(70, "一点就着"), (40, "火气在"), (15, "有点冲"), (0, "平静")]},
    {"key": "angerCh", "label": "愤怒(通道)", "base": 0.0, "rate": 0.8, "group": "core", "max": 120.0,
     "tiers": [(100, "堵死"), (60, "憋着"), (25, "有点堵"), (0, "平静")]},
    {"key": "fatigue", "label": "疲劳", "base": 10.0, "rate": 0.35, "group": "body",
     "tiers": [(80, "撑不住"), (55, "累了"), (25, "有点累"), (0, "正常")]},
    {"key": "depress", "label": "抑郁", "base": 5.0, "rate": 0.15, "group": "core",
     "tiers": [(70, "压得很低"), (40, "持续"), (15, "有点沉"), (0, "平稳")]},
    {"key": "satisfy", "label": "满足感", "base": 30.0, "rate": 0.2, "group": "core",
     "tiers": [(80, "很满足"), (50, "满足"), (5, "有点满足"), (0, "没有")]},
    {"key": "desire", "label": "欲望", "base": 10.0, "rate": 0.25, "group": "lust",
     "tiers": [(80, "很想要"), (50, "想要"), (20, "有点想要"), (0, "没什么想法")]},
]

GAUGE_MAP = {g["key"]: g for g in GAUGES}
DIMENSIONS = ["happy", "excited", "anger", "sad", "fatigue"]
MODE_DEFS = [
    {"key": "master", "label": "总开关"},
    {"key": "emotion", "label": "情绪mod"},
    {"key": "cold", "label": "冷落mod"},
    {"key": "love", "label": "情爱mod"},
    {"key": "lust", "label": "性欲mod"},
]

WAKE_WORDS = ["叫醒", "醒醒", "起床", "别睡了", "喊醒", "在吗", "人呢"]
POSITIVE = ["谢谢", "喜欢你", "可爱", "辛苦", "摸摸", "抱抱", "好棒", "厉害", "爱你", "乖"]
NEGATIVE = ["讨厌你", "闭嘴", "滚开", "笨蛋", "垃圾", "废物", "傻子", "烦死"]
FLIRT = ["亲亲", "抱我", "想你了", "老婆", "老公", "撩", "色色", "涩涩"]
APOLOGY = ["对不起", "抱歉", "不好意思"]
COLD = ["随便", "算了", "不想说", "别管我", "无所谓"]


# ── 纯函数引擎 ───────────────────────────────────────────────────────────────
def _num(value, default):
    try:
        n = float(value)
    except Exception:
        return default
    return n if math.isfinite(n) else default


def _clamp(value, mx=MAX_DEFAULT):
    n = _num(value, 0.0)
    return min(float(mx), max(0.0, n))


def _round1(value):
    return round(_num(value, 0.0) * 10) / 10.0


def _gauge(key):
    return GAUGE_MAP.get(key)


def _hits(text, words):
    return sum(1 for w in words if w in text)


def default_state(now=None):
    now = time.time() if now is None else now
    return {
        "v": STATE_VERSION,
        "at": now,
        "lastDecayAt": now,
        "values": {g["key"]: g["base"] for g in GAUGES},
        "modes": {"master": True, "emotion": True, "cold": False, "love": True, "lust": True},
        "sleep": {"state": "awake", "since": now},
        "paused": False,
        "busy": {"text": "", "since": 0.0},
        "health": {"perWeek": 2, "intercept": False},
        "gates": {"fatigue": True},
        "counters": {"turns": 0, "errors": 0},
    }


def normalize_state(raw, now=None):
    now = time.time() if now is None else now
    state = default_state(now)
    if not isinstance(raw, dict):
        return state

    values = raw.get("values") if isinstance(raw.get("values"), dict) else {}
    for g in GAUGES:
        if g["key"] in values:
            state["values"][g["key"]] = _round1(_clamp(values[g["key"]], g.get("max", MAX_DEFAULT)))

    modes = raw.get("modes") if isinstance(raw.get("modes"), dict) else {}
    for key in state["modes"]:
        if key in modes:
            state["modes"][key] = bool(modes[key])

    gates = raw.get("gates") if isinstance(raw.get("gates"), dict) else {}
    for key in state["gates"]:
        if key in gates:
            state["gates"][key] = bool(gates[key])

    sleep = raw.get("sleep") if isinstance(raw.get("sleep"), dict) else {}
    if sleep.get("state") == "sleeping":
        state["sleep"] = {"state": "sleeping", "since": _num(sleep.get("since"), now)}

    state["paused"] = bool(raw.get("paused"))

    busy = raw.get("busy") if isinstance(raw.get("busy"), dict) else {}
    state["busy"] = {"text": str(busy.get("text") or "")[:40], "since": _num(busy.get("since"), 0.0)}

    health = raw.get("health") if isinstance(raw.get("health"), dict) else {}
    state["health"] = {
        "perWeek": int(_num(health.get("perWeek"), 2)),
        "intercept": bool(health.get("intercept")),
    }

    counters = raw.get("counters") if isinstance(raw.get("counters"), dict) else {}
    state["counters"] = {
        "turns": int(_num(counters.get("turns"), 0)),
        "errors": int(_num(counters.get("errors"), 0)),
    }

    state["at"] = _num(raw.get("at"), now)
    state["lastDecayAt"] = _num(raw.get("lastDecayAt"), now)
    return state


def tier_of(gauge, value):
    for minimum, label in gauge["tiers"]:
        if value >= minimum:
            return {"min": minimum, "label": label}
    last = gauge["tiers"][-1]
    return {"min": last[0], "label": last[1]}


def minutes_to_tier(gauge, value):
    """距离掉到下一档还有几分钟；已经在基线上或没有下一档时返回 None。"""
    if value <= gauge["base"]:
        return None
    nxt = None
    for minimum, _label in gauge["tiers"]:
        if minimum < value:
            nxt = minimum
            break
    if nxt is None:
        return None
    minutes = (value - nxt) / gauge["rate"] if gauge["rate"] > 0 else 0.0
    if not math.isfinite(minutes) or minutes <= 0:
        return None
    return max(1, int(round(minutes)))


def decay(state, now=None):
    now = time.time() if now is None else now
    last = _num(state.get("lastDecayAt"), now)
    dt_min = max(0.0, (now - last) / 60.0)
    state["lastDecayAt"] = now
    if dt_min <= 0:
        return state

    asleep = (state.get("sleep") or {}).get("state") == "sleeping"
    for g in GAUGES:
        key = g["key"]
        rate = g["rate"] * 6 if (key == "fatigue" and asleep) else g["rate"]
        step = rate * dt_min
        cur = _num((state["values"] or {}).get(key), g["base"])
        if cur > g["base"]:
            nxt = max(g["base"], cur - step)
        else:
            nxt = min(g["base"], cur + step)
        state["values"][key] = _round1(_clamp(nxt, g.get("max", MAX_DEFAULT)))
    state["at"] = now
    return state


def _add(state, key, delta):
    gauge = _gauge(key)
    if gauge is None or not math.isfinite(_num(delta, float("nan"))) or delta == 0:
        return
    cur = _num((state["values"] or {}).get(key), 0.0)
    state["values"][key] = _round1(_clamp(cur + delta, gauge.get("max", MAX_DEFAULT)))


def judge_user(state, text, now=None):
    now = time.time() if now is None else now
    text = str(text or "")
    if not text:
        return state

    def cap(n):
        return min(MAX_MSG_DELTA, n)

    pos = _hits(text, POSITIVE)
    if pos:
        _add(state, "happy", cap(pos * 2))
        _add(state, "satisfy", cap(pos * 1.5))
        _add(state, "anger", -cap(pos))
        _add(state, "sad", -cap(pos))
    neg = _hits(text, NEGATIVE)
    if neg:
        _add(state, "anger", cap(neg * 3))
        _add(state, "quarrel", cap(neg * 2))
        _add(state, "angerCh", cap(neg * 2))
        _add(state, "happy", -cap(neg * 2))
        _add(state, "sad", cap(neg * 2))
    flirt = _hits(text, FLIRT)
    if flirt:
        _add(state, "affection", cap(flirt * 3))
        _add(state, "libido", cap(flirt * 2))
        _add(state, "lust", cap(flirt * 1.5))
    if _hits(text, APOLOGY):
        _add(state, "anger", -3)
        _add(state, "sad", -1)
        _add(state, "quarrel", -2)
    if _hits(text, COLD):
        _add(state, "sad", 2)
        _add(state, "quarrel", 1)

    _add(state, "fatigue", 0.15)
    state["counters"]["turns"] = int(_num((state.get("counters") or {}).get("turns"), 0)) + 1
    state["at"] = now
    return state


def judge_assistant(state, text, now=None):
    now = time.time() if now is None else now
    text = str(text or "")
    if not text:
        return state
    _add(state, "fatigue", 0.1)
    if len(text) > 600:
        _add(state, "fatigue", 0.1)
    state["at"] = now
    return state


def judge_error(state, now=None):
    now = time.time() if now is None else now
    _add(state, "angerCh", 3)
    _add(state, "anger", 1)
    _add(state, "fatigue", 0.5)
    state["counters"]["errors"] = int(_num((state.get("counters") or {}).get("errors"), 0)) + 1
    state["at"] = now
    return state


def set_value(state, key, value, now=None):
    now = time.time() if now is None else now
    gauge = _gauge(key)
    if gauge is None:
        return False
    state["values"][key] = _round1(_clamp(value, gauge.get("max", MAX_DEFAULT)))
    state["at"] = now
    return True


def set_mode(state, key, on, now=None):
    now = time.time() if now is None else now
    if key not in (state.get("modes") or {}):
        return False
    state["modes"][key] = bool(on)
    state["at"] = now
    return True


def set_sleep(state, action, now=None):
    now = time.time() if now is None else now
    if action == "sleep":
        state["sleep"] = {"state": "sleeping", "since": now}
    elif action == "wake":
        state["sleep"] = {"state": "awake", "since": now}
        state["paused"] = False
    elif action == "pause":
        state["paused"] = True
    elif action == "resume":
        state["paused"] = False
    else:
        return False
    state["at"] = now
    return True


def set_busy(state, text, now=None):
    now = time.time() if now is None else now
    state["busy"] = {"text": str(text or "")[:40], "since": now}
    state["at"] = now
    return True


TIME_SLOTS = [
    ("dawn", "夜里", 1),
    ("morning", "早上", 5),
    ("forenoon", "上午", 9),
    ("noon", "中午", 11),
    ("afternoon", "下午", 13),
    ("dusk", "傍晚", 17),
    ("evening", "晚上", 19),
    ("late", "深夜", 23),
]


def time_of_day(now=None):
    now = time.time() if now is None else now
    hour = time.localtime(now).tm_hour
    key, label = TIME_SLOTS[0][0], TIME_SLOTS[0][1]
    for slot_key, slot_label, start in TIME_SLOTS:
        if hour >= start:
            key, label = slot_key, slot_label
    return {"hour": hour, "label": label, "key": key,
            "text": "此刻 " + str(hour) + " 点 · " + label}


def active_tiers(state):
    """明显偏离常态的几项，按数值降序。刚离开基线的档不算。"""
    out = []
    values = state.get("values") or {}
    for g in GAUGES:
        value = _num(values.get(g["key"]), g["base"])
        if value < g["base"]:
            continue
        tier = tier_of(g, value)
        if tier["min"] <= g["base"]:
            continue
        out.append({"key": g["key"], "label": g["label"], "tier": tier["label"],
                    "value": _round1(value), "min": tier["min"]})
    out.sort(key=lambda item: item["value"], reverse=True)
    return out


def derive(state, now=None):
    now = time.time() if now is None else now
    values = state.get("values") or {}
    gauges = []
    for g in GAUGES:
        value = _round1(_num(values.get(g["key"]), g["base"]))
        gauge = {
            "key": g["key"], "label": g["label"], "value": value,
            "max": g.get("max", MAX_DEFAULT), "base": g["base"], "group": g["group"],
            "tier": tier_of(g, value)["label"],
            "eta": minutes_to_tier(g, value),
        }
        gauges.append(gauge)
    modes = state.get("modes") or {}
    return {
        "gauges": gauges,
        "dimensions": [next((item for item in gauges if item["key"] == key), None) for key in DIMENSIONS],
        "modes": [{"key": d["key"], "label": d["label"], "on": bool(modes.get(d["key"]))} for d in MODE_DEFS],
        "sleep": state.get("sleep") or {"state": "awake", "since": now},
        "paused": bool(state.get("paused")),
        "busy": state.get("busy") or {"text": "", "since": 0},
        "health": state.get("health") or {"perWeek": 2, "intercept": False},
        "gates": state.get("gates") or {"fatigue": True},
        "counters": state.get("counters") or {"turns": 0, "errors": 0},
        "clock": time_of_day(now),
    }


# ── 提示词两段 ───────────────────────────────────────────────────────────────
# 静态在前、动态在后：服务商按前缀缓存计费，动态段每轮都变，只能排在最后。
HEART_RULE = "\n".join([
    "## 心情",
    "",
    "你有一组 0~100 的数值，它们只决定这一轮说话的**脸色**，不改变立场、事实和该做的事。",
    "优先级：**用户此刻的真实需求 > 你的人设 > 心情**。",
    "",
    "**怎么表现**：写进措辞、句子长短、标点、愿不愿意多说一句；一段里透出一处就够，有情绪就直接上来，不用先声明“我现在有点……”。",
    "**禁止**：不报分值、不解释自己的心情；不把负面情绪变成对用户的态度问题（事照办、错照认、信息给全）；不拿它推掉该做的事；别给自己编一个心情的来由。",
    "**数值**由用户的话、你的回复、工具报错小幅推动，没人说话时慢慢回落到常态 —— 攒够才看得出来。",
])


def render_heart(state, now=None):
    """动态段。每轮都要重发，所以尽量短。"""
    now = time.time() if now is None else now
    lines = []
    clock = time_of_day(now)

    if state.get("paused"):
        return "## 当前心情\n**心情暂停中。** 这一轮按平常的样子说话，不用表现任何情绪。"

    if (state.get("sleep") or {}).get("state") == "sleeping":
        return "## 当前心情\n**你睡着了。** 除非被叫醒，不要主动开口、不要展开话题；被叫到就含糊地应一声。"

    if (state.get("modes") or {}).get("master") is False:
        return "## 当前心情\n心情系统总开关是关的 —— 这一轮不用表现情绪，按常态说话。"

    act = active_tiers(state)
    lines.append("## 当前心情（" + clock["text"] + "）")

    if not act:
        lines.append("现在是常态 —— 平静地说话，不用刻意带情绪。")
    else:
        top = act[:4]
        lines.append("明显的几处：" + "、".join(item["label"] + "（" + item["tier"] + "）" for item in top) + "。")
        if len(top) > 1:
            lines.append("以「" + top[0]["label"] + "」为主，其余只是点缀。")

    gates = state.get("gates") or {}
    fatigue = (state.get("values") or {}).get("fatigue") or 0
    if gates.get("fatigue") and fatigue >= 55:
        lines.append("**很累**：句子短、少追问、别起新话题，但该干的活照干。")

    modes = state.get("modes") or {}
    extra = []
    if modes.get("cold"):
        extra.append("冷落模式：话少、别主动找话题。")
    if modes.get("love"):
        extra.append("情爱模式：可以更亲近，记得对方说过的小事。")
    if modes.get("lust"):
        extra.append("性欲模式：亲密话题可以接，但不硬推。")
    if extra:
        lines.append("".join(extra))

    busy = state.get("busy") or {}
    if busy.get("text"):
        lines.append("在忙：" + str(busy["text"]) + "（可以透出一点分神，别当借口）。")

    return "\n".join(lines)


# ── 插件本体 ─────────────────────────────────────────────────────────────────
STATE_NAME = "state.json"


class HeartPlugin(PluginBase):
    META = PluginMeta(
        id="dsh_heart",
        name="心情系统（dsh-heart）",
        description="一组会自己回落的情绪数值，按数值改说话的脸色；带网页面板 /heart。",
        category="social",
        enabled_by_default=True,
        config_schema={
            "enabled": FieldSchema(type="bool", label="启用"),
            "injectPrompt": FieldSchema(type="bool", label="注入提示词",
                                        description="关掉后不再影响回复，只保留面板数值"),
            "panel": FieldSchema(type="bool", label="网页面板", description="/heart 页面可用"),
        },
        default_settings={"enabled": True, "injectPrompt": True, "panel": True},
    )

    def __init__(self, manager):
        super().__init__(manager)
        self._lock = threading.Lock()
        self._state = None
        self._dirty = False

    # ── 存档 ──
    def _path(self):
        return self.state_file(STATE_NAME)

    def _load(self):
        if self._state is None:
            raw = self.load_state(STATE_NAME, None)
            self._state = normalize_state(raw if isinstance(raw, dict) else None)
        return self._state

    def _save(self):
        data = self._load()
        try:
            path = self._path()
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
            os.replace(tmp, path)
            self._dirty = False
        except Exception as exc:
            print("[dsh_heart] 存档写入失败：" + str(exc))

    # ── 对外：面板与路由用 ──
    def snapshot(self):
        with self._lock:
            state = self._load()
            decay(state)
            return derive(state)

    def apply_action(self, action):
        """面板动作。返回 (ok, error, snapshot)。"""
        act = str((action or {}).get("action") or "")
        with self._lock:
            state = self._load()
            decay(state)
            ok = True
            error = ""
            if act == "value":
                if not set_value(state, str(action.get("key") or ""), action.get("value")):
                    ok, error = False, "unknown gauge"
            elif act == "mode":
                if not set_mode(state, str(action.get("key") or ""), action.get("on")):
                    ok, error = False, "unknown mode"
            elif act == "sleep":
                if not set_sleep(state, str(action.get("act") or "")):
                    ok, error = False, "unknown sleep action"
            elif act == "busy":
                set_busy(state, action.get("text"))
            elif act == "gate":
                key = str(action.get("key") or "")
                if key not in (state.get("gates") or {}):
                    ok, error = False, "unknown gate"
                else:
                    state["gates"][key] = bool(action.get("on"))
            elif act == "cheer":
                for g in GAUGES:
                    mx = g.get("max", MAX_DEFAULT)
                    cur = (state["values"] or {}).get(g["key"], 0) or 0
                    if g["key"] in ("happy", "satisfy", "excited"):
                        set_value(state, g["key"], min(mx, cur + 25))
                    if g["key"] in ("anger", "sad", "fatigue"):
                        set_value(state, g["key"], max(0, cur - 25))
            elif act == "resetAll":
                for g in GAUGES:
                    set_value(state, g["key"], 0)
            else:
                ok, error = False, "unknown action"

            if not ok:
                return False, error, derive(state)
            state["at"] = time.time()
            self._save()
            return True, "", derive(state)

    def status_line(self):
        """/心情 用的短文本。"""
        view = self.snapshot()
        clock = view["clock"]
        parts = [g["label"] + " " + str(int(round(g["value"]))) for g in view["gauges"] if g["value"] != g["base"]]
        head = "🫀 " + clock["text"]
        if view["paused"]:
            return head + "｜心情暂停中"
        if view["sleep"]["state"] == "sleeping":
            return head + "｜睡着了"
        if not parts:
            return head + "｜现在都挺正常"
        return head + "｜" + "、".join(parts[:6])

    # ── 宿主钩子 ──
    def on_ingest(self, message, runtime):
        try:
            text = str(message.get("text") or "").strip()
            if not text:
                return None
            if text in ("/心情", "/heart", "／心情"):
                return self.status_line()
            with self._lock:
                state = self._load()
                if (state.get("sleep") or {}).get("state") == "sleeping":
                    for word in WAKE_WORDS:
                        if word in text:
                            set_sleep(state, "wake")
                            self._save()
                            runtime.note("心情：被叫醒了")
                            break
            return None
        except Exception as exc:
            print("[dsh_heart] on_ingest 失败：" + str(exc))
            return None

    def on_pre_ai(self, message, conversation, runtime):
        try:
            if not self.get("enabled"):
                return None
            text = str(message.get("text") or "")
            with self._lock:
                state = self._load()
                decay(state)
                judge_user(state, text)
                self._save()
                dynamic = render_heart(state, time.time()) if self.get("injectPrompt") else ""
                master = (state.get("modes") or {}).get("master", True)

            if not master or not self.get("injectPrompt"):
                return None
            # 静态规则在前、动态心情在后：服务商按前缀缓存，前缀越稳命中越多。
            hint = {"extra_system": HEART_RULE}
            if dynamic:
                # mod 拿到的是只读门面（没有 runtime.plugins），volatile_hint 会退回
                # extra_system —— 那就接在规则后面，别覆盖掉已经写好的静态段。
                moved = self.volatile_hint(runtime, dynamic) or {}
                if moved.get("volatile_system"):
                    hint["volatile_system"] = moved["volatile_system"]
                elif moved.get("extra_system"):
                    hint["extra_system"] = hint["extra_system"] + "\n\n" + moved["extra_system"]
            return hint
        except Exception as exc:
            print("[dsh_heart] on_pre_ai 失败：" + str(exc))
            return None

    def on_sent(self, message, reply, runtime):
        try:
            if not self.get("enabled"):
                return
            with self._lock:
                state = self._load()
                decay(state)
                judge_assistant(state, str(reply or ""))
                self._save()
        except Exception as exc:
            print("[dsh_heart] on_sent 失败：" + str(exc))

    async def on_after_tool(self, tool_id, arguments, result_value, runtime):
        """工具报错记一笔；永远原样返回结果，不改工具行为。"""
        try:
            bad = False
            if isinstance(result_value, dict):
                if result_value.get("ok") is False or result_value.get("error"):
                    bad = True
            elif isinstance(result_value, str) and result_value.startswith("错误"):
                bad = True
            if bad and self.get("enabled"):
                with self._lock:
                    state = self._load()
                    judge_error(state)
                    self._save()
        except Exception:
            pass
        return result_value

    async def tick(self, runtime):
        try:
            with self._lock:
                state = self._load()
                before = dict(state.get("values") or {})
                decay(state)
                changed = any(abs(before.get(k, 0) - (state["values"] or {}).get(k, 0)) >= 0.05 for k in before)
                if changed:
                    self._save()
        except Exception as exc:
            print("[dsh_heart] tick 失败：" + str(exc))

