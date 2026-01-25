-- 添加设备密码管理功能
-- 创建时间: 2026-01-18
-- 说明: 为设备添加密码存储功能，密码加密后存储在服务器

-- 创建 device_info 表（如果不存在）
CREATE TABLE IF NOT EXISTS device_info (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL UNIQUE COMMENT '设备 ID',
    password_encrypted VARCHAR(255) DEFAULT NULL COMMENT '加密后的密码',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_device_id (device_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备基本信息表';

-- 为所有现有设备初始化默认密码 "123456"
-- 注意：这里的加密值是 "123456" 的 Base64 编码
INSERT INTO device_info (device_id, password_encrypted)
SELECT DISTINCT device_id, 'MTIzNDU2' as password_encrypted
FROM device_status
WHERE device_id NOT IN (SELECT device_id FROM device_info)
ON DUPLICATE KEY UPDATE device_id = device_id;

-- 验证数据
SELECT COUNT(*) as total_devices FROM device_info;
