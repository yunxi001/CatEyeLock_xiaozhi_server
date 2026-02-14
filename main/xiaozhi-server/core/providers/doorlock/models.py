"""
智能门锁AI功能数据模型

此模块定义了门锁AI功能所需的所有数据类，包括：
- DoorlockConfig: 设备配置
- VisitorIntent: 访客意图记录
- PackageAlert: 快递警报记录
- DoorlockSession: 会话数据
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
import json


@dataclass
class DoorlockConfig:
    """
    门锁设备配置数据类
    
    存储每个设备的门锁AI功能配置，包括意图识别、人脸识别和看护模式的开关状态
    """
    device_id: str
    intent_recognition_enabled: bool = True
    face_recognition_enabled: bool = True
    package_guard_available: bool = True
    package_guard_active: bool = False
    package_baseline_image: Optional[str] = None
    package_guard_start_time: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        # 处理 datetime 类型
        if self.package_guard_start_time:
            data['package_guard_start_time'] = self.package_guard_start_time.isoformat()
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        return data
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DoorlockConfig':
        """从字典创建实例"""
        # 处理 datetime 字符串
        if 'package_guard_start_time' in data and isinstance(data['package_guard_start_time'], str):
            data['package_guard_start_time'] = datetime.fromisoformat(data['package_guard_start_time'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'DoorlockConfig':
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class VisitorIntent:
    """
    访客意图识别记录数据类
    
    存储访客到访的意图识别结果，包括对话历史和意图总结
    """
    session_id: str
    id: Optional[int] = None
    visit_id: Optional[int] = None
    person_id: Optional[int] = None
    intent_type: str = "other"  # delivery/visit/sales/maintenance/other
    intent_summary: Dict[str, Any] = field(default_factory=dict)
    dialogue_history: List[Dict[str, str]] = field(default_factory=list)
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        # 处理 datetime 类型
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        return data
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VisitorIntent':
        """从字典创建实例"""
        # 处理 datetime 字符串
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        
        # 处理 JSON 字段（从数据库读取时可能是字符串）
        if 'intent_summary' in data and isinstance(data['intent_summary'], str):
            data['intent_summary'] = json.loads(data['intent_summary'])
        if 'dialogue_history' in data and isinstance(data['dialogue_history'], str):
            data['dialogue_history'] = json.loads(data['dialogue_history'])
        
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'VisitorIntent':
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def get_intent_summary_json(self) -> str:
        """获取意图总结的JSON字符串（用于数据库存储）"""
        return json.dumps(self.intent_summary, ensure_ascii=False)
    
    def get_dialogue_history_json(self) -> str:
        """获取对话历史的JSON字符串（用于数据库存储）"""
        return json.dumps(self.dialogue_history, ensure_ascii=False)


@dataclass
class PackageAlert:
    """
    快递异常警报记录数据类
    
    存储看护模式下检测到的异常行为警报
    """
    device_id: str
    session_id: str
    threat_level: str  # low/medium/high
    action: str = "normal"  # taking/searching/damaging/normal/passing
    id: Optional[int] = None
    description: str = ""
    photo_path: str = ""
    voice_warning_sent: bool = False
    notified: bool = False
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        # 处理 datetime 类型
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        return data
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PackageAlert':
        """从字典创建实例"""
        # 处理 datetime 字符串
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'PackageAlert':
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def is_high_threat(self) -> bool:
        """判断是否为高威胁"""
        return self.threat_level == "high"
    
    def is_medium_threat(self) -> bool:
        """判断是否为中威胁"""
        return self.threat_level == "medium"
    
    def is_low_threat(self) -> bool:
        """判断是否为低威胁"""
        return self.threat_level == "low"
    
    def needs_notification(self) -> bool:
        """判断是否需要发送通知（中威胁或高威胁）"""
        return self.threat_level in ["medium", "high"]


@dataclass
class DoorlockSession:
    """
    门锁会话数据类
    
    管理访客到访的完整会话，包括对话历史和拍照记录
    """
    session_id: str
    device_id: str
    dialogue_history: List[Dict[str, str]] = field(default_factory=list)
    photo_records: List[Dict[str, Any]] = field(default_factory=list)
    last_activity: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    person_id: Optional[int] = None
    person_name: Optional[str] = None
    is_owner: bool = False
    
    def add_dialogue(self, role: str, content: str):
        """
        添加对话记录
        
        Args:
            role: 角色（assistant/user）
            content: 对话内容
        """
        self.dialogue_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self.last_activity = datetime.now()
    
    def add_photo(self, photo_path: str, description: str = ""):
        """
        添加拍照记录
        
        Args:
            photo_path: 照片路径
            description: 照片描述
        """
        self.photo_records.append({
            "photo_path": photo_path,
            "description": description,
            "timestamp": datetime.now().isoformat()
        })
        self.last_activity = datetime.now()
    
    def get_recent_dialogue(self, max_rounds: int = 10) -> List[Dict[str, str]]:
        """
        获取最近的对话记录
        
        Args:
            max_rounds: 最大对话轮次
            
        Returns:
            最近的对话记录列表
        """
        # 每轮对话包含 assistant 和 user 两条消息
        max_messages = max_rounds * 2
        return self.dialogue_history[-max_messages:]
    
    def clear_old_dialogue(self, max_rounds: int = 10):
        """
        清理旧的对话记录，保留最近的对话
        
        Args:
            max_rounds: 保留的最大对话轮次
        """
        max_messages = max_rounds * 2
        if len(self.dialogue_history) > max_messages:
            self.dialogue_history = self.dialogue_history[-max_messages:]
    
    def get_silence_duration(self) -> float:
        """
        获取沉默时长（秒）
        
        Returns:
            从最后一次活动到现在的秒数
        """
        return (datetime.now() - self.last_activity).total_seconds()
    
    def is_timeout(self, timeout_seconds: int = 30) -> bool:
        """
        判断会话是否超时
        
        Args:
            timeout_seconds: 超时时间（秒）
            
        Returns:
            是否超时
        """
        return self.get_silence_duration() > timeout_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "session_id": self.session_id,
            "device_id": self.device_id,
            "dialogue_history": self.dialogue_history,
            "photo_records": self.photo_records,
            "last_activity": self.last_activity.isoformat(),
            "created_at": self.created_at.isoformat(),
            "person_id": self.person_id,
            "person_name": self.person_name,
            "is_owner": self.is_owner
        }
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DoorlockSession':
        """从字典创建实例"""
        # 处理 datetime 字符串
        if 'last_activity' in data and isinstance(data['last_activity'], str):
            data['last_activity'] = datetime.fromisoformat(data['last_activity'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'DoorlockSession':
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)


# 导出所有数据类
__all__ = [
    'DoorlockConfig',
    'VisitorIntent',
    'PackageAlert',
    'DoorlockSession'
]


# ==================== 人脸识别相关数据类 ====================

@dataclass
class Person:
    """人员信息数据类"""
    id: int
    name: str
    relation_type: str  # family, friend, worker, stranger
    face_encoding: Optional[bytes] = None
    custom_greeting: Optional[str] = None
    is_owner: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'relation_type': self.relation_type,
            'face_encoding': base64.b64encode(self.face_encoding).decode() if self.face_encoding else None,
            'custom_greeting': self.custom_greeting,
            'is_owner': self.is_owner,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Person':
        """从字典创建实例"""
        if 'face_encoding' in data and data['face_encoding']:
            data['face_encoding'] = base64.b64decode(data['face_encoding'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


@dataclass
class AccessPermission:
    """访问权限数据类"""
    id: int
    person_id: int
    permission_type: str  # unlock, view_history, manage_users
    granted_by: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'person_id': self.person_id,
            'permission_type': self.permission_type,
            'granted_by': self.granted_by,
            'valid_from': self.valid_from.isoformat() if self.valid_from else None,
            'valid_until': self.valid_until.isoformat() if self.valid_until else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AccessPermission':
        """从字典创建实例"""
        if 'valid_from' in data and isinstance(data['valid_from'], str):
            data['valid_from'] = datetime.fromisoformat(data['valid_from'])
        if 'valid_until' in data and isinstance(data['valid_until'], str):
            data['valid_until'] = datetime.fromisoformat(data['valid_until'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


@dataclass
class VisitRecord:
    """访问记录数据类"""
    id: Optional[int] = None
    person_id: Optional[int] = None
    device_id: str = ""
    visit_time: Optional[datetime] = None
    recognition_result: str = "unknown"  # known, unknown, no_face
    access_granted: bool = False
    deny_reason: Optional[str] = None
    photo_path: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'person_id': self.person_id,
            'device_id': self.device_id,
            'visit_time': self.visit_time.isoformat() if self.visit_time else None,
            'recognition_result': self.recognition_result,
            'access_granted': self.access_granted,
            'deny_reason': self.deny_reason,
            'photo_path': self.photo_path,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VisitRecord':
        """从字典创建实例"""
        if 'visit_time' in data and isinstance(data['visit_time'], str):
            data['visit_time'] = datetime.fromisoformat(data['visit_time'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


@dataclass
class RecognitionResult:
    """人脸识别结果数据类"""
    result: str  # known, unknown, no_face
    person: Optional[Person] = None
    confidence: float = 0.0
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'result': self.result,
            'person': self.person.to_dict() if self.person else None,
            'confidence': self.confidence,
            'message': self.message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RecognitionResult':
        """从字典创建实例"""
        if 'person' in data and data['person']:
            data['person'] = Person.from_dict(data['person'])
        return cls(**data)


# 更新导出列表
__all__ = [
    'DoorlockConfig',
    'VisitorIntent',
    'PackageAlert',
    'DoorlockSession',
    'Person',
    'AccessPermission',
    'VisitRecord',
    'RecognitionResult'
]
