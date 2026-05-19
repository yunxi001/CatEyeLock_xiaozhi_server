"""
智能门锁AI功能数据库服务

提供门锁AI功能的数据库操作，包括：
- 设备配置管理
- 访客意图记录
- 快递警报记录
- 欢迎词配置
"""
import json
import mysql.connector
from mysql.connector import pooling
from datetime import datetime
from typing import List, Optional, Tuple
from pathlib import Path
from loguru import logger

from .models import DoorlockConfig, VisitorIntent, PackageAlert

TAG = "DoorlockDatabase"


def _load_doorlock_config() -> dict:
    """加载智能门锁独立配置文件（在系统配置加载完成后调用）
    
    Returns:
        dict: 门锁配置字典
    """
    # 从当前文件位置向上找到项目根目录，然后定位到 config/doorlock_config.yaml
    # 当前文件: core/providers/doorlock/doorlock_database.py
    # 目标文件: config/doorlock_config.yaml
    current_file = Path(__file__)  # doorlock_database.py
    project_root = current_file.parent.parent.parent.parent  # 向上4层到项目根目录
    config_path = project_root / "config" / "doorlock_config.yaml"
    
    if not config_path.exists():
        logger.bind(tag=TAG).error(f"门锁配置文件不存在: {config_path}")
        raise FileNotFoundError(f"门锁配置文件不存在: {config_path}")
    
    try:
        from ruamel.yaml import YAML
        yaml = YAML()
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.load(f)
        logger.bind(tag=TAG).info(f"门锁独立配置加载成功（系统配置加载后）")
        return config
    except Exception as e:
        logger.bind(tag=TAG).error(f"加载门锁配置文件失败: {e}")
        raise


