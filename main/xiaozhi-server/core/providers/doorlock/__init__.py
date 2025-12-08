# 智能门锁人脸识别模块
from .models import Person, AccessPermission, VisitRecord, RecognitionResult
from .database import Database
from .face_service import FaceService

__all__ = [
    'Person',
    'AccessPermission', 
    'VisitRecord',
    'RecognitionResult',
    'Database',
    'FaceService'
]
