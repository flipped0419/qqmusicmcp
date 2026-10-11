"""Migrate the verified historical QQ Music probe to a persistent receipt.

This script does not contact QQ Music or modify any playlists.
"""

from qqmusicmcp.writes import migrate_legacy_probe, probe_valid


def main():
    try:
        result = migrate_legacy_probe()
    except (PermissionError, RuntimeError, ValueError) as exc:
        print("探针记录迁移失败：", type(exc).__name__)
        return 1
    print("探针迁移状态：", result)
    print("写入能力历史验证有效：", probe_valid())
    print("未在 QQ 音乐创建、删除或修改任何歌单。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
