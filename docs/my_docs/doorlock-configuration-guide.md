# 智能门锁配置指南

## 概述

本文档详细说明智能门锁系统的配置文件结构和配置项，包括统一模式配置、提示词配置、性能调优参数等。

## 配置文件

### 主配置文件

| 文件                    | 路径                              | 说明          |
| ----------------------- | --------------------------------- | ------------- |
| `doorlock_config.yaml`  | `config/doorlock_config.yaml`     | 门锁功能配置  |
| `doorlock_prompts.yaml` | `config/doorlock_prompts.yaml`    | AI 提示词配置 |
| `config.yaml`           | `main/xiaozhi-server/config.yaml` | 系统主配置    |

---

## doorlock_config.yaml 配置详解

### 完整配置示例

```yaml
# 统一模式配置
unified_mode:
  enabled: true # 启用统一模式

  # 对话配置
  dialogue:
    max_rounds: 10 # 最大对话轮次
    timeout_seconds: 30 # 沉默超时时间（秒）

  # 看护配置
  guard:
    threat_detection: "behavior_based" # 威胁检测方式
    report_threshold: "medium" # 报告阈值

  # Token 优化
  token_optimization:
    baseline_image_once: true # 仅第一轮传入基准图片
    reuse_context: true # 依赖 AI 上下文理解

# 照片缓存配置
photo_cache:
  interval_seconds: 5 # 拍照间隔（秒）
  max_cache_size: 10 # 最大缓存数量

# 性能配置
performance:
  vllm_limits:
    model_context_limit: 262144 # 模型上下文窗口
    max_input_tokens: 260096 # 最大输入 Token
    max_output_tokens: 32768 # 最大输出 Token
    max_image_tokens: 16384 # 最大图片 Token
    tokens_per_image: 7000 # 每张图片 Token 数
    input_warning_ratio: 0.8 # 输入 Token 警告阈值
    total_warning_ratio: 0.8 # 总 Token 警告阈值
```

---

### 统一模式配置

#### unified_mode.enabled

**类型**：`boolean`  
**默认值**：`true`  
**说明**：是否启用统一模式

**可选值**：

- `true`：启用统一模式（推荐）
- `false`：禁用统一模式，回退到分离模式

**影响**：

- 启用：访客对话和看护监控统一处理
- 禁用：看护模式激活时无法对话

**示例**：

```yaml
unified_mode:
  enabled: true # 启用统一模式
```

---

#### unified_mode.dialogue.max_rounds

**类型**：`integer`  
**默认值**：`10`  
**推荐范围**：`5-15`  
**说明**：最大对话轮次，超过后自动结束对话

**影响**：

- 太少（<5）：可能无法充分了解访客意图
- 适中（5-10）：平衡体验和成本
- 太多（>15）：Token 消耗增加，对话时间过长

**Token 消耗参考**：
| 轮次 | Token 消耗（看护激活） | Token 消耗（仅对话） |
|------|---------------------|-------------------|
| 5 轮 | ~65K | ~50K |
| 10 轮 | ~100K | ~85K |
| 15 轮 | ~135K | ~120K |

**示例**：

```yaml
unified_mode:
  dialogue:
    max_rounds: 10 # 最多 10 轮对话
```

---

#### unified_mode.dialogue.timeout_seconds

**类型**：`integer`  
**默认值**：`30`  
**推荐范围**：`20-60`  
**说明**：沉默超时时间（秒），超过后自动结束对话

**影响**：

- 太短（<20）：访客思考时间不足
- 适中（30-40）：平衡体验和效率
- 太长（>60）：等待时间过长

**示例**：

```yaml
unified_mode:
  dialogue:
    timeout_seconds: 30 # 沉默 30 秒后结束
```

---

#### unified_mode.guard.threat_detection

**类型**：`string`  
**默认值**：`"behavior_based"`  
**可选值**：`"behavior_based"` | `"time_based"`  
**说明**：威胁检测方式

**可选值说明**：

- `behavior_based`：基于访客行为触发（推荐）
  - 访客靠近快递时检测
  - 访客触碰快递时检测
  - 实时响应，准确度高

