"""
测试人脸识别：用 faces 目录中已注册的照片测试能否被识别出来
"""
import sys
import os
from pathlib import Path

# 确保项目路径在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import face_recognition
import numpy as np
from PIL import Image
import io


def load_image(path):
    """加载图片并转为 numpy 数组"""
    with open(path, 'rb') as f:
        jpeg_data = f.read()
    image = Image.open(io.BytesIO(jpeg_data))
    return np.array(image.convert('RGB')), jpeg_data


def test_face_detection():
    """测试每张照片是否能检测到人脸"""
    faces_dir = Path("data/face_recognition/faces")
    
    print("=" * 60)
    print("测试 1：检测每张注册照片中是否有人脸")
    print("=" * 60)
    
    for person_dir in sorted(faces_dir.iterdir()):
        if not person_dir.is_dir():
            continue
        for face_file in person_dir.iterdir():
            if not face_file.suffix.lower() in ('.jpg', '.jpeg', '.png'):
                continue
            
            image, raw_data = load_image(face_file)
            print(f"\n文件: {face_file}")
            print(f"  图片大小: {len(raw_data)} bytes")
            print(f"  图片尺寸: {image.shape[1]}x{image.shape[0]}")
            
            # 检测人脸（使用 hog 模型，和服务一致）
            face_locations = face_recognition.face_locations(image, model='hog')
            print(f"  检测到人脸数量: {len(face_locations)}")
            
            if face_locations:
                # 提取编码
                encodings = face_recognition.face_encodings(image, face_locations)
                print(f"  人脸编码数量: {len(encodings)}")
                if encodings:
                    print(f"  编码维度: {len(encodings[0])}")
            else:
                print(f"  ⚠️ 未检测到人脸！")


def test_self_recognition():
    """测试：用注册照片识别自己（应该能匹配）"""
    faces_dir = Path("data/face_recognition/faces")
    
    print("\n" + "=" * 60)
    print("测试 2：用注册照片识别自己（自我比对）")
    print("=" * 60)
    
    # 收集所有人脸编码
    all_encodings = []  # [(person_dir_name, encoding)]
    
    for person_dir in sorted(faces_dir.iterdir()):
        if not person_dir.is_dir():
            continue
        for face_file in person_dir.iterdir():
            if not face_file.suffix.lower() in ('.jpg', '.jpeg', '.png'):
                continue
            
            image, _ = load_image(face_file)
            face_locations = face_recognition.face_locations(image, model='hog')
            if face_locations:
                encodings = face_recognition.face_encodings(image, face_locations)
                if encodings:
                    all_encodings.append((person_dir.name, encodings[0]))
    
    print(f"\n成功加载 {len(all_encodings)} 个人脸编码")
    
    if len(all_encodings) < 2:
        print("编码数量不足，无法进行比对测试")
        return
    
    # 用每个人的照片去比对所有人
    print(f"\n比对结果（tolerance=0.6）：")
    print("-" * 60)
    
    for i, (name_i, enc_i) in enumerate(all_encodings):
        known_faces = [enc for _, enc in all_encodings]
        distances = face_recognition.face_distance(known_faces, enc_i)
        
        print(f"\n{name_i} 与各人的距离：")
        for j, (name_j, _) in enumerate(all_encodings):
            match = "✅ 匹配" if distances[j] <= 0.6 else "❌ 不匹配"
            self_mark = " (自己)" if i == j else ""
            print(f"  vs {name_j}: {distances[j]:.4f} {match}{self_mark}")


def test_with_database():
    """测试：通过 FaceService 的完整流程识别"""
    faces_dir = Path("data/face_recognition/faces")
    
    print("\n" + "=" * 60)
    print("测试 3：通过 FaceService 完整流程识别")
    print("=" * 60)
    
    try:
        from core.providers.doorlock.face_service import FaceService
        
        face_service = FaceService()
        print(f"FaceService 初始化成功")
        print(f"  tolerance: {face_service.tolerance}")
        print(f"  model: {face_service.model}")
        
        # 用每张注册照片测试识别
        for person_dir in sorted(faces_dir.iterdir()):
            if not person_dir.is_dir():
                continue
            for face_file in person_dir.iterdir():
                if not face_file.suffix.lower() in ('.jpg', '.jpeg', '.png'):
                    continue
                
                with open(face_file, 'rb') as f:
                    jpeg_data = f.read()
                
                result = face_service.recognize(jpeg_data)
                
                person_name = result.person.name if result.person else "无"
                person_id = result.person.id if result.person else "无"
                
                print(f"\n文件: {face_file.name} ({person_dir.name})")
                print(f"  识别结果: {result.result}")
                print(f"  匹配人员: {person_name} (ID: {person_id})")
                print(f"  置信度: {result.confidence:.4f}")
                
    except Exception as e:
        print(f"FaceService 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_face_detection()
    test_self_recognition()
    test_with_database()
