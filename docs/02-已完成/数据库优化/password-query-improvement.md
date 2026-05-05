# 密码查询功能改进说明

## 修改概述

将密码查询机制从"转发到 ESP32 查询"改为"服务器直接返回"，提升查询效率和离线可用性。

## 修改内容

### 1. 数据库变更

**新增表**: `device_info`

```sql
CREATE TABLE device_info (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL UNIQUE COMMENT '设备 ID',
    password_encrypted VARCHAR(255) DEFAULT NULL COMMENT '加密后的密码',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_device_id (device_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备基本信息表';
```

**字段说明**:

- `device_id`: 设备唯一标识
- `password_encrypted`: 加密后的密码（Base64 编码）
- 默认密码: "123456"

### 2. 代码修改

#### 2.1 数据库操作 (`database.py`)

**新增方法**:

- `encode_password_simple(password)`: 密码编码（Base64）
- `decrypt_password(encrypted)`: 密码解码
- `init_device_password(device_id, default_password)`: 初始化设备密码
- `update_device_password(device_id, password)`: 更新设备密码
- `get_device_password(device_id)`: 获取设备密码

#### 2.2 密码上报处理 (`passwordReportHandler.py`)

**修改逻辑**:

- 收到 ESP32 的 `password_report` 消息时
- 更新服务器数据库中的密码
- 转发给关联的 App（保持兼容性）

#### 2.3 查询处理 (`queryHandler.py`)

**新增功能**:

- 添加 `password` 查询目标
- 直接从服务器数据库读取密码
- 无需转发到 ESP32

#### 2.4 命令代理 (`commandProxyHandler.py`)

**修改逻辑**:

- 拦截 `user_mgmt` 中的密码查询命令（`category=password, command=query`）
- 返回错误提示，引导使用 `query` 接口

## 使用方式

### App 查询密码（新方式）

**请求**:

```json
{
  "type": "query",
  "seq_id": "1702234567890_019",
  "target": "password"
}
```

**响应**:

```json
{
  "type": "query_result",
  "target": "password",
  "status": "success",
  "data": {
    "password": "123456"
  }
}
```

### ESP32 上报密码（保持不变）

当 ESP32 设置密码或响应密码查询时，发送 `password_report`:

```json
{
  "type": "password_report",
  "ts": 1702234567890,
  "data": {
    "password": "123456"
  }
}
```

服务器会自动更新数据库中的密码。

### 设置密码（保持不变）

通过 `user_mgmt` 命令设置密码：

```json
{
  "type": "user_mgmt",
  "seq_id": "1702234567890_020",
  "category": "password",
  "command": "set",
  "payload": "654321"
}
```

## 数据迁移

### 执行迁移

```bash
# 方式 1: 使用 Python 脚本（推荐）
cd main/xiaozhi-server
python migrations/run_add_device_password.py

# 方式 2: 直接执行 SQL
mysql -u root -p smart_doorlock < migrations/add_device_password.sql
```

### 迁移内容

1. 创建 `device_info` 表
2. 为所有现有设备初始化默认密码 "123456"
3. 验证迁移结果

## 优势对比

### 修改前（转发到 ESP32）

```
App → Server → ESP32
    (user_mgmt)
    category: "password"
    command: "query"

ESP32 → Server → App
    (password_report)
    data: { password: "123456" }
```

**缺点**:

- ❌ 需要设备在线
- ❌ 查询延迟高（网络往返）
- ❌ 增加设备负担
- ❌ 需要重试机制

### 修改后（服务器直接返回）

```
App → Server
    (query)
    target: "password"

Server → App
    (query_result)
    data: { password: "123456" }
```

**优点**:

- ✅ 设备离线也可查询
- ✅ 查询速度快（直接读数据库）
- ✅ 减轻设备负担
- ✅ 无需重试机制
- ✅ 与其他查询接口一致

## 安全性说明

### 密码存储

- 使用 Base64 编码存储（可逆加密）
- 生产环境建议升级为 AES 对称加密
- 日志中不记录密码明文，仅记录长度

### 密码传输

- 通过 WebSocket 加密传输（WSS）
- 建议启用 TLS/SSL 证书

### 密码同步

- ESP32 上报密码时自动更新服务器
- 服务器作为密码的唯一可信来源
- 设备重启后可从服务器恢复密码

## 兼容性

### 向后兼容

- ESP32 仍可发送 `password_report` 消息
- 服务器会自动更新数据库并转发给 App
- 旧版 App 仍可接收 `password_report` 消息

### 废弃接口

- `user_mgmt` 中的密码查询（`category=password, command=query`）
- 建议 App 升级使用 `query` 接口（`target=password`）

## 测试建议

### 功能测试

1. **密码查询测试**
   - App 发送 `query` 请求（`target=password`）
   - 验证返回默认密码 "123456"

2. **密码更新测试**
   - ESP32 发送 `password_report` 消息
   - 验证服务器数据库已更新
   - App 再次查询，验证返回新密码

3. **离线查询测试**
   - ESP32 离线状态
   - App 查询密码
   - 验证仍可返回上次存储的密码

4. **默认密码测试**
   - 新设备首次连接
   - App 查询密码
   - 验证返回默认密码 "123456"

### 性能测试

- 对比修改前后的查询响应时间
- 预期提升: 从 2-3 秒降低到 < 100ms

## 相关文件

| 文件                                               | 修改内容           |
| -------------------------------------------------- | ------------------ |
| `core/providers/doorlock/database.py`              | 新增密码管理方法   |
| `core/handle/textHandler/passwordReportHandler.py` | 添加密码更新逻辑   |
| `core/handle/textHandler/queryHandler.py`          | 新增密码查询功能   |
| `core/handle/textHandler/commandProxyHandler.py`   | 拦截旧密码查询命令 |
| `migrations/add_device_password.sql`               | 数据库迁移脚本     |
| `migrations/run_add_device_password.py`            | Python 迁移脚本    |

## 后续优化建议

1. **加密升级**: 将 Base64 编码升级为 AES-256 对称加密
2. **密码策略**: 添加密码强度验证（长度、复杂度）
3. **密码历史**: 记录密码修改历史，防止重复使用
4. **密码过期**: 支持密码定期过期和强制修改
5. **多设备同步**: 支持一个账号下多个设备的密码同步

## 版本信息

- 修改日期: 2026-01-18
- 影响版本: v5.2+
- 兼容性: 向后兼容
