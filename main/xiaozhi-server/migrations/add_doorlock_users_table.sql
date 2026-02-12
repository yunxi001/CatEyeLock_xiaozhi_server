-- ============================================================================
-- 数据库迁移脚本：添加门锁用户表
-- ============================================================================
-- 创建日期：2026-01-30
-- 说明：本脚本用于创建 doorlock_users 表，统一管理指纹、NFC、密码用户
-- 
-- 主要功能：
-- 1. 创建 doorlock_users 表
-- 2. 存储用户类型、ID、备注等元数据
-- 3. 支持软删除
-- ============================================================================

-- 创建门锁用户表
CREATE TABLE IF NOT EXISTS doorlock_users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    device_id VARCHAR(64) NOT NULL COMMENT '设备 ID',
    user_type VARCHAR(16) NOT NULL COMMENT '用户类型：finger/nfc/password',
    user_id INT NOT NULL COMMENT 'ESP32 分配的用户 ID（指纹/NFC 的槽位 ID）',
    user_name VARCHAR(64) DEFAULT NULL COMMENT '用户备注名称',
    user_data VARCHAR(255) DEFAULT NULL COMMENT '额外数据（如 NFC 卡号、密码哈希）',
    status TINYINT DEFAULT 1 COMMENT '状态：0=已删除，1=正常',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by VARCHAR(64) DEFAULT NULL COMMENT '创建者 app_id',
    
    UNIQUE KEY uk_device_type_userid (device_id, user_type, user_id),
    INDEX idx_device_id (device_id),
    INDEX idx_user_type (user_type),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='门锁用户表（统一管理指纹、NFC、密码）';

-- ============================================================================
-- 验证表创建
-- ============================================================================

-- 验证表结构
SELECT 
    'doorlock_users 表结构验证' AS check_type,
    COLUMN_NAME,
    COLUMN_TYPE,
    IS_NULLABLE,
    COLUMN_DEFAULT,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() 
  AND TABLE_NAME = 'doorlock_users'
ORDER BY ORDINAL_POSITION;

-- 验证索引
SELECT 
    'doorlock_users 索引验证' AS check_type,
    INDEX_NAME,
    COLUMN_NAME,
    SEQ_IN_INDEX,
    NON_UNIQUE
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = DATABASE() 
  AND TABLE_NAME = 'doorlock_users'
ORDER BY INDEX_NAME, SEQ_IN_INDEX;

-- ============================================================================
-- 迁移脚本执行完成
-- ============================================================================
-- 
-- 执行方式：
-- 1. 手动执行：mysql -u username -p database_name < add_doorlock_users_table.sql
-- 2. 应用程序自动执行：通过 Python 代码读取并执行
-- 
-- 回滚方式（如需要）：
-- DROP TABLE IF EXISTS doorlock_users;
-- 
-- ============================================================================
