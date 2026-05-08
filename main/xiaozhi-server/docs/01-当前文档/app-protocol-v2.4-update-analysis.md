# App 通信协议 v2.4 更新分析报告

## 1. 变更时间线

- **协议文档最后更新**：2026年2月12日 16:52:33
- **分析时间范围**：2026年2月12日 - 2026年2月19日（7天）
- **主要提交记录**：
  - `c12260e2`: 完成服务器触发人脸识别功能全部实现
  - `9dbf6700`: 统一门锁VLLM的两种模式，完善智能门锁AI文档体系

## 2. 核心功能变更

### 2.1 智能门锁AI功能（新增）

#### 2.1.1 访客意图识别对话系统

**新增文件**：`main/xiaozhi-server/core/handle/doorlock_intent_handler.py`

**核心功能**：

- 访客到访时自动触发人脸识别
- 无权限访客启动意图识别对话
- 支持统一看护对话模式（同时处理对话和快递监控）
- 定时拍照机制（每5秒自动拍照并缓存）
- 对话结束后生成意图总结并发送App通知

**关键方法**：

- `handle_visitor()`: 处理访客到访主流程
- `start_unified_dialogue()`: 启动统一模式对话
- `start_photo_capture_task()`: 启动定时拍照任务
- `_post_dialogue_processing()`: 对话结束后处理

#### 2.1.2 图片上传处理器

**新增文件**：`main/xiaozhi-server/core/handle/image_upload_handler.py`

**核心功能**：

- 处理ESP32上传的图片数据
- 支持HTTP POST方式上传
- 图片上传回调机制

#### 2.1.3 事件上报处理器增强

**修改文件**：`main/xiaozhi-server/core/handle/textHandler/eventReportHandler.py`

**新增功能**：

- PIR事件和门铃事件触发人脸识别流程
- 集成智能门锁AI功能（意图识别对话）
- 支持看护模式状态检查
- 新增事件类型：`door_closed`、`lock_success`、`bolt_alarm`

**关键变更**：

```python
# 新增事件类型支持
valid_events = [
    "bell", "pir_trigger", "tamper", "door_open", "low_battery",
    "door_closed", "lock_success", "bolt_alarm"  # v5.2 新增
]

# 触发智能门锁AI处理流程
await self._trigger_face_recognition(
    conn=conn,
    ts=ts,
    param=param,
    trigger_type="bell"  # 或 "pir"
)
```

### 2.2 VLLM统一模式（重大升级）

**核心变更**：将分离的对话模式和看护模式统一为一个智能流程

**Token优化**：

- 第一轮对话：传入访客图片 + 基准图片（2张，~14K Token）
- 后续轮次：仅传入访客图片（1张，~7K Token）
- 10轮对话总计：~100K Token（相比旧版节省约30%）

**关键方法**：

- `analyze_unified()`: 统一模式分析
- `final_package_check()`: 对话结束后快递状态检查
- `generate_intent_summary()`: 生成访客意图总结

## 3. 需要新增的App协议消息

### 3.1 访客意图通知 (visitor_intent_notification)

**消息方向**：Server → App（服务器主动推送）

**触发时机**：访客对话结束后，服务器生成意图总结并发送给App

**消息格式**：

```json
{
  "type": "visitor_intent_notification",
  "ts": 1702234567890,
  "visit_id": 12345,
  "session_id": "session_123",
  "person_info": {
    "person_id": 10,
    "name": "张三",
    "relation_type": "family"
  },
  "intent_summary": {
    "intent_type": "delivery",
    "summary": "快递员送快递，已放门口",
    "important_notes": ["【留言】快递放门口了，麻烦签收一下"],
    "ai_analysis": "访客是快递员，来送快递..."
  },
  "dialogue_history": [
    {
      "role": "assistant",
      "content": "您好，请问有什么可以帮您？"
    },
    {
      "role": "user",
      "content": "我是来送快递的"
    }
  ],
  "package_check": {
    "threat_level": "low",
    "action": "normal",
    "description": "快递安全，未被触碰"
  }
}
```

**字段说明**：

