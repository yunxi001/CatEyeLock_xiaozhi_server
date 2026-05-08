# ESP32 音视频流扩展功能设计文档

## 需求分析

### 1. 核心需求
- 接收来自ESP32的音视频流
- 向ESP32发送音频流
- 具备开关控制功能（开启/关闭）
- 不影响原有功能
- 实现简单

### 2. 非功能性需求
- 最小化对现有系统的影响
- 支持独立端口，避免端口冲突
- 易于配置和管理
- 高效的音视频数据传输

## 技术方案分析

### 1. 通信协议选择对比

#### 1.1 WebSocket
**优势：**
- 与现有系统架构一致（xiaozhi-server已使用WebSocket）
- 支持二进制数据传输
- 实时双向通信
- 连接保持，减少连接开销

**劣势：**
- 需要单独的连接管理
- 音视频数据量大时可能影响现有WebSocket连接

#### 1.2 HTTP/HTTPS
**优势：**
- 标准化协议，易于调试
- 支持流式传输
- 与现有OTA和视觉分析功能一致

**劣势：**
- 基于请求-响应模型，实时性不如WebSocket
- 连接管理相对复杂

#### 1.3 MQTT
**优势：**
- 与现有MQTT网关集成
- 适合音视频数据发布/订阅
- QoS支持，数据传输可靠

**劣势：**
- 需要外部MQTT网关
- 消息大小限制（如需传输大文件）

### 2. 推荐方案：WebSocket + 独立端口

基于需求分析，推荐使用WebSocket协议配合独立端口，原因如下：

1. 与现有架构一致
2. 支持实时双向音视频流
3. 连接管理简单
4. 通过开关控制，不影响现有功能

## 详细设计方案

### 1. 系统架构

```
ESP32 Device ──┐
                ├─ WebSocket (新端口) ── 音视频流处理服务
ESP32 Device ──┘

原有功能 (WebSocket, HTTP, MQTT) ── 不受影响
```

### 2. 端口规划

- **现有WebSocket接口**: 8000 (默认)
- **新增音视频流接口**: 8001 (建议)
- **现有HTTP接口**: 8003 (默认)

### 3. 功能模块设计

#### 3.1 音视频流服务器模块
- `audio_video_stream_server.py`: 独立的WebSocket服务器
- `stream_handler.py`: 音视频数据处理
- `stream_manager.py`: 连接管理和开关控制

#### 3.2 配置管理
- 在 `config.yaml` 中添加音视频流配置项
- 支持运行时开关控制

### 4. 实现步骤

#### 4.1 创建音视频流服务器

1. **创建服务器文件** (`core/audio_video_stream_server.py`)

