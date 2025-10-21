from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

import random
import json
from pathlib import Path
from datetime import datetime

@register("helloworld", "YourName", "一个简单的 Hello World 插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 数据持久化文件：插件同目录 data/xiaosui_state.json
        self._data_dir = Path(__file__).parent / "data"
        self._data_path = self._data_dir / "xiaosui_state.json"
        self._state = {"users": {}}  # { user_id: {"favor": int, "marbles": int, "last_sign": "YYYY-MM-DD"} }

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            if self._data_path.exists():
                self._state = json.loads(self._data_path.read_text(encoding="utf-8"))
                if "users" not in self._state:
                    self._state["users"] = {}
            logger.info("小碎数据已加载")
        except Exception as e:
            logger.error(f"加载数据失败：{e}")

    def _save_state(self):
        try:
            self._data_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"保存数据失败：{e}")

    def _get_user_id(self, event: AstrMessageEvent) -> str:
        """尽量稳妥地拿一个用户唯一标识"""
        for getter in ("get_sender_id", "get_user_id", "get_sender_qq"):
            fn = getattr(event, getter, None)
            if callable(fn):
                try:
                    uid = fn()
                    if uid:
                        return str(uid)
                except Exception:
                    pass
        try:
            sender = getattr(event, "sender", None)
            if sender and hasattr(sender, "id"):
                return str(sender.id)
            if sender and hasattr(sender, "user_id"):
                return str(sender.user_id)
        except Exception:
            pass
        return f"name::{event.get_sender_name()}"


# ---- 已有指令：小碎（保留随机多语气） ----
    @filter.command("小碎")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个 hello world 指令"""
        user_name = event.get_sender_name()
        message_str = event.message_str  # 用户发的纯文本消息字符串
        message_chain = event.get_messages()  # 用户所发的消息的消息链
        logger.info(message_chain)

        replies = [
            f"你好呀，{user_name}，小碎在这里～",
            f"{user_name}，找我有什么事吗？",
            f"在呢在呢～{user_name}，小碎随时待命！",
            f"怎么了吗？",
            f"我在(*'▽'*)♪",
            f"嗨——"
        ]
        yield event.plain_result(random.choice(replies))



    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        self._save_state()
