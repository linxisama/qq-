# QQ 工作台插件包索引

宿主版本 `5.2.112`，共 **66** 个独立插件包：目录 mod **32** 个、裸 .py 覆盖 **34** 个。
其中与内置同名的 63 个，宿主默认不加载的 3 个。

## 目录 mod 包（`packs/`）

整目录复制进 `custom_plugins/` 即挂载；入口保留原 `META.id`，挂载后顶替内置实现。

| 包 id | 插件 id | 名称 | 分类 | 默认启用 | 钩子 |
| --- | --- | --- | --- | --- | --- |
| `pack_ambient_reply` | `ambient_reply` | 群聊随机接话 | social | 是 | wants_reply |
| `pack_anti_repeat` | `anti_repeat` | 打断复读 | rhythm | 是 | on_block |
| `pack_archive_isolation` | `archive_isolation` | 人设存档隔离 | utility | 是 | — |
| `pack_at_mention` | `at_mention` | @群友（按名字） | message | 否 | on_ingest, on_block, on_pre_ai, on_post_reply |
| `pack_audio_assets_config` | `audio_assets_config` | 音频素材与路由 | voice | 否 | validate_settings |
| `pack_burst_merge` | `burst_merge` | 连发合并 | rhythm | 是 | on_pre_ai |
| `pack_chatter_guard` | `chatter_guard` | 水聊免回 | message | 否 | on_block |
| `pack_context_chime` | `context_chime` | 上下文插话判定 | message | 否 | on_pre_ai, on_pre_ai_async |
| `pack_early_finish` | `early_finish` | 提前收尾（省 token） | utility | 否 | on_sent |
| `pack_emotion_state` | `emotion_state` | 鲸鱼娘情绪与精力 | social | 是 | on_ingest, on_pre_ai, on_sent |
| `pack_face_decode` | `face_decode` | QQ表情转译 | utility | 是 | on_pre_ai |
| `pack_keyword_reply` | `keyword_reply` | 关键词自动回复 | utility | 否 | validate_settings, on_ingest |
| `pack_local_agent_control` | `local_agent_control` | 本地电脑操作 | agent | 否 | on_ingest |
| `pack_member_aliases` | `member_aliases` | 群友外号对照 | knowledge | 否 | on_pre_ai, on_ingest |
| `pack_mention_gate` | `mention_gate` | 点名闸门 | message | 是 | post_load, on_block, on_pre_ai |
| `pack_mention_nudge_guard` | `mention_nudge_guard` | 重复艾特忽略 | rhythm | 是 | on_pre_ai |
| `pack_poke_counter` | `poke_counter` | 戳一戳统计 | utility | 否 | on_ingest |
| `pack_question_relay` | `question_relay` | 问号接龙 | social | 否 | on_ingest |
| `pack_quote_reply` | `quote_reply` | 引用规范 | style | 是 | on_pre_ai |
| `pack_repeat_echo` | `repeat_echo` | 群聊复读机 | social | 否 | on_ingest |
| `pack_reply_guards` | `reply_guards` | 复读接梗 | social | 否 | on_pre_ai |
| `pack_send_pacing` | `send_pacing` | 打字速度 | rhythm | 否 | on_post_reply |
| `pack_sleep_mode` | `sleep_mode` | 睡眠时段 | rhythm | 否 | on_block |
| `pack_speech_to_text_qq` | `speech_to_text_qq` | 语音转文字（QQ 原生） | media | 否 | on_prepare, on_pre_ai |
| `pack_sticker_admin` | `sticker_admin` | 表情包管理 | media | 是 | — |
| `pack_sticker_cap` | `sticker_cap` | 表情包库上限 | media | 否 | on_ingest, tick |
| `pack_sticker_memory` | `sticker_memory` | 表情包识别记忆 | media | 是 | — |
| `pack_token_saver` | `token_saver` | Token 节流 | utility | 是 | on_pre_ai |
| `pack_turn_complete` | `turn_complete` | 对话完成判定 | message | 否 | on_pre_ai |
| `pack_typing_indicator` | `typing_indicator` | 正在输入提示 | utility | 否 | on_pre_ai |
| `pack_typo_sim` | `typo_sim` | 打字错误模拟 | personality | 否 | on_post_reply |
| `pack_voice_reply` | `voice_reply` | 自动语音 | voice | 否 | on_pre_ai, on_post_reply |

