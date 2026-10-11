"""Read-only checks, plus independently confirmed clearing of a resolved journal.

Never retries writes or automatically changes QQ Music playlists.
"""

from __future__ import annotations
import asyncio
import sys
from qqmusicmcp.reconcile import analyze_unresolved, mark_resolved
from qqmusicmcp.safety import exclusive_write_lock


async def main() -> int:
    entries = await analyze_unresolved()
    if not entries:
        print("没有未解决的写入记录；不需要清理。")
        return 0
    for entry in entries:
        print("记录编号：", entry["operation_id"])
        print("操作：", entry["operation"])
        print("审计状态：", entry["journal_status"])
        print("只读回查判断：", entry["readback_outcome"])
    if not sys.stdin.isatty():
        print("未使用交互终端，仅展示只读状态；写入继续锁定。")
        return 2
    if len(entries) != 1 or entries[0]["readback_outcome"] not in {
        "applied",
        "not_applied",
    }:
        print("无法安全自动确认结果；需人工核实，保持锁定。")
        return 2
    entry = entries[0]
    confirm = "我已确认这项写入的回查结果"
    print("请同时在 QQ 音乐客户端核对该变化，然后再确认。")
    if input("确认后输入「" + confirm + "」：\n> ").strip() != confirm:
        print("未确认，保持锁定。")
        return 2
    # Read fresh again: refuse if state changed while the operator inspected.
    with exclusive_write_lock():
        second = await analyze_unresolved()
        if (
            len(second) != 1
            or second[0]["operation_id"] != entry["operation_id"]
            or second[0]["readback_outcome"] != entry["readback_outcome"]
        ):
            print("回查结果已改变；保持锁定。")
            return 2
        mark_resolved(entry["operation_id"], entry["readback_outcome"])
    print("审计状态已修复；没有重试或撤销远程写入。")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