| 字段                           | 类型   | 必填 | 说明                                               |
| ------------------------------ | ------ | ---- | -------------------------------------------------- |
| type                           | string | 是   | 固定为 `"visitor_intent_notification"`             |
| ts                             | int    | 是   | 时间戳（毫秒）                                     |
| visit_id                       | int    | 是   | 访问记录ID                                         |
| session_id                     | string | 是   | 会话ID                                             |
| person_info                    | object | 否   | 人员信息（识别成功时有值）                         |
| person_info.person_id          | int    | 否   | 人员ID                                             |
| person_info.name               | string | 否   | 人员姓名                                           |
| person_info.relation_type      | string | 否   | 关系类型：family/friend/unknown                    |
| intent_summary                 | object | 是   | 意图总结                                           |
| intent_summary.intent_type     | string | 是   | 意图类型：delivery/visit/sales/maintenance/other   |
| intent_summary.summary         | string | 是   | 简洁总结（一句话）                                 |
| intent_summary.important_notes | array  | 是   | 重要信息列表                                       |
| intent_summary.ai_analysis     | string | 是   | 详细AI分析                                         |
| dialogue_history               | array  | 是   | 完整对话历史                                       |
| package_check                  | object | 否   | 快递检查结果（看护模式激活时有值）                 |
| package_check.threat_level     | string | 否   | 威胁等级：low/medium/high                          |
| package_check.action           | string | 否   | 行为类型：normal/passing/searching/taking/damaging |
| package_check.description      | string | 否   | 详细描述                                           |

**意图类型说明**：

| intent_type | 说明          | 示例场景           |
| ----------- | ------------- | ------------------ |
| delivery    | 送快递/外卖   | 快递员、外卖员送货 |
| visit       | 拜访朋友/家人 | 朋友来访、邻居串门 |
| sales       | 推销产品/服务 | 推销员、广告宣传   |
| maintenance | 维修/物业工作 | 维修工、抄表员     |
| other       | 其他情况      | 无法识别的意图     |

**威胁等级说明**：

| threat_level | 说明   | 触发条件                           |
| ------------ | ------ | ---------------------------------- |
| low          | 低威胁 | 快递未被触碰、主人取快递、路人经过 |
| medium       | 中威胁 | 快递被移动但未拿走、访客翻看快递   |
| high         | 高威胁 | 快递被非主人拿走、快递被破坏       |

### 3.2 人脸识别结果推送 (face_result)

**消息方向**：Server → App（服务器主动推送）

**触发时机**：

- PIR事件或门铃事件触发人脸识别
- 人脸识别完成后推送结果给App

**消息格式**：

```json
{
  "type": "face_result",
  "ts": 1702234567890,
  "result": "known",
  "user_id": 10,
  "user_name": "张三",
  "access": {
    "granted": true,
    "reason": "authorized_user"
  }
}
```

**字段说明**：

| 字段           | 类型   | 必填 | 说明                                  |
| -------------- | ------ | ---- | ------------------------------------- |
| type           | string | 是   | 固定为 `"face_result"`                |
| ts             | int    | 是   | 时间戳（毫秒）                        |
| result         | string | 是   | 识别结果：known/unknown/no_face/error |
| user_id        | int    | 否   | 用户ID（识别成功时有值）              |
| user_name      | string | 否   | 用户姓名（识别成功时有值）            |
| access         | object | 是   | 访问控制信息                          |
| access.granted | bool   | 是   | 是否授权开锁                          |
| access.reason  | string | 是   | 授权/拒绝原因                         |

**识别结果说明**：

| result  | 说明         | access.granted | access.reason                       |
| ------- | ------------ | -------------- | ----------------------------------- |
| known   | 识别成功     | true/false     | authorized_user / unauthorized_user |
| unknown | 陌生人       | false          | unauthorized_user                   |
| no_face | 未检测到人脸 | false          | no_face_detected                    |
| error   | 识别错误     | false          | recognition_error                   |

**授权原因说明**：

| reason            | 说明                             |
| ----------------- | -------------------------------- |
| authorized_user   | 已授权用户（有开门权限）         |
| unauthorized_user | 未授权用户（无开门权限或陌生人） |
| no_face_detected  | 未检测到人脸                     |
| recognition_error | 识别过程出错                     |

**注意事项**：

- 此消息仅推送给App，不转发给ESP32
- ESP32有自己的face_result消息（v5.2协议）
- App收到此消息后应更新UI显示访客信息

### 3.3 图片上传接口 (HTTP)

**接口方向**：ESP32 → Server（HTTP POST）

**接口地址**：`POST http://{server}:8003/upload/image`

**请求头**：

