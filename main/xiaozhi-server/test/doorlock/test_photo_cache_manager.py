"""
照片缓存管理器测试

测试PhotoCacheManager的所有功能：
- 单例模式
- 添加照片到缓存
- 获取最新照片
- 超过10张照片时自动清理
- 清理缓存
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.providers.doorlock.photo_cache_manager import PhotoCacheManager


def test_singleton_pattern():
    """测试单例模式"""
    print("\n=== 测试1: 单例模式 ===")
    
    manager1 = PhotoCacheManager()
    manager2 = PhotoCacheManager()
    
    assert manager1 is manager2, "[FAIL] 单例模式失败：两个实例不相同"
    print("[PASS] 单例模式正常：两个实例是同一个对象")


def test_add_photo():
    """测试添加照片到缓存"""
    print("\n=== 测试2: 添加照片到缓存 ===")
    
    manager = PhotoCacheManager()
    session_id = "test_session_1"
    
    # 清理可能存在的旧缓存
    manager.clear_cache(session_id)
    
    # 添加一张照片
    photo_data = b"fake_photo_data_1"
    manager.add_photo(session_id, photo_data)
    
    cache_size = manager.get_cache_size(session_id)
    assert cache_size == 1, f"[FAIL] 缓存数量错误：期望1，实际{cache_size}"
    print(f"[PASS] 添加照片成功，当前缓存数量: {cache_size}")
    
    # 添加第二张照片
    photo_data2 = b"fake_photo_data_2"
    manager.add_photo(session_id, photo_data2)
    
    cache_size = manager.get_cache_size(session_id)
    assert cache_size == 2, f"[FAIL] 缓存数量错误：期望2，实际{cache_size}"
    print(f"[PASS] 添加第二张照片成功，当前缓存数量: {cache_size}")


def test_get_latest_photo():
    """测试获取最新照片"""
    print("\n=== 测试3: 获取最新照片 ===")
    
    manager = PhotoCacheManager()
    session_id = "test_session_2"
    
    # 清理缓存
    manager.clear_cache(session_id)
    
    # 测试空缓存
    latest = manager.get_latest_photo(session_id)
    assert latest is None, "[FAIL] 空缓存应返回None"
    print("[PASS] 空缓存返回None")
    
    # 添加照片
    photo_data1 = b"photo_1"
    photo_data2 = b"photo_2"
    photo_data3 = b"photo_3"
    
    manager.add_photo(session_id, photo_data1)
    manager.add_photo(session_id, photo_data2)
    manager.add_photo(session_id, photo_data3)
    
    # 获取最新照片
    latest = manager.get_latest_photo(session_id)
    assert latest is not None, "[FAIL] 获取最新照片失败"
    
    # 验证是最新的照片（photo_3）
    import base64
    expected = base64.b64encode(photo_data3).decode('utf-8')
    assert latest == expected, "[FAIL] 获取的不是最新照片"
    print("[PASS] 获取最新照片成功")


def test_auto_cleanup_old_photos():
    """测试超过10张照片时自动清理"""
    print("\n=== 测试4: 超过10张照片时自动清理 ===")
    
    manager = PhotoCacheManager()
    session_id = "test_session_3"
    
    # 清理缓存
    manager.clear_cache(session_id)
    
    # 添加15张照片
    for i in range(15):
        photo_data = f"photo_{i}".encode()
        manager.add_photo(session_id, photo_data)
    
    # 验证只保留了10张
    cache_size = manager.get_cache_size(session_id)
    assert cache_size == 10, f"[FAIL] 缓存数量错误：期望10，实际{cache_size}"
    print(f"[PASS] 自动清理成功，保留最新10张照片")
    
    # 验证保留的是最新的10张（photo_5到photo_14）
    import base64
    latest = manager.get_latest_photo(session_id)
    expected = base64.b64encode(b"photo_14").decode('utf-8')
    assert latest == expected, "[FAIL] 保留的不是最新照片"
    print("[PASS] 验证保留的是最新照片")


def test_clear_cache():
    """测试清理缓存"""
    print("\n=== 测试5: 清理缓存 ===")
    
    manager = PhotoCacheManager()
    session_id = "test_session_4"
    
    # 添加一些照片
    for i in range(5):
        photo_data = f"photo_{i}".encode()
        manager.add_photo(session_id, photo_data)
    
    cache_size = manager.get_cache_size(session_id)
    assert cache_size == 5, f"[FAIL] 添加照片失败：期望5，实际{cache_size}"
    print(f"[PASS] 添加5张照片成功")
    
    # 清理缓存
    manager.clear_cache(session_id)
    
    cache_size = manager.get_cache_size(session_id)
    assert cache_size == 0, f"[FAIL] 清理缓存失败：期望0，实际{cache_size}"
    print("[PASS] 清理缓存成功")
    
    # 验证获取照片返回None
    latest = manager.get_latest_photo(session_id)
    assert latest is None, "[FAIL] 清理后应返回None"
    print("[PASS] 清理后获取照片返回None")


def test_multiple_sessions():
    """测试多个session独立管理"""
    print("\n=== 测试6: 多个session独立管理 ===")
    
    manager = PhotoCacheManager()
    session1 = "session_1"
    session2 = "session_2"
    
    # 清理缓存
    manager.clear_cache(session1)
    manager.clear_cache(session2)
    
    # 为session1添加3张照片
    for i in range(3):
        manager.add_photo(session1, f"s1_photo_{i}".encode())
    
    # 为session2添加5张照片
    for i in range(5):
        manager.add_photo(session2, f"s2_photo_{i}".encode())
    
    # 验证各自的缓存数量
    size1 = manager.get_cache_size(session1)
    size2 = manager.get_cache_size(session2)
    
    assert size1 == 3, f"[FAIL] session1缓存数量错误：期望3，实际{size1}"
    assert size2 == 5, f"[FAIL] session2缓存数量错误：期望5，实际{size2}"
    print(f"[PASS] session1缓存: {size1}张，session2缓存: {size2}张")
    
    # 清理session1
    manager.clear_cache(session1)
    
    size1 = manager.get_cache_size(session1)
    size2 = manager.get_cache_size(session2)
    
    assert size1 == 0, f"[FAIL] session1清理失败：期望0，实际{size1}"
    assert size2 == 5, f"[FAIL] session2不应被清理：期望5，实际{size2}"
    print("[PASS] 清理session1后，session2不受影响")


def test_timestamp_recording():
    """测试照片时间戳记录"""
    print("\n=== 测试7: 照片时间戳记录 ===")
    
    manager = PhotoCacheManager()
    session_id = "test_session_5"
    
    # 清理缓存
    manager.clear_cache(session_id)
    
    # 添加照片
    import time
    manager.add_photo(session_id, b"photo_1")
    time.sleep(0.1)  # 等待一小段时间
    manager.add_photo(session_id, b"photo_2")
    
    # 验证缓存中有时间戳
    if session_id in manager._cache:
        entries = list(manager._cache[session_id])
        assert len(entries) == 2, "[FAIL] 缓存数量错误"
        
        # 验证每个entry都有timestamp
        for entry in entries:
            assert 'timestamp' in entry, "[FAIL] 缺少timestamp字段"
            assert 'photo' in entry, "[FAIL] 缺少photo字段"
        
        # 验证时间戳是递增的
        ts1 = entries[0]['timestamp']
        ts2 = entries[1]['timestamp']
        assert ts2 > ts1, "[FAIL] 时间戳应该递增"
        
        print("[PASS] 照片时间戳记录正常")
    else:
        raise AssertionError("[FAIL] session不存在")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始测试 PhotoCacheManager")
    print("=" * 60)
    
    try:
        test_singleton_pattern()
        test_add_photo()
        test_get_latest_photo()
        test_auto_cleanup_old_photos()
        test_clear_cache()
        test_multiple_sessions()
        test_timestamp_recording()
        
        print("\n" + "=" * 60)
        print("[PASS] 所有测试通过！")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n[FAIL] 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
