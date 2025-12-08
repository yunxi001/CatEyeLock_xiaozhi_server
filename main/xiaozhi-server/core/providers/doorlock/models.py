"""
智能门锁数据模型
"""
from dataclasses import dataclass, field
from datetime import datetime, date, time
from typing import Optional, List
import numpy as np


# 关系类型枚举
RELATION_TYPES = [
    'family',      # 家人
    'friend',      # 朋友
    'colleague',   # 同事
    'property',    # 物业
    'courier',     # 快递
    'delivery',    # 外卖
    'tutor',       # 家教
    'classmate',   # 同学
    'other'        # 其他
]

# 权限类型枚举
PERMISSION_TYPES = ['permanent', 'temporary']

# 时段类型枚举
DAY_TYPES = ['daily', 'weekly', 'monthly']

# 识别结果枚举
RECOGNITION_RESULTS = ['known', 'unknown', 'no_face']


@dataclass
class Person:
    """人员信息"""
    id: Optional[int] = None
    name: str = ""
    relation_type: str = "other"
    face_encoding: Optional[np.ndarray] = None
    photo_path: str = ""
    custom_greeting: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """转换为字典（不含人脸编码）"""
        return {
            'id': self.id,
            'name': self.name,
            'relation_type': self.relation_type,
            'photo_path': self.photo_path,
            'custom_greeting': self.custom_greeting,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


@dataclass
class AccessPermission:
    """开门权限"""
    id: Optional[int] = None
    person_id: int = 0
    permission_type: str = "permanent"  # permanent, temporary
    time_start: time = field(default_factory=lambda: time(0, 0))
    time_end: time = field(default_factory=lambda: time(23, 59))
    day_type: str = "daily"  # daily, weekly, monthly
    week_days: Optional[str] = None  # "1,2,3,4,5" (1=周一)
    month_days: Optional[str] = None  # "1,15,30"
    remaining_count: int = 1  # 临时权限剩余次数
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'person_id': self.person_id,
            'permission_type': self.permission_type,
            'time_start': self.time_start.strftime('%H:%M') if self.time_start else None,
            'time_end': self.time_end.strftime('%H:%M') if self.time_end else None,
            'day_type': self.day_type,
            'week_days': self.week_days,
            'month_days': self.month_days,
            'remaining_count': self.remaining_count,
            'valid_from': self.valid_from.isoformat() if self.valid_from else None,
            'valid_until': self.valid_until.isoformat() if self.valid_until else None,
            'is_active': self.is_active
        }


@dataclass
class VisitRecord:
    """到访记录"""
    id: Optional[int] = None
    person_id: Optional[int] = None  # 可为 None 表示陌生人
    recognition_result: str = "unknown"  # known, unknown, no_face
    access_granted: bool = False
    deny_reason: Optional[str] = None
    photo_path: str = ""
    visit_time: Optional[datetime] = None
    notified: bool = False
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'person_id': self.person_id,
            'recognition_result': self.recognition_result,
            'access_granted': self.access_granted,
            'deny_reason': self.deny_reason,
            'photo_path': self.photo_path,
            'visit_time': self.visit_time.isoformat() if self.visit_time else None,
            'notified': self.notified
        }


@dataclass
class RecognitionResult:
    """识别结果"""
    result: str = "no_face"  # known, unknown, no_face
    person: Optional[Person] = None
    confidence: float = 0.0
    
    def to_dict(self) -> dict:
        """转换为字典"""
        data = {
            'result': self.result,
            'confidence': self.confidence
        }
        if self.person:
            data['person'] = {
                'id': self.person.id,
                'name': self.person.name,
                'relation': self.person.relation_type
            }
        return data