## 裸 .py 覆盖包（`overrides/`）

这些插件在钩子里直接读宿主 `runtime` 的成员（`mode`/`db`/`account`/`onebot`/`ai`/…），目录 mod 通道只给只读门面 `ModRuntime`，一调用就 `AttributeError`；因此必须以单文件形式放进 `custom_plugins/<插件 id>.py`，走同名覆盖通道拿活的 `QQRuntime`。

| 插件 id | 名称 | 分类 | 默认启用 | 走覆盖通道的原因 |
| --- | --- | --- | --- | --- |
| `addressee_guard` | 点名判定 | intelligence | 是 | 钩子直接读宿主 runtime.config |
| `affinity` | 群友好感度 | social | 否 | 钩子直接读宿主 runtime.account/runtime.db/runtime.mode |
| `affinity_proactive` | 好感度主动开话题 | utility | 否 | 钩子直接读宿主 runtime.has_plugin_outgoing/runtime.onebot/runtime.queue_plugin_outgoing |
| `cache_stability` | 缓存稳定性 | utility | 否 | 钩子直接读宿主 runtime.style |
| `chat_controls` | 群聊上下文与回复控制 | rhythm | 是 | 钩子直接读宿主 runtime.account/runtime.db/runtime.mode；调用了宿主 chat_state.scope_of()，它内部读 runtime.mode / runtime.account() / runtime.plugins |
| `conversation_memory` | 长期记忆与群友档案 | utility | 是 | 钩子直接读宿主 runtime.db；调用了宿主 chat_state.scope_of()，它内部读 runtime.mode / runtime.account() / runtime.plugins |
| `cross_chat_link` | 跨会话认人 | social | 是 | 钩子直接读宿主 runtime.account/runtime.db/runtime.mode；调用了宿主 chat_state.scope_of()，它内部读 runtime.mode / runtime.account() / runtime.plugins |
| `emoji_echo` | 跟着贴表情 | social | 否 | 钩子直接读宿主 runtime.account/runtime.mode/runtime.onebot/runtime.running；钩子里 await sleep，超过目录 mod 的 2 秒围栏就会被整钩子跳过 |
| `forward_summary` | 合并转发阅读与总结 | media | 是 | 钩子直接读宿主 runtime.mode |
| `group_cost_report` | 群友花费统计 | utility | 否 | 钩子直接读宿主 runtime.account/runtime.db/runtime.mode |
| `hot_trend_tracker` | 热梗与热点收集 | utility | 是 | 钩子里联网读网页，单次超时预算可达 4~6 秒，超过目录 mod 的 2 秒围栏 |
| `icebreaker` | 定时暖场 | utility | 否 | 钩子直接读宿主 runtime.ai_lock/runtime.can_send_proactive/runtime.has_plugin_outgoing/runtime.last_interaction/runtime.onebot/runtime.queue_plugin_outgoing/runtime.recent_chats/runtime.style |
| `image_library` | 表情包与自定义图库 | media | 是 | 钩子直接读宿主 runtime.mode |
| `image_understanding` | 图片与表情包识别 | utility | 是 | 钩子直接读宿主 runtime.ai/runtime.bridge/runtime.mode/runtime.onebot |
| `long_image_reader` | 长图分段阅读 | media | 是 | 钩子直接读宿主 runtime.ai/runtime.bridge/runtime.mode/runtime.onebot |
| `market_probe` | 市场探针 | utility | 否 | 钩子直接读宿主 runtime.plugins；钩子里联网读网页，单次超时预算可达 4~6 秒，超过目录 mod 的 2 秒围栏 |
| `memes` | 表情包制作（NoneBot 适配） | media | 是 | 钩子直接读宿主 runtime.bridge/runtime.mode/runtime.onebot |
| `minimal_mode` | 极简模式（省 token） | utility | 否 | 钩子直接读宿主 runtime.plugins |
| `msg_reaction` | 消息表情回应 | social | 否 | 钩子直接读宿主 runtime.ai/runtime.ai_lock/runtime.mode/runtime.onebot/runtime.running |
| `pc_control` | 机器人控制台管理 | utility | 否 | 钩子直接读宿主 runtime.account/runtime.ai/runtime.config/runtime.db/runtime.mode/runtime.pc/runtime.plugins/runtime.set_persona/runtime.style |
| `pixiv_illust` | Pixiv 插图 | media | 否 | 钩子直接读宿主 runtime.mode；钩子里联网读网页，单次超时预算可达 4~6 秒，超过目录 mod 的 2 秒围栏 |
| `proactive_chat` | 指定群主动开话题 | social | 否 | 钩子直接读宿主 runtime.ai/runtime.ai_lock/runtime.can_send_proactive/runtime.db/runtime.has_plugin_outgoing/runtime.last_interaction/runtime.mode/runtime.queue_plugin_outgoing/runtime.style；钩子里 await sleep，超过目录 mod 的 2 秒围栏就会被整钩子跳过 |
| `probability_reply` | 戳一戳概率回应 | social | 否 | 钩子直接读宿主 runtime.account/runtime.onebot |
| `qqagent_bridge` | QQ Agent 能力桥 | utility | 否 | 会起 node 子进程，远超目录 mod 的 2 秒钩子超时；且用 __file__ 定位宿主脚本；宿主根定位由 `parents[2]` 改为逐级向上探测，装到 custom_plugins/ 下仍能找到 runtime/qqagent-host |
| `quick_menu` | 功能菜单与B站分享 | utility | 是 | 钩子直接读宿主 runtime.mode/runtime.reply_meta |
| `reply_freshness` | 回复时机与引用 | social | 否 | 钩子直接读宿主 runtime.account/runtime.db/runtime.mode |
| `reply_variety` | 回复多样化（防复读） | rhythm | 是 | 钩子直接读宿主 runtime.account |
| `scheduled_announcer` | 定时消息与文案推送 | social | 否 | 钩子直接读宿主 runtime.ai/runtime.ai_lock/runtime.can_send_proactive/runtime.mode/runtime.outgoing_exists/runtime.queue_outgoing/runtime.running |
| `search_query_hygiene` | 搜索词清理与联网查找 | utility | 是 | 钩子里联网读网页，单次超时预算可达 4~6 秒，超过目录 mod 的 2 秒围栏 |
| `share_card` | 分享卡片与网页解读 | media | 否 | 钩子里联网读网页，单次超时预算可达 4~6 秒，超过目录 mod 的 2 秒围栏 |
| `short_followup` | 短期跟聊 | rhythm | 是 | 钩子直接读宿主 runtime.onebot |
| `silence_ping` | 主动私信 | social | 否 | 钩子直接读宿主 runtime.ai/runtime.ai_lock/runtime.can_send_proactive/runtime.db/runtime.has_plugin_outgoing/runtime.last_interaction/runtime.last_outbound/runtime.queue_plugin_outgoing/runtime.style |
| `sticker_cadence` | 每三次表情 | personality | 否 | 钩子直接读宿主 runtime.reply_meta；调用了宿主 chat_state.scope_of()，它内部读 runtime.mode / runtime.account() / runtime.plugins |
| `sticker_steal` | 偷表情包与本地收藏 | media | 否 | 钩子直接读宿主 runtime.plugins |

## 做过源码补丁的包

- `qqagent_bridge`：会起 node 子进程，远超目录 mod 的 2 秒钩子超时；且用 __file__ 定位宿主脚本；宿主根定位由 `parents[2]` 改为逐级向上探测，装到 custom_plugins/ 下仍能找到 runtime/qqagent-host