- `time_based`：定时检查（不推荐）
  - 每隔固定时间检查
  - 可能错过关键行为
  - 资源消耗较高

**示例**：

```yaml
unified_mode:
  guard:
    threat_detection: "behavior_based" # 基于行为触发
```

---

#### unified_mode.guard.report_threshold

**类型**：`string`  
**默认值**：`"medium"`  
**可选值**：`"low"` | `"medium"` | `"high"`  
**说明**：报告阈值，威胁等级达到此值时报告

**可选值说明**：

- `low`：所有威胁都报告（包括路人经过）
  - 优点：不遗漏任何情况
  - 缺点：误报率高，通知频繁

- `medium`：中等及以上威胁报告（推荐）
  - 优点：平衡准确度和覆盖率
  - 缺点：可能遗漏低威胁

- `high`：仅高威胁报告
  - 优点：误报率低
  - 缺点：可能遗漏中等威胁

**示例**：

```yaml
unified_mode:
  guard:
    report_threshold: "medium" # 中等及以上威胁报告
```

---

#### unified_mode.token_optimization.baseline_image_once

**类型**：`boolean`  
**默认值**：`true`  
**说明**：是否仅第一轮传入基准图片

**可选值**：

- `true`：仅第一轮传入（推荐）
  - 节省约 30% Token
  - 依赖 AI 上下文理解

- `false`：每轮都传入
  - Token 消耗增加
  - AI 理解更准确

**Token 消耗对比**：
| 配置 | 10 轮对话 Token 消耗 | 节省比例 |
|------|-------------------|---------|
| `true` | ~100K | 基准 |
| `false` | ~140K | -40% |

**示例**：

```yaml
unified_mode:
  token_optimization:
    baseline_image_once: true # 仅第一轮传入
```

---

#### unified_mode.token_optimization.reuse_context

**类型**：`boolean`  
**默认值**：`true`  
**说明**：是否依赖 AI 上下文理解

**可选值**：

- `true`：依赖上下文（推荐）
  - Token 消耗降低
  - 需要 AI 记忆能力强

- `false`：不依赖上下文
  - 每轮都重新说明
  - Token 消耗增加

**示例**：

```yaml
unified_mode:
  token_optimization:
    reuse_context: true # 依赖上下文
```

---

### 照片缓存配置

#### photo_cache.interval_seconds

**类型**：`integer`  
**默认值**：`5`  
**推荐范围**：`3-10`  
**说明**：拍照间隔（秒）

**影响**：

- 太短（<3）：资源消耗增加，存储压力大
- 适中（5）：平衡实时性和资源消耗
- 太长（>10）：可能错过关键行为

**资源消耗参考**：
| 间隔 | 10 分钟拍照次数 | 存储占用 |
|------|---------------|---------|
| 3 秒 | 200 次 | ~40MB |
| 5 秒 | 120 次 | ~24MB |
| 10 秒 | 60 次 | ~12MB |

**示例**：

```yaml
photo_cache:
  interval_seconds: 5 # 每 5 秒拍照一次
```

---

#### photo_cache.max_cache_size

**类型**：`integer`  
**默认值**：`10`  
**推荐范围**：`5-20`  
**说明**：最大缓存照片数量

**影响**：

- 太少（<5）：可能无法回溯历史行为
- 适中（10）：平衡内存和功能
- 太多（>20）：内存占用增加

**内存占用参考**：
| 缓存数量 | 内存占用 |
|---------|---------|
| 5 张 | ~0.5-1MB |
| 10 张 | ~1-2MB |
| 20 张 | ~2-4MB |

**示例**：

```yaml
photo_cache:
  max_cache_size: 10 # 最多缓存 10 张照片
```

---

### 性能配置

#### performance.vllm_limits.model_context_limit

**类型**：`integer`  
**默认值**：`262144`  
**说明**：模型上下文窗口大小（Token）

**注意**：

- 此值由模型决定，不建议修改
- Qwen2-VL-7B-Instruct 的上下文窗口为 262144

**示例**：

```yaml
performance:
  vllm_limits:
    model_context_limit: 262144 # 模型上下文窗口
```

---

#### performance.vllm_limits.max_input_tokens

**类型**：`integer`  
**默认值**：`260096`  
**说明**：最大输入 Token 数

