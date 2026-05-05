# 智能门锁故障排查指南

## 概述

本文档提供智能门锁系统常见问题的排查方法、解决方案和降级策略。帮助快速定位和解决问题，确保系统稳定运行。

## 快速诊断

### 系统健康检查

```bash
# 1. 检查服务状态
cd main/xiaozhi-server
ps aux | grep "python app.py"

# 2. 检查日志
tail -f logs/xiaozhi-server.log

# 3. 检查配置
python -c "from ruamel.yaml import YAML; yaml=YAML(); print(yaml.load(open('config/doorlock_config.yaml')))"

# 4. 检查数据库连接
python -c "import pymysql; conn=pymysql.connect(host='localhost', user='root', password='xxx', database='xiaozhi'); print('数据库连接正常')"

# 5. 检查 VLLM 服务
curl http://localhost:8001/health
```

---

## 常见问题

### 问题 1：对话无响应

#### 症状

- 访客到访后无任何反应
- AI 不播放问候语音
- 对话无法启动

#### 可能原因

1. VLLM 服务不可用
2. 网络连接问题
3. 配置文件错误
4. 数据库连接失败

#### 排查步骤

**步骤 1：检查 VLLM 服务**

```bash
# 检查 VLLM 服务状态
curl http://localhost:8001/health

# 如果无响应，重启 VLLM 服务
cd /path/to/vllm
./start_vllm.sh
```

**步骤 2：检查日志**

```bash
# 查看最近的错误日志
cd main/xiaozhi-server
tail -100 logs/xiaozhi-server.log | grep "ERROR"

# 常见错误信息：
# - "VLLM 调用失败"：VLLM 服务不可用
# - "数据库连接失败"：数据库问题
# - "配置加载失败"：配置文件错误
```

**步骤 3：检查配置**

```bash
# 验证配置文件格式
cd main/xiaozhi-server
python test_config_validation.py

# 检查统一模式是否启用
grep "enabled" config/doorlock_config.yaml
```

**步骤 4：检查网络连接**

```bash
# 检查 ESP32 连接
netstat -an | grep 8000

# 检查 VLLM 连接
netstat -an | grep 8001
```

#### 解决方案

**方案 1：重启 VLLM 服务**

```bash
cd /path/to/vllm
./stop_vllm.sh
./start_vllm.sh
```

**方案 2：重启 xiaozhi-server**

```bash
cd main/xiaozhi-server
pkill -f "python app.py"
python app.py
```

**方案 3：检查并修复配置**

```bash
# 恢复默认配置
cp config/doorlock_config.yaml.bak config/doorlock_config.yaml

# 重启服务
python app.py
```

---

### 问题 2：拍照失败

#### 症状

- 定时拍照任务失败
- 日志显示"拍照失败"
- 对话中无法获取最新照片

#### 可能原因

1. ESP32 摄像头故障
2. 网络连接不稳定
3. 存储空间不足
4. 拍照频率过高

#### 排查步骤

**步骤 1：检查 ESP32 状态**

```bash
# 查看 ESP32 连接状态
cd main/xiaozhi-server
tail -f logs/xiaozhi-server.log | grep "ESP32"

# 检查摄像头状态
# 通过 WebSocket 发送测试命令
```

**步骤 2：检查存储空间**

```bash
# 检查服务器存储空间
df -h

# 检查 ESP32 存储空间
# 通过设备管理界面查看
```

**步骤 3：检查拍照频率**

```bash
# 查看配置的拍照间隔
grep "interval_seconds" config/doorlock_config.yaml

# 如果间隔过短（<3秒），可能导致拍照失败
```

#### 解决方案

**方案 1：重启 ESP32 设备**

```bash
# 通过 WebSocket 发送重启命令
# 或物理重启设备
```

**方案 2：调整拍照频率**

```yaml
# config/doorlock_config.yaml
photo_cache:
  interval_seconds: 10 # 从 5 秒调整到 10 秒
```

**方案 3：清理存储空间**

```bash
# 清理旧照片
cd main/xiaozhi-server/data
rm -rf old_photos/

# 清理日志
cd logs
rm -f *.log.old
```

---

### 问题 3：Token 超限

#### 症状

- 日志显示"Token 超限"警告
- 对话被强制截断
- VLLM 调用失败

#### 可能原因

1. 对话轮次过多
2. 对话历史过长
3. 图片数量过多
4. 提示词过长

#### 排查步骤

**步骤 1：检查 Token 使用量**

