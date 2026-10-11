"""Independent human approval for one exact MCP preview. No account writes."""

from __future__ import annotations
import sys
import getpass
from qqmusicmcp.safety import SafetyError, describe_preview, approve_preview
from qqmusicmcp.writes import account_fingerprint

CONFIRM = "确认批准本次写入"


def main() -> int:
    if not sys.stdin.isatty():
        print("必须在可信任的交互式终端批准；未执行写入。")
        return 2
    ticket = getpass.getpass(
        "请粘贴 MCP 预览返回的 confirmation_token（不回显）： "
    ).strip()
    try:
        details = describe_preview(ticket, account_fingerprint())
    except (SafetyError, ValueError) as exc:
        print("无法确认预览：", type(exc).__name__)
        return 1
    print("\n将批准以下唯一一次写入：")
    print("操作：", details["operation"])
    print("参数：", details["arguments"])
    print("目标歌单：", details.get("target_name") or "(新建歌单)")
    print("票据过期前使用一次，超过五分钟需重新预览。")
    if input("确认无误后输入「" + CONFIRM + "」：\n> ").strip() != CONFIRM:
        print("未批准。")
        return 2
    try:
        approve_preview(ticket, account_fingerprint())
    except (SafetyError, ValueError) as exc:
        print("批准失败：", type(exc).__name__)
        return 1
    print("批准成功。可以由 MCP 客户端执行该预览票据一次。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