**计算公式**：

```
max_input_tokens = model_context_limit - max_output_tokens
                 = 262144 - 2048
                 = 260096
```

**示例**：

```yaml
performance:
  vllm_limits:
    max_input_tokens: 260096 # 最大输入 Token
```

---

#### performance.vllm_limits.max_output_tokens

**类型**：`integer`  
**默认值**：`32768`  
**推荐范围**：`2048-32768`  
**说明**：最大输出 Token 数

**影响**：

- 太少（<2048）：AI 回复可能被截断
- 适中（2048-8192）：满足大部分场景
- 太多（>8192）：响应时间增加

**示例**：

```yaml
performance:
  vllm_limits:
    max_output_tokens: 32768 # 最大输出 Token
```

---

#### performance.vllm_limits.max_image_tokens

**类型**：`integer`  
**默认值**：`16384`  
**说明**：最大图片 Token 数

**计算公式**：

```
max_image_tokens = tokens_per_image × max_image_count
                 = 7000 × 2
                 = 14000（实际配置 16384 留有余量）
```

**示例**：

```yaml
performance:
  vllm_limits:
    max_image_tokens: 16384 # 最大图片 Token
```

---

#### performance.vllm_limits.tokens_per_image

**类型**：`integer`  
**默认值**：`7000`  
**说明**：每张图片消耗的 Token 数

**注意**：

- 此值为估算值，实际消耗可能略有不同
- 取决于图片分辨率和内容复杂度

**示例**：

```yaml
performance:
  vllm_limits:
    tokens_per_image: 7000 # 每张图片 7000 Token
```

---

#### performance.vllm_limits.input_warning_ratio

**类型**：`float`  
**默认值**：`0.8`  
**推荐范围**：`0.7-0.9`  
**说明**：输入 Token 警告阈值（比例）

**触发条件**：

```
当前输入 Token / max_input_tokens > input_warning_ratio
```

**示例**：

```yaml
performance:
  vllm_limits:
    input_warning_ratio: 0.8 # 超过 80% 时警告
```

---

#### performance.vllm_limits.total_warning_ratio

**类型**：`float`  
**默认值**：`0.8`  
**推荐范围**：`0.7-0.9`  
**说明**：总 Token 警告阈值（比例）

**触发条件**：

```
总 Token / model_context_limit > total_warning_ratio
```

**示例**：

```yaml
performance:
  vllm_limits:
    total_warning_ratio: 0.8 # 超过 80% 时警告
```

---

## doorlock_prompts.yaml 配置详解

### 完整配置示例

````yaml
# 核心角色和风格
core_role_and_style: |
  【系统角色】
  你是一个智能门锁的AI门卫助手，负责管理门口的访客接待和安全监控。

  【对话风格指南】
  - 礼貌正式，但不失亲和力
  - 根据访客身份调整语气
  - 使用简洁明了的语言
  - 对话保持简洁，每次回复不超过2-3句话

# 对话任务
dialogue_tasks: |
  【对话任务】
  你的主要任务是与访客进行自然对话，了解来访目的。

  - 主动引导对话，明确询问来访目的
  - 对重要信息进行二次确认
  - 识别推销意图时礼貌但坚定地拒绝
  - 不要在对话中提及快递监控功能

# 看护任务
guard_tasks: |
  【看护任务】（后台任务，不影响对话）
  你同时负责监控门口快递的安全。

  **重要**：这是后台任务，不要在对话中提及监控功能。

  【监控要点】
  - 观察访客是否靠近、触碰、翻看快递
  - 判断访客行为是否可疑
  - 评估威胁等级（low/medium/high）

  【触发条件】
  仅在以下情况调用 report_package_status：
  - 访客靠近快递并触碰、翻看
  - 访客长时间停留在快递旁边（>10秒）
  - 访客试图拿走快递（非主人）
  - 访客破坏、踢踹快递

  【威胁等级判断】
  - low：路人经过、主人取快递
  - medium：翻看快递、长时间停留
  - high：非主人拿走快递、破坏快递

