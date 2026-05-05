# 门锁 VLLM 配置重构文档

## 修改目标

让门锁的 VLLM 配置完全复用系统已加载的配置，而不是独立配置。确保：

1. 门锁配置加载不影响系统配置加载流程
2. 系统配置加载完成后，门锁才加载自己的业务配置
3. 从 `config.yaml` 中移除 `DoorlockVLLM` 配置段和智能门锁AI功能配置段

## 配置架构变更

### 修改前

```
config.yaml（系统配置）
├── selected_module.VLLM: "DoorlockVLLM"  ❌ 需要独立配置
├── VLLM.DoorlockVLLM                      ❌ 独立的门锁 VLLM 配置
└── doorlock                               ❌ 门锁业务配置在系统配置中

doorlock_config.yaml（门锁独立配置）
├── mysql: 数据库配置
├── package_guard: 看护模式配置
└── performance: 性能配置
```

### 修改后

```
config.yaml（系统配置）
├── selected_module.VLLM: "ChatGLMVLLM"    ✅ 使用系统 VLLM 配置
└── VLLM.ChatGLMVLLM                       ✅ 系统 VLLM 配置（门锁复用）

doorlock_config.yaml（门锁独立配置）
├── mysql: 数据库配置
├── package_guard: 看护模式配置
├── intent_recognition: 意图识别配置
├── face_recognition: 人脸识别配置
└── performance: 性能配置
```

## 配置加载流程

### 系统启动流程

```
1. app.py 启动
   ↓
2. load_config() 加载系统配置
   ├── 从 manage-api 加载（如果配置了）
   └── 或从 config.yaml 加载
   ↓
3. HTTP Server 初始化
   ├── 传入系统配置 config
   └── 初始化 DoorlockGuardHandler(config)
   ↓
4. 延迟初始化（首次 API 调用时）
   ├── DoorlockVLLMProvider(config)  ← 复用系统配置
   └── 加载 doorlock_config.yaml    ← 仅用于业务配置
```

### 配置复用机制

```python
# DoorlockVLLMProvider 初始化
def __init__(self, config: dict, logger_instance=None):
    # 1. 从系统配置获取选中的 VLLM 模块
    selected_vllm = config.get("selected_module", {}).get("VLLM", "")
    # 例如：selected_vllm = "ChatGLMVLLM"

    # 2. 从系统配置提取 VLLM 配置
    vllm_config = config.get("VLLM", {})[selected_vllm]

    # 3. 完全复用系统配置的参数
    self.model_name = vllm_config.get("model_name")
    self.api_key = vllm_config.get("api_key")
    self.base_url = vllm_config.get("base_url")
    self.max_tokens = vllm_config.get("max_tokens", 500)
    self.temperature = vllm_config.get("temperature", 0.7)

    # 4. 仅从门锁配置读取业务参数
    doorlock_config = self._load_doorlock_config()
    self.max_token_usage_ratio = doorlock_config.get("performance", {}).get("max_token_usage_ratio", 0.8)
```

## 核心文件修改

### 1. `core/providers/vllm/doorlock_vllm.py`

**修改内容：**

- 完全复用系统已加载的 VLLM 配置
- 不再独立配置模型参数
- 仅从 `doorlock_config.yaml` 读取业务配置（Token 警告阈值）

**关键代码：**

```python
class DoorlockVLLMProvider(VLLMProviderBase):
    """门锁AI专用VLLM提供者

    复用系统已加载的 VLLM 配置，不独立配置模型参数
    """

    def __init__(self, config: dict, logger_instance=None):
        # 从系统配置获取选中的 VLLM 配置
        selected_vllm = config.get("selected_module", {}).get("VLLM", "")
        vllm_config = config.get("VLLM", {})[selected_vllm]

        # 完全复用系统配置的参数
        self.model_name = vllm_config.get("model_name")
        self.api_key = vllm_config.get("api_key")
        self.base_url = vllm_config.get("base_url")
        # ...
```

### 2. `core/api/doorlock_guard_handler.py`

**修改内容：**

- 延迟初始化机制，避免影响系统启动
- 初始化时传入系统配置，复用 VLLM 配置
- 从 `doorlock_config.yaml` 加载业务配置

**关键代码：**

```python
def _ensure_initialized(self):
    """确保看护管理器已初始化（延迟初始化，首次 API 调用时触发）

    说明：
        - 延迟初始化避免影响系统启动速度
        - VLLM 提供者复用系统已加载的配置
        - 门锁业务配置从独立文件加载
    """
    # 初始化VLLM提供者（复用系统已加载的配置）
    vllm_provider = DoorlockVLLMProvider(self.config, logger)

    # 加载门锁独立配置（仅用于业务配置）
    doorlock_config = self._load_doorlock_config()
```

### 3. `core/providers/doorlock/doorlock_database.py`

**修改内容：**

- 明确说明在系统配置加载完成后初始化
- 不依赖系统配置，使用独立的数据库配置

**关键代码：**

```python
def _load_doorlock_config() -> dict:
    """加载智能门锁独立配置文件（在系统配置加载完成后调用）"""
    # ...

class DoorlockDatabase:
    """门锁AI功能数据库操作类

    注意：此类在系统配置加载完成后初始化，不影响系统配置加载流程
    """
```

### 4. `config/doorlock_config.yaml`

**修改内容：**

- 更新顶部注释，明确说明配置复用机制
- 移除了 VLLM 相关配置（完全复用系统配置）

**新注释：**

