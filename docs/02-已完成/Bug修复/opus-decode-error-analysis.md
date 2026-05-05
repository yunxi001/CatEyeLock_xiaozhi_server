# Opus 解码错误分析与解决方案

## 问题描述

在监控模式下，服务器日志出现大量 `opus 解码失败: b'corrupted stream'` 错误。

## 错误日志示例

```
260118 15:44:38[0.8.8-SiDoAlHushcaQw][core.connection]-ERROR-opus 解码失败: b'corrupted stream'
```

## 问题分析

### 1. 触发场景

- 当 ESP32 进入**监控模式**（`start_monitor`）后开始出现
- 错误持续出现，直到退出监控模式（`stop_monitor`）

### 2. 根本原因

监控模式下 ESP32 发送的音频数据存在以下问题之一：

1. **数据格式不匹配**
   - 解码器期望：16kHz 单声道，960 采样点/帧（60ms）
   - 实际数据：可能不符合标准 opus 格式

2. **数据包损坏**
   - ESP32 在监控模式下可能发送了不完整或损坏的 opus 数据包
   - 网络传输过程中数据包可能被截断

3. **解码器状态异常**
   - 连续解码失败可能导致解码器内部状态损坏
   - 需要定期重置解码器

### 3. 当前配置

```yaml
# config.yaml
xiaozhi:
  audio_params:
    format: opus
    sample_rate: 16000
    channels: 1
    frame_duration: 60 # 60ms = 960 采样点 @ 16kHz
```

## 解决方案

### 已实施的改进

1. **错误日志限流**
   - 避免日志刷屏，每 5 秒或每 100 次错误才记录一次
   - 添加累计错误计数，便于监控

2. **自动重置解码器**
   - 当连续错误超过 10 次时，自动重置 opus 解码器
   - 清除可能损坏的解码器状态

3. **增强错误信息**
   - 记录数据包长度，便于诊断
   - 显示累计错误次数

### 代码修改位置

**文件**: `main/xiaozhi-server/core/connection.py`

**方法**: `_forward_to_apps()`

**关键改进**:

```python
# 添加错误计数和限流
self._opus_decode_error_count = 0
self._opus_decode_last_error_time = 0

# 限制日志频率
if (current_time - self._opus_decode_last_error_time > 5.0 or
    self._opus_decode_error_count % 100 == 1):
    self.logger.bind(tag=TAG).warning(...)

# 自动重置解码器
if self._opus_decode_error_count > 10:
    self._opus_decoder_for_app = opuslib_next.Decoder(16000, 1)
```

## 进一步排查建议

### 1. 检查 ESP32 端配置

确认 ESP32 在监控模式下的音频编码参数：

```c
// ESP32 端应确保
opus_encoder_ctl(encoder, OPUS_SET_BITRATE(16000));
opus_encoder_ctl(encoder, OPUS_SET_COMPLEXITY(5));
opus_encoder_ctl(encoder, OPUS_SET_SIGNAL(OPUS_SIGNAL_VOICE));
```

### 2. 验证数据包完整性

在 `_forward_to_apps()` 中添加调试日志：

```python
# 检查数据包长度是否合理
if len(data) < 10 or len(data) > 1000:
    self.logger.bind(tag=TAG).warning(
        f"异常数据包长度: {len(data)} bytes"
    )
```

### 3. 尝试不同的解码参数

如果问题持续，可以尝试调整解码参数：

```python
# 尝试不同的帧大小
pcm_data = self._opus_decoder_for_app.decode(data, 480)  # 30ms
# 或
pcm_data = self._opus_decoder_for_app.decode(data, 1920)  # 120ms
```

### 4. 考虑直接转发原始数据

如果解码持续失败，可以考虑直接转发 opus 数据给 App：

```python
# 方案：让 App 端自己解码
for app_conn in app_conns:
    if app_conn.websocket:
        await app_conn.websocket.send(data)  # 发送原始 opus 数据
```

## 监控指标

### 正常状态

- opus 解码成功率 > 99%
- 错误日志每小时 < 10 条

### 异常状态（需要介入）

- opus 解码成功率 < 90%
- 错误日志持续刷屏
- 解码器频繁重置（每分钟 > 1 次）

## 相关文件

- `main/xiaozhi-server/core/connection.py` - 连接处理和 opus 解码
- `main/xiaozhi-server/core/handle/textHandler/systemMessageHandler.py` - 监控模式控制
- `main/xiaozhi-server/config.yaml` - 音频参数配置

## 更新日志

- **2026-01-18**: 实施错误日志限流和自动重置解码器
- **2026-01-18**: 创建本诊断文档