# 工具调用指南
tools_guide: |
  【工具调用说明】
  你可以调用以下4个工具函数：

  1. enable_package_guard
     - 功能：启用快递看护模式
     - 触发时机：访客提到"快递放门口了"
     - 参数：device_id, reason

  2. disable_package_guard
     - 功能：关闭快递看护模式
     - 触发时机：判断快递已被主人取走
     - 参数：device_id, reason

  3. update_package_baseline
     - 功能：更新看护基准图片
     - 触发时机：访客说"我把快递放这了"
     - 参数：device_id

  4. report_package_status
     - 功能：报告快递状态和威胁等级
     - 触发时机：检测到访客可疑行为（威胁等级≥medium）
     - 参数：device_id, session_id, action, threat_level, description

# 对话结束后的专用提示词
final_package_check_prompt: |
  【任务】
  访客已离开，请对比基准图片和当前图片，判断快递的最终状态。

  【要求】
  - 对比两张图片，判断快递是否被移动、拿走或破坏
  - 评估威胁等级
  - 以纯JSON格式返回结果

  【输出格式】
  ```json
  {
    "threat_level": "low|medium|high",
    "action": "taking|searching|damaging|normal|passing",
    "description": "详细描述你看到的情况"
  }
````

【判断标准】

- 快递位置未变化 = low + normal
- 快递被移动但未拿走 = medium + searching
- 快递被拿走 = high + taking（除非是主人）
- 快递被破坏 = high + damaging

intent_summary_prompt: |
【任务】
根据完整的对话历史和访客照片，生成结构化的访客意图总结。

【要求】

- 识别访客意图类型
- 提取重要信息（留言、提醒）
- 生成完整总结
- 提供AI分析

【输出格式】

```json
{
  "intent_type": "delivery|visit|sales|maintenance|other",
  "summary": "简洁的总结（一句话）",
  "important_notes": ["【留言】...", "【提醒】..."],
  "ai_analysis": "详细的AI分析，包括访客特征、行为观察、建议等"
}
```

【意图类型说明】

- delivery: 送快递/外卖
- visit: 拜访朋友/家人
- sales: 推销产品/服务
- maintenance: 维修/物业工作
- other: 其他情况

````

---

### 提示词配置说明

#### core_role_and_style

**说明**：核心角色和对话风格定义

**包含内容**：
- 系统角色定位
- 对话风格指南
- 语气和语言要求

**自定义建议**：
- 根据品牌调性调整语气
- 根据目标用户调整语言风格
- 保持简洁明了

---

#### dialogue_tasks

**说明**：对话任务说明

**包含内容**：
- 主要任务描述
- 对话引导策略
- 特殊情况处理

**自定义建议**：
- 明确对话目标
- 提供具体引导策略
- 说明特殊情况处理方式

---

#### guard_tasks

**说明**：看护任务说明（仅在看护模式激活时添加）

**包含内容**：
- 监控要点
- 触发条件
- 威胁等级判断标准

**自定义建议**：
- 明确监控重点
- 细化触发条件
- 调整威胁等级标准

---

#### tools_guide

**说明**：工具调用指南

**包含内容**：
- 可用工具列表
- 工具功能说明
- 触发时机说明
- 参数说明

**自定义建议**：
- 明确工具用途
- 说明触发时机
- 提供使用示例

---

#### final_package_check_prompt

**说明**：对话结束后的快递状态检查提示词

**包含内容**：
- 任务描述
- 输出格式要求
- 判断标准

**自定义建议**：
- 明确输出格式
- 细化判断标准
- 提供示例

---

#### intent_summary_prompt

**说明**：访客意图总结生成提示词

**包含内容**：
- 任务描述
- 输出格式要求
- 意图类型说明

**自定义建议**：
- 明确输出格式
- 扩展意图类型
- 提供示例

---

## 配置最佳实践

### 1. 开发环境配置

```yaml
# 开发环境：快速迭代，降低成本
unified_mode:
  dialogue:
    max_rounds: 5              # 减少对话轮次
    timeout_seconds: 20        # 缩短超时时间

photo_cache:
  interval_seconds: 10         # 降低拍照频率

performance:
  vllm_limits:
    max_output_tokens: 2048    # 限制输出长度
````

---

### 2. 生产环境配置

