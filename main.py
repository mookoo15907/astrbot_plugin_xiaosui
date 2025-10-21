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

    def _time_period(self, now: datetime | None = None) -> str:
        """按小时划分时间段：早上/中午/下午/晚上/半夜"""
        h = (now or datetime.now()).hour
        if 5 <= h <= 10:
            return "morning"
        if 11 <= h <= 13:
            return "noon"
        if 14 <= h <= 17:
            return "afternoon"
        if 18 <= h <= 22:
            return "evening"
        return "midnight"  # 23~4


# ==== 固定回复库：添加 / 删除 / 查看（前20条），含三条示例预置 =================

# 在 initialize() 之后的任意位置（类内）补一个确保库存在的小段：
async def initialize(self):
    # 你原本的初始化逻辑……
    try:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        if self._data_path.exists():
            self._state = json.loads(self._data_path.read_text(encoding="utf-8"))
            if "users" not in self._state:
                self._state["users"] = {}
        # >>> 新增：固定回复库的容器
        if "fixed_replies" not in self._state:
            self._state["fixed_replies"] = {}
        # >>> 预置三条示例（可当导入样例；若已存在则跳过）
        seeds = [
            ("好开心", "可以的"),
            ("哈哈", "开心"),
            ("摸摸", "(=^･ω･^=)"),
        ]
        for k, v in seeds:
            self._state["fixed_replies"].setdefault(k, v)
        self._save_state()
        logger.info("固定回复库已就绪（含三条示例种子）。")
    except Exception as e:
        logger.error(f"加载数据失败：{e}")

# 1) 管理员添加：格式 “管理员添加 a to b”
@filter.command("管理员添加")
async def admin_add_fixed(self, event: AstrMessageEvent):
    """
    用法：管理员添加 触发词 to 回复内容
    例：管理员添加 哈哈 to 开心
    """
    text = event.message_str.strip()
    # 去掉命令本身
    payload = text[len("管理员添加"):].strip()
    # 解析 "a to b"（支持全角空格、大小写 to）
    import re
    m = re.match(r"(.+?)\s*[tT][oO]\s*(.+)", payload)
    if not m:
        yield event.plain_result("格式不对呀～请用：管理员添加 触发词 to 回复内容")
        return
    key = m.group(1).strip()
    val = m.group(2).strip()
    if not key or not val:
        yield event.plain_result("触发词或回复内容为空啦～再试试？")
        return

    repo = self._state.setdefault("fixed_replies", {})
    existed = key in repo
    repo[key] = val
    self._save_state()

    total = len(repo)
    action = "更新" if existed else "添加"
    yield event.plain_result(f"✅ 已{action}固定回复：『{key}』 → 『{val}』\n📚 当前条数：{total}")

# 2) 删除：格式 “删除 a”
@filter.command("删除")
async def admin_del_fixed(self, event: AstrMessageEvent):
    """
    用法：删除 触发词
    例：删除 哈哈
    """
    text = event.message_str.strip()
    payload = text[len("删除"):].strip()
    if not payload:
        yield event.plain_result("请提供要删除的触发词：删除 触发词")
        return

    repo = self._state.setdefault("fixed_replies", {})
    if payload in repo:
        val = repo.pop(payload)
        self._save_state()
        yield event.plain_result(f"🗑️ 已删除：『{payload}』 → 『{val}』")
    else:
        yield event.plain_result(f"没找到这个触发词：『{payload}』")

# 3) 查看前20条：格式 “查看固定回复”
@filter.command("查看固定回复")
async def view_fixed_list(self, event: AstrMessageEvent):
    """
    展示当前固定回复库的前20条（按键名排序）
    """
    repo = self._state.setdefault("fixed_replies", {})
    if not repo:
        yield event.plain_result("固定回复库还是空的～可以试试：管理员添加 哈哈 to 开心")
        return

    # 排序后仅取前20条
    items = sorted(repo.items(), key=lambda kv: kv[0])[:20]
    lines = [f"{i+1}. 『{k}』 → 『{v}』" for i, (k, v) in enumerate(items)]
    more = "" if len(repo) <= 20 else f"\n……（共 {len(repo)} 条，已显示前 20 条）"
    # 同时在末尾附上添加示例三条，方便你导入时参考格式
    examples = [
        "管理员添加 好开心 to 可以的",
        "管理员添加 哈哈 to 开心",
        "管理员添加 摸摸 to (=^･ω･^=)",
    ]
    example_block = "\n示例（添加格式）：\n" + "\n".join(f"- {ex}" for ex in examples)

    yield event.plain_result("📚 固定回复（前20条）：\n" + "\n".join(lines) + more + "\n" + example_block)

# （可选）如果你有“群内任意消息入口”，想让任意消息触发固定回复，
# 可在那个入口调用这个小工具函数（不注册为 command，避免崩）：
def _try_fixed_reply_lookup(self, event: AstrMessageEvent):
    """
    若消息文本完全匹配某触发词，则返回一个 plain_result；否则返回 None。
    供你的全局 on_message/默认回调里调用，不会影响现有命令。
    """
    try:
        msg = event.message_str.strip()
        repo = self._state.get("fixed_replies", {})
        if repo and msg in repo:
            return event.plain_result(repo[msg])
    except Exception as e:
        logger.error(f"fixed reply lookup failed: {e}")
    return None




    


    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        self._save_state()