```
Content-Type: application/octet-stream
device-id: AA:BB:CC:DD:EE:FF
timestamp: 1702234567890
width: 640
height: 480
```

**请求体**：JPEG图片二进制数据

**响应格式**：

```json
{
  "success": true,
  "message": "图片上传成功"
}
```

**错误响应**：

```json
{
  "success": false,
  "message": "缺少device-id头部"
}
```

**注意事项**：

- 此接口用于ESP32上传访客照片
- 服务器收到后触发回调处理
- 不直接转发给App，而是在意图通知中包含

## 4. 现有协议需要更新的部分

### 4.1 event_report 消息

**需要更新**：新增事件类型说明

**当前版本**（v2.4）：

```
事件类型：
- bell: 门铃按下
- pir_trigger: PIR 人体检测
- tamper: 撬锁报警
- door_open: 门未关超时
- low_battery: 低电量警告
```

**需要新增**（v5.2同步）：

```
- door_closed: 门已关闭
- lock_success: 上锁成功
- bolt_alarm: 反锁报警
```

**更新后的完整事件类型表**：

| event        | 说明        | param含义      | 触发条件         |
| ------------ | ----------- | -------------- | ---------------- |
| bell         | 门铃按下    | 按下次数       | 用户按门铃       |
| pir_trigger  | PIR人体检测 | 持续时间（秒） | PIR检测到人体    |
| tamper       | 撬锁报警    | 报警级别(1-3)  | 检测到撬锁行为   |
| door_open    | 门未关超时  | 超时分钟数     | 门长时间未关闭   |
| low_battery  | 低电量警告  | 电量百分比     | 电量低于阈值     |
| door_closed  | 门已关闭    | 0              | 门从开启变为关闭 |
| lock_success | 上锁成功    | 0              | 门锁成功上锁     |
| bolt_alarm   | 反锁报警    | 报警类型       | 反锁异常         |

**代码实现位置**：

- `main/xiaozhi-server/core/handle/textHandler/eventReportHandler.py`
- 已实现新事件类型的处理逻辑

### 4.2 消息类型汇总表

**需要新增到协议文档**：

| 消息类型                    | 方向         | 说明             | 版本      |
| --------------------------- | ------------ | ---------------- | --------- |
| visitor_intent_notification | Server → App | 访客意图通知     | v2.5 新增 |
| face_result                 | Server → App | 人脸识别结果推送 | v2.5 新增 |

**更新现有表格**：

在"7. 服务器推送消息"章节中新增：

```markdown
### 7.X 访客意图通知 (visitor_intent_notification)

（详细内容见3.1节）

### 7.Y 人脸识别结果推送 (face_result)

（详细内容见3.2节）
```

## 5. 协议版本升级建议

### 5.1 版本号

建议升级到 **v2.5**，理由：

- 新增2个重要的服务器推送消息类型
- 更新event_report事件类型（与ESP32 v5.2同步）
- 新增HTTP图片上传接口说明
- 向后兼容v2.4（仅新增功能，无破坏性变更）

### 5.2 升级说明模板

```markdown
> **协议升级提示**：本文档已从 v2.4 升级到 v2.5，主要变更：
>
> - 新增 visitor_intent_notification 消息（访客意图通知）
> - 新增 face_result 消息（人脸识别结果推送）
> - 更新 event_report 事件类型（新增 door_closed、lock_success、bolt_alarm）
> - 新增 HTTP 图片上传接口说明
> - 完善智能门锁AI功能的协议支持
```

### 5.3 兼容性说明

**向后兼容**：

- 所有v2.4的消息格式保持不变
- 新增消息为可选功能，不影响现有功能
- App可以选择性实现新消息的处理

**升级路径**：

1. 服务器端已实现所有新功能（2月12日后的提交）
2. App端需要实现新消息的接收和处理
3. 建议优先实现visitor_intent_notification（核心功能）
4. face_result可选实现（用于实时显示识别结果）

## 6. 实现状态总结

### 6.1 服务器端（已完成）

✅ **已实现功能**：

- 访客意图识别对话系统
- 统一看护对话模式
- 定时拍照机制
- 人脸识别触发流程
- 意图总结生成
- 快递状态检查
- 图片上传处理
- 事件上报增强

**关键文件**：

- `core/handle/doorlock_intent_handler.py` - 意图处理器
- `core/handle/image_upload_handler.py` - 图片上传处理器
- `core/handle/textHandler/eventReportHandler.py` - 事件处理器
- `core/providers/vllm/doorlock_vllm.py` - VLLM提供者