```bash
# 查看 Token 使用量日志
cd main/xiaozhi-server
tail -f logs/xiaozhi-server.log | grep "Token"

# 示例输出：
# VLLM 调用统计 | 输入: 250000 | 输出: 5000 | 总计: 255000
```

**步骤 2：检查对话轮次**

```bash
# 查看配置的最大对话轮次
grep "max_rounds" config/doorlock_config.yaml

# 如果轮次过多（>15），可能导致 Token 超限
```

**步骤 3：检查提示词长度**

```bash
# 查看提示词文件大小
wc -c config/doorlock_prompts.yaml

# 如果文件过大（>10KB），可能导致 Token 超限
```

#### 解决方案

**方案 1：减少对话轮次**

```yaml
# config/doorlock_config.yaml
unified_mode:
  dialogue:
    max_rounds: 5 # 从 10 降到 5
```

**方案 2：启用对话历史截断**

```yaml
# config/doorlock_config.yaml
unified_mode:
  token_optimization:
    baseline_image_once: true # 启用优化
    reuse_context: true # 启用上下文复用
```

**方案 3：精简提示词**

```yaml
# config/doorlock_prompts.yaml
# 删除冗余内容，使用简洁表达
```

---

### 问题 4：误报警告

#### 症状

- 正常访客被判定为威胁
- 主人取快递触发警报
- 路人经过触发警报

#### 可能原因

1. 基准图片不准确
2. 光线变化影响判断
3. 威胁阈值设置过低
4. AI 判断错误

#### 排查步骤

**步骤 1：检查基准图片**

```bash
# 查看基准图片
cd main/xiaozhi-server/data
ls -lh baseline_images/

# 检查图片是否清晰、光线是否正常
```

**步骤 2：检查威胁阈值**

```bash
# 查看配置的威胁阈值
grep "report_threshold" config/doorlock_config.yaml

# 如果设置为 "low"，可能导致误报
```

**步骤 3：查看误报日志**

```bash
# 查看威胁报告日志
cd main/xiaozhi-server
tail -f logs/xiaozhi-server.log | grep "report_package_status"

# 分析误报原因
```

#### 解决方案

**方案 1：更新基准图片**

```bash
# 通过 App 或对话更新基准图片
# 确保光线充足、角度合适
```

**方案 2：调整威胁阈值**

```yaml
# config/doorlock_config.yaml
unified_mode:
  guard:
    report_threshold: "medium" # 从 "low" 调整到 "medium"
```

**方案 3：优化提示词**

```yaml
# config/doorlock_prompts.yaml
guard_tasks: |
  【威胁等级判断】
  - low：路人经过、主人取快递、邻居帮忙
  - medium：翻看快递、长时间停留（>30秒）
  - high：非主人拿走快递、破坏快递
```

---

### 问题 5：响应速度慢

#### 症状

- 对话响应时间过长（>10 秒）
- 拍照操作缓慢
- 对话结束后处理时间过长

#### 可能原因

1. VLLM 服务负载过高
2. 网络延迟
3. Token 消耗过多
4. 数据库查询慢

#### 排查步骤

**步骤 1：检查 VLLM 响应时间**

```bash
# 查看 VLLM 响应时间日志
cd main/xiaozhi-server
tail -f logs/xiaozhi-server.log | grep "响应时间"

# 示例输出：
# VLLM 响应时间: 8.5s
```

**步骤 2：检查网络延迟**

```bash
# 测试到 VLLM 服务的延迟
ping localhost

# 测试到 ESP32 的延迟
# 通过设备管理界面查看
```

**步骤 3：检查系统负载**

```bash
# 查看 CPU 使用率
top

# 查看内存使用率
free -h

# 查看磁盘 I/O
iostat
```

#### 解决方案

**方案 1：优化 Token 消耗**

```yaml
# config/doorlock_config.yaml
unified_mode:
  dialogue:
    max_rounds: 5 # 减少对话轮次

  token_optimization:
    baseline_image_once: true # 启用优化
```

**方案 2：降低拍照频率**

```yaml
# config/doorlock_config.yaml
photo_cache:
  interval_seconds: 10 # 从 5 秒调整到 10 秒
```

**方案 3：升级硬件**

- 增加 CPU 核心数
- 增加内存容量
- 使用 SSD 存储

---

### 问题 6：内存泄漏

#### 症状

- 内存使用量持续增长
- 系统变慢
- 最终服务崩溃

#### 可能原因

1. 照片缓存未清理
2. 对话历史未清理
3. 会话数据未清理
4. 代码 bug