```python
import asyncio
import websockets
import json
from config.logger import setup_logging

class AudioVideoStreamServer:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        self.enabled = config.get("audio_video_stream", {}).get("enabled", False)
        self.port = config.get("audio_video_stream", {}).get("port", 8001)
        self.host = config.get("audio_video_stream", {}).get("host", "0.0.0.0")
        self.connections = set()
        
    async def start(self):
        if not self.enabled:
            self.logger.info("音视频流服务已禁用")
            return
            
        self.logger.info(f"启动音视频流服务，监听端口: {self.port}")
        
        server = await websockets.serve(
            self._handle_connection,
            self.host,
            self.port
        )
        
        self.logger.info(f"音视频流服务已启动，端口: {self.port}")
        await server.wait_closed()
        
    async def _handle_connection(self, websocket, path):
        self.logger.info(f"新音视频流连接: {websocket.remote_address}")
        self.connections.add(websocket)
        try:
            async for message in websocket:
                # 处理音视频数据
                await self._handle_audio_video_data(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"音视频流连接断开: {websocket.remote_address}")
        finally:
            self.connections.discard(websocket)
            
    async def _handle_audio_video_data(self, websocket, data):
        # 处理接收到的音视频数据
        # 可以根据数据格式前缀来区分音频和视频数据
        if isinstance(data, bytes):
            # 音视频二进制数据
            await self._process_media_data(websocket, data)
        elif isinstance(data, str):
            # 控制消息
            await self._process_control_message(websocket, data)
            
    async def _process_media_data(self, websocket, data):
        # 处理音视频数据
        # 可以根据数据头部标识区分音频/视频/控制数据
        data_type = data[0:4] if len(data) >= 4 else b''
        
        if data_type == b'AUDD':  # 音频数据
            audio_data = data[4:]
            await self._handle_audio_data(websocket, audio_data)
        elif data_type == b'VIDD':  # 视频数据
            video_data = data[4:]
            await self._handle_video_data(websocket, video_data)
        else:
            # 未定义的数据类型，可能需要根据具体格式调整
            self.logger.warning(f"未知的媒体数据类型: {data_type[:8]}...")
            
    async def _handle_audio_data(self, websocket, audio_data):
        # 处理音频数据
        self.logger.debug(f"接收到音频数据: {len(audio_data)} 字节")
        # 可以添加音频处理逻辑
        
    async def _handle_video_data(self, websocket, video_data):
        # 处理视频数据
        self.logger.debug(f"接收到视频数据: {len(video_data)} 字节")
        # 可以添加视频处理逻辑
        
    async def _process_control_message(self, websocket, message):
        # 处理控制消息
        try:
            msg_obj = json.loads(message)
            action = msg_obj.get('action')
            if action == 'stream_start':
                self.logger.info(f"开始流媒体传输: {websocket.remote_address}")
            elif action == 'stream_stop':
                self.logger.info(f"停止流媒体传输: {websocket.remote_address}")
        except json.JSONDecodeError:
            self.logger.warning(f"无效的控制消息: {message}")
            
    async def broadcast_audio(self, audio_data: bytes):
        """向所有连接的设备广播音频数据"""
        if not self.connections:
            return
            
        # 添加音频数据标识头
        message = b'AUDD' + audio_data
        
        disconnected = set()
        for connection in self.connections.copy():
            try:
                await connection.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(connection)
                
        # 移除断开的连接
        for connection in disconnected:
            self.connections.discard(connection)
```

2. **创建配置文件修改** (`config.yaml`)

```yaml
# 音视频流功能
audio_video_stream:
  enabled: false  # 默认关闭，不影响原有功能
  port: 8001      # 独立端口
  host: 0.0.0.0   # 监听地址
  # 其他音视频流相关配置
```

3. **修改主应用** (`app.py`)

```python
# 在 app.py 中添加对音视频流服务的支持
async def main():
    # ... 现有代码 ...
    
    # 音视频流服务器
    av_stream_server = None
    av_stream_task = None
    
    # 检查配置是否启用音视频流功能
    if config.get("audio_video_stream", {}).get("enabled", False):
        av_stream_server = AudioVideoStreamServer(config)
        av_stream_task = asyncio.create_task(av_stream_server.start())
        logger.bind(tag=TAG).info(
            "音视频流服务已启用，监听地址: {}:{}", 
            config.get("audio_video_stream", {}).get("host", "0.0.0.0"),
            config.get("audio_video_stream", {}).get("port", 8001)
        )
    
    # ... 现有任务启动代码 ...
    
    try:
        await wait_for_exit()
    finally:
        # ... 现有清理代码 ...
        
        # 清理音视频流服务
        if av_stream_task:
            av_stream_task.cancel()
            try:
                await asyncio.wait_for(av_stream_task, timeout=3.0)
            except asyncio.TimeoutError:
                pass
```

#### 4.2 实现开关控制

1. **创建开关管理器** (`core/audio_video_stream_manager.py`)

```python
import asyncio
from config.logger import setup_logging

class AudioVideoStreamManager:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        self.is_enabled = config.get("audio_video_stream", {}).get("enabled", False)
        self.server = None
        self.task = None
        
    async def start_service(self):
        if self.is_enabled:
            from core.audio_video_stream_server import AudioVideoStreamServer
            self.server = AudioVideoStreamServer(self.config)
            self.task = asyncio.create_task(self.server.start())
            self.logger.info("音视频流服务已启动")
        else:
            self.logger.info("音视频流服务未启用")
    
    async def stop_service(self):
        if self.task:
            self.task.cancel()
            try:
                await asyncio.wait_for(self.task, timeout=3.0)
            except asyncio.TimeoutError:
                self.logger.warning("音视频流服务停止超时")
            self.task = None
            self.logger.info("音视频流服务已停止")
    
    def enable_service(self):
        if not self.is_enabled:
            self.is_enabled = True
            self.config["audio_video_stream"]["enabled"] = True
            asyncio.create_task(self.start_service())
    
    def disable_service(self):
        if self.is_enabled:
            self.is_enabled = False
            self.config["audio_video_stream"]["enabled"] = False
            asyncio.create_task(self.stop_service())
```

