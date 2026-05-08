# 智能门锁 AI 功能测试指南

## 目录

1. [测试概述](#测试概述)
2. [测试环境配置](#测试环境配置)
3. [单元测试](#单元测试)
4. [集成测试](#集成测试)
5. [测试编写指南](#测试编写指南)
6. [测试覆盖率](#测试覆盖率)
7. [常见问题](#常见问题)

---

## 测试概述

智能门锁 AI 功能的测试分为两个层次：

### 单元测试

测试单个模块或类的功能，使用 mock 模拟外部依赖。

**测试范围**：

- 数据模型（`models.py`）
- 数据库服务（`doorlock_database.py`）
- 会话管理器（`session_manager.py`）
- 看护模式管理器（`package_guard_manager.py`）
- 工具函数（`doorlock_tools.py`）
- 人脸识别处理器（`face_recognition_handler.py`）
- 欢迎词处理器（`greeting_handler.py`）
- 意图识别处理器（`doorlock_intent_handler.py`）

### 集成测试

测试多个模块协同工作的完整流程。

**测试范围**：

- 完整访客流程（PIR 触发 → 人脸识别 → 意图识别 → 通知 App）
- 看护模式流程（启用 → 监控 → 威胁检测 → 关闭）
- 人脸识别重试流程
- 并发访客处理

### 测试覆盖率要求

- **单元测试覆盖率**: > 80%
- **核心功能覆盖率**: > 90%
- **关键路径覆盖率**: 100%

---

## 测试环境配置

### 1. Python 环境要求

**Python 版本**: 3.10+

**安装依赖**：

```bash
cd main/xiaozhi-server

# 安装项目依赖
pip install -r requirements.txt

# 安装测试依赖
pip install pytest pytest-asyncio pytest-cov pytest-mock
```

### 2. 数据库配置

#### 方案 A: 使用测试数据库（推荐）

创建独立的测试数据库，避免影响生产数据。

```sql
-- 创建测试数据库
CREATE DATABASE xiaozhi_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 授权
GRANT ALL PRIVILEGES ON xiaozhi_test.* TO 'xiaozhi_user'@'localhost';
FLUSH PRIVILEGES;
```

**配置测试数据库连接**：

编辑 `test/doorlock/conftest.py`，设置测试数据库配置：

```python
@pytest.fixture
def test_config():
    """测试配置"""
    return {
        "mysql": {
            "host": "localhost",
            "port": 3306,
            "user": "xiaozhi_user",
            "password": "your_password",
            "database": "xiaozhi_test"  # 使用测试数据库
        }
    }
```

**执行测试数据库迁移**：

```bash
cd main/xiaozhi-server/migrations

# 修改迁移脚本，指向测试数据库
# 然后执行迁移
python run_doorlock_ai_migration.py
```

#### 方案 B: 使用 SQLite（轻量级）

如果不想配置 MySQL 测试库，可以使用 SQLite 进行单元测试。

```python
# 在 conftest.py 中配置
@pytest.fixture
def test_config():
    """测试配置（使用 SQLite）"""
    return {
        "mysql": {
            "database": ":memory:"  # 内存数据库
        }
    }
```

### 3. Mock 服务配置

测试时需要 mock 以下外部服务：

- **VLLM 服务**: 视觉语言模型
- **人脸识别服务**: 人脸识别 API
- **TTS 服务**: 语音合成
- **ASR 服务**: 语音识别
- **ESP32 设备**: 拍照、PIR 传感器

**Mock 配置示例**（在 `conftest.py` 中）：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_vllm_service():
    """Mock VLLM 服务"""
    mock = AsyncMock()
    mock.analyze.return_value = {
        "success": True,
        "tool_calls": [],
        "response": "测试响应"
    }
    return mock

@pytest.fixture
def mock_face_service():
    """Mock 人脸识别服务"""
    mock = AsyncMock()
    mock.recognize.return_value = {
        "success": True,
        "person_id": 5,
        "name": "张三"
    }
    return mock

@pytest.fixture
def mock_tts_service():
    """Mock TTS 服务"""
    mock = AsyncMock()
    mock.speak.return_value = True
    return mock
```

### 4. 测试数据准备

#### 准备测试图片

```bash
# 创建测试图片目录
mkdir -p main/xiaozhi-server/test/fixtures/images

# 准备测试图片（可以使用任意图片）
# - baseline.jpg: 基准图片
# - visitor.jpg: 访客照片
# - alert.jpg: 警报照片
```

#### 准备测试数据库记录

```sql
-- 插入测试设备配置
INSERT INTO doorlock_config (device_id, intent_recognition_enabled, package_guard_available)
VALUES ('test_device', TRUE, TRUE);

-- 插入测试用户
INSERT INTO persons (name, is_owner, custom_greeting)
VALUES
  ('张三', TRUE, '{"default": "欢迎回家，张三"}'),
  ('李四', FALSE, '{"default": "欢迎回家，李四"}');
```

---

## 单元测试

### 运行单元测试

#### 运行所有单元测试

```bash
cd main/xiaozhi-server

# 运行所有测试
pytest test/doorlock/ -v

# 运行特定测试文件
pytest test_doorlock_models.py -v

# 运行特定测试函数
pytest test_doorlock_models.py::test_doorlock_config -v
```

#### 运行测试并查看覆盖率

```bash
# 生成覆盖率报告
pytest test/doorlock/ --cov=core/providers/doorlock --cov-report=html

# 查看覆盖率报告
# 打开 htmlcov/index.html
```

#### 运行测试并输出详细日志

```bash
# 显示 print 输出
pytest test/doorlock/ -v -s

# 显示日志输出
pytest test/doorlock/ -v --log-cli-level=INFO
```

### 单元测试示例

#### 测试数据模型

```python
# test_doorlock_models.py
import pytest
from datetime import datetime
from core.providers.doorlock.models import DoorlockConfig, VisitorIntent, PackageAlert

def test_doorlock_config():
    """测试 DoorlockConfig 数据类"""
    config = DoorlockConfig(
        device_id="device001",
        intent_recognition_enabled=True,
        package_guard_available=True
    )

    assert config.device_id == "device001"
    assert config.intent_recognition_enabled is True
    assert config.package_guard_available is True
    assert config.package_guard_active is False

def test_visitor_intent():
    """测试 VisitorIntent 数据类"""
    intent = VisitorIntent(
        session_id="device001_1234567890",
        person_id=5,
        intent_type="visit",
        intent_summary={"purpose": "拜访朋友"}
    )

    assert intent.session_id == "device001_1234567890"
    assert intent.person_id == 5
    assert intent.intent_type == "visit"
    assert intent.intent_summary["purpose"] == "拜访朋友"

def test_package_alert():
    """测试 PackageAlert 数据类"""
    alert = PackageAlert(
        device_id="device001",
        session_id="device001_1234567890",
        threat_level="high",
        action="taking",
        description="检测到陌生人拿走快递"
    )

    assert alert.device_id == "device001"
    assert alert.threat_level == "high"
    assert alert.action == "taking"
    assert alert.voice_warning_sent is False
```

#### 测试数据库服务

```python
# test_doorlock_database.py
import pytest
from core.providers.doorlock.doorlock_database import DoorlockDatabase
from core.providers.doorlock.models import DoorlockConfig

@pytest.mark.asyncio
async def test_get_config(test_config):
    """测试获取设备配置"""
    db = DoorlockDatabase(test_config)

    # 获取配置
    config = await db.get_config("test_device")

    assert config is not None
    assert config.device_id == "test_device"
    assert isinstance(config.intent_recognition_enabled, bool)

@pytest.mark.asyncio
async def test_update_config(test_config):
    """测试更新设备配置"""
    db = DoorlockDatabase(test_config)

    # 获取现有配置
    config = await db.get_config("test_device")

    # 修改配置
    config.intent_recognition_enabled = False

    # 更新配置
    success = await db.update_config(config)

    assert success is True

    # 验证更新
    updated_config = await db.get_config("test_device")
    assert updated_config.intent_recognition_enabled is False
```

#### 测试会话管理器

```python
# test_session_manager.py
import pytest
from core.providers.doorlock.session_manager import SessionManager

def test_create_session():
    """测试创建会话"""
    manager = SessionManager()

    session = manager.create_session("device001")

    assert session.device_id == "device001"
    assert session.session_id.startswith("device001_")
    assert len(session.dialogue_history) == 0

def test_get_session():
    """测试获取会话"""
    manager = SessionManager()

    # 创建会话
    session = manager.create_session("device001")
    session_id = session.session_id

    # 获取会话
    retrieved_session = manager.get_session(session_id)

    assert retrieved_session is not None
    assert retrieved_session.session_id == session_id

def test_cleanup_session():
    """测试清除会话"""
    manager = SessionManager()

    # 创建会话
    session = manager.create_session("device001")
    session_id = session.session_id

    # 清除会话
    manager.cleanup_session(session_id)

    # 验证会话已清除
    retrieved_session = manager.get_session(session_id)
    assert retrieved_session is None
```

#### 测试欢迎词选择算法

```python
# test_greeting_handler.py
import pytest
from datetime import datetime
from core.providers.doorlock.greeting_handler import GreetingHandler

def test_select_morning_greeting():
    """测试早晨欢迎词选择"""
    handler = GreetingHandler({})

    greeting = {
        "morning": "早上好",
        "default": "欢迎回家"
    }

    # 早晨 8:00
    result = handler.select_greeting(greeting, datetime(2026, 2, 9, 8, 0))
    assert result == "早上好"

def test_select_default_greeting():
    """测试默认欢迎词选择"""
    handler = GreetingHandler({})

    greeting = {"default": "欢迎回家"}

    # 早晨 8:00，但未配置 morning
    result = handler.select_greeting(greeting, datetime(2026, 2, 9, 8, 0))
    assert result == "欢迎回家"

def test_select_fallback_greeting():
    """测试回退欢迎词"""
    handler = GreetingHandler({})

    greeting = {}  # 空配置

    # 应该返回默认的"欢迎回家"
    result = handler.select_greeting(greeting, datetime(2026, 2, 9, 8, 0))
    assert result == "欢迎回家"
```

---

## 集成测试

### 运行集成测试

```bash
cd main/xiaozhi-server

# 运行集成测试
pytest test/doorlock/test_integration.py -v

# 运行特定集成测试
pytest test/doorlock/test_integration.py::test_visitor_flow -v
```

### 集成测试示例

#### 测试完整访客流程

```python
# test/doorlock/test_integration.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_visitor_flow(test_config, mock_face_service, mock_vllm_service, mock_tts_service):
    """测试完整访客流程"""
    from core.handle.doorlock_intent_handler import DoorlockIntentHandler

    # 创建处理器
    handler = DoorlockIntentHandler(test_config)

    # Mock 外部服务
    with patch.object(handler, 'face_service', mock_face_service), \
         patch.object(handler, 'vllm_service', mock_vllm_service), \
         patch.object(handler, 'tts_service', mock_tts_service):

        # 模拟访客到访
        await handler.handle_visitor("test_device", "test_session_001")

        # 验证人脸识别被调用
        mock_face_service.recognize.assert_called_once()

        # 验证 VLLM 被调用
        mock_vllm_service.analyze.assert_called()

        # 验证 TTS 被调用
        mock_tts_service.speak.assert_called()
```

#### 测试看护模式流程

```python
@pytest.mark.asyncio
async def test_package_guard_flow(test_config, mock_vllm_service):
    """测试看护模式流程"""
    from core.providers.doorlock.package_guard_manager import PackageGuardManager

    # 创建管理器
    manager = PackageGuardManager(test_config)

    # Mock VLLM 服务
    with patch.object(manager, 'vllm_service', mock_vllm_service):
        # 启用看护模式
        success = await manager.enable_guard("test_device", "测试启用")
        assert success is True

        # 验证看护模式已激活
        is_active = await manager.is_active("test_device")
        assert is_active is True

        # 关闭看护模式
        success = await manager.disable_guard("test_device", "测试关闭")
        assert success is True

        # 验证看护模式已关闭
        is_active = await manager.is_active("test_device")
        assert is_active is False
```

#### 测试人脸识别重试

```python
@pytest.mark.asyncio
async def test_face_recognition_retry(test_config, mock_face_service, mock_tts_service):
    """测试人脸识别重试流程"""
    from core.providers.doorlock.face_recognition_handler import FaceRecognitionHandler

    # 创建处理器
    handler = FaceRecognitionHandler(test_config)

    # Mock 人脸识别服务（前两次失败，第三次成功）
    mock_face_service.recognize.side_effect = [
        {"success": False},
        {"success": False},
        {"success": True, "person_id": 5, "name": "张三"}
    ]

    with patch.object(handler, 'face_service', mock_face_service), \
         patch.object(handler, 'tts_service', mock_tts_service):

        # 执行人脸识别（带重试）
        result = await handler.recognize_with_retry("test_device", max_retries=3)

        # 验证调用了3次
        assert mock_face_service.recognize.call_count == 3

        # 验证最终成功
        assert result["success"] is True
        assert result["person_id"] == 5

        # 验证播放了语音提示（第一次失败时）
        mock_tts_service.speak.assert_called_once()
```

---

## 测试编写指南

### 测试结构

推荐使用 AAA（Arrange-Act-Assert）模式：

```python
def test_example():
    # Arrange（准备）：设置测试数据和环境
    config = DoorlockConfig(device_id="test_device")

    # Act（执行）：执行被测试的操作
    result = config.device_id

    # Assert（断言）：验证结果
    assert result == "test_device"
```

### Mock 使用指南

#### 使用 pytest-mock

```python
def test_with_mocker(mocker):
    """使用 mocker fixture"""
    # Mock 函数
    mock_func = mocker.patch('module.function')
    mock_func.return_value = "mocked_value"

    # 调用被测试代码
    result = call_function_that_uses_mock()

    # 验证
    assert result == "mocked_value"
    mock_func.assert_called_once()
```

#### 使用 unittest.mock

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_patch():
    """使用 patch 装饰器"""
    with patch('module.async_function', new_callable=AsyncMock) as mock_func:
        mock_func.return_value = "mocked_value"

        # 调用被测试代码
        result = await call_async_function()

        # 验证
        assert result == "mocked_value"
```

### 断言方式

#### 基本断言

```python
# 相等断言
assert value == expected

# 布尔断言
assert condition is True
assert condition is False

# None 断言
assert value is None
assert value is not None

# 包含断言
assert item in collection
assert item not in collection
```

#### 异常断言

```python
import pytest

def test_exception():
    """测试异常抛出"""
    with pytest.raises(ValueError) as exc_info:
        raise ValueError("错误信息")

    assert "错误信息" in str(exc_info.value)
```

#### 近似断言

```python
import pytest

def test_approximate():
    """测试浮点数近似相等"""
    assert 0.1 + 0.2 == pytest.approx(0.3)
```

### 异步测试

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """测试异步函数"""
    result = await async_function()
    assert result == expected_value
```

### Fixture 使用

```python
import pytest

@pytest.fixture
def sample_data():
    """提供测试数据"""
    return {"key": "value"}

def test_with_fixture(sample_data):
    """使用 fixture"""
    assert sample_data["key"] == "value"

@pytest.fixture
async def async_fixture():
    """异步 fixture"""
    # Setup
    resource = await create_resource()
    yield resource
    # Teardown
    await cleanup_resource(resource)
```

### 参数化测试

```python
import pytest

@pytest.mark.parametrize("input,expected", [
    ("morning", "早上好"),
    ("afternoon", "下午好"),
    ("evening", "晚上好"),
    ("night", "夜深了"),
])
def test_greeting_selection(input, expected):
    """参数化测试欢迎词选择"""
    result = select_greeting_by_time(input)
    assert result == expected
```

---

## 测试覆盖率

### 生成覆盖率报告

```bash
# 生成 HTML 覆盖率报告
pytest test/doorlock/ --cov=core/providers/doorlock --cov-report=html

# 生成终端覆盖率报告
pytest test/doorlock/ --cov=core/providers/doorlock --cov-report=term

# 生成 XML 覆盖率报告（用于 CI/CD）
pytest test/doorlock/ --cov=core/providers/doorlock --cov-report=xml
```

### 查看覆盖率报告

```bash
# 打开 HTML 报告
# Windows
start htmlcov/index.html

# macOS
open htmlcov/index.html

# Linux
xdg-open htmlcov/index.html
```

### 覆盖率要求

| 模块类型     | 覆盖率要求 |
| ------------ | ---------- |
| 数据模型     | > 90%      |
| 数据库服务   | > 85%      |
| 核心业务逻辑 | > 90%      |
| 工具函数     | > 80%      |
| API 处理器   | > 80%      |
| 整体覆盖率   | > 80%      |

### 提高覆盖率的建议

1. **测试边界条件**: 测试空值、极值、异常输入
2. **测试错误路径**: 不仅测试成功场景，也要测试失败场景
3. **测试异常处理**: 确保异常被正确捕获和处理
4. **测试并发场景**: 测试多线程/多协程场景
5. **测试集成点**: 测试模块之间的交互

---

## 常见问题

### Q1: 如何运行单个测试文件？

```bash
pytest test_doorlock_models.py -v
```

### Q2: 如何运行单个测试函数？

```bash
pytest test_doorlock_models.py::test_doorlock_config -v
```

### Q3: 如何查看测试输出（print 语句）？

```bash
pytest test_doorlock_models.py -v -s
```

### Q4: 如何跳过某些测试？

```python
import pytest

@pytest.mark.skip(reason="暂时跳过")
def test_something():
    pass

@pytest.mark.skipif(condition, reason="条件不满足时跳过")
def test_conditional():
    pass
```

### Q5: 如何标记慢速测试？

```python
import pytest

@pytest.mark.slow
def test_slow_operation():
    """慢速测试"""
    pass
```

运行时排除慢速测试：

```bash
pytest -m "not slow"
```

### Q6: 测试数据库连接失败怎么办？

**检查配置**：

```python
# 在 conftest.py 中打印配置
print(test_config["mysql"])
```

**检查数据库**：

```bash
mysql -u xiaozhi_user -p -e "SHOW DATABASES;"
```

**使用 SQLite 替代**：

```python
@pytest.fixture
def test_config():
    return {
        "mysql": {
            "database": ":memory:"
        }
    }
```

### Q7: 异步测试报错 "RuntimeError: Event loop is closed"？

**解决方法**：安装 `pytest-asyncio` 并使用 `@pytest.mark.asyncio` 装饰器。

```bash
pip install pytest-asyncio
```

```python
import pytest

@pytest.mark.asyncio
async def test_async():
    result = await async_function()
    assert result == expected
```

### Q8: Mock 不生效怎么办？

**检查 patch 路径**：

```python
# 错误：patch 导入路径
with patch('original.module.function'):
    pass

# 正确：patch 使用路径
with patch('test.module.function'):
    pass
```

**使用 spec 参数**：

```python
mock = AsyncMock(spec=RealClass)
```

### Q9: 如何测试日志输出？

```python
import pytest
from loguru import logger

def test_logging(caplog):
    """测试日志输出"""
    with caplog.at_level("INFO"):
        logger.info("测试日志")

    assert "测试日志" in caplog.text
```

### Q10: 如何清理测试数据？

```python
@pytest.fixture
async def clean_database(test_config):
    """清理测试数据"""
    # Setup: 创建测试数据
    yield

    # Teardown: 清理测试数据
    db = DoorlockDatabase(test_config)
    await db.execute("DELETE FROM doorlock_visitor_intents WHERE session_id LIKE 'test_%'")
    await db.execute("DELETE FROM doorlock_package_alerts WHERE device_id = 'test_device'")
```

---

## 持续集成（CI/CD）

### GitHub Actions 配置示例

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      mysql:
        image: mysql:5.7
        env:
          MYSQL_ROOT_PASSWORD: root
          MYSQL_DATABASE: xiaozhi_test
        ports:
          - 3306:3306

    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: "3.10"

      - name: Install dependencies
        run: |
          cd main/xiaozhi-server
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Run tests
        run: |
          cd main/xiaozhi-server
          pytest test/doorlock/ --cov=core/providers/doorlock --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          file: ./coverage.xml
```

---

## 总结

### 测试最佳实践

1. **测试先行**: 编写代码前先写测试（TDD）
2. **小而专注**: 每个测试只测试一个功能点
3. **独立性**: 测试之间不应相互依赖
4. **可重复**: 测试结果应该是确定的
5. **快速执行**: 单元测试应该快速完成
6. **清晰命名**: 测试名称应该清楚描述测试内容
7. **充分断言**: 验证所有重要的输出和副作用

### 测试清单

- [ ] 所有数据模型都有单元测试
- [ ] 所有数据库操作都有单元测试
- [ ] 所有业务逻辑都有单元测试
- [ ] 所有 API 接口都有单元测试
- [ ] 完整流程有集成测试
- [ ] 错误场景有测试覆盖
- [ ] 边界条件有测试覆盖
- [ ] 测试覆盖率 > 80%
- [ ] 所有测试都能通过
- [ ] 测试文档完整清晰

---

## 参考资源

- [pytest 官方文档](https://docs.pytest.org/)
- [pytest-asyncio 文档](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock 文档](https://docs.python.org/3/library/unittest.mock.html)
- [pytest-cov 文档](https://pytest-cov.readthedocs.io/)

---

## 更新日志

### v1.0.0 (2026-02-09)

- 初始版本发布
- 单元测试指南
- 集成测试指南
- 测试编写指南
- 覆盖率要求说明
