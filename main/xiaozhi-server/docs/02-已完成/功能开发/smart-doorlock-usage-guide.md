# 智能门锁 AI 功能使用指南

## 目录

1. [功能概述](#功能概述)
2. [系统要求](#系统要求)
3. [配置步骤](#配置步骤)
4. [意图识别功能](#意图识别功能)
5. [看护模式功能](#看护模式功能)
6. [欢迎词配置](#欢迎词配置)
7. [常见问题解答](#常见问题解答)

---

## 功能概述

智能门锁 AI 功能为您的智能门锁系统提供两大核心能力：

### 1. 访客意图识别

当有访客到访时，系统会：

- 自动进行人脸识别
- 对有权限用户播放个性化欢迎词并开门
- 对无权限访客进行礼貌对话，识别来访意图
- 生成结构化总结并通知手机 App
- 记录完整对话历史供后续查询

**适用场景**：

- 快递员送货
- 朋友拜访
- 推销人员
- 物业维修
- 其他访客

### 2. 快递看护模式

系统可以自动监控门口快递，防止被盗或破坏：

- AI 自动判断何时启用看护（如快递员提到"放门口了"）
- 持续拍照监控，对比基准图片检测异常
- 根据威胁等级采取不同响应（语音提示/警告、App 通知）
- 主人取走快递后自动关闭看护
- 记录所有警报事件供后续查询

**威胁等级**：

- **低威胁**：路人经过、主人取件、工作人员
- **中威胁**：长时间停留、翻看快递、多次往返
- **高威胁**：非主人拿走、破坏快递、撬门撬锁

---

## 系统要求

### 硬件要求

- ESP32 智能门锁设备（带摄像头、PIR 传感器、扬声器）
- 稳定的网络连接（WiFi）

### 软件要求

- xiaozhi-server（Python 后端服务）
- MySQL 数据库（5.7+）
- VLLM 视觉语言模型服务
- 人脸识别服务
- TTS 语音合成服务

### 数据库要求

- 已执行门锁 AI 功能的数据库迁移脚本
- 数据库表：`doorlock_config`、`doorlock_visitor_intents`、`doorlock_package_alerts`、`persons`

---

## 配置步骤

### 步骤 1: 数据库迁移

首先需要执行数据库迁移，创建必要的表结构。

```bash
cd main/xiaozhi-server/migrations

# 执行迁移脚本
python run_doorlock_ai_migration.py

# 验证迁移结果
python verify_doorlock_ai_migration.py
```

**预期输出**：

```
✓ 数据库连接成功
✓ doorlock_config 表创建成功
✓ doorlock_visitor_intents 表创建成功
✓ doorlock_package_alerts 表创建成功
✓ persons 表扩展成功
✓ 所有索引创建成功
```

### 步骤 2: 配置主配置文件

编辑 `main/xiaozhi-server/config.yaml`，添加门锁配置段：

```yaml
# 门锁AI功能配置
doorlock:
  # 看护模式配置
  package_guard:
    photo_interval: 5 # 拍照间隔（秒）
    baseline_dir: "data/face_recognition/package_baseline/" # 基准图片目录

  # 意图识别配置
  intent_recognition:
    dialogue_timeout: 30 # 对话超时时间（秒）
    max_dialogue_rounds: 10 # 最大对话轮次

  # 人脸识别配置
  face_recognition:
    max_retries: 3 # 最大重试次数
    retry_interval: 1 # 重试间隔（秒）

  # 性能配置
  performance:
    max_token_usage_ratio: 0.8 # Token使用量警告阈值
    session_cleanup_delay: 0 # 会话清理延迟（秒）
```

**配置说明**：

| 配置项                | 说明                        | 推荐值                                  |
| --------------------- | --------------------------- | --------------------------------------- |
| photo_interval        | 看护模式拍照间隔            | 5秒                                     |
| baseline_dir          | 基准图片存储目录            | data/face_recognition/package_baseline/ |
| dialogue_timeout      | 访客沉默多久后结束对话      | 30秒                                    |
| max_dialogue_rounds   | 最多保留多少轮对话历史      | 10轮                                    |
| max_retries           | 人脸识别失败后最多重试几次  | 3次                                     |
| retry_interval        | 人脸识别重试间隔            | 1秒                                     |
| max_token_usage_ratio | Token使用量超过此比例时警告 | 0.8 (80%)                               |

### 步骤 3: 配置提示词文件

提示词配置文件位于 `main/xiaozhi-server/config/doorlock_prompts.yaml`。

**默认配置已包含**：

- 意图识别提示词（`intent_recognition_prompt`）
- 看护模式提示词（`package_guard_prompt`）
- 欢迎词模板（`welcome_templates`）

**如需自定义**，可以编辑此文件。建议保留默认配置，除非您对提示词工程有深入了解。

### 步骤 4: 初始化设备配置

为每个设备创建初始配置（通过 API 或直接插入数据库）：

```bash
# 通过 API 创建设备配置
curl -X POST "http://localhost:8003/api/doorlock/config" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "intent_recognition_enabled": true,
    "package_guard_available": true
  }'
```

或直接在数据库中插入：

```sql
INSERT INTO doorlock_config (device_id, intent_recognition_enabled, package_guard_available)
VALUES ('device001', TRUE, TRUE);
```

### 步骤 5: 配置用户权限

在 `persons` 表中标记哪些用户是主人（可以取走快递）：

```sql
-- 将用户ID为5的用户标记为主人
UPDATE persons SET is_owner = TRUE WHERE id = 5;
```

### 步骤 6: 重启服务

```bash
cd main/xiaozhi-server

# 重启 xiaozhi-server 服务
python app.py
```

---

## 意图识别功能

### 功能说明

意图识别功能会在访客到访时自动启动，通过对话了解访客来访目的。

### 工作流程

```
PIR检测到人体
    ↓
人脸识别（最多3次重试）
    ↓
├─ 有权限 → 播放欢迎词 → 开门
└─ 无权限 → 意图识别对话
              ↓
          生成意图总结
              ↓
          通知手机App
```

### 如何配置

#### 1. 启用/禁用意图识别

```bash
# 启用意图识别
curl -X POST "http://localhost:8003/api/doorlock/config" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "intent_recognition_enabled": true
  }'

# 禁用意图识别
curl -X POST "http://localhost:8003/api/doorlock/config" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "intent_recognition_enabled": false
  }'
```

#### 2. 查看当前配置

```bash
curl -X GET "http://localhost:8003/api/doorlock/config?device_id=device001"
```

### 如何查看记录

#### 1. 通过 API 查询

```bash
# 查询最近20条记录
curl -X GET "http://localhost:8003/api/doorlock/intents/history?device_id=device001&limit=20"

# 查询指定日期范围
curl -X GET "http://localhost:8003/api/doorlock/intents/history?device_id=device001&start_date=2026-02-01&end_date=2026-02-28"

# 分页查询（第2页，每页10条）
curl -X GET "http://localhost:8003/api/doorlock/intents/history?device_id=device001&limit=10&offset=10"
```

#### 2. 通过数据库查询

```sql
-- 查询最近的意图识别记录
SELECT
    id,
    session_id,
    person_id,
    intent_type,
    intent_summary,
    created_at
FROM doorlock_visitor_intents
WHERE session_id LIKE 'device001%'
ORDER BY created_at DESC
LIMIT 20;
```

### 意图类型说明

| 意图类型    | 说明          | 示例                      |
| ----------- | ------------- | ------------------------- |
| delivery    | 送快递/外卖   | "我是快递员，有您的包裹"  |
| visit       | 拜访朋友/家人 | "我来找李四，他在家吗？"  |
| sales       | 推销          | "您好，我们是XX公司的..." |
| maintenance | 维修/物业     | "我是物业，来检查水表"    |
| other       | 其他          | 无法明确分类的情况        |

### 意图总结格式

```json
{
  "important_notes": [
    "【留言】明天下午3点再来拜访",
    "【提醒】带了一份礼物放在门口"
  ],
  "intent_type": "visit",
  "purpose": "拜访朋友，约定明天见面",
  "full_summary": "访客张三来拜访，主人不在家。访客表示明天下午3点会再来，并留下了一份礼物在门口。"
}
```

---

## 看护模式功能

### 功能说明

看护模式会持续监控门口快递，检测异常行为并及时警报。

### 工作流程

```
启用看护模式
    ↓
拍摄基准图片
    ↓
PIR检测到人体
    ↓
每5秒拍照一次
    ↓
VLLM分析（当前图片 vs 基准图片）
    ↓
判断威胁等级
    ↓
├─ 低威胁 → 无操作
├─ 中威胁 → 语音提示 + App通知
└─ 高威胁 → 语音警告 + App通知
    ↓
主人取走快递 → 自动关闭看护
```

### 如何启用

#### 1. 确保功能可用

```bash
# 启用看护模式功能
curl -X POST "http://localhost:8003/api/doorlock/config" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "package_guard_available": true
  }'
```

#### 2. 手动启动看护

```bash
curl -X POST "http://localhost:8003/api/doorlock/package_guard/start" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "reason": "有快递需要看护"
  }'
```

#### 3. AI 自动启动

当访客对话中提到"快递放门口了"、"外卖在这"等关键词时，AI 会自动启动看护模式。

### 如何停止

#### 1. 手动停止

```bash
curl -X POST "http://localhost:8003/api/doorlock/package_guard/stop" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "reason": "手动停止看护"
  }'
```

#### 2. AI 自动停止

当 AI 判断快递已被主人（`is_owner=true`）取走时，会自动关闭看护模式。

### 如何查看警报

#### 1. 通过 API 查询

```bash
# 查询最近20条警报
curl -X GET "http://localhost:8003/api/doorlock/alerts/history?device_id=device001&limit=20"

# 查询指定日期范围
curl -X GET "http://localhost:8003/api/doorlock/alerts/history?device_id=device001&start_date=2026-02-01&end_date=2026-02-28"
```

#### 2. 通过数据库查询

```sql
-- 查询高威胁警报
SELECT
    id,
    session_id,
    threat_level,
    action,
    description,
    photo_path,
    created_at
FROM doorlock_package_alerts
WHERE device_id = 'device001'
  AND threat_level = 'high'
ORDER BY created_at DESC
LIMIT 20;
```

### 威胁等级说明

| 威胁等级 | 响应措施           | 典型场景                       |
| -------- | ------------------ | ------------------------------ |
| low      | 无操作             | 路人经过、主人取件、工作人员   |
| medium   | 语音提示 + App通知 | 长时间停留、翻看快递、多次往返 |
| high     | 语音警告 + App通知 | 非主人拿走、破坏快递、撬门撬锁 |

### 行为类型说明

| 行为类型  | 说明                   |
| --------- | ---------------------- |
| passing   | 路人快速经过           |
| normal    | 正常行为（如主人取件） |
| searching | 翻找、查看快递         |
| taking    | 拿走快递               |
| damaging  | 破坏、踢踹快递         |

---

## 欢迎词配置

### 功能说明

为有开门权限的用户配置个性化欢迎词，根据不同时段播放不同内容。

### 时段划分

| 时段 | 时间范围         | 配置键    |
| ---- | ---------------- | --------- |
| 早晨 | 6:00 - 12:00     | morning   |
| 下午 | 12:00 - 18:00    | afternoon |
| 晚上 | 18:00 - 22:00    | evening   |
| 夜间 | 22:00 - 6:00     | night     |
| 默认 | 未配置时段时使用 | default   |

### 如何配置

#### 1. 获取预设模板

```bash
curl -X GET "http://localhost:8003/api/doorlock/welcome/templates"
```

**响应示例**：

```json
{
  "success": true,
  "data": {
    "templates": [
      {
        "name": "温馨家庭",
        "morning": "早上好，{name}",
        "afternoon": "下午好，{name}",
        "evening": "晚上好，{name}",
        "night": "夜深了，{name}",
        "default": "欢迎回家"
      },
      {
        "name": "简洁风格",
        "default": "欢迎回家，{name}"
      },
      {
        "name": "正式风格",
        "morning": "早安，{name}先生/女士",
        "afternoon": "午安，{name}先生/女士",
        "evening": "晚安，{name}先生/女士",
        "night": "夜深了，{name}先生/女士，请注意休息",
        "default": "欢迎回家，{name}先生/女士"
      }
    ]
  }
}
```

#### 2. 配置用户欢迎词

```bash
# 使用温馨家庭风格
curl -X POST "http://localhost:8003/api/doorlock/welcome/config" \
  -H "Content-Type: application/json" \
  -d '{
    "person_id": 5,
    "custom_greeting": {
      "morning": "早上好，张三",
      "afternoon": "下午好，张三",
      "evening": "晚上好，张三",
      "night": "夜深了，张三",
      "default": "欢迎回家"
    }
  }'

# 使用简洁风格
curl -X POST "http://localhost:8003/api/doorlock/welcome/config" \
  -H "Content-Type: application/json" \
  -d '{
    "person_id": 6,
    "custom_greeting": {
      "default": "欢迎回家，李四"
    }
  }'
```

#### 3. 查询用户欢迎词

```bash
curl -X GET "http://localhost:8003/api/doorlock/welcome/config?person_id=5"
```

### 配置示例

#### 示例 1: 完整配置（所有时段）

```json
{
  "person_id": 5,
  "custom_greeting": {
    "morning": "早上好，张三，新的一天开始了",
    "afternoon": "下午好，张三，辛苦了",
    "evening": "晚上好，张三，欢迎回家",
    "night": "夜深了，张三，早点休息",
    "default": "欢迎回家，张三"
  }
}
```

#### 示例 2: 简化配置（只配置默认）

```json
{
  "person_id": 6,
  "custom_greeting": {
    "default": "欢迎回家"
  }
}
```

#### 示例 3: 部分时段配置

```json
{
  "person_id": 7,
  "custom_greeting": {
    "morning": "早安",
    "evening": "晚安",
    "default": "欢迎回家"
  }
}
```

### 注意事项

1. **占位符**: 模板中的 `{name}` 会被替换为用户姓名
2. **回退机制**: 如果当前时段未配置，会使用 `default`；如果 `default` 也未配置，使用"欢迎回家"
3. **仅对有权限用户生效**: 欢迎词只对有开门权限的用户播放
4. **长度建议**: 欢迎词建议控制在 20 字以内，避免播放时间过长

---

## 常见问题解答

### Q1: 意图识别功能不工作，访客到访时没有对话？

**可能原因**：

1. 意图识别功能未启用
2. 人脸识别成功且用户有开门权限（会直接开门，不进行对话）
3. VLLM 服务未启动或配置错误

**解决方法**：

```bash
# 1. 检查配置
curl -X GET "http://localhost:8003/api/doorlock/config?device_id=device001"

# 2. 启用意图识别
curl -X POST "http://localhost:8003/api/doorlock/config" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "intent_recognition_enabled": true
  }'

# 3. 检查日志
tail -f main/xiaozhi-server/logs/app.log | grep "doorlock"
```

### Q2: 看护模式无法启动，提示"看护模式功能未启用"？

**原因**: `package_guard_available` 开关未启用。

**解决方法**：

```bash
curl -X POST "http://localhost:8003/api/doorlock/config" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "package_guard_available": true
  }'
```

### Q3: 看护模式启动后，为什么没有拍照监控？

**可能原因**：

1. PIR 传感器未检测到人体
2. ESP32 拍照功能异常
3. 看护模式已自动关闭

**解决方法**：

```bash
# 1. 检查看护模式状态
curl -X GET "http://localhost:8003/api/doorlock/config?device_id=device001"
# 查看 package_guard_active 字段

# 2. 检查日志
tail -f main/xiaozhi-server/logs/app.log | grep "package_guard"

# 3. 手动触发 PIR 传感器（在门口走动）
```

### Q4: 主人取走快递后，看护模式没有自动关闭？

**可能原因**：

1. 用户未标记为主人（`is_owner=false`）
2. AI 未正确识别取件行为

**解决方法**：

```sql
-- 1. 检查用户是否为主人
SELECT id, name, is_owner FROM persons WHERE id = 5;

-- 2. 标记用户为主人
UPDATE persons SET is_owner = TRUE WHERE id = 5;

-- 3. 手动关闭看护模式
```

```bash
curl -X POST "http://localhost:8003/api/doorlock/package_guard/stop" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "reason": "手动停止"
  }'
```

### Q5: 欢迎词配置后不生效，仍然播放默认欢迎词？

**可能原因**：

1. 用户 ID 错误
2. 配置格式错误
3. TTS 服务异常

**解决方法**：

```bash
# 1. 查询当前配置
curl -X GET "http://localhost:8003/api/doorlock/welcome/config?person_id=5"

# 2. 重新配置
curl -X POST "http://localhost:8003/api/doorlock/welcome/config" \
  -H "Content-Type: application/json" \
  -d '{
    "person_id": 5,
    "custom_greeting": {
      "default": "欢迎回家，张三"
    }
  }'

# 3. 检查数据库
```

```sql
SELECT id, name, custom_greeting FROM persons WHERE id = 5;
```

### Q6: 如何查看系统运行日志？

**日志位置**: `main/xiaozhi-server/logs/app.log`

**查看实时日志**：

```bash
# 查看所有门锁相关日志
tail -f main/xiaozhi-server/logs/app.log | grep "doorlock"

# 查看意图识别日志
tail -f main/xiaozhi-server/logs/app.log | grep "intent"

# 查看看护模式日志
tail -f main/xiaozhi-server/logs/app.log | grep "package_guard"

# 查看错误日志
tail -f main/xiaozhi-server/logs/app.log | grep "ERROR"
```

### Q7: 如何清理历史记录？

**不建议删除历史记录**，但如果确实需要：

```sql
-- 删除指定设备的意图识别记录（保留最近30天）
DELETE FROM doorlock_visitor_intents
WHERE session_id LIKE 'device001%'
  AND created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);

-- 删除指定设备的快递警报记录（保留最近30天）
DELETE FROM doorlock_package_alerts
WHERE device_id = 'device001'
  AND created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
```

### Q8: Token 使用量警告是什么意思？

**警告信息**: `Token使用量已达 XXX/YYY，接近上限`

**说明**: VLLM 模型有 Token 上限，当对话历史过长时会触发警告。

**解决方法**：

- 系统会自动清理最早的对话历史（保留最近 10 轮）
- 如果频繁出现警告，可以减少 `max_dialogue_rounds` 配置值
- 优化提示词，减少不必要的内容

### Q9: 如何备份和恢复配置？

**备份配置**：

```bash
# 备份数据库
mysqldump -u root -p xiaozhi_db doorlock_config doorlock_visitor_intents doorlock_package_alerts > doorlock_backup.sql

# 备份配置文件
cp main/xiaozhi-server/config.yaml config_backup.yaml
cp main/xiaozhi-server/config/doorlock_prompts.yaml doorlock_prompts_backup.yaml
```

**恢复配置**：

```bash
# 恢复数据库
mysql -u root -p xiaozhi_db < doorlock_backup.sql

# 恢复配置文件
cp config_backup.yaml main/xiaozhi-server/config.yaml
cp doorlock_prompts_backup.yaml main/xiaozhi-server/config/doorlock_prompts.yaml

# 重启服务
cd main/xiaozhi-server
python app.py
```

### Q10: 如何禁用门锁 AI 功能？

**临时禁用**（不删除数据）：

```bash
# 禁用意图识别
curl -X POST "http://localhost:8003/api/doorlock/config" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "intent_recognition_enabled": false
  }'

# 禁用看护模式
curl -X POST "http://localhost:8003/api/doorlock/config" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device001",
    "package_guard_available": false
  }'
```

**永久禁用**（删除数据）：

```sql
-- 删除设备配置
DELETE FROM doorlock_config WHERE device_id = 'device001';

-- 删除历史记录
DELETE FROM doorlock_visitor_intents WHERE session_id LIKE 'device001%';
DELETE FROM doorlock_package_alerts WHERE device_id = 'device001';
```

---

## 技术支持

如有其他问题，请：

1. 查看系统日志：`main/xiaozhi-server/logs/app.log`
2. 查看 API 文档：`docs/my_docs/doorlock-api-documentation.md`
3. 查看设计文档：`.kiro/specs/smart-doorlock-ai/design.md`
4. 提交 Issue 到项目仓库

---

## 更新日志

### v1.0.0 (2026-02-09)

- 初始版本发布
- 意图识别功能
- 看护模式功能
- 欢迎词配置功能
