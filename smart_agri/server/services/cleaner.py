from sqlalchemy import text
from database import SessionLocal
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def auto_clean_old_data():
    """
    自动清理 7 天前的原始热数据 (raw_environmental_readings)
    保留二级分析数据 (agri_analytical_metrics) 
    """
    db = SessionLocal()
    try:
        # 计算 7 天前的时间点
        retention_limit = datetime.now() - timedelta(days=7)
        
        # 执行删除语句
        # 注意：这里只删表 1，因为表 2 是你的核心资产
        sql = text("DELETE FROM raw_environmental_readings WHERE timestamp < :limit")
        result = db.execute(sql, {"limit": retention_limit})
        db.commit()
        
        logger.info(f"🧹 [数据清理] 成功清理 {result.rowcount} 条 7 天前的过期原始数据。")
    except Exception as e:
        db.rollback()
        logger.error(f"❌ [清理失败] 自动清理逻辑出现异常: {e}")
    finally:
        db.close()