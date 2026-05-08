# 数据库迁移总结 - v5.0 到 v5.2

## 迁移概述

本次迁移为 xiaozhi-server 数据库添加了协议 v5.2 所需的新字段和表结构。

## 已完成的工作

### 1. 创建迁移脚本 ✓

**文件**: `migrations/upgrade_v5.0_to_v5.2.sql`

**内容**:
- 使用动态 SQL 确保幂等性（可以安全地多次执行）
- 自动检查字段和索引是否已存在
- 包含数据迁移逻辑
- 包含验证查询

**特性**:
- ✅ 幂等性设计：可以安全地重复执行
- ✅ 自动检测：只在需要时添加字段和索引
- ✅ 数据迁移：自动将旧的 result 字段转换为新的 status 字段
- ✅ 验证查询：执行后自动验证迁移结果

### 2. unlock_logs 表更新 ✓

**新增字段**:
- `status` VARCHAR(16) DEFAULT 'success' - 状态字段（success/fail/locked）
- `lock_time` INT DEFAULT 0 - 剩余锁定时间（分钟）

**新增索引**:
- `idx_status` - status 字段索引，提高查询性能

**数据迁移**:
- result=1 → status='success'
- result=0 → status='fail'
- 保留原有 result 字段以保持向后兼容

### 3. door_opened_logs 表验证 ✓

**状态**: 表已存在于代码中（database.py 第 155-165 行）

**表结构**:
```sql
CREATE TABLE IF NOT EXISTS door_opened_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL COMMENT '设备 ID',
    method VARCHAR(16) NOT NULL COMMENT '开锁方式',
    source VARCHAR(16) NOT NULL COMMENT '开门来源: outside/inside/unknown',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_device_time (device_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='开门日志表'
```

**说明**: 此表由应用程序在启动时自动创建，无需手动迁移

### 4. device_events 表验证 ✓

**状态**: 表已支持新事件类型

**表结构**:
```sql
CREATE TABLE IF NOT EXISTS device_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(32) NOT NULL,  -- 使用 VARCHAR，已支持新事件类型
    param INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_device_time (device_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
```

**新增事件类型**:
- `door_closed` - 门关闭事件
- `lock_success` - 上锁成功事件
- `bolt_alarm` - 门栓报警事件

**说明**: 使用 VARCHAR(32) 类型，无需修改表结构即可支持新事件类型

## 辅助工具

### 1. 迁移执行脚本 ✓

**文件**: `migrations/run_migration.py`

**功能**:
- 从配置文件或命令行参数读取数据库配置
- 自动执行迁移脚本
- 验证迁移结果
- 提供详细的日志输出

**使用方式**:
```bash
# 使用配置文件
python run_migration.py --config ../config.yaml

# 使用命令行参数
python run_migration.py --host localhost --user root --password xxx --database xiaozhi
```

### 2. 验证脚本 ✓

**文件**: `test/verify_migration_script.py`

**功能**:
- 验证迁移脚本语法
- 验证执行脚本语法
- 验证 README 文档完整性
- 提供详细的验证报告

**使用方式**:
```bash
cd main/xiaozhi-server
python test/verify_migration_script.py
```

**验证结果**: ✓ 所有验证通过

### 3. 文档 ✓

**文件**: `migrations/README.md`

**内容**:
- 迁移脚本说明
- 执行方式（3种方式）
- 验证方法
- 回滚方法
- 注意事项
- 故障排查

## 执行建议

### 执行前准备