```yaml
# 生产环境：平衡体验和成本
unified_mode:
  dialogue:
    max_rounds: 10 # 标准对话轮次
    timeout_seconds: 30 # 标准超时时间

photo_cache:
  interval_seconds: 5 # 标准拍照频率

performance:
  vllm_limits:
    max_output_tokens: 8192 # 标准输出长度
```

---

### 3. 高安全场景配置

```yaml
# 高安全场景：提高监控灵敏度
unified_mode:
  guard:
    report_threshold: "low" # 所有威胁都报告

photo_cache:
  interval_seconds: 3 # 提高拍照频率
  max_cache_size: 20 # 增加缓存数量
```

---

### 4. 低成本场景配置

```yaml
# 低成本场景：降低 Token 消耗
unified_mode:
  dialogue:
    max_rounds: 5 # 减少对话轮次

  token_optimization:
    baseline_image_once: true # 启用 Token 优化

photo_cache:
  interval_seconds: 10 # 降低拍照频率
```

---

## 性能调优参数

### Token 消耗优化

**目标**：降低 Token 消耗，减少成本

**调整参数**：

```yaml
unified_mode:
  dialogue:
    max_rounds: 5 # 从 10 降到 5

  token_optimization:
    baseline_image_once: true # 启用优化
    reuse_context: true # 启用上下文复用
```

**效果**：

- Token 消耗降低约 50%
- 成本降低约 50%
- 对话体验略有下降

---

### 响应速度优化

**目标**：提高响应速度，改善体验

**调整参数**：

```yaml
photo_cache:
  interval_seconds: 3 # 从 5 降到 3

performance:
  vllm_limits:
    max_output_tokens: 2048 # 从 8192 降到 2048
```

**效果**：

- 响应速度提升约 30%
- 照片更新更及时
- Token 消耗略有增加

---

### 内存占用优化

**目标**：降低内存占用，提高稳定性

**调整参数**：

```yaml
photo_cache:
  max_cache_size: 5 # 从 10 降到 5

unified_mode:
  dialogue:
    max_rounds: 5 # 从 10 降到 5
```

**效果**：

- 内存占用降低约 50%
- 系统稳定性提升
- 功能略有限制

---

## 配置验证

### 验证配置文件格式

```bash
cd main/xiaozhi-server
python test_config_validation.py
```

**验证内容**：

- YAML 格式正确性
- 必需字段存在性
- 数值范围合理性

---

### 验证配置加载

```bash
cd main/xiaozhi-server
python test_config_loading.py
```

**验证内容**：

- 配置文件可正常加载
- 配置项可正常访问
- 默认值正确设置

---

## 常见问题

### Q1：修改配置后需要重启服务吗？

**是的**。配置文件在服务启动时加载，修改后需要重启服务生效。

```bash
cd main/xiaozhi-server
python app.py
```

---

### Q2：如何查看当前配置？

**方式 1：查看配置文件**

```bash
cat config/doorlock_config.yaml
```

**方式 2：查看日志**

```bash
tail -f logs/xiaozhi-server.log | grep "配置加载"
```

---

### Q3：配置错误会导致服务无法启动吗？

**会**。配置错误会导致服务启动失败，需要检查日志并修复配置。

**常见错误**：

- YAML 格式错误
- 必需字段缺失
- 数值超出范围

---

### Q4：如何恢复默认配置？

**方式 1：从备份恢复**

```bash
cp config/doorlock_config.yaml.bak config/doorlock_config.yaml
```

**方式 2：重新生成**

```bash
cd main/xiaozhi-server
python generate_default_config.py
```

---

## 相关文档

- [统一模式用户手册](./unified-mode-user-guide.md)
- [VLLM 提供者 API 参考](./doorlock-vllm-api-reference.md)
- [意图处理器 API 参考](./doorlock-intent-handler-api-reference.md)
- [提示词自定义指南](./doorlock-prompt-customization-guide.md)
- [故障排查指南](./doorlock-troubleshooting-guide.md)

---

## 更新日志

| 版本  | 日期       | 说明                   |
| ----- | ---------- | ---------------------- |
| 1.0.0 | 2024-02-16 | 初始版本，完整配置指南 |