```yaml
# 智能门锁AI功能独立配置文件
#
# 配置说明：
# 1. 此配置文件独立于系统主配置，不会被 manager-api 覆盖
# 2. VLLM 模型配置完全复用系统配置（从 manage-api 或 config.yaml 加载）
# 3. 此文件仅包含门锁业务配置（数据库、看护模式、性能参数等）
# 4. 加载时机：在系统配置加载完成后，门锁模块初始化时加载
# 5. 不影响系统配置加载流程
```

### 5. `config.yaml`

**修改内容：**

- 移除 `VLLM.DoorlockVLLM` 配置段
- 移除 `doorlock` 配置段（已迁移到 `doorlock_config.yaml`）

**删除的配置：**

```yaml
# ❌ 已删除
VLLM:
  DoorlockVLLM:
    type: doorlock_vllm
    model_name: glm-4v-flash
    # ...

# ❌ 已删除
doorlock:
  package_guard:
    # ...
```

## 配置使用示例

### 场景 1：使用 manage-api 配置

```yaml
# data/.config.yaml
manager-api:
  url: "http://your-api-server:8080"
  secret: "your-secret"
```

**系统行为：**

1. 系统从 manage-api 加载配置，包括 VLLM 配置
2. 门锁初始化时，自动复用系统加载的 VLLM 配置
3. 门锁从 `doorlock_config.yaml` 加载业务配置

### 场景 2：使用本地配置

```yaml
# config.yaml
selected_module:
  VLLM: ChatGLMVLLM

VLLM:
  ChatGLMVLLM:
    type: openai
    model_name: glm-4v-flash
    api_key: sk-xxx
    base_url: https://open.bigmodel.cn/api/paas/v4/
    max_tokens: 500
    temperature: 0.7
```

**系统行为：**

1. 系统从 `config.yaml` 加载配置
2. 门锁初始化时，自动复用 `ChatGLMVLLM` 配置
3. 门锁从 `doorlock_config.yaml` 加载业务配置

## 配置优先级

| 配置项         | 来源                                  | 优先级 |
| -------------- | ------------------------------------- | ------ |
| VLLM 模型配置  | 系统配置（manage-api 或 config.yaml） | 最高   |
| Token 警告阈值 | doorlock_config.yaml                  | 中     |
| 数据库配置     | doorlock_config.yaml                  | 中     |
| 看护模式配置   | doorlock_config.yaml                  | 中     |

## 优势总结

### ✅ 配置复用

- 门锁不需要独立配置 VLLM 模型
- 系统配置什么 VLLM，门锁就使用什么
- 避免配置冗余和不一致

### ✅ 配置隔离

- 门锁业务配置独立管理
- 不会被 manage-api 覆盖
- 可以独立调整业务参数

### ✅ 加载顺序

- 系统配置先加载
- 门锁配置后加载（延迟初始化）
- 不影响系统启动流程

### ✅ 易于维护

- 配置职责清晰
- 修改系统 VLLM 配置，门锁自动生效
- 门锁业务配置独立维护

## 测试验证

### 验证点 1：系统配置加载

```bash
# 启动系统，查看日志
python app.py

# 预期日志：
# [INFO] 系统配置加载成功
# [INFO] 选中的 VLLM: ChatGLMVLLM
```

### 验证点 2：门锁 VLLM 初始化

```bash
# 调用门锁 API，触发延迟初始化
curl -X POST http://localhost:8003/api/doorlock/package_guard/start \
  -H "Content-Type: application/json" \
  -d '{"device_id": "test001", "reason": "测试"}'

# 预期日志：
# [INFO] 门锁VLLM提供者初始化完成: 复用系统配置 ChatGLMVLLM
# [INFO] 门锁看护管理器延迟初始化成功（复用系统 VLLM 配置）
```

### 验证点 3：配置复用

```python
# 在 doorlock_vllm.py 中添加调试日志
self.logger.bind(tag=TAG).info(
    f"门锁VLLM配置: model={self.model_name}, "
    f"api_key={self.api_key[:10]}..., "
    f"max_tokens={self.max_tokens}"
)

# 预期输出：
# [INFO] 门锁VLLM配置: model=glm-4v-flash, api_key=sk-xxx..., max_tokens=500
```

## 注意事项

### ⚠️ 系统配置必须包含 VLLM

如果系统配置中没有配置 VLLM，门锁初始化会失败：

```python
# 错误示例
selected_module:
  VLLM: ""  # ❌ 未配置 VLLM

# 正确示例
selected_module:
  VLLM: "ChatGLMVLLM"  # ✅ 配置了 VLLM
```

### ⚠️ 延迟初始化

门锁的 VLLM 提供者在首次 API 调用时才初始化，不会影响系统启动速度。

### ⚠️ 配置文件路径

`doorlock_config.yaml` 必须存在于 `config/` 目录下，否则会使用默认配置。

## 相关文件清单

### 修改的文件

- `core/providers/vllm/doorlock_vllm.py`
- `core/api/doorlock_guard_handler.py`
- `core/providers/doorlock/doorlock_database.py`
- `config/doorlock_config.yaml`
- `config.yaml`

### 未修改的文件

- `core/http_server.py`（仅传入系统配置）
- `config/config_loader.py`（配置加载逻辑不变）
- `app.py`（启动流程不变）

## 总结

通过这次重构，实现了：

1. ✅ 门锁完全复用系统 VLLM 配置
2. ✅ 门锁配置加载不影响系统配置加载
3. ✅ 从 `config.yaml` 移除了门锁相关配置
4. ✅ 配置职责清晰，易于维护

系统配置什么 VLLM，门锁就使用什么，无需独立配置。