2. **添加HTTP API用于运行时控制** (`core/api/audio_video_stream_api.py`)

```python
import json
from aiohttp import web
from config.logger import setup_logging

class AudioVideoStreamAPI:
    def __init__(self, stream_manager):
        self.stream_manager = stream_manager
        self.logger = setup_logging()
    
    async def handle_control(self, request):
        """处理音视频流控制请求"""
        if request.method == 'POST':
            try:
                data = await request.json()
                action = data.get('action')
                
                if action == 'enable':
                    self.stream_manager.enable_service()
                    return web.json_response({"success": True, "message": "服务已启用"})
                elif action == 'disable':
                    self.stream_manager.disable_service()
                    return web.json_response({"success": True, "message": "服务已禁用"})
                else:
                    return web.json_response({"success": False, "error": "无效操作"}, status=400)
            except Exception as e:
                self.logger.error(f"控制请求处理失败: {str(e)}")
                return web.json_response({"success": False, "error": str(e)}, status=500)
        elif request.method == 'GET':
            return web.json_response({
                "enabled": self.stream_manager.is_enabled,
                "status": "running" if self.stream_manager.task and not self.stream_manager.task.done() else "stopped"
            })
```

3. **在HTTP服务器中注册API** (`core/http_server.py`)

```python
# 导入新的API处理器
from core.api.audio_video_stream_api import AudioVideoStreamAPI

# 在HTTP服务器初始化时添加API实例
class SimpleHttpServer:
    def __init__(self, config: dict):
        # ... 现有代码 ...
        self.av_stream_api = AudioVideoStreamAPI(stream_manager)  # 需要初始化流管理器
        
    def _add_routes(self, app):
        # ... 现有路由 ...
        # 添加音视频流控制API
        app.add_routes([
            web.get("/xiaozhi/av_stream/control", self.av_stream_api.handle_control),
            web.post("/xiaozhi/av_stream/control", self.av_stream_api.handle_control),
        ])
```

### 5. ESP32端协议设计

#### 5.1 数据格式
- **音频数据**: `AUDD` + 音频数据 (4字节标识 + 实际数据)
- **视频数据**: `VIDD` + 视频数据 (4字节标识 + 实际数据)
- **控制消息**: JSON格式的字符串消息

#### 5.2 连接流程
1. ESP32连接到新端口 (8001)
2. 发送连接确认消息
3. 开始发送音视频数据流
4. 服务器可以推送音频数据回ESP32

### 6. 安全考虑

#### 6.1 认证机制
- 使用JWT令牌认证
- 设备ID验证
- 连接频率限制

#### 6.2 数据安全
- 支持WSS (WebSocket Secure)
- 可选的数据加密

### 7. 性能优化

#### 7.1 流量控制
- 实现数据缓冲区管理
- 支持流量控制和拥塞避免

#### 7.2 资源管理
- 连接数限制
- 内存使用监控
- 连接超时处理

## 部署考虑

### 1. 配置示例

```yaml
# 完整的音视频流配置示例
audio_video_stream:
  enabled: false      # 默认禁用，不影响现有功能
  port: 8001          # 独立端口
  host: 0.0.0.0       # 监听地址
  max_connections: 10 # 最大连接数
  buffer_size: 8192   # 缓冲区大小
  enable_ssl: false   # 是否启用SSL
```

### 2. 监控和日志
- 详细的连接日志
- 数据传输统计
- 错误和异常监控

## 总结

此方案具有以下优点：

1. **不影响现有功能** - 独立端口和独立服务
2. **易于开关控制** - 配置文件和运行时API双重控制
3. **架构一致性** - 使用WebSocket，与现有架构一致
4. **扩展性好** - 模块化设计，易于后续扩展
5. **实现简单** - 遵循现有代码模式，易于理解和维护

该方案可以满足您的所有需求，同时保持系统的稳定性和可维护性。