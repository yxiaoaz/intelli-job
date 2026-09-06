# -*- coding: utf-8 -*-
"""补嵌脚本：为 embedding_generated=false 的岗位补生成向量并写入 Milvus。

背景：GH Actions secrets 的 LLM_EMBEDDING_API_KEY 无效导致一批岗位
落库但无向量（401 invalid_api_key，逐条跳过不中断）。

用法（backend 目录，venv）：
  python scripts/reembed_failed.py                 # 全部未向量化行
  python scripts/reembed_failed.py --limit 500     # 本次最多补 500 条
  python scripts/reembed_failed.py --source Greenhouse
幂等：只处理 embedding_generated=false 的行，成功后置 true。
"""
import argparse
import json
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import select  # noqa: E402

from app.models import JobItem  # noqa: E402
from app.models.constants import JobSource  # noqa: E402
from app.services.crawler_db_controller import CrawlerDBController  # noqa: E402
from app.services.crawler_embedding_service import CrawlerEmbeddingService  # noqa: E402
from app.services.vector_db_service import VectorDBService  # noqa: E402
from app.utils.logger import get_logger, setup_logging  # noqa: E402

logger = get_logger()

BATCH_SIZE = 50  # 每批生成 embedding 的条数


def main():
    parser = argparse.ArgumentParser(description="补嵌未向量化岗位")
    parser.add_argument("--limit", type=int, default=None,
                        help="本次最多处理的条数")
    parser.add_argument("--source", type=str, default=None,
                        help="只处理指定 JobSource 枚举名（如 Greenhouse）")
    parser.add_argument("--since", type=str, default=None,
                        help="只处理 created_at >= 此时间的行（ISO 格式，如 2026-09-06）")
    args = parser.parse_args()

    controller = CrawlerDBController()
    embedding_service = CrawlerEmbeddingService(
        api_url=__import__("os").getenv(
            "LLM_EMBEDDING_API_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        api_key=__import__("os").getenv("LLM_EMBEDDING_API_KEY"),
    )
    vector_db = VectorDBService()

    with controller.session_maker() as session:
        stmt = select(JobItem).where(JobItem.embedding_generated == False)  # noqa: E712
        if args.source:
            stmt = stmt.where(
                JobItem.source == JobSource[args.source.upper()])
        if args.since:
            from datetime import datetime as _dt
            stmt = stmt.where(
                JobItem.created_at >= _dt.fromisoformat(args.since))
        if args.limit:
            stmt = stmt.limit(args.limit)
        rows = session.scalars(stmt).all()

    total = len(rows)
    logger.info(f"[reembed] 待补嵌 {total} 条")
    if not total:
        return

    done = failed = 0
    for start in range(0, total, BATCH_SIZE):
        chunk = rows[start:start + BATCH_SIZE]
        results = []
        for row in chunk:
            try:
                emb = embedding_service._get_single_embedding(str(row))
                results.append({"id": str(row.id), "embedding": emb})
            except Exception as e:
                failed += 1
                logger.error(f"[reembed] item {row.id} failed: {e}")

        if not results:
            continue

        # 写 Milvus（复用 pipeline 的 content/language 结构）
        import langid
        id_content = {str(r.id): str(r) for r in chunk}
        embeddings = []
        for r in results:
            content = id_content[r["id"]]
            embeddings.append({
                "id": r["id"],
                "embedding": r["embedding"],
                "content": content,
                "language": langid.classify(content)[0],
            })
        vector_db.insert_embeddings(embeddings)

        # 更新状态（仅本批成功的 id）
        with controller.session_maker() as session:
            ok_ids = [uuid.UUID(r["id"]) for r in results]
            session.query(JobItem).filter(
                JobItem.id.in_(ok_ids)).update(
                {"embedding_generated": True}, synchronize_session=False)
            session.commit()

        done += len(results)
        logger.info(f"[reembed] 进度 {min(start + BATCH_SIZE, total)}/{total} "
                    f"(done={done}, failed={failed})")

    logger.info(f"[reembed] 完成：成功 {done}，失败 {failed}")
    print({"success": done, "failed": failed})


if __name__ == "__main__":
    setup_logging()
    main()
