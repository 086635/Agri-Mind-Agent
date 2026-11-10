# ============================================================================
# 智慧农业 AI 网关系统 - 环境初始化脚本
# ============================================================================
# 使用方法:
#   1. 先安装 PostgreSQL 数据库 (https://www.postgresql.org/download/windows/)
#   2. 以管理员身份运行此脚本: python init_environment.py
# ============================================================================

import os
import sys
import subprocess
from pathlib import Path

# 设置 UTF-8 编码
os.environ.setdefault("PYTHONUTF8", "1")

print("=" * 60)
print("  智慧农业 AI 网关系统 - 环境初始化")
print("=" * 60)

# ============================================================================
# 步骤 1: 检查 PostgreSQL 是否已安装
# ============================================================================
print("\n[步骤 1] 检查 PostgreSQL 数据库...")

def check_postgresql():
    """检查 PostgreSQL 是否已安装"""
    try:
        result = subprocess.run(
            ["psql", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print(f"  ✓ PostgreSQL 已安装: {result.stdout.strip()}")
            return True
        else:
            print("  ✗ PostgreSQL 未安装或未配置到 PATH")
            return False
    except FileNotFoundError:
        print("  ✗ PostgreSQL 未安装")
        return False
    except Exception as e:
        print(f"  ✗ 检查失败: {e}")
        return False

if not check_postgresql():
    print("\n" + "=" * 60)
    print("  PostgreSQL 未安装，请先安装 PostgreSQL")
    print("=" * 60)
    print("\n安装方法:")
    print("  1. 访问 https://www.postgresql.org/download/windows/")
    print("  2. 下载 PostgreSQL 安装程序 (推荐版本 15 或 16)")
    print("  3. 安装时设置密码为: Ysw@88516251 (或修改 database.py 中的密码)")
    print("  4. 安装完成后，将 PostgreSQL 的 bin 目录添加到系统 PATH")
    print("     默认路径: C:\\Program Files\\PostgreSQL\\16\\bin")
    print("\n或者使用以下命令安装 (需要管理员权限):")
    print("  winget install PostgreSQL.PostgreSQL")
    print("\n" + "=" * 60)
    print("  安装完成后，请重新运行此脚本")
    print("=" * 60)
    sys.exit(1)

# ============================================================================
# 步骤 2: 创建数据库
# ============================================================================
print("\n[步骤 2] 创建 agri_ai 数据库...")

DB_NAME = "agri_ai"
DB_USER = "postgres"
DB_PASSWORD = "Ysw@88516251"  # 请根据实际密码修改

def create_database():
    """创建数据库"""
    try:
        # 检查数据库是否已存在
        result = subprocess.run(
            ["psql", "-U", DB_USER, "-lqt"],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "PGPASSWORD": DB_PASSWORD}
        )
        
        if DB_NAME in result.stdout:
            print(f"  ✓ 数据库 '{DB_NAME}' 已存在")
            return True
        
        # 创建数据库
        result = subprocess.run(
            ["psql", "-U", DB_USER, "-c", f"CREATE DATABASE {DB_NAME};"],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "PGPASSWORD": DB_PASSWORD}
        )
        
        if result.returncode == 0:
            print(f"  ✓ 数据库 '{DB_NAME}' 创建成功")
            return True
        else:
            print(f"  ✗ 创建数据库失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"  ✗ 创建数据库失败: {e}")
        return False

if not create_database():
    print("\n请手动创建数据库:")
    print(f"  psql -U postgres -c \"CREATE DATABASE {DB_NAME};\"")
    sys.exit(1)

# ============================================================================
# 步骤 3: 创建数据库表结构
# ============================================================================
print("\n[步骤 3] 创建数据库表结构...")

try:
    from dotenv import load_dotenv
    load_dotenv()
    
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    
    from server.models import Base
    
    SYNC_URL = os.getenv("SYNC_DATABASE_URL", f"postgresql://{DB_USER}:{DB_PASSWORD.replace('@', '%40')}@localhost:5432/{DB_NAME}")
    engine = create_engine(SYNC_URL)
    
    # 创建所有表
    Base.metadata.create_all(engine)
    print("  ✓ 数据库表结构创建成功")
    
    # 显示创建的表
    print("\n  已创建的表:")
    for table in Base.metadata.tables.keys():
        print(f"    - {table}")
        
except Exception as e:
    print(f"  ✗ 创建表结构失败: {e}")
    sys.exit(1)

# ============================================================================
# 步骤 4: 填充种子数据
# ============================================================================
print("\n[步骤 4] 填充模拟数据...")

try:
    from seed_data import (
        seed_raw_readings,
        seed_device_twins,
        calculate_secondary_metrics,
        seed_policy_thresholds,
        seed_audit_logs,
        seed_system_service_status,
        seed_user_profile,
        seed_operation_logics,
        seed_chat_messages,
    )
    
    with Session(engine) as session:
        seed_raw_readings(session, days=7)
        seed_device_twins(session)
        calculate_secondary_metrics(session)
        seed_policy_thresholds(session)
        seed_audit_logs(session)
        seed_system_service_status(session)
        seed_user_profile(session)
        seed_operation_logics(session)
        seed_chat_messages(session)
    
    print("  ✓ 模拟数据填充成功")
    
except Exception as e:
    print(f"  ✗ 填充数据失败: {e}")
    sys.exit(1)

# ============================================================================
# 步骤 5: 验证环境
# ============================================================================
print("\n[步骤 5] 验证环境配置...")

try:
    from sqlalchemy import text
    
    with engine.connect() as conn:
        # 检查各表数据量
        tables = [
            "raw_environmental_readings",
            "agri_analytical_metrics",
            "device_digital_twin_status",
            "esg_value_realization",
            "policy_risk_thresholds",
            "agent_action_audit",
            "system_service_status",
            "system_user_profile",
            "operation_logic_records",
            "chat_message_records",
        ]
        
        print("\n  数据统计:")
        for table in tables:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            print(f"    - {table}: {count} 条")
    
    print("\n  ✓ 环境验证成功")
    
except Exception as e:
    print(f"  ✗ 验证失败: {e}")
    sys.exit(1)

# ============================================================================
# 完成
# ============================================================================
print("\n" + "=" * 60)
print("  环境初始化完成！")
print("=" * 60)
print("\n下一步:")
print("  1. 启动超级网关: python super_gateway.py")
print("  2. 启动 AI 网关: python ai_gateway.py")
print("  3. 启动视觉服务: python vision_server.py")
print("\n数据库连接信息:")
print(f"  - 数据库名: {DB_NAME}")
print(f"  - 用户名: {DB_USER}")
print(f"  - 端口: 5432")
print("=" * 60)