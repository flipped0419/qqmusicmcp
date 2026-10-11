"""Explicit one-shot QQ Music temporary playlist write test.

Never run as an MCP tool or without interactive user consent.
"""

from __future__ import annotations
import asyncio
import sys
from qqmusicmcp.writes import (
    run_temporary_probe,
    writes_enabled,
    probe_valid,
    migrate_legacy_probe,
)

CONFIRM = "我同意创建并删除临时测试歌单"


def main():
    if not sys.stdin.isatty():
        print("仅支持在交互式终端手动运行；未修改 QQ 音乐。")
        return 2
    if not writes_enabled():
        print("写入测试未启用（QQMUSIC_ENABLE_WRITES 不是 true）；未修改 QQ 音乐。")
        return 2
    if probe_valid():
        print("当前账号已通过一次性探针：无需重测，未创建任何歌单。")
        return 0
    try:
        if migrate_legacy_probe() == "migrated_without_new_probe":
            print("已将原有成功探针升级为长期有效记录，未创建任何歌单。")
            return 0
    except PermissionError:
        pass
    print(
        "将创建一个临时歌单，添加一首“我喜欢”里的歌曲，回读验证、移除歌曲，最后删除临时歌单。"
    )
    print("不修改已有歌单和“我喜欢”。任何网络失败可能遗留临时歌单，需人工检查。")
    typed = input("若同意，请输入：" + CONFIRM + "\n> ")
    if typed.strip() != CONFIRM:
        print("未确认；未修改 QQ 音乐。")
        return 2
    try:
        result = asyncio.run(run_temporary_probe())
        print("状态：", result["status"], "；探针记录不按时间自动过期。")
        return 0
    except Exception as exc:
        print("测试失败；请检查是否遗留 qqmusicmcp-test- 开头的临时歌单。")
        print("错误类型：", type(exc).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
