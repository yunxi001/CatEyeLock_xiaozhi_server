"""
智能门锁数据库操作模块
"""
import pickle
import numpy as np
import mysql.connector
from mysql.connector import pooling
from datetime import datetime, date, time, timedelta
from typing import List, Optional, Tuple
from .models import Person, AccessPermission, VisitRecord

TAG = __name__


class Database:
    """MySQL 数据库操作"""
    
    def __init__(self, config: dict, logger=None):
        self.config = config
        self.logger = logger
        self.pool = None
        # 先创建数据库和表，再初始化连接池
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
        """获取数据库连接"""
        return self.pool.get_connection()
    
    # ==================== 序列化方法 ====================
    
    @staticmethod
    def serialize_encoding(encoding: np.ndarray) -> bytes:
        """序列化人脸编码为 bytes"""
        return pickle.dumps(encoding)
    
    @staticmethod
    def deserialize_encoding(data: bytes) -> np.ndarray:
        """反序列化 bytes 为人脸编码"""
        return pickle.loads(data)

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
