# 协议版本兼容性修复

## 问题描述

ESP32 从 version=1 切换到 version=2 后，服务器代码错误地将所有 >=16 字节的消息当作 BinaryProtocol2 解析，导致以下错误：

```
解析BinaryProtocol2失败：'utf-8' codec can't decode byte 0xe0 in position 1: invalid continuation byte
```

## ESP32 协议版本说明

根据 ESP32 代码和实际需求：

### Version 1（旧版本）
- **格式**：原始音频数据，无头部
- **用途**：正常模式下的音频传输
- **处理**：直接送入 ASR 队列
- **状态**：已弃用，ESP32 现在使用 version=2

### Version 2（当前版本）
- **格式**：16 字节头部 + 负载数据
- **结构**：
  ```c
  struct BinaryProtocol2 {
      uint16_t version;      // 2
      uint16_t type;         // 0: OPUS/VIDEO, 1: JSON
      uint32_t reserved;     // 音频=0, 视频=(width<<16)|height
      uint32_t timestamp;    // 时间戳（毫秒）
      uint32_t payload_size; // 负载大小
      uint8_t payload[];     // 负载数据
  }
  ```
- **用途**：
  - type=0, reserved=0: OPUS 音频
  - type=0, reserved!=0: JPEG 视频（监控模式）
  - type=1: JSON 消息
- **字节序**：大端序（big-endian）

## 音频格式说明

### 服务器 → ESP32 音频格式

根据 `sendAudioHandle.py`，服务器发送给 ESP32 的音频有两种格式：

1. **普通 ESP32**：原始 OPUS 数据（无头部）
   ```python
   await conn.websocket.send(opus_packet)
   ```

2. **MQTT 网关**：带 16 字节头部的数据包
   ```python
   header = bytearray(16)
   header[0] = 1  # type
   header[2:4] = len(opus_packet).to_bytes(2, "big")
   header[4:8] = sequence.to_bytes(4, "big")
   header[8:12] = timestamp.to_bytes(4, "big")
   header[12:16] = len(opus_packet).to_bytes(4, "big")
   complete_packet = bytes(header) + opus_packet
   ```

### App → ESP32 音频格式

App 发送的音频应该和"服务器发送给 ESP32"的格式一致：
- 普通 ESP32: 原始 OPUS 数据
- MQTT 网关: 带 16 字节头部

服务器只需识别并转发，不需要解析。

## 修复方案

### 1. 智能协议检测

修改 `_route_message` 方法，只有当版本号为 2 时才尝试解析为 BinaryProtocol2：

```python
async def _route_message(self, message):
    if isinstance(message, bytes):
        handled = False
        
        # 检查是否为 BinaryProtocol2 格式
        if len(message) >= 16:
            try:
                version = int.from_bytes(message[0:2], "big")
                
                # 只有当版本号为 2 时才尝试解析
                if version == 2:
                    handled = await self._process_binary_protocol2(message)
            except Exception:
                pass
        
        # 如果没有被处理，当作原始音频（version=1）
        if not handled:
            if self.vad is not None and self.asr is not None:
                self.asr_audio_queue.put(message)
```

### 2. ESP32 → 服务器 → App 数据流

添加 `_build_binary_protocol2` 方法，确保转发给 App 的数据包含完整的 BinaryProtocol2 头部：

```python
def _build_binary_protocol2(self, msg_type: int, reserved: int, 
                            timestamp: int, payload: bytes) -> bytes:
    import struct
    
    version = 2
    payload_size = len(payload)
    
    # 构造16字节头部 (大端序)
    header = struct.pack('>HHIII', 
        version, msg_type, reserved, timestamp, payload_size
    )
    
    return header + payload
```

在 `_handle_audio_data` 和 `_handle_video_data` 中使用：

```python
# 监控模式：构造 BinaryProtocol2 格式并转发给 App
bp2_message = self._build_binary_protocol2(
    msg_type=0,
    reserved=0,  # 音频: reserved = 0
    timestamp=timestamp,
    payload=audio_data
)
await self._forward_to_apps(bp2_message, is_video=False)
```

### 3. App → 服务器 → ESP32 音频流

App 发送的音频直接转发给 ESP32，保持原始格式：

```python
async def _handle_binary_message(self, message: bytes):
    """处理二进制消息（App 发送的音频，用于对讲）
    
    App 发送的音频格式应该和服务器发送给 ESP32 的格式一致：
    - 普通 ESP32: 原始 OPUS 数据（无头部）
    - MQTT 网关: 带 16 字节头部的数据包
    """
    # 转发给 ESP32（保持原始格式）
    await esp32_conn.websocket.send(message)
```

## 数据流向图

```
正常模式（语音对话）：
ESP32 --[version=2, type=0, reserved=0, OPUS]-> 服务器 -> ASR -> LLM -> TTS
服务器 --[原始 OPUS]-> ESP32

监控模式（视频监控 + 对讲）：
ESP32 --[version=2, type=0, reserved=0, OPUS]-> 服务器 --[version=2]-> App
ESP32 --[version=2, type=0, reserved!=0, JPEG]-> 服务器 --[version=2]-> App
App --[原始 OPUS]-> 服务器 --[原始 OPUS]-> ESP32
```

## 测试验证

### 1. Version 2 音频测试（正常模式）
```bash
# ESP32 使用 version=2 发送音频
# 服务器应该正确解析并送入 ASR
# 服务器日志应该没有解析错误
```

### 2. Version 2 视频测试（监控模式）
```bash
# 启动监控模式
# ESP32 发送视频数据（version=2, type=0, reserved=(width<<16)|height）
# App 应该能正确接收并显示视频
```

### 3. App 对讲测试
```bash
# App 发送原始 OPUS 音频
# 服务器转发给 ESP32
# ESP32 应该能正常播放
```

## 修改的文件

1. **main/xiaozhi-server/core/connection.py**
   - `_route_message()`: 添加版本检测，只解析 version=2
   - `_process_binary_protocol2()`: 支持 version=2（移除 version=3）
   - `_build_binary_protocol2()`: 新增方法，构造 BinaryProtocol2 消息
   - `_handle_audio_data()`: 构造完整的 BinaryProtocol2 消息转发给 App
   - `_handle_video_data()`: 构造完整的 BinaryProtocol2 消息转发给 App

2. **main/xiaozhi-server/core/app_connection.py**
   - `_handle_binary_message()`: 直接转发 App 音频给 ESP32，保持原始格式

## 预期结果

修复后：
- ✅ Version 2 音频正常工作，无解析错误
- ✅ Version 2 视频正常工作，App 能接收并显示
- ✅ App 对讲功能正常，音频能正确转发
- ✅ 向后兼容 version=1（如果有旧设备）

## 注意事项

1. **版本号检测**：只有版本号为 2 时才尝试解析 BinaryProtocol2
2. **字节序**：所有多字节字段使用大端序（big-endian）
3. **App 音频格式**：App 发送的音频应该和服务器发送给 ESP32 的格式一致（原始 OPUS）
4. **错误处理**：解析失败时回退到原始音频处理（version=1 兼容）
5. **监控模式**：ESP32 → 服务器 → App 使用 BinaryProtocol2 格式
6. **对讲模式**：App → 服务器 → ESP32 使用原始 OPUS 格式
