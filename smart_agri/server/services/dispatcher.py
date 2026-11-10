import pandas as pd
import sys
import os
import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal
from models import RawEnvironmentalReading, AgriAnalyticalMetric
import importlib

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 将算法文件夹加入系统路径
SKILL_PATH = r"E:\important_project\FWWBC\aidemo\skill_tools_engine"
sys.path.append(SKILL_PATH)

class SkillDispatcher:
    def __init__(self):
        # 自动扫描文件夹下所有的算法脚本
        self.skills = [f[:-3] for f in os.listdir(SKILL_PATH) if f.endswith('.py') and f != '__init__.py']

    def _fetch_data(self, db: Session, days=1):
        """统一读取：拉取过去 24 小时数据"""
        start_time = datetime.now() - timedelta(days=days)
        query = db.query(RawEnvironmentalReading).filter(RawEnvironmentalReading.timestamp >= start_time)
        df = pd.read_sql(query.statement, db.bind)
        return df

    def _run_single_skill(self, skill_name, data_json, config):
        """包装器：动态加载并运行单个算法"""
        try:
            # 动态导入模块
            module = importlib.import_module(skill_name)
            importlib.reload(module) # 确保读取最新代码
            
            # 将 JSON 转回 DataFrame (跨进程传输需要)
            data = pd.read_json(data_json)
            
            # 执行统一入口
            result = module.run_analysis(data, config)
            return {"skill_name": skill_name, "result": result, "success": True}
        except ModuleNotFoundError as e:
            logger.error(f"算法模块未找到: {skill_name}, error={str(e)}")
            return {"skill_name": skill_name, "result": None, "success": False, "error": f"模块未找到: {str(e)}"}
        except AttributeError as e:
            logger.error(f"算法模块缺少 run_analysis 方法: {skill_name}, error={str(e)}")
            return {"skill_name": skill_name, "result": None, "success": False, "error": f"方法缺失: {str(e)}"}
        except Exception as e:
            logger.error(f"算法 {skill_name} 运行异常: {str(e)}", exc_info=True)
            return {"skill_name": skill_name, "result": None, "success": False, "error": str(e)}

    async def run_all_skills(self):
        """并发执行：利用多进程避开 GIL 锁，提升计算效率"""
        db = SessionLocal()
        try:
            # 1. 统一读取
            raw_df = self._fetch_data(db)
            if raw_df.empty:
                logger.warning("无可用环境数据，跳过本次批处理。")
                return

            # 跨进程传输前先序列化
            data_json = raw_df.to_json()
            config = {"processed_at": datetime.now().isoformat()}

            # 2. 并发分发 (使用进程池处理计算密集型任务)
            loop = asyncio.get_event_loop()
            with ProcessPoolExecutor() as pool:
                tasks = [
                    loop.run_in_executor(pool, self._run_single_skill, skill, data_json, config)
                    for skill in self.skills
                ]
                results = await asyncio.gather(*tasks)

            # 3. 结果聚合与批量写入
            final_metrics = {}
            failed_skills = []
            
            for res in results:
                if res and res.get("success"):
                    skill_result = res.get("result")
                    if skill_result:
                        final_metrics.update(skill_result) # 汇总所有算法产出的字段
                else:
                    # 记录失败的算法
                    failed_skills.append({
                        "skill_name": res.get("skill_name"),
                        "error": res.get("error")
                    })
            
            # 记录失败统计
            if failed_skills:
                logger.warning(f"以下算法执行失败: {failed_skills}")
            
            if final_metrics:
                # 构造数据库 ORM 对象
                new_metric = AgriAnalyticalMetric(
                    batch_id=f"BATCH_{datetime.now().strftime('%Y%m%d')}",
                    device_id="GLOBAL_001", # 示例 ID
                    record_date=datetime.now().date(),
                    **final_metrics
                )
                db.add(new_metric)
                db.commit()
                logger.info(f"[Dispatcher] 每日批处理完成，数据已入库。成功算法数: {len(results) - len(failed_skills)}, 失败算法数: {len(failed_skills)}")

        finally:
            db.close()

# 全局单例
dispatcher = SkillDispatcher()