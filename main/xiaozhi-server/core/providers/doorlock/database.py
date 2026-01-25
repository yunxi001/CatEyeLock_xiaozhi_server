"""
智能门锁数据库操作模块
"""
import pickle
import hashlib
import base64
import numpy as np
import mysql.connector
from mysql.connector import pooling
from datetime import datetime, date, time, timedelta
from typing import List, Optional, Tuple
from .models import Person, AccessPermission, VisitRecord

TAG = __name__


class Database:
    """MySQL 数据库操作"""
    
    def __init__(self, config: dict, logger=None, auto_init: bool = True):
        """初始化数据库连接
        
        Args:
            config: 数据库配置
            logger: 日志记录器
            auto_init: 是否自动初始化数据库表（默认 True）
                      生产环境建议设为 False，通过迁移脚本管理表结构
        """
        self.config = config
        self.logger = logger
        self.pool = None
        
        # 可选的自动初始化（开发环境方便，生产环境建议关闭）
        if auto_init:
            self._init_database()
        
        self._init_pool()
    
    def _init_pool(self):
        """初始化连接池"""
        try:
            # 先连接到 MySQL（不指定数据库）
            self.pool = pooling.MySQLConnectionPool(
                pool_name="doorlock_pool",
                pool_size=self.config.get('pool_size', 5),
                host=self.config.get('host', '127.0.0.1'),
                port=self.config.get('port', 3306),
                user=self.config.get('user', 'root'),
                password=self.config.get('password', ''),
                database=self.config.get('database', 'smart_doorlock'),
                charset='utf8mb4'
            )
        except mysql.connector.Error as e:
            if self.logger:
                self.logger.bind(tag=TAG).error(f"数据库连接池初始化失败: {e}")
            raise
    
    def _init_database(self):
        """初始化数据库和表"""
        conn = None
        cursor = None
        try:
            # 先不指定数据库连接
            conn = mysql.connector.connect(
                host=self.config.get('host', '127.0.0.1'),
                port=self.config.get('port', 3306),
                user=self.config.get('user', 'root'),
                password=self.config.get('password', ''),
                charset='utf8mb4'
            )
            cursor = conn.cursor()
            
            # 创建数据库
            db_name = self.config.get('database', 'smart_doorlock')
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.execute(f"USE {db_name}")
            
            # 创建 persons 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS persons (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(50) NOT NULL,
                    relation_type ENUM('family', 'friend', 'colleague', 'property', 'courier', 'delivery', 'tutor', 'classmate', 'other') NOT NULL DEFAULT 'other',
                    face_encoding BLOB,
                    photo_path VARCHAR(255),
                    custom_greeting VARCHAR(255),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 创建 access_permissions 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS access_permissions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    person_id INT NOT NULL,
                    permission_type ENUM('permanent', 'temporary') NOT NULL DEFAULT 'permanent',
                    time_start TIME DEFAULT '00:00:00',
                    time_end TIME DEFAULT '23:59:59',
                    day_type ENUM('daily', 'weekly', 'monthly') NOT NULL DEFAULT 'daily',
                    week_days VARCHAR(20),
                    month_days VARCHAR(100),
                    remaining_count INT DEFAULT 1,
                    valid_from DATE,
                    valid_until DATE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # 创建 visit_records 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS visit_records (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    person_id INT,
                    recognition_result ENUM('known', 'unknown', 'no_face') NOT NULL,
                    access_granted BOOLEAN DEFAULT FALSE,
                    deny_reason VARCHAR(100),
                    photo_path VARCHAR(255),
                    visit_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    notified BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # 创建 device_info 表（设备基本信息）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device_info (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    device_id VARCHAR(64) NOT NULL UNIQUE COMMENT '设备 ID',
                    password_encrypted VARCHAR(255) DEFAULT NULL COMMENT '加密后的密码',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_device_id (device_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备基本信息表'
            """)
            
            # 创建 device_status 表（设备状态记录）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device_status (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    device_id VARCHAR(64) NOT NULL,
                    battery INT,
                    lux INT,
                    lock_state TINYINT,
                    light_state TINYINT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_device_time (device_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # 创建 device_events 表（设备事件记录）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device_events (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    device_id VARCHAR(64) NOT NULL,
                    event_type VARCHAR(32) NOT NULL,
                    param INT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_device_time (device_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # 创建 unlock_logs 表（开锁日志记录）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS unlock_logs (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    device_id VARCHAR(64) NOT NULL,
                    method VARCHAR(16) NOT NULL,
                    user_id INT,
                    result TINYINT,
                    fail_count INT DEFAULT 0,
                    status VARCHAR(16) DEFAULT 'success' COMMENT '状态：success/fail/locked',
                    lock_time INT DEFAULT 0 COMMENT '剩余锁定时间（分钟）',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_device_time (device_id, created_at),
                    INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # 创建 door_opened_logs 表（开门日志记录）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS door_opened_logs (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    device_id VARCHAR(64) NOT NULL COMMENT '设备 ID',
                    method VARCHAR(16) NOT NULL COMMENT '开锁方式',
                    source VARCHAR(16) NOT NULL COMMENT '开门来源: outside/inside/unknown',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    INDEX idx_device_time (device_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='开门日志表'
            """)
            
            # 创建 doorlock_users 表（门锁用户信息）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS doorlock_users (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    device_id VARCHAR(64) NOT NULL,
                    user_id INT NOT NULL,
                    name VARCHAR(64),
                    role VARCHAR(16) DEFAULT 'member',
                    finger_ids JSON,
                    nfc_ids JSON,
                    face_registered TINYINT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_device_user (device_id, user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # 创建 media_files 表（媒体文件元数据）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS media_files (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    device_id VARCHAR(64) NOT NULL,
                    file_type VARCHAR(16) NOT NULL,
                    file_path VARCHAR(256) NOT NULL,
                    file_size INT,
                    duration INT,
                    user_id INT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_device_type_time (device_id, file_type, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            conn.commit()
            if self.logger:
                self.logger.bind(tag=TAG).info("数据库表初始化完成")
                
        except mysql.connector.Error as e:
            if self.logger:
                self.logger.bind(tag=TAG).error(f"数据库初始化失败: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def get_connection(self):
        """获取数据库连接
        
        Returns:
            数据库连接对象
            
        Raises:
            mysql.connector.PoolError: 连接池耗尽
            mysql.connector.Error: 其他数据库错误
        """
        try:
            return self.pool.get_connection()
        except mysql.connector.PoolError as e:
            if self.logger:
                self.logger.bind(tag=TAG).error(f"数据库连接池耗尽: {e}")
            raise
        except mysql.connector.Error as e:
            if self.logger:
                self.logger.bind(tag=TAG).error(f"获取数据库连接失败: {e}")
            raise
    
    # ==================== 序列化方法 ====================
    
    @staticmethod
    def serialize_encoding(encoding: np.ndarray) -> bytes:
        """序列化人脸编码为 bytes"""
        return pickle.dumps(encoding)
    
    @staticmethod
    def deserialize_encoding(data: bytes) -> np.ndarray:
        """反序列化 bytes 为人脸编码"""
        return pickle.loads(data)
    
    # ==================== 密码加密/解密方法 ====================
    
    @staticmethod
    def encrypt_password(password: str) -> str:
        """加密密码（使用 SHA256 + Base64）
        
        Args:
            password: 明文密码
            
        Returns:
            加密后的密码字符串
        """
        # 使用 SHA256 哈希
        hash_obj = hashlib.sha256(password.encode('utf-8'))
        # Base64 编码
        encrypted = base64.b64encode(hash_obj.digest()).decode('utf-8')
        return encrypted
    
    @staticmethod
    def decrypt_password(encrypted_password: str) -> str:
        """解密密码（SHA256 是单向哈希，这里实际上是存储原文的 Base64）
        
        注意：为了支持查询返回明文，我们改用可逆加密
        这里使用简单的 Base64 编码（生产环境应使用 AES 等对称加密）
        
        Args:
            encrypted_password: 加密后的密码
            
        Returns:
            明文密码
        """
        try:
            # 简单的 Base64 解码（实际存储时我们会用 Base64 编码明文）
            decrypted = base64.b64decode(encrypted_password.encode('utf-8')).decode('utf-8')
            return decrypted
        except Exception:
            # 如果解密失败，返回默认密码
            return "123456"
    
    @staticmethod
    def encode_password_simple(password: str) -> str:
        """简单编码密码（Base64，可逆）
        
        Args:
            password: 明文密码
            
        Returns:
            编码后的密码字符串
        """
        return base64.b64encode(password.encode('utf-8')).decode('utf-8')

    # ==================== Person CRUD ====================
    
    def save_person(self, person: Person) -> int:
        """保存人员信息，返回 person_id"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            encoding_blob = self.serialize_encoding(person.face_encoding) if person.face_encoding is not None else None
            cursor.execute("""
                INSERT INTO persons (name, relation_type, face_encoding, photo_path, custom_greeting)
                VALUES (%s, %s, %s, %s, %s)
            """, (person.name, person.relation_type, encoding_blob, person.photo_path, person.custom_greeting))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()
    
    def get_person(self, person_id: int) -> Optional[Person]:
        """获取单个人员信息"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM persons WHERE id = %s", (person_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_person(row)
            return None
        finally:
            cursor.close()
            conn.close()
    
    def get_all_persons(self) -> List[Person]:
        """获取所有人员"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM persons ORDER BY created_at DESC")
            return [self._row_to_person(row) for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()
    
    def get_all_encodings(self) -> List[Tuple[int, np.ndarray]]:
        """获取所有人脸编码用于比对，返回 [(person_id, encoding), ...]"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, face_encoding FROM persons WHERE face_encoding IS NOT NULL")
            result = []
            for row in cursor.fetchall():
                person_id, encoding_blob = row
                if encoding_blob:
                    encoding = self.deserialize_encoding(encoding_blob)
                    result.append((person_id, encoding))
            return result
        finally:
            cursor.close()
            conn.close()
    
    def delete_person(self, person_id: int) -> bool:
        """删除人员"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM persons WHERE id = %s", (person_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
            conn.close()
    
    def _row_to_person(self, row: dict) -> Person:
        """将数据库行转换为 Person 对象"""
        encoding = None
        if row.get('face_encoding'):
            encoding = self.deserialize_encoding(row['face_encoding'])
        return Person(
            id=row['id'],
            name=row['name'],
            relation_type=row['relation_type'],
            face_encoding=encoding,
            photo_path=row.get('photo_path', ''),
            custom_greeting=row.get('custom_greeting'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )

    # ==================== Permission CRUD ====================
    
    def save_permission(self, perm: AccessPermission) -> int:
        """保存权限配置"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO access_permissions 
                (person_id, permission_type, time_start, time_end, day_type, week_days, month_days, remaining_count, valid_from, valid_until, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                perm.person_id, perm.permission_type,
                perm.time_start, perm.time_end, perm.day_type,
                perm.week_days, perm.month_days, perm.remaining_count,
                perm.valid_from, perm.valid_until, perm.is_active
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()
    
    def get_permissions(self, person_id: int) -> List[AccessPermission]:
        """获取人员的所有权限"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM access_permissions WHERE person_id = %s AND is_active = TRUE", (person_id,))
            return [self._row_to_permission(row) for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()
    
    def update_permission(self, perm: AccessPermission) -> bool:
        """更新权限"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE access_permissions SET
                permission_type = %s, time_start = %s, time_end = %s, day_type = %s,
                week_days = %s, month_days = %s, remaining_count = %s,
                valid_from = %s, valid_until = %s, is_active = %s
                WHERE id = %s
            """, (
                perm.permission_type, perm.time_start, perm.time_end, perm.day_type,
                perm.week_days, perm.month_days, perm.remaining_count,
                perm.valid_from, perm.valid_until, perm.is_active, perm.id
            ))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
            conn.close()
    
    def decrement_remaining_count(self, perm_id: int) -> bool:
        """扣减临时权限次数"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE access_permissions SET remaining_count = remaining_count - 1
                WHERE id = %s AND remaining_count > 0
            """, (perm_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
            conn.close()
    
    def _row_to_permission(self, row: dict) -> AccessPermission:
        """将数据库行转换为 AccessPermission 对象"""
        return AccessPermission(
            id=row['id'],
            person_id=row['person_id'],
            permission_type=row['permission_type'],
            time_start=self._convert_to_time(row.get('time_start')),
            time_end=self._convert_to_time(row.get('time_end')),
            day_type=row['day_type'],
            week_days=row.get('week_days'),
            month_days=row.get('month_days'),
            remaining_count=row.get('remaining_count', 1),
            valid_from=row.get('valid_from'),
            valid_until=row.get('valid_until'),
            is_active=row.get('is_active', True),
            created_at=row.get('created_at')
        )
    
    @staticmethod
    def _convert_to_time(value) -> time:
        """将数据库返回的时间值转换为 time 对象
        
        MySQL 返回的 TIME 类型可能是 timedelta 或 time 对象
        """
        if value is None:
            return time(0, 0)
        if isinstance(value, time):
            return value
        if isinstance(value, timedelta):
            # timedelta 转 time：提取时分秒
            total_seconds = int(value.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return time(hours, minutes, seconds)
        # 字符串格式
        try:
            return time.fromisoformat(str(value))
        except ValueError:
            # 处理 '8:00:00' 这种格式（缺少前导零）
            parts = str(value).split(':')
            return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)

    # ==================== VisitRecord CRUD ====================
    
    def save_visit(self, visit: VisitRecord) -> int:
        """保存到访记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO visit_records 
                (person_id, recognition_result, access_granted, deny_reason, photo_path, visit_time, notified)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                visit.person_id, visit.recognition_result, visit.access_granted,
                visit.deny_reason, visit.photo_path, visit.visit_time or datetime.now(), visit.notified
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()
    
    def get_visits(self, page: int = 1, page_size: int = 20, 
                   date_from: date = None, date_to: date = None) -> Tuple[List[dict], int]:
        """获取到访记录（分页），返回 (records, total)"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # 构建查询条件
            where_clauses = []
            params = []
            if date_from:
                where_clauses.append("DATE(visit_time) >= %s")
                params.append(date_from)
            if date_to:
                where_clauses.append("DATE(visit_time) <= %s")
                params.append(date_to)
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # 查询总数
            cursor.execute(f"SELECT COUNT(*) as total FROM visit_records WHERE {where_sql}", params)
            total = cursor.fetchone()['total']
            
            # 查询记录
            offset = (page - 1) * page_size
            cursor.execute(f"""
                SELECT v.*, p.name as person_name, p.relation_type
                FROM visit_records v
                LEFT JOIN persons p ON v.person_id = p.id
                WHERE {where_sql}
                ORDER BY v.visit_time DESC
                LIMIT %s OFFSET %s
            """, params + [page_size, offset])
            
            records = []
            for row in cursor.fetchall():
                records.append({
                    'id': row['id'],
                    'person_id': row['person_id'],
                    'person_name': row.get('person_name'),
                    'relation': row.get('relation_type'),
                    'result': row['recognition_result'],
                    'access_granted': row['access_granted'],
                    'deny_reason': row.get('deny_reason'),
                    'visit_time': row['visit_time'].isoformat() if row['visit_time'] else None,
                    'photo_path': row.get('photo_path')
                })
            
            return records, total
        finally:
            cursor.close()
            conn.close()
    
    def mark_visit_notified(self, visit_id: int) -> bool:
        """标记到访记录已通知"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE visit_records SET notified = TRUE WHERE id = %s", (visit_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
            conn.close()

    # ==================== 设备状态 CRUD ====================
    
    def save_device_status(self, device_id: str, battery: int, lux: int, 
                           lock_state: int, light_state: int) -> int:
        """保存设备状态记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO device_status (device_id, battery, lux, lock_state, light_state)
                VALUES (%s, %s, %s, %s, %s)
            """, (device_id, battery, lux, lock_state, light_state))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()
    
    def get_latest_status(self, device_id: str) -> Optional[dict]:
        """获取设备最新状态
        
        Args:
            device_id: 设备 ID
            
        Returns:
            最新状态记录，如果没有则返回 None
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT battery, lux, lock_state, light_state, created_at as last_update
                FROM device_status 
                WHERE device_id = %s 
                ORDER BY created_at DESC LIMIT 1
            """, (device_id,))
            return cursor.fetchone()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def get_status_history(self, device_id: str, limit: int = 100, 
                           offset: int = 0) -> Tuple[List[dict], int]:
        """获取设备状态历史（带分页）
        
        Args:
            device_id: 设备 ID
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
            
            # 查询总数
            cursor.execute("""
                SELECT COUNT(*) as total FROM device_status WHERE device_id = %s
            """, (device_id,))
            total = cursor.fetchone()['total']
            
            # 查询记录
            cursor.execute("""
                SELECT id, battery, lux, lock_state, light_state, created_at
                FROM device_status 
                WHERE device_id = %s 
                ORDER BY created_at DESC LIMIT %s OFFSET %s
            """, (device_id, limit, offset))
            records = cursor.fetchall()
            
            # 转换 datetime 为字符串
            for r in records:
                if r.get('created_at'):
                    try:
                        r['created_at'] = r['created_at'].isoformat()
                    except (AttributeError, ValueError) as e:
                        if self.logger:
                            self.logger.bind(tag=TAG).warning(f"转换 created_at 失败: {e}")
                        r['created_at'] = str(r['created_at'])
            
            return records, total
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def get_device_status_history(self, device_id: str, limit: int = 100) -> List[dict]:
        """获取设备状态历史（兼容旧接口）"""
        records, _ = self.get_status_history(device_id, limit)
        return records

    # ==================== 设备事件 CRUD ====================
    
    def save_device_event(self, device_id: str, event_type: str, param: int = None) -> int:
        """保存设备事件记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO device_events (device_id, event_type, param)
                VALUES (%s, %s, %s)
            """, (device_id, event_type, param))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()
    
    def get_events(self, device_id: str, event_type: str = None, 
                   limit: int = 100, offset: int = 0) -> Tuple[List[dict], int]:
        """获取设备事件历史（带分页）
        
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
                        if self.logger:
                            self.logger.bind(tag=TAG).warning(f"转换 created_at 失败: {e}")
                        r['created_at'] = str(r['created_at'])
            
            return records, total
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def get_device_events(self, device_id: str, event_type: str = None, 
                          limit: int = 100) -> List[dict]:
        """获取设备事件历史（兼容旧接口）"""
        records, _ = self.get_events(device_id, event_type, limit)
        return records

    # ==================== 开锁日志 CRUD ====================
    
    def save_unlock_log(self, device_id: str, method: str, user_id: int,
                        result: bool = None, fail_count: int = 0,
                        status: str = None, lock_time: int = 0) -> int:
        """保存开锁日志
        
        支持 v5.0 和 v5.2 两种格式：
        - v5.0: 使用 result (bool) 参数
        - v5.2: 使用 status (str) 和 lock_time (int) 参数
        
        Args:
            device_id: 设备 ID
            method: 开锁方式
            user_id: 用户 ID
            result: 开锁结果（旧版，bool）
            fail_count: 连续失败次数
            status: 开锁状态（新版，success/fail/locked）
            lock_time: 剩余锁定时间（分钟）
            
        Returns:
            插入记录的 ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 如果没有提供 status，从 result 转换
            if status is None:
                if result is None:
                    raise ValueError("必须提供 result 或 status 参数")
                status = "success" if result else "fail"
                lock_time = 0
            
            cursor.execute("""
                INSERT INTO unlock_logs (device_id, method, user_id, result, fail_count, status, lock_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (device_id, method, user_id, 1 if status == "success" else 0, fail_count, status, lock_time))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()
    
    def get_unlock_logs(self, device_id: str, method: str = None, 
                        result: int = None, limit: int = 100, 
                        offset: int = 0) -> Tuple[List[dict], int]:
        """获取开锁日志历史（带分页和过滤）
        
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
            where_sql = "device_id = %s"
            params = [device_id]
            if method:
                where_sql += " AND method = %s"
                params.append(method)
            if result is not None:
                where_sql += " AND result = %s"
                params.append(result)
            
            # 查询总数
            cursor.execute(f"SELECT COUNT(*) as total FROM unlock_logs WHERE {where_sql}", params)
            total = cursor.fetchone()['total']
            
            # 查询记录
            cursor.execute(f"""
                SELECT id, method, user_id, result, fail_count, created_at
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
                        if self.logger:
                            self.logger.bind(tag=TAG).warning(f"转换 created_at 失败: {e}")
                        r['created_at'] = str(r['created_at'])
            
            return records, total
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    # ==================== 开门日志 CRUD ====================
    
    def save_door_opened_log(self, device_id: str, method: str, source: str) -> int:
        """保存开门日志
        
        Args:
            device_id: 设备 ID
            method: 开锁方式
            source: 开门来源 (outside/inside/unknown)
            
        Returns:
            插入记录的 ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO door_opened_logs (device_id, method, source)
                VALUES (%s, %s, %s)
            """, (device_id, method, source))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()
    
    def get_door_opened_logs(self, device_id: str, method: str = None,
                             source: str = None, limit: int = 100,
                             offset: int = 0) -> Tuple[List[dict], int]:
        """获取开门日志历史（带分页和过滤）
        
        Args:
            device_id: 设备 ID
            method: 开锁方式过滤（可选）
            source: 开门来源过滤（可选）
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
            if method:
                where_sql += " AND method = %s"
                params.append(method)
            if source:
                where_sql += " AND source = %s"
                params.append(source)
            
            # 查询总数
            cursor.execute(f"SELECT COUNT(*) as total FROM door_opened_logs WHERE {where_sql}", params)
            total = cursor.fetchone()['total']
            
            # 查询记录
            cursor.execute(f"""
                SELECT id, method, source, created_at
                FROM door_opened_logs 
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
                        if self.logger:
                            self.logger.bind(tag=TAG).warning(f"转换 created_at 失败: {e}")
                        r['created_at'] = str(r['created_at'])
            
            return records, total
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def get_media_file_by_id(self, file_id: int) -> Optional[dict]:
        """根据 ID 获取单个媒体文件信息
        
        Args:
            file_id: 媒体文件 ID
            
        Returns:
            文件信息字典，如果不存在则返回 None
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, device_id, file_type, file_path, file_size, duration, user_id, created_at
                FROM media_files 
                WHERE id = %s
            """, (file_id,))
            record = cursor.fetchone()
            if record and record.get('created_at'):
                try:
                    record['created_at'] = record['created_at'].isoformat()
                except (AttributeError, ValueError) as e:
                    if self.logger:
                        self.logger.bind(tag=TAG).warning(f"转换 created_at 失败: {e}")
                    record['created_at'] = str(record['created_at'])
            return record
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # ==================== 门锁用户 CRUD ====================
    
    def save_doorlock_user(self, device_id: str, user_id: int, name: str = None,
                           role: str = 'member') -> int:
        """保存门锁用户"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO doorlock_users (device_id, user_id, name, role)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE name = VALUES(name), role = VALUES(role)
            """, (device_id, user_id, name, role))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()
    
    def update_doorlock_user_finger(self, device_id: str, user_id: int, 
                                     finger_ids: list) -> bool:
        """更新用户指纹 ID 列表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            import json
            cursor.execute("""
                UPDATE doorlock_users SET finger_ids = %s
                WHERE device_id = %s AND user_id = %s
            """, (json.dumps(finger_ids), device_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
            conn.close()
    
    def update_doorlock_user_nfc(self, device_id: str, user_id: int, 
                                  nfc_ids: list) -> bool:
        """更新用户 NFC ID 列表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            import json
            cursor.execute("""
                UPDATE doorlock_users SET nfc_ids = %s
                WHERE device_id = %s AND user_id = %s
            """, (json.dumps(nfc_ids), device_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
            conn.close()
    
    def get_doorlock_users(self, device_id: str) -> List[dict]:
        """获取设备的所有用户"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT * FROM doorlock_users WHERE device_id = %s
            """, (device_id,))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    # ==================== 媒体文件 CRUD ====================
    
    def save_media_file(self, device_id: str, file_type: str, file_path: str,
                        file_size: int = None, duration: int = None, 
                        user_id: int = None) -> int:
        """保存媒体文件元数据"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO media_files (device_id, file_type, file_path, file_size, duration, user_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (device_id, file_type, file_path, file_size, duration, user_id))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()
    
    def get_media_files(self, device_id: str, file_type: str = None,
                        date_from: str = None, date_to: str = None,
                        limit: int = 100, offset: int = 0) -> Tuple[List[dict], int]:
        """获取媒体文件列表（带分页和日期过滤）
        
        Args:
            device_id: 设备 ID
            file_type: 文件类型过滤（可选）
            date_from: 开始日期（可选，格式 YYYY-MM-DD）
            date_to: 结束日期（可选，格式 YYYY-MM-DD）
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
            if file_type:
                where_sql += " AND file_type = %s"
                params.append(file_type)
            if date_from:
                where_sql += " AND DATE(created_at) >= %s"
                params.append(date_from)
            if date_to:
                where_sql += " AND DATE(created_at) <= %s"
                params.append(date_to)
            
            # 查询总数
            cursor.execute(f"SELECT COUNT(*) as total FROM media_files WHERE {where_sql}", params)
            total = cursor.fetchone()['total']
            
            # 查询记录
            cursor.execute(f"""
                SELECT id, file_type, file_path, file_size, duration, user_id, created_at
                FROM media_files 
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
                        if self.logger:
                            self.logger.bind(tag=TAG).warning(f"转换 created_at 失败: {e}")
                        r['created_at'] = str(r['created_at'])
            
            return records, total
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # ==================== 数据清理 ====================
    
    def cleanup_old_data(self, status_days: int = 7, event_days: int = 30, 
                         log_days: int = 90, media_days: int = 30) -> dict:
        """清理过期数据
        
        Args:
            status_days: 状态记录保留天数
            event_days: 事件记录保留天数
            log_days: 开锁日志保留天数
            media_days: 媒体文件保留天数（人脸图片）
            
        Returns:
            各表删除的记录数
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        result = {}
        try:
            # 清理设备状态
            cursor.execute("""
                DELETE FROM device_status 
                WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (status_days,))
            result['device_status'] = cursor.rowcount
            
            # 清理设备事件
            cursor.execute("""
                DELETE FROM device_events 
                WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (event_days,))
            result['device_events'] = cursor.rowcount
            
            # 清理开锁日志
            cursor.execute("""
                DELETE FROM unlock_logs 
                WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (log_days,))
            result['unlock_logs'] = cursor.rowcount
            
            # 获取需要删除的媒体文件路径
            cursor.execute("""
                SELECT file_path FROM media_files 
                WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (media_days,))
            result['media_files_paths'] = [row[0] for row in cursor.fetchall()]
            
            # 清理媒体文件记录
            cursor.execute("""
                DELETE FROM media_files 
                WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (media_days,))
            result['media_files'] = cursor.rowcount
            
            conn.commit()
            return result
        finally:
            cursor.close()
            conn.close()
    
    # ==================== 设备密码管理 ====================
    
    def init_device_password(self, device_id: str, default_password: str = "123456") -> bool:
        """初始化设备密码（如果不存在）
        
        Args:
            device_id: 设备 ID
            default_password: 默认密码，默认为 "123456"
            
        Returns:
            是否成功初始化
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 检查设备是否已存在
            cursor.execute("SELECT id FROM device_info WHERE device_id = %s", (device_id,))
            if cursor.fetchone():
                # 设备已存在，不需要初始化
                return True
            
            # 加密密码
            encrypted = self.encode_password_simple(default_password)
            
            # 插入设备信息
            cursor.execute("""
                INSERT INTO device_info (device_id, password_encrypted)
                VALUES (%s, %s)
            """, (device_id, encrypted))
            conn.commit()
            
            if self.logger:
                self.logger.bind(tag=TAG).info(f"设备 {device_id} 密码已初始化为默认值")
            return True
        except mysql.connector.Error as e:
            if self.logger:
                self.logger.bind(tag=TAG).error(f"初始化设备密码失败: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    
    def update_device_password(self, device_id: str, password: str) -> bool:
        """更新设备密码
        
        Args:
            device_id: 设备 ID
            password: 新密码（明文）
            
        Returns:
            是否更新成功
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 加密密码
            encrypted = self.encode_password_simple(password)
            
            # 更新或插入
            cursor.execute("""
                INSERT INTO device_info (device_id, password_encrypted)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE password_encrypted = VALUES(password_encrypted)
            """, (device_id, encrypted))
            conn.commit()
            
            if self.logger:
                self.logger.bind(tag=TAG).info(f"设备 {device_id} 密码已更新")
            return cursor.rowcount > 0
        except mysql.connector.Error as e:
            if self.logger:
                self.logger.bind(tag=TAG).error(f"更新设备密码失败: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    
    def get_device_password(self, device_id: str) -> Optional[str]:
        """获取设备密码（明文）
        
        Args:
            device_id: 设备 ID
            
        Returns:
            密码明文，如果不存在则返回默认密码 "123456"
        """
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT password_encrypted FROM device_info WHERE device_id = %s
            """, (device_id,))
            row = cursor.fetchone()
            
            if row and row.get('password_encrypted'):
                # 解密密码
                return self.decrypt_password(row['password_encrypted'])
            else:
                # 设备不存在或密码为空，初始化默认密码
                self.init_device_password(device_id)
                return "123456"
        except mysql.connector.Error as e:
            if self.logger:
                self.logger.bind(tag=TAG).error(f"获取设备密码失败: {e}")
            return "123456"
        finally:
            cursor.close()
            conn.close()
