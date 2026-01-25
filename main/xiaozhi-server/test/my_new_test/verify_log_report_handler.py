"""
验证 LogReportHandler 的 v5.2 更新（独立测试）

测试场景：
1. v5.2 新版格式（status + lock_time）
2. v5.0 旧版格式兼容（result）
3. 字段验证（status 取值、lock_time 验证）
4. 日志输出增强
"""
import asyncio
import json


class MockLogger:
    """模拟日志记录器"""
    def __init__(self):
        self.logs = []
    
    def bind(self, tag):
        return self
    
    def debug(self, msg):
        self.logs.append(('DEBUG', msg))
        print(f"[DEBUG] {msg}")
    
    def info(self, msg):
        self.logs.append(('INFO', msg))
        print(f"[INFO] {msg}")
    
    def warning(self, msg):
        self.logs.append(('WARNING', msg))
        print(f"[WARNING] {msg}")
    
    def error(self, msg):
        self.logs.append(('ERROR', msg))
        print(f"[ERROR] {msg}")


class MockConnection:
    """模拟连接对象"""
    def __init__(self):
        self.device_id = "test_device_001"
        self.logger = MockLogger()
        self.websocket = None


async def simulate_handle(conn, msg_json):
    """模拟 LogReportHandler.handle() 的核心逻辑"""
    TAG = "LogReportHandler"
    
    try:
        ts = msg_json.get("ts")
        data = msg_json.get("data", {})
        
        method = data.get("method")
        uid = data.get("uid", 0)
        fail_count = data.get("fail_count", 0)
        
        # 子任务 7.1: 支持 status 字段
        # 子任务 7.2: 兼容旧版 result 字段
        if "status" in data:
            # v5.2 新版格式
            status = data["status"]
            lock_time = data.get("lock_time", 0)
        elif "result" in data:
            # v5.0 旧版格式兼容
            result = data["result"]
            status = "success" if result else "fail"
            lock_time = 0
            conn.logger.bind(tag=TAG).debug(
                f"兼容旧版 result 字段: result={result} -> status={status}"
            )
        else:
            conn.logger.bind(tag=TAG).error("缺少 status 或 result 字段")
            return
        
        # 子任务 7.3: 验证字段取值
        if status not in ["success", "fail", "locked"]:
            conn.logger.bind(tag=TAG).error(f"无效的 status 值: {status}")
            return
        
        # 验证 locked 状态时 lock_time 必须 > 0
        if status == "locked" and lock_time <= 0:
            conn.logger.bind(tag=TAG).warning(
                f"locked 状态但 lock_time 无效: {lock_time}，应该 > 0"
            )
        
        # 验证 success/fail 状态时 lock_time 应该为 0
        if status in ["success", "fail"] and lock_time != 0:
            conn.logger.bind(tag=TAG).warning(
                f"{status} 状态但 lock_time 不为 0: {lock_time}，应该为 0"
            )
        
        # 子任务 7.5: 增强日志输出（包含 status 和 lock_time）
        if status == "success":
            conn.logger.bind(tag=TAG).info(
                f"开锁成功: method={method}, uid={uid}, status={status}"
            )
        elif status == "locked":
            conn.logger.bind(tag=TAG).warning(
                f"设备已锁定: method={method}, uid={uid}, status={status}, lock_time={lock_time}分钟"
            )
        else:  # fail
            conn.logger.bind(tag=TAG).warning(
                f"开锁失败: method={method}, uid={uid}, status={status}, fail_count={fail_count}"
            )
            
            # 连续失败次数过多，触发警报
            if fail_count >= 5:
                conn.logger.bind(tag=TAG).error(
                    f"连续开锁失败 {fail_count} 次，触发警报"
                )
        
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"处理开锁日志失败: {e}")


async def test_v52_success_format():
    """测试 v5.2 成功格式"""
    print("\n=== 测试 1: v5.2 成功格式 ===")
    
    conn = MockConnection()
    
    msg_json = {
        "type": "log_report",
        "ts": 1702234567890,
        "data": {
            "method": "finger",
            "uid": 5,
            "status": "success",
            "lock_time": 0,
            "fail_count": 0
        }
    }
    
    try:
        await simulate_handle(conn, msg_json)
        print("✓ v5.2 成功格式处理成功")
        
        # 验证日志
        info_logs = [log for log in conn.logger.logs if log[0] == 'INFO']
        assert len(info_logs) > 0, "应该有 INFO 日志"
        assert "status=success" in info_logs[0][1], "日志应包含 status"
        print("✓ 日志包含 status 字段")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
    
    return True


async def test_v52_locked_format():
    """测试 v5.2 锁定格式"""
    print("\n=== 测试 2: v5.2 锁定格式 ===")
    
    conn = MockConnection()
    
    msg_json = {
        "type": "log_report",
        "ts": 1702234567890,
        "data": {
            "method": "pwd",
            "uid": 3,
            "status": "locked",
            "lock_time": 30,
            "fail_count": 5
        }
    }
    
    try:
        await simulate_handle(conn, msg_json)
        print("✓ v5.2 锁定格式处理成功")
        
        # 验证日志
        warning_logs = [log for log in conn.logger.logs if log[0] == 'WARNING']
        assert len(warning_logs) > 0, "应该有 WARNING 日志"
        assert "status=locked" in warning_logs[0][1], "日志应包含 status=locked"
        assert "lock_time=30" in warning_logs[0][1], "日志应包含 lock_time"
        print("✓ 日志包含 status 和 lock_time 字段")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
    
    return True


