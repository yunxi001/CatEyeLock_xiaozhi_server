-- 智能门锁AI功能数据库迁移脚本
-- 版本: 1.0
-- 日期: 2026-02-09
-- 描述: 添加意图识别和快递看护功能所需的数据库表

-- 1. 扩展 persons 表
-- 添加 is_owner 字段标识主人身份（可取走快递）
-- 注意：如果字段已存在会报错，但迁移脚本会忽略此类错误
ALTER TABLE persons
ADD COLUMN is_owner BOOLEAN DEFAULT FALSE COMMENT '是否为主人（可取走快递）';

-- 修改 custom_greeting 字段为 TEXT 类型以支持 JSON 格式的欢迎词配置
ALTER TABLE persons
MODIFY COLUMN custom_greeting TEXT COMMENT '欢迎词配置(JSON格式: {"morning":"早上好","afternoon":"下午好","evening":"晚上好","night":"夜深了","default":"欢迎回家"})';

-- 2. 创建 doorlock_config 表
-- 存储每个设备的门锁AI功能配置
CREATE TABLE IF NOT EXISTS doorlock_config (
    device_id VARCHAR(50) PRIMARY KEY COMMENT '设备ID',
    intent_recognition_enabled BOOLEAN DEFAULT TRUE COMMENT '是否启用意图识别功能',
    package_guard_available BOOLEAN DEFAULT TRUE COMMENT '是否启用快递看护功能（总开关）',
    package_guard_active BOOLEAN DEFAULT FALSE COMMENT '快递看护模式是否当前激活',
    package_baseline_image VARCHAR(255) DEFAULT NULL COMMENT '看护基准图片路径',
    package_guard_start_time DATETIME DEFAULT NULL COMMENT '看护模式启动时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='门锁AI功能配置表';

-- 3. 创建 doorlock_visitor_intents 表
-- 存储访客意图识别记录
CREATE TABLE IF NOT EXISTS doorlock_visitor_intents (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
    visit_id INT DEFAULT NULL COMMENT '关联的访问记录ID',
    session_id VARCHAR(50) NOT NULL COMMENT '会话ID（格式：device_id_timestamp）',
    person_id INT DEFAULT NULL COMMENT '识别到的人员ID',
    intent_type VARCHAR(50) DEFAULT 'other' COMMENT '意图类型：delivery(送快递/外卖)、visit(拜访)、sales(推销)、maintenance(维修/物业)、other(其他)',
    intent_summary TEXT COMMENT '意图总结（JSON格式：{"important_notes":[],"purpose":"","full_summary":""}）',
    dialogue_history TEXT COMMENT '对话历史（JSON格式：[{"role":"assistant","content":""},{"role":"user","content":""}]）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (visit_id) REFERENCES visit_records(id) ON DELETE CASCADE,
    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE SET NULL,
    INDEX idx_session (session_id),
    INDEX idx_person (person_id),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='访客意图识别记录表';

-- 4. 创建 doorlock_package_alerts 表
-- 存储快递异常警报记录
CREATE TABLE IF NOT EXISTS doorlock_package_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '警报ID',
    device_id VARCHAR(50) NOT NULL COMMENT '设备ID',
    session_id VARCHAR(50) NOT NULL COMMENT '会话ID',
    threat_level ENUM('low', 'medium', 'high') NOT NULL COMMENT '威胁等级：low(低威胁)、medium(中威胁)、high(高威胁)',
    action VARCHAR(50) DEFAULT 'normal' COMMENT '行为类型：taking(拿走)、searching(翻找)、damaging(破坏)、normal(正常)、passing(路过)',
    description TEXT COMMENT '详细描述',
    photo_path VARCHAR(255) DEFAULT NULL COMMENT '证据照片路径',
    voice_warning_sent BOOLEAN DEFAULT FALSE COMMENT '是否已发送语音警告',
    notified BOOLEAN DEFAULT FALSE COMMENT '是否已通知App',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_device_time (device_id, created_at),
    INDEX idx_session (session_id),
    INDEX idx_threat_level (threat_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='快递异常警报记录表';

-- 迁移完成
SELECT '数据库迁移脚本执行完成' AS status;
