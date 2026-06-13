"""
测试爬虫模块的导入和基本功能
"""
import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

print("=" * 60)
print("测试 job-crawler 模块导入")
print("=" * 60)

# 测试1: 导入模型
print("\n1. 测试模型导入...")
try:
    from app.models import JobItem
    from app.models.constants import JobSource, RecruitmentType, AcademicQualification
    print("[OK] 模型导入成功")
except Exception as e:
    print(f"[FAIL] 模型导入失败: {e}")
    sys.exit(1)

# 测试2: 测试 JobItem.from_scrapy_item 方法
print("\n2. 测试 JobItem.from_scrapy_item 方法...")
try:
    class MockScrapyItem(dict):
        pass
    
    mock_item = MockScrapyItem({
        "id": "test-id",
        "source": JobSource.ZHILIAN,
        "url": "https://test.com",
        "fingerprint": "test-fingerprint",
        "job_title": "测试职位",
        "company_name": "测试公司",
    })
    
    job_item = JobItem.from_scrapy_item(mock_item)
    print(f"[OK] from_scrapy_item 方法正常工作")
    print(f"   - Job Title: {job_item.job_title}")
    print(f"   - Company: {job_item.company_name}")
except Exception as e:
    print(f"[FAIL] from_scrapy_item 方法失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试3: 导入数据库控制器
print("\n3. 测试数据库控制器导入...")
try:
    from app.services.crawler_db_controller import CrawlerDBController
    print("[OK] 数据库控制器导入成功")
except Exception as e:
    print(f"[FAIL] 数据库控制器导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试4: 导入 embedding 服务
print("\n4. 测试 embedding 服务导入...")
try:
    from app.services.crawler_embedding_service import CrawlerEmbeddingService
    print("[OK] Embedding 服务导入成功")
except Exception as e:
    print(f"[FAIL] Embedding 服务导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试5: 导入向量数据库服务
print("\n5. 测试向量数据库服务导入...")
try:
    from app.services.vector_db_service import VectorDBService
    print("[OK] 向量数据库服务导入成功")
except Exception as e:
    print(f"[FAIL] 向量数据库服务导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试6: 导入 pipelines
print("\n6. 测试 pipelines 导入...")
try:
    from job_crawler.pipelines import JobCrawlerPipeline
    print("[OK] Pipelines 导入成功")
except Exception as e:
    print(f"[FAIL] Pipelines 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试7: 导入 spider
print("\n7. 测试 spider 导入...")
try:
    from job_crawler.spiders.zhilian_spider import ZhilianSpider
    print("[OK] Spider 导入成功")
except Exception as e:
    print(f"[FAIL] Spider 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("[OK] 所有测试通过！job-crawler 模块可以正常使用")
print("=" * 60)
