# dsh-heart-qq 心情系统插件包（QQ 控制台）

把「心情系统」装进 WhaleGirlQQ（QQ 控制台）：14 项情绪数值、模式开关、睡眠闸门、
五维滑杆，外加一套会随对话变化、并注入到 AI 提示词里的情绪状态。

控制台标签栏会多出一个「🫀 心情」页，面板就嵌在那里；单独打开 `http://127.0.0.1:8090/heart` 也能用。

---

## 目录结构

```
heart/
├─ install.py                安装 / 卸载器（默认只预演）
├─ verify.py                 只读校验器（装完/出问题时跑一下）
├─ README.md                 本文件
├─ dsh-heart-qq-0.1.0.zip    整个目录的压缩分发件（内容与本目录一致）
├─ dsh-heart-qq/             插件包本体 → 装进 custom_plugins/
│  ├─ plugin.json            清单（id=dsh-heart-qq，目录名必须一致）
│  ├─ heart_qq.py            入口：引擎 + 钩子 + 面板接口
│  ├─ web/heart.html         面板页面（由宿主路由发给浏览器）
│  └─ README.md              插件自身的说明（数值规则、钩子行为）
└─ host/
   └─ heart_api.py           宿主新增模块 → 装进 src/heart_api.py
```

## 为什么要改宿主

插件层**没有**注册 HTTP 路由的钩子（`register_tool` 注册的是 AI 工具，不是路由），
所以面板的 `/heart` 与 `/api/heart/*` 只能由宿主提供。`install.py` 会做四件事：

| # | 目标 | 改动 |
|---|------|------|
| 1 | `data/qq-only/custom_plugins/dsh-heart-qq/` | 整个插件目录拷进去（目录包不需要登记 `custom_plugins.json`） |
| 2 | `src/heart_api.py` | 新增模块：发面板页 + 转发动作，自带本机访问校验与 `x-dsh-heart` 头防跨站 |
| 3 | `src/qq_app.py` | 在 `install_log_routes(app)` 之后插 3 行，装配上面的路由 |
| 4 | `src/web/static/qq.html` + `qq.js` | 标签栏第 6 个按钮、`tab-heart` 面板（iframe）、插件页入口、懒加载与重载逻辑 |

不打第 3、4 步插件照样算数值、照样注入提示词，只是没有面板。

## 安装

```bash
cd qqplugin/heart

# 1. 先预演，看清楚要动哪些文件（不写盘）
python install.py

# 2. 确认后真装
python install.py --apply

# 3. 重启控制台
cd D:/qq机器人5.0 && .venv-qq/Scripts/python.exe qq_main.py
```

打开 `http://127.0.0.1:8090/`，点标签栏的「🫀 心情」。

### 参数

| 参数 | 作用 |
|------|------|
| （无） | 预演，只打印计划 |
| `--apply` | 真写盘 |
| `--overwrite` | 覆盖已存在的插件目录（整个挪成 `.bak-dsh-heart-<8位>`） |
| `--uninstall` | 反向卸载：删插件目录、删 `src/heart_api.py`、回滚三处静态文件 |
| `--dir <路径>` | 指定 `custom_plugins` 目录（默认问控制台 `GET /api/plugins/custom`） |
| `--host-dir <路径>` | 指定宿主源码根（默认由插件库位置反推） |
| `--url <地址>` | 控制台地址，默认 `http://127.0.0.1:8090` |