#### 排查步骤

**步骤 1：监控内存使用**

```bash
# 实时监控内存
watch -n 1 'ps aux | grep "python app.py"'

# 查看内存增长趋势
```

**步骤 2：检查缓存大小**

```bash
# 查看照片缓存
cd main/xiaozhi-server
python -c "from core.providers.doorlock.photo_cache_manager import PhotoCacheManager; print(PhotoCacheManager().get_cache_size())"
```

**步骤 3：检查会话数量**

```bash
# 查看活跃会话数量
# 通过日志或监控工具查看
```

#### 解决方案

**方案 1：定期重启服务**

```bash
# 设置定时任务，每天凌晨重启
crontab -e
# 添加：0 3 * * * cd /path/to/xiaozhi-server && ./restart.sh
```

**方案 2：减少缓存大小**

```yaml
# config/doorlock_config.yaml
photo_cache:
  max_cache_size: 5 # 从 10 降到 5
```

**方案 3：添加内存监控**

```python
# 在代码中添加内存监控
import psutil
import gc

def check_memory():
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    if memory_mb > 1000:  # 超过 1GB
        logger.warning(f"内存使用过高: {memory_mb:.2f}MB")
        gc.collect()  # 强制垃圾回收
```

---

## 日志查看方法

### 日志文件位置

```
main/xiaozhi-server/logs/
├── xiaozhi-server.log        # 主日志
├── xiaozhi-server.log.1      # 历史日志
└── error.log                 # 错误日志
```

### 常用日志命令

```bash
# 实时查看日志
tail -f logs/xiaozhi-server.log

# 查看最近 100 行
tail -100 logs/xiaozhi-server.log

# 查看错误日志
grep "ERROR" logs/xiaozhi-server.log

# 查看警告日志
grep "WARNING" logs/xiaozhi-server.log

# 查看特定模块日志
grep "DoorlockVLLM" logs/xiaozhi-server.log

# 查看特定时间段日志
grep "2024-02-16 10:" logs/xiaozhi-server.log

# 统计错误数量
grep -c "ERROR" logs/xiaozhi-server.log
```

### 日志级别说明

| 级别    | 说明         | 示例                              |
| ------- | ------------ | --------------------------------- |
| DEBUG   | 调试信息     | 执行统一模式分析                  |
| INFO    | 正常流程信息 | 对话结束 - 会话: xxx, 轮次: 5     |
| WARNING | 警告信息     | Token 使用量已达 85%，接近上限    |
| ERROR   | 错误信息     | VLLM 调用失败: Connection refused |

---

## 性能监控方法

### 监控指标

| 指标                | 目标值 | 监控方法 |
| ------------------- | ------ | -------- |
| VLLM 响应时间       | <3 秒  | 查看日志 |
| 对话结束后处理时间  | <10 秒 | 查看日志 |
| Token 消耗（10 轮） | <120K  | 查看日志 |
| 内存使用量          | <2GB   | `ps aux` |
| CPU 使用率          | <80%   | `top`    |

### 监控脚本

```bash
#!/bin/bash
# monitor.sh - 性能监控脚本

while true; do
    echo "=== $(date) ==="

    # 检查服务状态
    if ps aux | grep -q "python app.py"; then
        echo "✓ 服务运行中"
    else
        echo "✗ 服务已停止"
    fi

    # 检查内存使用
    memory=$(ps aux | grep "python app.py" | awk '{print $6}')
    echo "内存使用: ${memory}KB"

    # 检查 CPU 使用
    cpu=$(ps aux | grep "python app.py" | awk '{print $3}')
    echo "CPU 使用: ${cpu}%"

    # 检查最近错误
    errors=$(tail -100 logs/xiaozhi-server.log | grep -c "ERROR")
    echo "最近错误数: ${errors}"

    echo ""
    sleep 60
done
```

---

## 降级方案

### 方案 1：禁用统一模式

**适用场景**：统一模式不稳定，需要回退到分离模式

**操作步骤**：

```yaml
# config/doorlock_config.yaml
unified_mode:
  enabled: false # 禁用统一模式
```

**效果**：

- 回退到分离模式
- 看护模式激活时无法对话
- 系统稳定性提高
- Token 消耗降低

---

### 方案 2：禁用看护功能

**适用场景**：看护功能导致问题，仅保留对话功能

**操作步骤**：

```yaml
# config/doorlock_config.yaml
unified_mode:
  enabled: true
  guard:
    enabled: false # 禁用看护功能
```

