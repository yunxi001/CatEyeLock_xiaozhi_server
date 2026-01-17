"""
人脸识别核心服务
"""
import os
import io
import base64
import struct
import numpy as np
from PIL import Image
from datetime import datetime, date, time as dt_time
from typing import Optional, Tuple, List
import face_recognition
import yaml

from .database import Database
from .models import Person, AccessPermission, VisitRecord, RecognitionResult

TAG = __name__


class FaceService:
    """人脸识别核心服务"""
    
    def __init__(self, config_path: str = None, logger=None):
        self.logger = logger
        self.config = self._load_config(config_path)
        self.db = Database(self.config.get('database', {}), logger)
        self.tolerance = self.config.get('recognition', {}).get('tolerance', 0.6)
        self.model = self.config.get('recognition', {}).get('model', 'hog')
        self.greetings = self.config.get('greetings', {})
        self.storage_config = self.config.get('storage', {})
        
        # 确保存储目录存在
        self._ensure_storage_dirs()
    
    def _load_config(self, config_path: str = None) -> dict:
        """加载配置文件"""
        if config_path is None:
            # 默认配置路径
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            config_path = os.path.join(base_dir, 'config', 'face_recognition_config.yaml')
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            if self.logger:
                self.logger.bind(tag=TAG).warning(f"加载配置文件失败: {e}，使用默认配置")
            return self._default_config()
    
    def _default_config(self) -> dict:
        """默认配置"""
        return {
            'database': {
                'host': '127.0.0.1',
                'port': 3306,
                'user': 'root',
                'password': '123456',
                'database': 'smart_doorlock'
            },
            'recognition': {
                'tolerance': 0.6,
                'model': 'hog'
            },
            'storage': {
                'base_dir': 'data/face_recognition',
                'faces_dir': 'data/face_recognition/faces',
                'visits_dir': 'data/face_recognition/visits'
            },
            'greetings': {
                'family': '欢迎回家，{name}！',
                'friend': '您好，{name}，欢迎来访！',
                'unknown': '您好，请问您找谁？',
                'denied': '抱歉，{name}，{reason}。'
            }
        }
    
    def _ensure_storage_dirs(self):
        """确保存储目录存在"""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        for key in ['faces_dir', 'visits_dir']:
            dir_path = os.path.join(base_dir, self.storage_config.get(key, f'data/face_recognition/{key}'))
            os.makedirs(dir_path, exist_ok=True)

    # ==================== 图像解析 ====================
    
    def parse_image(self, image_data: bytes) -> bytes:
        """解析 BinaryProtocol2 格式的图像数据
        
        Args:
            image_data: BinaryProtocol2 格式的原始 bytes 数据（ESP32 直接发送二进制，无 base64 编码）
            
        Returns:
            JPEG 图像的原始 bytes
        """
        # ESP32 直接发送二进制数据，无需 base64 解码
        raw_data = image_data
        
        # BinaryProtocol2 格式（大端序）：
        # - version: uint16_t (2 bytes)
        # - type: uint16_t (2 bytes)
        # - width: uint16_t (2 bytes) - 图像宽度
        # - height: uint16_t (2 bytes) - 图像高度
        # - timestamp: uint32_t (4 bytes)
        # - payload_size: uint32_t (4 bytes)
        # - payload: uint8_t[] (变长)
        # 协议头总长度：16 bytes
        
        HEADER_SIZE = 16
        
        if len(raw_data) < HEADER_SIZE:
            raise ValueError("数据长度不足，无法解析 BinaryProtocol2 协议")
        
        # 解析协议头（大端序）
        # version = struct.unpack('>H', raw_data[0:2])[0]
        # type = struct.unpack('>H', raw_data[2:4])[0]
        # width = struct.unpack('>H', raw_data[4:6])[0]
        # height = struct.unpack('>H', raw_data[6:8])[0]
        # timestamp = struct.unpack('>I', raw_data[8:12])[0]
        payload_size = struct.unpack('>I', raw_data[12:16])[0]
        
        # 提取 JPEG payload
        jpeg_data = raw_data[HEADER_SIZE:HEADER_SIZE + payload_size]
        
        # 验证 JPEG 格式（JPEG 文件以 0xFFD8 开头）
        if len(jpeg_data) < 2 or jpeg_data[0:2] != b'\xff\xd8':
            raise ValueError("无效的 JPEG 数据")
        
        return jpeg_data
    
    def _jpeg_to_numpy(self, jpeg_data: bytes) -> np.ndarray:
        """将 JPEG 数据转换为 numpy 数组"""
        image = Image.open(io.BytesIO(jpeg_data))
        return np.array(image.convert('RGB'))
    
    # ==================== 人脸识别 ====================
    
    def recognize(self, jpeg_data: bytes) -> RecognitionResult:
        """执行人脸识别
        
        Args:
            jpeg_data: JPEG 图像的原始 bytes
            
        Returns:
            RecognitionResult 识别结果
        """
        try:
            # 转换为 numpy 数组
            image = self._jpeg_to_numpy(jpeg_data)
            
            # 检测人脸位置
            face_locations = face_recognition.face_locations(image, model=self.model)
            
            if not face_locations:
                return RecognitionResult(result='no_face')
            
            # 提取人脸编码（只取第一个人脸）
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            if not face_encodings:
                return RecognitionResult(result='no_face')
            
            target_encoding = face_encodings[0]
            
            # 从数据库获取所有已知人脸编码
            known_encodings = self.db.get_all_encodings()
            
            if not known_encodings:
                return RecognitionResult(result='unknown')
            
            # 比对人脸
            known_ids = [item[0] for item in known_encodings]
            known_faces = [item[1] for item in known_encodings]
            
            # 计算距离
            distances = face_recognition.face_distance(known_faces, target_encoding)
            
            # 找到最小距离
            min_idx = np.argmin(distances)
            min_distance = distances[min_idx]
            
            # 判断是否匹配
            if min_distance <= self.tolerance:
                person_id = known_ids[min_idx]
                person = self.db.get_person(person_id)
                confidence = 1.0 - min_distance
                return RecognitionResult(result='known', person=person, confidence=confidence)
            else:
                return RecognitionResult(result='unknown')
                
        except Exception as e:
            if self.logger:
                self.logger.bind(tag=TAG).error(f"人脸识别失败: {e}")
            return RecognitionResult(result='no_face')

    # ==================== 人脸录入 ====================
    
    def register_face(self, name: str, relation_type: str, 
                      images: List[bytes], permission: dict = None) -> Tuple[int, str]:
        """录入人脸
        
        Args:
            name: 姓名
            relation_type: 关系类型
            images: JPEG 图像列表（已解码的 bytes）
            permission: 权限配置
            
        Returns:
            (person_id, error_message) - 成功时 error_message 为 None
        """
        try:
            # 从第一张图像提取人脸编码
            if not images:
                return 0, "no_images"
            
            face_encoding = None
            for img_data in images:
                image = self._jpeg_to_numpy(img_data)
                face_locations = face_recognition.face_locations(image, model=self.model)
                
                if face_locations:
                    encodings = face_recognition.face_encodings(image, face_locations)
                    if encodings:
                        face_encoding = encodings[0]
                        break
            
            if face_encoding is None:
                return 0, "no_face_detected"
            
            # 保存人员信息
            person = Person(
                name=name,
                relation_type=relation_type,
                face_encoding=face_encoding
            )
            person_id = self.db.save_person(person)
            
            # 保存照片
            self._save_face_photo(person_id, images[0])
            
            # 创建权限
            if permission:
                perm = self._create_permission_from_dict(person_id, permission)
                self.db.save_permission(perm)
            else:
                # 默认永久权限
                perm = AccessPermission(
                    person_id=person_id,
                    permission_type='permanent',
                    day_type='daily'
                )
                self.db.save_permission(perm)
            
            return person_id, None
            
        except Exception as e:
            if self.logger:
                self.logger.bind(tag=TAG).error(f"人脸录入失败: {e}")
            return 0, str(e)
    
    def _save_face_photo(self, person_id: int, jpeg_data: bytes):
        """保存人脸照片"""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        faces_dir = os.path.join(base_dir, self.storage_config.get('faces_dir', 'data/face_recognition/faces'))
        person_dir = os.path.join(faces_dir, f'person_{person_id}')
        os.makedirs(person_dir, exist_ok=True)
        
        photo_path = os.path.join(person_dir, 'face_1.jpg')
        with open(photo_path, 'wb') as f:
            f.write(jpeg_data)
        
        # 更新数据库中的照片路径（相对路径）
        # 这里简化处理，实际可以更新 person 记录
    
    def _create_permission_from_dict(self, person_id: int, perm_dict: dict) -> AccessPermission:
        """从字典创建权限对象"""
        perm = AccessPermission(person_id=person_id)
        perm.permission_type = perm_dict.get('type', 'permanent')
        
        if 'time_start' in perm_dict:
            perm.time_start = dt_time.fromisoformat(perm_dict['time_start'])
        if 'time_end' in perm_dict:
            perm.time_end = dt_time.fromisoformat(perm_dict['time_end'])
        
        perm.day_type = perm_dict.get('day_type', 'daily')
        perm.week_days = perm_dict.get('week_days')
        perm.month_days = perm_dict.get('month_days')
        perm.remaining_count = perm_dict.get('remaining_count', 1)
        
        if 'valid_from' in perm_dict:
            perm.valid_from = date.fromisoformat(perm_dict['valid_from'])
        if 'valid_until' in perm_dict:
            perm.valid_until = date.fromisoformat(perm_dict['valid_until'])
        
        return perm

    # ==================== 权限验证 ====================
    
    def check_permission(self, person_id: int, check_time: datetime = None) -> Tuple[bool, Optional[str]]:
        """验证开门权限
        
        Args:
            person_id: 人员 ID
            check_time: 检查时间，默认当前时间
            
        Returns:
            (是否允许, 拒绝原因或 None)
        """
        if check_time is None:
            check_time = datetime.now()
        
        current_date = check_time.date()
        current_time = check_time.time()
        current_weekday = check_time.isoweekday()  # 1=周一, 7=周日
        current_day = check_time.day
        
        permissions = self.db.get_permissions(person_id)
        
        if not permissions:
            return False, "无有效权限"
        
        for perm in permissions:
            # 1. 检查有效期
            if perm.valid_from and current_date < perm.valid_from:
                continue
            if perm.valid_until and current_date > perm.valid_until:
                continue
            
            # 2. 检查时段
            if not self._check_time_range(current_time, perm.time_start, perm.time_end):
                continue
            
            # 3. 检查日期类型
            if perm.day_type == 'weekly':
                if perm.week_days:
                    allowed_days = [int(d.strip()) for d in perm.week_days.split(',') if d.strip()]
                    if current_weekday not in allowed_days:
                        continue
            elif perm.day_type == 'monthly':
                if perm.month_days:
                    allowed_days = [int(d.strip()) for d in perm.month_days.split(',') if d.strip()]
                    if current_day not in allowed_days:
                        continue
            
            # 4. 检查临时权限次数
            if perm.permission_type == 'temporary':
                if perm.remaining_count <= 0:
                    continue
                # 扣减次数
                self.db.decrement_remaining_count(perm.id)
            
            # 权限验证通过
            return True, None
        
        return False, "不在允许时段或权限已过期"
    
    def _check_time_range(self, current: dt_time, start: dt_time, end: dt_time) -> bool:
        """检查时间是否在范围内"""
        if start <= end:
            return start <= current <= end
        else:
            # 跨午夜的情况（如 22:00 - 06:00）
            return current >= start or current <= end
    
    # ==================== 问候语生成 ====================
    
    def generate_greeting(self, result: RecognitionResult, 
                          access_granted: bool, deny_reason: str = None) -> Optional[str]:
        """生成问候语
        
        Args:
            result: 识别结果
            access_granted: 是否允许开门
            deny_reason: 拒绝原因
            
        Returns:
            问候语文本，无人脸时返回 None
        """
        if result.result == 'no_face':
            return None
        
        if result.result == 'unknown':
            return self.greetings.get('unknown', '您好，请问您找谁？')
        
        # 已知人员
        if result.person:
            name = result.person.name
            relation = result.person.relation_type
            
            # 优先使用自定义问候语
            if result.person.custom_greeting:
                return result.person.custom_greeting.format(name=name)
            
            if access_granted:
                template = self.greetings.get(relation, self.greetings.get('other', '您好，{name}，请进！'))
                return template.format(name=name)
            else:
                template = self.greetings.get('denied', '抱歉，{name}，{reason}。')
                return template.format(name=name, reason=deny_reason or '当前时段不允许进入')
        
        return None

    # ==================== 到访记录 ====================
    
    def save_visit_record(self, result: RecognitionResult, access_granted: bool,
                          deny_reason: str, jpeg_data: bytes) -> int:
        """保存到访记录
        
        Returns:
            visit_id
        """
        # 保存照片
        photo_path = self._save_visit_photo(jpeg_data)
        
        visit = VisitRecord(
            person_id=result.person.id if result.person else None,
            recognition_result=result.result,
            access_granted=access_granted,
            deny_reason=deny_reason,
            photo_path=photo_path,
            visit_time=datetime.now()
        )
        
        return self.db.save_visit(visit)
    
    def _save_visit_photo(self, jpeg_data: bytes) -> str:
        """保存到访照片，返回相对路径"""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        visits_dir = os.path.join(base_dir, self.storage_config.get('visits_dir', 'data/face_recognition/visits'))
        
        # 按年月组织目录
        now = datetime.now()
        month_dir = os.path.join(visits_dir, f'{now.year}-{now.month:02d}')
        os.makedirs(month_dir, exist_ok=True)
        
        # 生成文件名
        filename = f'visit_{now.strftime("%Y%m%d_%H%M%S_%f")}.jpg'
        photo_path = os.path.join(month_dir, filename)
        
        with open(photo_path, 'wb') as f:
            f.write(jpeg_data)
        
        # 返回相对路径
        return os.path.relpath(photo_path, base_dir)
    
    def get_visits(self, page: int = 1, page_size: int = 20,
                   date_from: str = None, date_to: str = None) -> dict:
        """获取到访记录"""
        from_date = date.fromisoformat(date_from) if date_from else None
        to_date = date.fromisoformat(date_to) if date_to else None
        
        records, total = self.db.get_visits(page, page_size, from_date, to_date)
        
        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'records': records
        }
    
    # ==================== 管理功能 ====================
    
    def get_persons(self) -> List[dict]:
        """获取所有人员列表"""
        persons = self.db.get_all_persons()
        result = []
        for p in persons:
            data = p.to_dict()
            # 获取权限信息
            permissions = self.db.get_permissions(p.id)
            if permissions:
                data['permission'] = permissions[0].to_dict()
            result.append(data)
        return result
    
    def get_person(self, person_id: int) -> Optional[dict]:
        """获取单个人员详情"""
        person = self.db.get_person(person_id)
        if person:
            data = person.to_dict()
            permissions = self.db.get_permissions(person_id)
            if permissions:
                data['permission'] = permissions[0].to_dict()
            return data
        return None
    
    def delete_person(self, person_id: int) -> bool:
        """删除人员"""
        # 删除照片文件
        person = self.db.get_person(person_id)
        if person and person.photo_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            photo_full_path = os.path.join(base_dir, person.photo_path)
            if os.path.exists(photo_full_path):
                os.remove(photo_full_path)
        
        return self.db.delete_person(person_id)
    
    def update_permission(self, person_id: int, permission: dict) -> bool:
        """更新权限"""
        permissions = self.db.get_permissions(person_id)
        if permissions:
            perm = permissions[0]
            # 更新字段
            if 'type' in permission:
                perm.permission_type = permission['type']
            if 'time_start' in permission:
                perm.time_start = dt_time.fromisoformat(permission['time_start'])
            if 'time_end' in permission:
                perm.time_end = dt_time.fromisoformat(permission['time_end'])
            if 'day_type' in permission:
                perm.day_type = permission['day_type']
            if 'week_days' in permission:
                perm.week_days = permission['week_days']
            if 'month_days' in permission:
                perm.month_days = permission['month_days']
            if 'remaining_count' in permission:
                perm.remaining_count = permission['remaining_count']
            if 'valid_from' in permission:
                perm.valid_from = date.fromisoformat(permission['valid_from'])
            if 'valid_until' in permission:
                perm.valid_until = date.fromisoformat(permission['valid_until'])
            
            return self.db.update_permission(perm)
        return False