async def test_v50_compatibility():
    """测试 v5.0 兼容性"""
    print("\n=== 测试 3: v5.0 旧版格式兼容 ===")
    
    conn = MockConnection()
    
    # 旧版格式：使用 result 字段
    msg_json = {
        "type": "log_report",
        "ts": 1702234567890,
        "data": {
            "method": "nfc",
            "uid": 7,
            "result": True,
            "fail_count": 0
        }
    }
    
    try:
        await simulate_handle(conn, msg_json)
        print("✓ v5.0 旧版格式处理成功")
        
        # 验证兼容性日志
        debug_logs = [log for log in conn.logger.logs if log[0] == 'DEBUG']
        compat_log = [log for log in debug_logs if "兼容旧版 result 字段" in log[1]]
        assert len(compat_log) > 0, "应该有兼容性日志"
        assert "result=True -> status=success" in compat_log[0][1], "应该转换为 status=success"
        print("✓ 旧版 result 字段正确转换为 status")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
    
    return True


async def test_invalid_status():
    """测试无效的 status 值"""
    print("\n=== 测试 4: 无效的 status 值 ===")
    
    conn = MockConnection()
    
    msg_json = {
        "type": "log_report",
        "ts": 1702234567890,
        "data": {
            "method": "finger",
            "uid": 5,
            "status": "invalid_status",
            "lock_time": 0,
            "fail_count": 0
        }
    }
    
    try:
        await simulate_handle(conn, msg_json)
        
        # 验证错误日志
        error_logs = [log for log in conn.logger.logs if log[0] == 'ERROR']
        assert len(error_logs) > 0, "应该有 ERROR 日志"
        assert "无效的 status 值" in error_logs[0][1], "应该记录无效 status 错误"
        print("✓ 无效 status 值被正确拒绝")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
    
    return True


async def test_locked_without_lock_time():
    """测试 locked 状态但 lock_time 无效"""
    print("\n=== 测试 5: locked 状态但 lock_time 无效 ===")
    
    conn = MockConnection()
    
    msg_json = {
        "type": "log_report",
        "ts": 1702234567890,
        "data": {
            "method": "pwd",
            "uid": 3,
            "status": "locked",
            "lock_time": 0,  # 应该 > 0
            "fail_count": 5
        }
    }
    
    try:
        await simulate_handle(conn, msg_json)
        
        # 验证警告日志
        warning_logs = [log for log in conn.logger.logs if log[0] == 'WARNING']
        lock_time_warning = [log for log in warning_logs if "lock_time 无效" in log[1]]
        assert len(lock_time_warning) > 0, "应该有 lock_time 无效的警告"
        print("✓ locked 状态的 lock_time 验证正确")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
    
    return True


async def test_success_with_lock_time():
    """测试 success 状态但 lock_time 不为 0"""
    print("\n=== 测试 6: success 状态但 lock_time 不为 0 ===")
    
    conn = MockConnection()
    
    msg_json = {
        "type": "log_report",
        "ts": 1702234567890,
        "data": {
            "method": "finger",
            "uid": 5,
            "status": "success",
            "lock_time": 10,  # 应该为 0
            "fail_count": 0
        }
    }
    
    try:
        await simulate_handle(conn, msg_json)
        
        # 验证警告日志
        warning_logs = [log for log in conn.logger.logs if log[0] == 'WARNING']
        lock_time_warning = [log for log in warning_logs if "lock_time 不为 0" in log[1]]
        assert len(lock_time_warning) > 0, "应该有 lock_time 不为 0 的警告"
        print("✓ success 状态的 lock_time 验证正确")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
    
    return True


async def test_missing_status_and_result():
    """测试缺少 status 和 result 字段"""
    print("\n=== 测试 7: 缺少 status 和 result 字段 ===")
    
    conn = MockConnection()
    
    msg_json = {
        "type": "log_report",
        "ts": 1702234567890,
        "data": {
            "method": "finger",
            "uid": 5,
            "fail_count": 0
        }
    }
    
    try:
        await simulate_handle(conn, msg_json)
        
        # 验证错误日志
        error_logs = [log for log in conn.logger.logs if log[0] == 'ERROR']
        assert len(error_logs) > 0, "应该有 ERROR 日志"
        assert "缺少 status 或 result 字段" in error_logs[0][1], "应该记录缺少字段错误"
        print("✓ 缺少必需字段被正确拒绝")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
    
    return True


async def main():
    """运行所有测试"""
    print("开始验证 LogReportHandler v5.2 更新...")
    
    tests = [
        test_v52_success_format,
        test_v52_locked_format,
        test_v50_compatibility,
        test_invalid_status,
        test_locked_without_lock_time,
        test_success_with_lock_time,
        test_missing_status_and_result,
    ]
    
    results = []
    for test in tests:
        result = await test()
        results.append(result)
    
    print("\n" + "="*50)
    print(f"测试完成: {sum(results)}/{len(results)} 通过")
    
    if all(results):
        print("✓ 所有测试通过！")
        return 0
    else:
        print("✗ 部分测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