**效果**：

- 仅进行意图识别对话
- 不进行快递监控
- Token 消耗降低约 30%

---

### 方案 3：减少对话轮次

**适用场景**：Token 消耗过高，需要降低成本

**操作步骤**：

```yaml
# config/doorlock_config.yaml
unified_mode:
  dialogue:
    max_rounds: 3 # 从 10 降到 3
```

**效果**：

- 对话时间缩短
- Token 消耗降低约 70%
- 可能影响意图识别准确性

---

### 方案 4：禁用定时拍照

**适用场景**：拍照功能导致问题，使用手动拍照

**操作步骤**：

```yaml
# config/doorlock_config.yaml
photo_cache:
  enabled: false # 禁用定时拍照
```

**效果**：

- 每轮对话手动拍照
- 响应时间略有增加
- 资源消耗降低

---

### 方案 5：使用默认配置

**适用场景**：配置错误导致问题，恢复默认配置

**操作步骤**：

```bash
# 恢复默认配置
cp config/doorlock_config.yaml.default config/doorlock_config.yaml
cp config/doorlock_prompts.yaml.default config/doorlock_prompts.yaml

# 重启服务
python app.py
```

**效果**：

- 恢复到稳定状态
- 丢失自定义配置
- 需要重新配置

---

## 紧急处理流程

### 服务完全不可用

```bash
# 1. 停止服务
pkill -f "python app.py"

# 2. 检查日志
tail -100 logs/xiaozhi-server.log

# 3. 恢复默认配置
cp config/doorlock_config.yaml.bak config/doorlock_config.yaml

# 4. 清理缓存
rm -rf data/cache/*

# 5. 重启服务
python app.py

# 6. 验证服务
curl http://localhost:8003/health
```

---

### 数据库连接失败

```bash
# 1. 检查数据库状态
systemctl status mysql

# 2. 重启数据库
systemctl restart mysql

# 3. 验证连接
mysql -u root -p -e "SELECT 1"

# 4. 重启服务
cd main/xiaozhi-server
python app.py
```

---

### VLLM 服务不可用

```bash
# 1. 检查 VLLM 状态
curl http://localhost:8001/health

# 2. 重启 VLLM
cd /path/to/vllm
./stop_vllm.sh
./start_vllm.sh

# 3. 等待服务启动（约 1-2 分钟）
sleep 120

# 4. 验证服务
curl http://localhost:8001/health

# 5. 重启 xiaozhi-server
cd main/xiaozhi-server
python app.py
```

---

## 预防措施

### 1. 定期备份

```bash
# 备份配置文件
cp config/doorlock_config.yaml config/doorlock_config.yaml.bak
cp config/doorlock_prompts.yaml config/doorlock_prompts.yaml.bak

# 备份数据库
mysqldump -u root -p xiaozhi > backup_$(date +%Y%m%d).sql

# 备份日志
tar -czf logs_$(date +%Y%m%d).tar.gz logs/
```

---

### 2. 监控告警

```bash
# 设置监控脚本
crontab -e
# 添加：*/5 * * * * /path/to/monitor.sh

# 监控脚本示例
#!/bin/bash
# 检查服务状态
if ! ps aux | grep -q "python app.py"; then
    echo "服务已停止" | mail -s "告警" admin@example.com
fi

# 检查内存使用
memory=$(ps aux | grep "python app.py" | awk '{print $6}')
if [ $memory -gt 2000000 ]; then
    echo "内存使用过高: ${memory}KB" | mail -s "告警" admin@example.com
fi
```

---

### 3. 定期维护

```bash
# 每周清理日志
find logs/ -name "*.log.*" -mtime +7 -delete

# 每月清理缓存
rm -rf data/cache/*

# 每月优化数据库
mysql -u root -p -e "OPTIMIZE TABLE xiaozhi.visits"
```

---

## 联系支持

### 技术文档

- [VLLM 提供者 API 参考](./doorlock-vllm-api-reference.md)
- [意图处理器 API 参考](./doorlock-intent-handler-api-reference.md)
- [配置指南](./doorlock-configuration-guide.md)
- [提示词自定义指南](./doorlock-prompt-customization-guide.md)

### 社区支持

- GitHub Issues
- 技术论坛
- 用户群组

---

## 更新日志

| 版本  | 日期       | 说明                   |
| ----- | ---------- | ---------------------- |
| 1.0.0 | 2024-02-16 | 初始版本，故障排查指南 |