### 6.2 协议文档（待更新）

❌ **待更新内容**：

- 新增 visitor_intent_notification 消息定义
- 新增 face_result 消息定义
- 更新 event_report 事件类型
- 新增 HTTP 图片上传接口
- 更新消息类型汇总表
- 更新版本号到 v2.5

### 6.3 App端（待实现）

❌ **待实现功能**：

- 接收并显示访客意图通知
- 接收并显示人脸识别结果
- 处理新增的事件类型
- UI界面更新

## 7. 详细更新清单

### 7.1 必须更新的章节

1. **第1章 - 协议概述**
   - 更新版本号：v2.4 → v2.5
   - 添加升级说明

2. **第7章 - 服务器推送消息**
   - 新增 7.X 访客意图通知
   - 新增 7.Y 人脸识别结果推送
   - 更新 7.2 事件推送的事件类型表

3. **第10章 - 消息类型汇总**
   - 更新消息类型表，新增2个消息类型

4. **附录**
   - 新增 HTTP 图片上传接口说明

### 7.2 建议新增的章节

1. **智能门锁AI功能说明**
   - 访客意图识别流程
   - 统一看护对话模式
   - 意图类型说明
   - 威胁等级说明

2. **集成指南**
   - App端如何处理新消息
   - UI设计建议
   - 错误处理建议

## 8. Token消耗参考

### 8.1 VLLM调用Token消耗

| 场景               | 对话轮次 | Token消耗 | 说明                                    |
| ------------------ | -------- | --------- | --------------------------------------- |
| 看护激活（10轮）   | 10       | ~100K     | 第一轮14K + 后续9×7K + 检查15K + 总结8K |
| 看护激活（5轮）    | 5        | ~65K      | 第一轮14K + 后续4×7K + 检查15K + 总结8K |
| 仅对话模式（10轮） | 10       | ~85K      | 第一轮7K + 后续9×7K + 总结8K            |

### 8.2 性能指标

| 操作           | 目标时间 | 说明                 |
| -------------- | -------- | -------------------- |
| 单轮对话       | <5秒     | 包含ASR + VLLM + TTS |
| 拍照操作       | <1秒     | ESP32拍照            |
| 对话结束后处理 | <10秒    | 包含检查和总结       |
| 完整对话流程   | <2分钟   | 10轮对话             |

## 9. 相关文档

### 9.1 新增文档（已完成）

- `unified-mode-user-guide.md` - 统一模式用户手册
- `doorlock-vllm-api-reference.md` - VLLM API参考
- `doorlock-intent-handler-api-reference.md` - 意图处理器API参考
- `doorlock-configuration-guide.md` - 配置指南
- `doorlock-prompt-customization-guide.md` - 提示词自定义指南
- `doorlock-troubleshooting-guide.md` - 故障排查指南

### 9.2 需要更新的文档

- `智能猫眼门锁系统-服务器与App通信协议规范-v2.4.md` → v2.5
- `智能猫眼门锁系统-ESP32与服务器通信协议规范-v5.2.md` （参考对比）

## 10. 下一步行动

### 10.1 立即执行

1. ✅ 生成本分析报告
2. ⏳ 更新App协议文档到v2.5
3. ⏳ 编写App端集成指南
4. ⏳ 更新CHANGELOG.md

### 10.2 后续跟进

1. App端实现新消息处理
2. 进行端到端测试
3. 更新API文档
4. 编写用户使用手册

## 11. 总结

### 11.1 核心变更

本次更新主要围绕**智能门锁AI功能**展开，实现了：

- 访客到访时的智能对话和意图识别
- 统一的看护对话模式（Token优化）
- 完整的访客意图通知机制
- 人脸识别结果实时推送

### 11.2 协议影响

- 新增2个重要的服务器推送消息
- 更新事件类型定义（与ESP32 v5.2同步）
- 向后兼容，不影响现有功能
- 为智能门锁AI功能提供完整的协议支持

### 11.3 实施建议

1. **优先级高**：visitor_intent_notification（核心功能）
2. **优先级中**：face_result（用户体验提升）
3. **优先级低**：HTTP图片上传接口（内部使用）

---

**报告生成时间**：2026年2月19日  
**分析人员**：Kiro AI  
**文档版本**：v1.0
