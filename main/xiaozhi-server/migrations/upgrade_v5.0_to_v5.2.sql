-- ============================================================================
-- 数据库迁移脚本：协议升级 v5.0 到 v5.2
-- ============================================================================
-- 创建日期：2026-01-17
-- 说明：本脚本用于升级 xiaozhi-server 数据库以支持协议 v5.2
-- 
-- 主要变更：
-- 1. unlock_logs 表新增 status 和 lock_time 字段
-- 2. door_opened_logs 表已存在，无需创建
-- 3. device_events 表使用 VARCHAR 类型，已支持新事件类型
-- ============================================================================

-- ============================================================================
-- 1. 更新 unlock_logs 表
-- ============================================================================

-- 检查并添加 status 字段
SET @dbname = DATABASE();
SET @tablename = 'unlock_logs';
SET @columnname = 'status';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (TABLE_SCHEMA = @dbname)
      AND (TABLE_NAME = @tablename)
      AND (COLUMN_NAME = @columnname)
  ) > 0,
  'SELECT 1',
  CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(16) DEFAULT ''success'' COMMENT ''状态：success/fail/locked'' AFTER result')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- 检查并添加 lock_time 字段
SET @columnname = 'lock_time';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (TABLE_SCHEMA = @dbname)
      AND (TABLE_NAME = @tablename)
      AND (COLUMN_NAME = @columnname)
  ) > 0,
  'SELECT 1',
  CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' INT DEFAULT 0 COMMENT ''剩余锁定时间（分钟）'' AFTER status')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- 迁移旧数据：将 result 字段转换为 status 字段
-- 只更新 status 为默认值 'success' 的记录（即新添加字段后的默认值）
UPDATE unlock_logs 
SET status = CASE 
    WHEN result = 1 THEN 'success' 
    WHEN result = 0 THEN 'fail'
    ELSE 'success'
END
WHERE status = 'success' AND result IS NOT NULL;

-- 检查并添加 idx_status 索引
SET @indexname = 'idx_status';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE
      (TABLE_SCHEMA = @dbname)
      AND (TABLE_NAME = @tablename)
      AND (INDEX_NAME = @indexname)
  ) > 0,
  'SELECT 1',
  CONCAT('CREATE INDEX ', @indexname, ' ON ', @tablename, '(status)')
));
PREPARE createIndexIfNotExists FROM @preparedStatement;
EXECUTE createIndexIfNotExists;
DEALLOCATE PREPARE createIndexIfNotExists;

-- ============================================================================
-- 2. 验证 door_opened_logs 表
-- ============================================================================
-- 注意：door_opened_logs 表已在代码中通过 CREATE TABLE IF NOT EXISTS 创建
-- 此处仅添加验证注释，无需额外操作

-- 验证表是否存在
SELECT 
    CASE 
        WHEN COUNT(*) > 0 THEN 'door_opened_logs 表已存在'
        ELSE 'door_opened_logs 表不存在，将由应用程序自动创建'
    END AS status
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'door_opened_logs';

-- ============================================================================
-- 3. 验证 device_events 表
-- ============================================================================
-- 注意：device_events 表使用 VARCHAR(32) 类型，已支持新事件类型
-- 无需修改表结构

-- 验证表结构
SELECT 
    COLUMN_NAME,
    COLUMN_TYPE,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() 
  AND TABLE_NAME = 'device_events'
  AND COLUMN_NAME = 'event_type';

-- ============================================================================
-- 4. 迁移完成验证
-- ============================================================================

-- 验证 unlock_logs 表结构
SELECT 
    'unlock_logs 表结构验证' AS check_type,
    COLUMN_NAME,
    COLUMN_TYPE,
    IS_NULLABLE,
    COLUMN_DEFAULT,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() 
  AND TABLE_NAME = 'unlock_logs'
  AND COLUMN_NAME IN ('status', 'lock_time')
ORDER BY ORDINAL_POSITION;

-- 验证索引
SELECT 
    'unlock_logs 索引验证' AS check_type,
    INDEX_NAME,
    COLUMN_NAME,
    SEQ_IN_INDEX
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = DATABASE() 
  AND TABLE_NAME = 'unlock_logs'
  AND INDEX_NAME = 'idx_status';

-- ============================================================================
-- 迁移脚本执行完成
-- ============================================================================
-- 
-- 执行方式：
-- 1. 手动执行：mysql -u username -p database_name < upgrade_v5.0_to_v5.2.sql
-- 2. 应用程序自动执行：通过 Python 代码读取并执行
-- 
-- 回滚方式（如需要）：
-- ALTER TABLE unlock_logs DROP COLUMN status;
-- ALTER TABLE unlock_logs DROP COLUMN lock_time;
-- DROP INDEX idx_status ON unlock_logs;
-- 
-- ============================================================================
