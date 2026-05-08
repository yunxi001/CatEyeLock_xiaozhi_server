#!/usr/bin/env python3
"""
智能门锁AI功能数据库迁移验证脚本

此脚本会详细检查迁移后的数据库状态，包括：
- 表结构验证
- 索引验证
- 外键验证
- 数据类型验证

用法：
    # 从 config.yaml 读取配置（推荐）
    python verify_doorlock_ai_migration.py
    
    # 或使用命令行参数
    python verify_doorlock_ai_migration.py --host localhost --user root --password xxx --database smart_doorlock
"""

import argparse
import sys
from pathlib import Path
import pymysql
from loguru import logger
from typing import Dict, List, Tuple

# 添加父目录到 Python 路径以导入配置
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ruamel.yaml import YAML
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def load_config_from_yaml() -> dict:
    """
    从 config.yaml 读取 MySQL 配置
    
    Returns:
        dict: MySQL 配置字典，如果读取失败返回 None
    """
    config_path = Path(__file__).parent.parent / "config.yaml"
    
    if not config_path.exists():
        logger.warning(f"配置文件不存在: {config_path}")
        return None
    
    if not HAS_YAML:
        logger.warning("未安装 ruamel.yaml，无法读取配置文件")
        return None
    
    try:
        yaml = YAML()
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.load(f)
        
        if 'mysql' not in config:
            logger.warning("config.yaml 中未找到 mysql 配置段")
            return None
        
        mysql_config = config['mysql']
        
        # 验证必需字段
        required_fields = ['host', 'port', 'user', 'password', 'database']
        for field in required_fields:
            if field not in mysql_config:
                logger.warning(f"mysql 配置缺少必需字段: {field}")
                return None
        
        logger.info(f"✓ 从 config.yaml 读取到 MySQL 配置")
        return mysql_config
        
    except Exception as e:
        logger.warning(f"读取配置文件失败: {e}")
        return None


