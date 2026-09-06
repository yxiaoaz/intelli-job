"""
修复 PostgreSQL enum 类型
将 enum 类型的值从成员名（如 SHIXISENG）更新为实际的枚举值（如 "Shixiseng | 实习僧"）
用法: python scripts/fix_enum_types.py
"""

import os
import sys
from pathlib import Path

# 修复 Windows GBK 编码问题
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 添加 backend 目录到 Python 路径
backend_dir = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, ".env"))

import psycopg2

# 构建数据库连接 URL
rds_host = os.getenv("RDS_HOST")
rds_port = os.getenv("RDS_PORT", "5432")
rds_username = os.getenv("RDS_USERNAME")
rds_password = os.getenv("RDS_PASSWORD")
rds_db_name = os.getenv("RDS_DB_NAME")

print(f"连接数据库: {rds_host}:{rds_port}/{rds_db_name}")

conn = psycopg2.connect(
    host=rds_host,
    port=int(rds_port),
    user=rds_username,
    password=rds_password,
    dbname=rds_db_name,
)
conn.autocommit = True  # ALTER TYPE 必须在事务外执行

cur = conn.cursor()

# 定义所有 enum 类型及其期望的值
enum_definitions = {
    "jobsource": [
        "Zhilian | 智联招聘",
        "Shixiseng | 实习僧",
        "Welcome to the Jungle",
        "CT Good Jobs HK",
        # ATS 海外源（job-source-adapter-refactor 枚举占位）
        "Greenhouse",
        "Lever",
        "Ashby",
    ],
    "recruitmenttype": [
        "实习 | internship",
        "校招 | graduate job",
        "社招 | experienced or senior level",
    ],
    "academicqualification": [
        "不限",
        "专科",
        "本科",
        "硕士",
        "博士",
    ],
    "applicationstatus": [
        "saved",
        "applied",
        "interviewing",
        "rejected",
        "accepted",
    ],
}


def get_existing_enum_values(enum_name):
    """获取 PostgreSQL 中已有 enum 类型的值列表"""
    cur.execute(
        """
        SELECT e.enumlabel
        FROM pg_enum e
        JOIN pg_type t ON e.enumtypid = t.oid
        WHERE t.typname = %s
        ORDER BY e.enumsortorder
        """,
        (enum_name,),
    )
    return [row[0] for row in cur.fetchall()]


def enum_type_exists(enum_name):
    """检查 enum 类型是否存在"""
    cur.execute(
        "SELECT 1 FROM pg_type WHERE typname = %s",
        (enum_name,),
    )
    return cur.fetchone() is not None


for enum_name, expected_values in enum_definitions.items():
    print(f"\n{'='*50}")
    print(f"处理 enum 类型: {enum_name}")
    print(f"{'='*50}")

    if not enum_type_exists(enum_name):
        # enum 不存在，创建新的
        quoted_values = ", ".join(f"'{v}'" for v in expected_values)
        cur.execute(f"CREATE TYPE {enum_name} AS ENUM ({quoted_values})")
        print(f"  ✅ 创建 enum 类型: {enum_name}")
        print(f"     值: {expected_values}")
        continue

    # enum 已存在，检查并添加缺失的值
    existing_values = get_existing_enum_values(enum_name)
    print(f"  当前值: {existing_values}")
    print(f"  期望值: {expected_values}")

    missing_values = [v for v in expected_values if v not in existing_values]

    if not missing_values:
        print(f"  ✅ 所有值已存在，无需更新")
        continue

    print(f"  需要添加的值: {missing_values}")

    for value in missing_values:
        # 转义单引号
        escaped_value = value.replace("'", "''")
        cur.execute(f"ALTER TYPE {enum_name} ADD VALUE '{escaped_value}'")
        print(f"  ✅ 添加值: '{value}'")

# 验证最终结果
print(f"\n{'='*50}")
print("验证最终 enum 值")
print(f"{'='*50}")

for enum_name in enum_definitions:
    if enum_type_exists(enum_name):
        values = get_existing_enum_values(enum_name)
        print(f"  {enum_name}: {values}")

cur.close()
conn.close()
print("\n✅ 完成！enum 类型已更新")
