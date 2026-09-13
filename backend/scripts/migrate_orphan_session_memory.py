"""老会话 L1（session-*.md）存量搬迁脚本

背景（agent-context-overhaul E2E 验收发现）：9/6 部署的那版代码取不到
`request.state.user_id`，`_get_user_workspace_dir` 落到 `"default"`，于是那批
会话的 L1 markdown 写在 `workspace/default/session-{thread}.md`。而 Phase 2 之后
deepagents 的虚拟根已经是 `workspace/user-{id}`，agent 按 prompt 规则去
`read_file("/session-{thread}.md")` 只能落空——**老会话冷启动恢复不了上下文**
（实测它确实按新规则试了 read_file + ls，然后诚实地说"答不上来"，没有编造）。

本脚本做且仅做一件事：把非 `user-*` 目录（以及散在 base_dir 根下的）
`session-{thread}.md` 按 `chat_sessions.user_id` 归属搬到 `user-{uid}/` 下。

不做的事：
- 不解析 markdown 回填 `session_memories` 表（Phase 3 已删除 `parse_*_memory`
  解析器，不为此重建）；agent 冷启动读的是文件，搬对位置即可
- 不删任何文件：目标已存在时跳过并报告，源文件保留

用法:
  python scripts/migrate_orphan_session_memory.py --dry-run   # 仅打印计划（默认）
  python scripts/migrate_orphan_session_memory.py --execute   # 真正移动

生产上须在**容器内**跑（workspace 是宿主机 bind mount，本地这份镜像无关）:
  docker exec -it intellijob-backend python backend/scripts/migrate_orphan_session_memory.py --dry-run
"""
import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

load_dotenv(backend_dir / ".env")

import psycopg  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services.intent_file_service import IntentFileService  # noqa: E402

SESSION_FILE_RE = re.compile(r"^session-(?P<thread>[0-9a-fA-F-]{36})\.md$")


def _collect_orphan_files(base_dir: Path) -> list[Path]:
    """列出需要搬迁的 L1 文件

    两处来源：
    1. `base_dir/<非 user-*>/session-*.md`（如 `default/`）
    2. `base_dir/session-*.md`（更早期没有按用户分目录时留下的）
    """
    files: list[Path] = []

    for entry in sorted(base_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("user-"):
            continue
        files.extend(
            f for f in sorted(entry.iterdir())
            if f.is_file() and SESSION_FILE_RE.match(f.name)
        )

    files.extend(
        f for f in sorted(base_dir.iterdir())
        if f.is_file() and SESSION_FILE_RE.match(f.name)
    )
    return files


def _owner_map(threads: list[str]) -> dict[str, str]:
    """thread_id -> user_id（查不到的不返回，由调用方报告）"""
    if not threads:
        return {}

    dsn = get_settings().CHECKPOINTER_DSN
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cast(id as text), cast(user_id as text) FROM chat_sessions "
                "WHERE cast(id as text) = ANY(%s)",
                (threads,),
            )
            return {str(thread): str(user_id) for thread, user_id in cur.fetchall()}


def main(execute: bool, base_dir: Path) -> int:
    print(f"===== migrate_orphan_session_memory ({'EXECUTE' if execute else 'DRY-RUN'}) =====")
    print(f"base_dir = {base_dir}")

    if not base_dir.exists():
        print("base_dir 不存在，无需搬迁")
        return 0

    files = _collect_orphan_files(base_dir)
    if not files:
        print("未发现需要搬迁的 L1 文件，幂等退出")
        return 0

    threads = [SESSION_FILE_RE.match(f.name).group("thread") for f in files]
    owners = _owner_map(threads)

    moved = skipped_exists = unknown = failed = 0
    for path in files:
        thread = SESSION_FILE_RE.match(path.name).group("thread")
        user_id = owners.get(thread)
        if not user_id:
            print(f"[unknown-session] {path}  （chat_sessions 里已无此会话，保留原位）")
            unknown += 1
            continue

        target = base_dir / f"user-{user_id}" / path.name
        if target.exists():
            print(f"[skip-exists] {path}  →  {target} 已存在，不动源文件")
            skipped_exists += 1
            continue

        if not execute:
            print(f"[preview] {path}  →  {target}")
            moved += 1
            continue

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            path.replace(target)
            print(f"[moved] {path.name}  →  user-{user_id[:8]}…/")
            moved += 1
        except OSError as e:
            print(f"[failed] {path}: {e}")
            failed += 1

    print(
        f"\n汇总: {'待搬' if not execute else '已搬'} {moved}    "
        f"目标已存在跳过 {skipped_exists}    归属未知 {unknown}    失败 {failed}"
    )
    if not execute and moved:
        print("确认无误后执行: python scripts/migrate_orphan_session_memory.py --execute")
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="老会话 L1 markdown 归属搬迁")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="仅打印搬迁计划（默认）")
    group.add_argument("--execute", action="store_true", help="真正移动文件")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="记忆根目录，默认取 IntentFileService().base_dir（即 workspace）",
    )
    args = parser.parse_args()

    base = args.base_dir or Path(IntentFileService().base_dir)
    sys.exit(main(execute=args.execute, base_dir=base))