class MigrationVerifier:
    """数据库迁移验证器"""
    
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.conn = None
        self.cursor = None
        self.verification_results = []
    
    def connect(self) -> bool:
        """连接数据库"""
        try:
            self.conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset='utf8mb4'
            )
            self.cursor = self.conn.cursor()
            logger.success(f"✓ 数据库连接成功: {self.host}:{self.port}/{self.database}")
            return True
        except Exception as e:
            logger.error(f"✗ 数据库连接失败: {e}")
            return False
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("数据库连接已关闭")
    
    def verify_persons_table(self) -> bool:
        """验证 persons 表的扩展字段"""
        logger.info("")
        logger.info("1. 验证 persons 表扩展")
        logger.info("-"*70)
        
        try:
            # 检查 is_owner 字段
            self.cursor.execute("""
                SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'persons'
                  AND COLUMN_NAME = 'is_owner'
            """, (self.database,))
            
            is_owner_field = self.cursor.fetchone()
            if is_owner_field:
                logger.success(f"  ✓ is_owner 字段存在")
                logger.info(f"    类型: {is_owner_field[1]}, 默认值: {is_owner_field[3]}, 注释: {is_owner_field[4]}")
                is_owner_ok = True
            else:
                logger.error(f"  ✗ is_owner 字段不存在")
                is_owner_ok = False
            
            # 检查 custom_greeting 字段类型
            self.cursor.execute("""
                SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'persons'
                  AND COLUMN_NAME = 'custom_greeting'
            """, (self.database,))
            
            custom_greeting_field = self.cursor.fetchone()
            if custom_greeting_field:
                field_type = custom_greeting_field[1].lower()
                if 'text' in field_type:
                    logger.success(f"  ✓ custom_greeting 字段类型正确: {custom_greeting_field[1]}")
                    logger.info(f"    注释: {custom_greeting_field[2]}")
                    custom_greeting_ok = True
                else:
                    logger.warning(f"  ⚠ custom_greeting 字段类型不是 TEXT: {custom_greeting_field[1]}")
                    custom_greeting_ok = False
            else:
                logger.error(f"  ✗ custom_greeting 字段不存在")
                custom_greeting_ok = False
            
            result = is_owner_ok and custom_greeting_ok
            self.verification_results.append(("persons 表扩展", result))
            return result
            
        except Exception as e:
            logger.error(f"  ✗ 验证失败: {e}")
            self.verification_results.append(("persons 表扩展", False))
            return False
    
    def verify_doorlock_config_table(self) -> bool:
        """验证 doorlock_config 表"""
        logger.info("")
        logger.info("2. 验证 doorlock_config 表")
        logger.info("-"*70)
        
        try:
            # 检查表是否存在
            self.cursor.execute("""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'doorlock_config'
            """, (self.database,))
            
            if not self.cursor.fetchone():
                logger.error("  ✗ doorlock_config 表不存在")
                self.verification_results.append(("doorlock_config 表", False))
                return False
            
            logger.success("  ✓ doorlock_config 表存在")
            
            # 检查必需字段
            required_fields = [
                'device_id',
                'intent_recognition_enabled',
                'package_guard_available',
                'package_guard_active',
                'package_baseline_image',
                'package_guard_start_time'
            ]
            
            self.cursor.execute("""
                SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'doorlock_config'
                ORDER BY ORDINAL_POSITION
            """, (self.database,))
            
            columns = self.cursor.fetchall()
            existing_fields = {col[0] for col in columns}
            
            logger.info("  表字段:")
            for col in columns:
                logger.info(f"    - {col[0]:30} {col[1]:20} 默认值: {col[2]}")
            
            missing_fields = set(required_fields) - existing_fields
            if missing_fields:
                logger.error(f"  ✗ 缺少字段: {', '.join(missing_fields)}")
                result = False
            else:
                logger.success(f"  ✓ 所有必需字段都存在")
                result = True
            
            self.verification_results.append(("doorlock_config 表", result))
            return result
            
        except Exception as e:
            logger.error(f"  ✗ 验证失败: {e}")
            self.verification_results.append(("doorlock_config 表", False))
            return False
    
    def verify_doorlock_visitor_intents_table(self) -> bool:
        """验证 doorlock_visitor_intents 表"""
        logger.info("")
        logger.info("3. 验证 doorlock_visitor_intents 表")
        logger.info("-"*70)
        
        try:
            # 检查表是否存在
            self.cursor.execute("""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'doorlock_visitor_intents'
            """, (self.database,))
            
            if not self.cursor.fetchone():
                logger.error("  ✗ doorlock_visitor_intents 表不存在")
                self.verification_results.append(("doorlock_visitor_intents 表", False))
                return False
            
            logger.success("  ✓ doorlock_visitor_intents 表存在")
            
            # 检查字段
            self.cursor.execute("""
                SELECT COLUMN_NAME, COLUMN_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'doorlock_visitor_intents'
                ORDER BY ORDINAL_POSITION
            """, (self.database,))
            
            columns = self.cursor.fetchall()
            logger.info("  表字段:")
            for col in columns:
                logger.info(f"    - {col[0]:25} {col[1]}")
            
            # 检查外键
            self.cursor.execute("""
                SELECT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'doorlock_visitor_intents'
                  AND REFERENCED_TABLE_NAME IS NOT NULL
            """, (self.database,))
            
            foreign_keys = self.cursor.fetchall()
            logger.info("  外键约束:")
            for fk in foreign_keys:
                logger.info(f"    - {fk[1]} -> {fk[2]}.{fk[3]}")
            
            if len(foreign_keys) >= 2:
                logger.success(f"  ✓ 外键约束正确（{len(foreign_keys)} 个）")
                result = True
            else:
                logger.warning(f"  ⚠ 外键约束数量不足: {len(foreign_keys)}")
                result = False
            
            self.verification_results.append(("doorlock_visitor_intents 表", result))
            return result
            
        except Exception as e:
            logger.error(f"  ✗ 验证失败: {e}")
            self.verification_results.append(("doorlock_visitor_intents 表", False))
            return False
    
    def verify_doorlock_package_alerts_table(self) -> bool:
        """验证 doorlock_package_alerts 表"""
        logger.info("")
        logger.info("4. 验证 doorlock_package_alerts 表")
        logger.info("-"*70)
        
        try:
            # 检查表是否存在
            self.cursor.execute("""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'doorlock_package_alerts'
            """, (self.database,))
            
            if not self.cursor.fetchone():
                logger.error("  ✗ doorlock_package_alerts 表不存在")
                self.verification_results.append(("doorlock_package_alerts 表", False))
                return False
            
            logger.success("  ✓ doorlock_package_alerts 表存在")
            
            # 检查字段
            self.cursor.execute("""
                SELECT COLUMN_NAME, COLUMN_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'doorlock_package_alerts'
                ORDER BY ORDINAL_POSITION
            """, (self.database,))
            
            columns = self.cursor.fetchall()
            logger.info("  表字段:")
            for col in columns:
                logger.info(f"    - {col[0]:25} {col[1]}")
            
            # 检查索引
            self.cursor.execute("""
                SELECT INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX
                FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'doorlock_package_alerts'
                ORDER BY INDEX_NAME, SEQ_IN_INDEX
            """, (self.database,))
            
            indexes = self.cursor.fetchall()
            logger.info("  索引:")
            
            index_dict = {}
            for idx in indexes:
                index_name = idx[0]
                if index_name not in index_dict:
                    index_dict[index_name] = []
                index_dict[index_name].append(idx[1])
            
            for index_name, columns in index_dict.items():
                logger.info(f"    - {index_name}: {', '.join(columns)}")
            
            # 验证 idx_device_time 索引
            if 'idx_device_time' in index_dict:
                idx_columns = index_dict['idx_device_time']
                if 'device_id' in idx_columns and 'created_at' in idx_columns:
                    logger.success(f"  ✓ idx_device_time 索引正确")
                    result = True
                else:
                    logger.error(f"  ✗ idx_device_time 索引字段不正确")
                    result = False
            else:
                logger.error(f"  ✗ idx_device_time 索引不存在")
                result = False
            
            self.verification_results.append(("doorlock_package_alerts 表", result))
            return result
            
        except Exception as e:
            logger.error(f"  ✗ 验证失败: {e}")
            self.verification_results.append(("doorlock_package_alerts 表", False))
            return False
    
    def test_data_operations(self) -> bool:
        """测试数据操作"""
        logger.info("")
        logger.info("5. 测试数据操作")
        logger.info("-"*70)
        
        try:
            # 测试插入 doorlock_config
            self.cursor.execute("""
                INSERT INTO doorlock_config (device_id, intent_recognition_enabled, package_guard_available)
                VALUES ('test_device_verify', TRUE, TRUE)
                ON DUPLICATE KEY UPDATE device_id = device_id
            """)
            logger.success("  ✓ doorlock_config 插入测试成功")
            
            # 测试读取
            self.cursor.execute("""
                SELECT device_id, intent_recognition_enabled, package_guard_available
                FROM doorlock_config
                WHERE device_id = 'test_device_verify'
            """)
            record = self.cursor.fetchone()
            if record:
                logger.success(f"  ✓ doorlock_config 读取测试成功: {record}")
            
            # 清理测试数据
            self.cursor.execute("DELETE FROM doorlock_config WHERE device_id = 'test_device_verify'")
            self.conn.commit()
            logger.success("  ✓ 测试数据已清理")
            
            self.verification_results.append(("数据操作测试", True))
            return True
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"  ✗ 数据操作测试失败: {e}")
            self.verification_results.append(("数据操作测试", False))
            return False
    
    def print_summary(self):
        """打印验证总结"""
        logger.info("")
        logger.info("="*70)
        logger.info("验证总结")
        logger.info("="*70)
        
        all_passed = all(result for _, result in self.verification_results)
        
        for name, result in self.verification_results:
            status = "✓" if result else "✗"
            logger.info(f"  {status} {name}")
        
        logger.info("")
        if all_passed:
            logger.success("="*70)
            logger.success("✓ 所有验证项通过，迁移成功！")
            logger.success("="*70)
            logger.info("")
            logger.info("迁移内容:")
            logger.info("  ✓ persons 表新增 is_owner 字段")
            logger.info("  ✓ persons 表 custom_greeting 字段改为 TEXT 类型")
            logger.info("  ✓ doorlock_config 表已创建")
            logger.info("  ✓ doorlock_visitor_intents 表已创建")
            logger.info("  ✓ doorlock_package_alerts 表已创建")
            logger.info("  ✓ idx_device_time 索引已创建")
        else:
            logger.error("="*70)
            logger.error("✗ 部分验证项失败，请检查上述错误")
            logger.error("="*70)
        
        return all_passed
    
    def verify_all(self) -> bool:
        """执行所有验证"""
        if not self.connect():
            return False
        
        try:
            logger.info("="*70)
            logger.info("智能门锁AI功能数据库迁移验证")
            logger.info("="*70)
            
            self.verify_persons_table()
            self.verify_doorlock_config_table()
            self.verify_doorlock_visitor_intents_table()
            self.verify_doorlock_package_alerts_table()
            self.test_data_operations()
            
            return self.print_summary()
            
        finally:
            self.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='验证智能门锁AI功能数据库迁移结果',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从 config.yaml 读取配置（推荐）
  python verify_doorlock_ai_migration.py
  
  # 使用命令行参数
  python verify_doorlock_ai_migration.py --user root --password 123456 --database smart_doorlock
        """
    )
    parser.add_argument('--host', type=str, help='数据库主机（默认: 从config.yaml读取或localhost）')
    parser.add_argument('--port', type=int, help='数据库端口（默认: 从config.yaml读取或3306）')
    parser.add_argument('--user', type=str, help='数据库用户（默认: 从config.yaml读取）')
    parser.add_argument('--password', type=str, help='数据库密码（默认: 从config.yaml读取）')
    parser.add_argument('--database', type=str, help='数据库名称（默认: 从config.yaml读取）')
    
    args = parser.parse_args()
    
    # 尝试从 config.yaml 读取配置
    yaml_config = load_config_from_yaml()
    
    # 合并配置：命令行参数优先级高于配置文件
    host = args.host or (yaml_config.get('host') if yaml_config else None) or 'localhost'
    port = args.port or (yaml_config.get('port') if yaml_config else None) or 3306
    user = args.user or (yaml_config.get('user') if yaml_config else None)
    password = args.password or (str(yaml_config.get('password')) if yaml_config else None)
    database = args.database or (yaml_config.get('database') if yaml_config else None)
    
    # 验证必需参数
    if not user or not password or not database:
        logger.error("错误: 缺少必需的数据库连接参数")
        logger.error("")
        logger.error("请使用以下方式之一:")
        logger.error("  1. 在 config.yaml 中配置 mysql 段（推荐）")
        logger.error("  2. 使用命令行参数: --user USER --password PASSWORD --database DATABASE")
        logger.error("")
        logger.error("运行 'python verify_doorlock_ai_migration.py --help' 查看详细帮助")
        return 1
    
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # 执行验证
    verifier = MigrationVerifier(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )
    
    success = verifier.verify_all()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