class DoorlockDatabase:
    """门锁AI功能数据库操作类
    
    注意：此类在系统配置加载完成后初始化，不影响系统配置加载流程
    """
    
    def __init__(self, config: dict = None):
        """初始化数据库连接
        
        Args:
            config: 系统配置字典（传入但不使用，门锁使用独立的数据库配置）
        
        说明：
            - 门锁数据库配置从 doorlock_config.yaml 独立加载
            - 不依赖系统配置，避免影响系统配置加载流程
        """
        # 加载门锁独立配置文件（在系统配置加载完成后）
        doorlock_config = _load_doorlock_config()
        self.config = doorlock_config['mysql']
        
        logger.bind(tag=TAG).info("门锁数据库使用独立配置（不影响系统配置）")
        
        self.pool = None
        self._init_pool()
    
    def _init_pool(self):
        """初始化数据库连接池"""
        try:
            # 确保密码是字符串类型（YAML可能将纯数字密码解析为整数）
            password = self.config.get('password', '')
            if password is not None:
                password = str(password)
            
            self.pool = pooling.MySQLConnectionPool(
                pool_name="doorlock_ai_pool",
                pool_size=self.config.get('pool_size', 5),
                host=self.config.get('host', '127.0.0.1'),
                port=self.config.get('port', 3306),
                user=self.config.get('user', 'root'),
                password=password,
                database=self.config.get('database', 'smart_doorlock'),
                charset='utf8mb4'
            )
            logger.bind(tag=TAG).info("数据库连接池初始化成功")
        except mysql.connector.Error as e:
            logger.bind(tag=TAG).error(f"数据库连接池初始化失败: {e}")
            raise
    
    def get_connection(self):
        """获取数据库连接
        
        Returns:
            数据库连接对象
            
        Raises:
            mysql.connector.Error: 数据库连接错误
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self.pool.get_connection()
            except mysql.connector.PoolError as e:
                if attempt < max_retries - 1:
                    logger.bind(tag=TAG).warning(f"数据库连接池耗尽，重试 {attempt + 1}/{max_retries}")
                    continue
                logger.bind(tag=TAG).error(f"数据库连接池耗尽: {e}")
                raise
            except mysql.connector.Error as e:
                logger.bind(tag=TAG).error(f"获取数据库连接失败: {e}")
                raise
    
    # ==================== 设备配置管理 ====================
    
    async def get_config(self, device_id: str) -> Optional[DoorlockConfig]:
        """获取设备配置
        
        Args:
            device_id: 设备ID
            
        Returns:
            设备配置对象，如果不存在则返回默认配置
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT device_id, intent_recognition_enabled, package_guard_available,
                       package_guard_active, package_baseline_image, package_guard_start_time
                FROM doorlock_config
                WHERE device_id = %s
            """, (device_id,))
            
            row = cursor.fetchone()
            
            if row:
                logger.bind(tag=TAG).debug(f"获取设备配置成功: device_id={device_id}")
                return DoorlockConfig(
                    device_id=row['device_id'],
                    intent_recognition_enabled=bool(row['intent_recognition_enabled']),
                    package_guard_available=bool(row['package_guard_available']),
                    package_guard_active=bool(row['package_guard_active']),
                    package_baseline_image=row.get('package_baseline_image'),
                    package_guard_start_time=row.get('package_guard_start_time')
                )
            else:
                # 返回默认配置
                logger.bind(tag=TAG).info(f"设备配置不存在，返回默认配置: device_id={device_id}")
                return DoorlockConfig(device_id=device_id)
                
        except mysql.connector.Error as e:
            logger.bind(tag=TAG).error(f"获取设备配置失败: device_id={device_id}, error={e}")
            # 返回默认配置而不是抛出异常
            return DoorlockConfig(device_id=device_id)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    async def update_config(self, config: DoorlockConfig) -> bool:
        """更新设备配置
        
        Args:
            config: 设备配置对象
            
        Returns:
            是否更新成功
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO doorlock_config 
                (device_id, intent_recognition_enabled, package_guard_available,
                 package_guard_active, package_baseline_image, package_guard_start_time)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    intent_recognition_enabled = VALUES(intent_recognition_enabled),
                    package_guard_available = VALUES(package_guard_available),
                    package_guard_active = VALUES(package_guard_active),
                    package_baseline_image = VALUES(package_baseline_image),
                    package_guard_start_time = VALUES(package_guard_start_time)
            """, (
                config.device_id,
                config.intent_recognition_enabled,
                config.package_guard_available,
                config.package_guard_active,
                config.package_baseline_image,
                config.package_guard_start_time
            ))
            
            conn.commit()
            logger.bind(tag=TAG).info(f"更新设备配置成功: device_id={config.device_id}")
            return True
            
        except mysql.connector.Error as e:
            logger.bind(tag=TAG).error(f"更新设备配置失败: device_id={config.device_id}, error={e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    # ==================== 访客意图记录管理 ====================
    
    async def save_visitor_intent(self, intent: VisitorIntent) -> int:
        """保存访客意图记录
        
        Args:
            intent: 访客意图对象
            
        Returns:
            插入记录的ID，失败返回0
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 将字典和列表转换为JSON字符串
            intent_summary_json = json.dumps(intent.intent_summary, ensure_ascii=False) if intent.intent_summary else None
            dialogue_history_json = json.dumps(intent.dialogue_history, ensure_ascii=False) if intent.dialogue_history else None
            
            cursor.execute("""
                INSERT INTO doorlock_visitor_intents
                (visit_id, session_id, person_id, intent_type, intent_summary, dialogue_history)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                intent.visit_id,
                intent.session_id,
                intent.person_id,
                intent.intent_type,
                intent_summary_json,
                dialogue_history_json
            ))
            
            conn.commit()
            record_id = cursor.lastrowid
            logger.bind(tag=TAG).info(
                f"保存访客意图记录成功: id={record_id}, session_id={intent.session_id}, "
                f"intent_type={intent.intent_type}"
            )
            return record_id
            
        except mysql.connector.Error as e:
            logger.bind(tag=TAG).error(f"保存访客意图记录失败: session_id={intent.session_id}, error={e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    async def get_visitor_intents(
        self, 
        device_id: str, 
        limit: int = 20, 
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> tuple[List[VisitorIntent], int]:
        """查询访客意图识别历史
        
        Args:
            device_id: 设备ID
            limit: 返回记录数量限制
            offset: 偏移量（用于分页）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            
        Returns:
            (访客意图记录列表, 总记录数)
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # 构建WHERE条件
            where_conditions = ["session_id LIKE %s"]
            params = [f"{device_id}_%"]
            
            if start_date:
                where_conditions.append("created_at >= %s")
                params.append(start_date)
            
            if end_date:
                where_conditions.append("created_at <= %s")
                params.append(end_date)
            
            where_clause = " AND ".join(where_conditions)
            
            # 查询总记录数
            count_query = f"""
                SELECT COUNT(*) as total
                FROM doorlock_visitor_intents
                WHERE {where_clause}
            """
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']
            
            # 查询记录列表
            query = f"""
                SELECT id, visit_id, session_id, person_id, intent_type,
                       intent_summary, dialogue_history, created_at
                FROM doorlock_visitor_intents
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(query, params + [limit, offset])
            
            results = []
            for row in cursor.fetchall():
                # 解析JSON字段
                intent_summary = json.loads(row['intent_summary']) if row.get('intent_summary') else {}
                dialogue_history = json.loads(row['dialogue_history']) if row.get('dialogue_history') else []
                
                results.append(VisitorIntent(
                    id=row['id'],
                    visit_id=row.get('visit_id'),
                    session_id=row['session_id'],
                    person_id=row.get('person_id'),
                    intent_type=row.get('intent_type', 'other'),
                    intent_summary=intent_summary,
                    dialogue_history=dialogue_history,
                    created_at=row.get('created_at')
                ))
            
            logger.bind(tag=TAG).debug(
                f"查询访客意图历史成功: device_id={device_id}, count={len(results)}, total={total}"
            )
            return results, total
            
        except mysql.connector.Error as e:
            logger.bind(tag=TAG).error(f"查询访客意图历史失败: device_id={device_id}, error={e}")
            return [], 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    # ==================== 快递警报记录管理 ====================
    
    async def save_package_alert(self, alert: PackageAlert) -> int:
        """保存快递警报记录
        
        Args:
            alert: 快递警报对象
            
        Returns:
            插入记录的ID，失败返回0
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO doorlock_package_alerts
                (device_id, session_id, threat_level, action, description,
                 photo_path, voice_warning_sent, notified)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                alert.device_id,
                alert.session_id,
                alert.threat_level,
                alert.action,
                alert.description,
                alert.photo_path,
                alert.voice_warning_sent,
                alert.notified
            ))
            
            conn.commit()
            record_id = cursor.lastrowid
            logger.bind(tag=TAG).info(
                f"保存快递警报记录成功: id={record_id}, device_id={alert.device_id}, "
                f"threat_level={alert.threat_level}, action={alert.action}"
            )
            return record_id
            
        except mysql.connector.Error as e:
            logger.bind(tag=TAG).error(
                f"保存快递警报记录失败: device_id={alert.device_id}, "
                f"session_id={alert.session_id}, error={e}"
            )
            if conn:
                conn.rollback()
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    async def get_package_alerts(
        self, 
        device_id: str, 
        limit: int = 20,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> tuple[List[PackageAlert], int]:
        """查询快递警报历史
        
        Args:
            device_id: 设备ID
            limit: 返回记录数量限制
            offset: 偏移量（用于分页）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            
        Returns:
            (快递警报记录列表, 总记录数)
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # 构建WHERE条件
            where_conditions = ["device_id = %s"]
            params = [device_id]
            
            if start_date:
                where_conditions.append("created_at >= %s")
                params.append(start_date)
            
            if end_date:
                where_conditions.append("created_at <= %s")
                params.append(end_date)
            
            where_clause = " AND ".join(where_conditions)
            
            # 查询总记录数
            count_query = f"""
                SELECT COUNT(*) as total
                FROM doorlock_package_alerts
                WHERE {where_clause}
            """
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']
            
            # 查询记录列表
            query = f"""
                SELECT id, device_id, session_id, threat_level, action, description,
                       photo_path, voice_warning_sent, notified, created_at
                FROM doorlock_package_alerts
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(query, params + [limit, offset])
            
            results = []
            for row in cursor.fetchall():
                results.append(PackageAlert(
                    id=row['id'],
                    device_id=row['device_id'],
                    session_id=row['session_id'],
                    threat_level=row['threat_level'],
                    action=row['action'],
                    description=row.get('description', ''),
                    photo_path=row.get('photo_path', ''),
                    voice_warning_sent=bool(row.get('voice_warning_sent', False)),
                    notified=bool(row.get('notified', False)),
                    created_at=row.get('created_at')
                ))
            
            logger.bind(tag=TAG).debug(
                f"查询快递警报历史成功: device_id={device_id}, count={len(results)}, total={total}"
            )
            return results, total
            
        except mysql.connector.Error as e:
            logger.bind(tag=TAG).error(f"查询快递警报历史失败: device_id={device_id}, error={e}")
            return [], 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    # ==================== 欢迎词配置管理 ====================
    
    async def get_person_greeting(self, person_id: int) -> Optional[dict]:
        """获取用户欢迎词配置
        
        Args:
            person_id: 用户ID
            
        Returns:
            欢迎词配置字典（JSON格式），如果不存在返回None
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT custom_greeting
                FROM persons
                WHERE id = %s
            """, (person_id,))
            
            row = cursor.fetchone()
            
            if row and row.get('custom_greeting'):
                try:
                    # 尝试解析JSON
                    greeting = json.loads(row['custom_greeting'])
                    logger.bind(tag=TAG).debug(f"获取用户欢迎词成功: person_id={person_id}")
                    return greeting
                except json.JSONDecodeError:
                    # 如果不是JSON格式，返回为default字段
                    logger.bind(tag=TAG).warning(f"欢迎词不是JSON格式: person_id={person_id}")
                    return {"default": row['custom_greeting']}
            
            logger.bind(tag=TAG).debug(f"用户欢迎词不存在: person_id={person_id}")
            return None
            
        except mysql.connector.Error as e:
            logger.bind(tag=TAG).error(f"获取用户欢迎词失败: person_id={person_id}, error={e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    async def update_person_greeting(self, person_id: int, greeting: dict) -> bool:
        """更新用户欢迎词配置
        
        Args:
            person_id: 用户ID
            greeting: 欢迎词配置字典（JSON格式）
            
        Returns:
            是否更新成功
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 将字典转换为JSON字符串
            greeting_json = json.dumps(greeting, ensure_ascii=False)
            
            cursor.execute("""
                UPDATE persons
                SET custom_greeting = %s
                WHERE id = %s
            """, (greeting_json, person_id))
            
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.bind(tag=TAG).info(f"更新用户欢迎词成功: person_id={person_id}")
                return True
            else:
                logger.bind(tag=TAG).warning(f"用户不存在: person_id={person_id}")
                return False
            
        except mysql.connector.Error as e:
            logger.bind(tag=TAG).error(f"更新用户欢迎词失败: person_id={person_id}, error={e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # ==================== 设备事件和日志查询 ====================
    
    def get_events(self, device_id: str, event_type: str = None, 
                   limit: int = 100, offset: int = 0) -> Tuple[List[dict], int]:
        """查询设备事件历史（带分页）
        
        Args:
            device_id: 设备 ID
            event_type: 事件类型过滤（可选）
            limit: 每页数量
            offset: 偏移量
            
        Returns:
            (记录列表, 总数)
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # 构建查询条件
            where_sql = "device_id = %s"
            params = [device_id]
            if event_type:
                where_sql += " AND event_type = %s"
                params.append(event_type)
            
            # 查询总数
            cursor.execute(f"SELECT COUNT(*) as total FROM device_events WHERE {where_sql}", params)
            total = cursor.fetchone()['total']
            
            # 查询记录
            cursor.execute(f"""
                SELECT id, event_type, param, created_at
                FROM device_events 
                WHERE {where_sql}
                ORDER BY created_at DESC LIMIT %s OFFSET %s
            """, params + [limit, offset])
            records = cursor.fetchall()
            
            # 转换 datetime 为字符串
            for r in records:
                if r.get('created_at'):
                    try:
                        r['created_at'] = r['created_at'].isoformat()
                    except (AttributeError, ValueError) as e:
                        logger.bind(tag=TAG).warning(f"转换 created_at 失败: {e}")
                        r['created_at'] = str(r['created_at'])
            
            return records, total
        except Exception as e:
            logger.bind(tag=TAG).error(f"查询事件历史失败: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def get_unlock_logs(self, device_id: str, method: str = None, 
                        result: int = None, limit: int = 100, 
                        offset: int = 0) -> Tuple[List[dict], int]:
        """查询开锁日志（带分页）
        
        Args:
            device_id: 设备 ID
            method: 开锁方式过滤（可选）
            result: 结果过滤（可选，1=成功，0=失败）
            limit: 每页数量
            offset: 偏移量
            
        Returns:
            (记录列表, 总数)
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # 构建查询条件
            where_clauses = ["device_id = %s"]
            params = [device_id]
            
            if method:
                where_clauses.append("method = %s")
                params.append(method)
            
            if result is not None:
                # result 字段在数据库中可能是 TINYINT 类型
                # status 字段是 VARCHAR，需要根据实际表结构调整
                where_clauses.append("(result = %s OR status = %s)")
                status_str = "success" if result == 1 else "fail"
                params.extend([result, status_str])
            
            where_sql = " AND ".join(where_clauses)
            
            # 查询总数
            cursor.execute(f"SELECT COUNT(*) as total FROM unlock_logs WHERE {where_sql}", params)
            total = cursor.fetchone()['total']
            
            # 查询记录
            cursor.execute(f"""
                SELECT id, method, user_id, result, status, fail_count, lock_time, created_at
                FROM unlock_logs 
                WHERE {where_sql}
                ORDER BY created_at DESC LIMIT %s OFFSET %s
            """, params + [limit, offset])
            records = cursor.fetchall()
            
            # 转换 datetime 为字符串
            for r in records:
                if r.get('created_at'):
                    try:
                        r['created_at'] = r['created_at'].isoformat()
                    except (AttributeError, ValueError) as e:
                        logger.bind(tag=TAG).warning(f"转换 created_at 失败: {e}")
                        r['created_at'] = str(r['created_at'])
            
            return records, total
        except Exception as e:
            logger.bind(tag=TAG).error(f"查询开锁日志失败: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
