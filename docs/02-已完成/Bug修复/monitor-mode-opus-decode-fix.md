# 监控模式 Opus 解码错误修复报告

## 问题描述

监控模式启动后，日志中出现大量 `opus 解码失败: corrupted stream` 错误。

## 根因分析

### 问题 1：未正确解析 BinaryProtocol2 协议头

**错误代码**：

```python
# 直接对完整帧（包含 16 字节头部）进行 opus 解码
pcm_data = self._opus_decoder_for_app.decode(data, 960)  # ❌
```

**问题**：

- ESP32 发送的是 `[16字节头部] + [payload]` 格式
- 直接解码会把头部数据也传给 opus 解码器
- 导致 `corrupted stream` 错误

### 问题 2：未区分音频帧和视频帧

**BinaryProtocol2 协议规范**：

```
struct BinaryProtocol2 {
    uint16_t version;      // 协议版本 = 2
    uint16_t type;         // 消息类型 = 0（音视频）
    uint32_t reserved;     // 音频=0，视频=(width<<16)|height
    uint32_t timestamp;    // 时间戳（毫秒）
    uint32_t payload_size; // 载荷大小
    uint8_t payload[];     // 载荷数据
}
```

**区分规则**：

- `reserved == 0` → 音频帧（opus 编码）
- `reserved != 0` → 视频帧（JPEG 编码）

**问题**：

- 原代码未检查 `reserved` 字段
- 将视频帧（9KB JPEG 数据）当作音频帧解码
- 导致 opus 解码器收到 JPEG 数据，报 `corrupted stream`

## 修复方案

### 1. 正确解析协议头并提取 payload

```python
# 解析头部
version = int.from_bytes(data[0:2], 'big')
msg_type = int.from_bytes(data[2:4], 'big')
reserved = int.from_bytes(data[4:8], 'big')
timestamp = int.from_bytes(data[8:12], 'big')
payload_size = int.from_bytes(data[12:16], 'big')

# 提取 payload
opus_payload = data[16:16 + payload_size]

# 解码 payload
pcm_data = self._opus_decoder_for_app.decode(opus_payload, 960)  # ✅
```

### 2. 区分音频和视频帧

```python
# 区分帧类型
is_audio = (reserved == 0)
is_video = (reserved != 0)

if is_video:
    # 视频帧：不需要转发给 App（App 直接从 ESP32 接收）
    return

# 只处理音频帧
if is_audio:
    opus_payload = data[16:16 + payload_size]
    pcm_data = self._opus_decoder_for_app.decode(opus_payload, 960)
    # 转发 PCM 给 App
```

## 修复后的行为

1. **视频帧**：识别后跳过，不进行 opus 解码
2. **音频帧**：正确提取 opus payload 后解码为 PCM
3. **调试日志**：前几帧打印详细信息，便于验证

## 验证方法

启动监控模式后，日志应显示：

```
[INFO] 视频帧 #1: 640x480, payload=9256 bytes, 跳过转发
[INFO] 音频帧 #1: payload_size=120, total_len=136
[INFO] 转发 PCM 数据到 1 个 App: 1920 bytes
```

不应再出现 `opus 解码失败` 错误。

## 相关文件

- `main/xiaozhi-server/core/connection.py`：修复位置
- `main/xiaozhi-server/test/test_monitor_opus_decode.py`：协议解析测试

## 技术要点

1. **BinaryProtocol2 使用网络字节序（大端序）**
2. **音频帧特征**：reserved=0，payload 约 100-200 字节（60ms opus）
3. **视频帧特征**：reserved 包含分辨率，payload 约 5-15 KB（JPEG）
4. **Opus 解码参数**：16kHz 单声道，960 采样点（60ms）