1. **备份数据库**
   ```bash
   mysqldump -u username -p database_name > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **在测试环境验证**
   - 先在测试环境执行迁移
   - 验证应用程序功能正常
   - 确认数据迁移正确

3. **检查应用程序版本**
   - 确保应用程序代码已更新以支持新字段
   - 确保所有 Handler 已实现（任务 1-10）

### 执行步骤

1. **停止应用程序**（可选，建议）
   ```bash
   # 停止 xiaozhi-server
   pkill -f "python.*app.py"
   ```

2. **执行迁移**
   ```bash
   cd main/xiaozhi-server/migrations
   python run_migration.py --config ../config.yaml
   ```

3. **验证迁移结果**
   ```sql
   -- 验证字段
   DESCRIBE unlock_logs;
   
   -- 验证数据迁移
   SELECT result, status, COUNT(*) FROM unlock_logs GROUP BY result, status;
   
   -- 验证索引
   SHOW INDEX FROM unlock_logs WHERE Key_name = 'idx_status';
   ```

4. **启动应用程序**
   ```bash
   cd main/xiaozhi-server
   python app.py
   ```

5. **功能测试**
   - 测试开锁日志上报
   - 测试开门日志上报
   - 测试新增事件类型
   - 测试 locked 状态

### 回滚方案

如果迁移后出现问题，可以执行回滚：

```sql
-- 回滚迁移
ALTER TABLE unlock_logs DROP COLUMN status;
ALTER TABLE unlock_logs DROP COLUMN lock_time;
DROP INDEX idx_status ON unlock_logs;

-- 恢复备份（如果需要）
mysql -u username -p database_name < backup_YYYYMMDD_HHMMSS.sql
```

## 验证清单

- [x] 迁移脚本创建完成
- [x] 迁移脚本语法验证通过
- [x] 执行脚本创建完成
- [x] 执行脚本语法验证通过
- [x] README 文档创建完成
- [x] 验证脚本创建完成
- [x] 所有验证测试通过

## 下一步

1. **任务 12**: 实现数据库访问方法
   - 更新 `save_unlock_log()` 方法支持新字段
   - 实现 `save_door_opened_log()` 方法
   - 更新 `save_device_event()` 方法

2. **任务 13**: 核心功能验证
   - 验证所有 Handler 正常工作
   - 验证消息路由正确
   - 验证数据库操作正常

3. **任务 14-16**: 测试与验证（可选）
   - 编写单元测试
   - 编写集成测试
   - 最终验证

## 相关文件

```
main/xiaozhi-server/
├── migrations/
│   ├── upgrade_v5.0_to_v5.2.sql      # 迁移脚本
│   ├── run_migration.py              # 执行脚本
│   ├── README.md                     # 使用文档
│   └── MIGRATION_SUMMARY.md          # 本文件
├── test/
│   └── verify_migration_script.py    # 验证脚本
└── core/
    └── providers/
        └── doorlock/
            └── database.py           # 数据库访问层
```

## 技术细节

### 幂等性实现

迁移脚本使用 MySQL 的动态 SQL 和 INFORMATION_SCHEMA 来实现幂等性：

```sql
-- 检查字段是否存在
SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
   WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename 
   AND COLUMN_NAME = @columnname) > 0,
  'SELECT 1',  -- 字段已存在，执行空操作
  CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ...')  -- 字段不存在，添加字段
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
```

### 数据迁移策略

只迁移 status 字段为默认值的记录，避免覆盖已经更新的数据：

```sql
UPDATE unlock_logs 
SET status = CASE 
    WHEN result = 1 THEN 'success' 
    WHEN result = 0 THEN 'fail'
    ELSE 'success'
END
WHERE status = 'success' AND result IS NOT NULL;
```

## 注意事项

1. **向后兼容**: 保留了 result 字段，确保旧版本应用程序仍能正常工作
2. **性能影响**: 添加索引可能需要一些时间，取决于表的大小
3. **锁定时间**: ALTER TABLE 操作会锁定表，建议在低峰期执行
4. **磁盘空间**: 确保有足够的磁盘空间用于表重建

## 联系方式

如有问题，请查看：
- 需求文档: `.kiro/specs/protocol-upgrade-v5.0-to-v5.2/requirements.md`
- 设计文档: `.kiro/specs/protocol-upgrade-v5.0-to-v5.2/design.md`
- 任务列表: `.kiro/specs/protocol-upgrade-v5.0-to-v5.2/tasks.md`

---

**创建日期**: 2026-01-17  
**任务状态**: ✓ 已完成  
**验证状态**: ✓ 所有验证通过
