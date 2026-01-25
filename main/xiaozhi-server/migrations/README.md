# 数据库迁移脚本

本目录包含 xiaozhi-server 的数据库迁移脚本。

## 迁移脚本列表

### upgrade_v5.0_to_v5.2.sql

**目的**：升级数据库以支持协议 v5.2

**主要变更**：
1. `unlock_logs` 表新增 `status` 和 `lock_time` 字段
2. 验证 `door_opened_logs` 表存在（由应用程序自动创建）
3. 验证 `device_events` 表支持新事件类型

**执行方式**：

#### 方式 1：使用 Python 脚本（推荐）

```bash
# 使用配置文件
cd main/xiaozhi-server/migrations
python run_migration.py --config ../config.yaml

# 或者直接指定数据库参数
python run_migration.py --host localhost --user root --password your_password --database xiaozhi
```

#### 方式 2：手动执行 SQL

```bash
# 连接到数据库并执行迁移脚本
mysql -u username -p database_name < migrations/upgrade_v5.0_to_v5.2.sql
```

#### 方式 3：通过 Python 代码执行

```python
import pymysql
from pathlib import Path

def run_migration(host, user, password, database):
    """执行数据库迁移"""
    # 读取迁移脚本
    script_path = Path(__file__).parent / "upgrade_v5.0_to_v5.2.sql"
    with open(script_path, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    # 连接数据库
    conn = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        charset='utf8mb4'
    )
    
    try:
        cursor = conn.cursor()
        
        # 分割并执行 SQL 语句
        # 注意：需要处理存储过程和复杂语句
        for statement in sql_script.split(';'):
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                cursor.execute(statement)
        
        conn.commit()
        print("迁移成功完成")
        
    except Exception as e:
        conn.rollback()
        print(f"迁移失败: {e}")
        raise
    finally:
        conn.close()

# 使用示例
if __name__ == "__main__":
    run_migration(
        host="localhost",
        user="root",
        password="your_password",
        database="xiaozhi"
    )
```

## 验证迁移结果

执行迁移后，可以通过以下 SQL 验证：

```sql
-- 验证 unlock_logs 表结构
DESCRIBE unlock_logs;

-- 验证新字段存在
SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT 
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() 
  AND TABLE_NAME = 'unlock_logs'
  AND COLUMN_NAME IN ('status', 'lock_time');

-- 验证索引
SHOW INDEX FROM unlock_logs WHERE Key_name = 'idx_status';

-- 验证数据迁移
SELECT result, status, COUNT(*) as count
FROM unlock_logs
GROUP BY result, status;
```

## 回滚迁移

如果需要回滚迁移，可以执行以下 SQL：

```sql
-- 删除新增字段
ALTER TABLE unlock_logs DROP COLUMN status;
ALTER TABLE unlock_logs DROP COLUMN lock_time;

-- 删除索引
DROP INDEX idx_status ON unlock_logs;
```

**警告**：回滚操作会删除 `status` 和 `lock_time` 字段中的所有数据，请谨慎操作！

## 注意事项

1. **备份数据库**：执行迁移前，请务必备份数据库
2. **测试环境验证**：建议先在测试环境执行迁移，验证无误后再在生产环境执行
3. **应用程序兼容性**：确保应用程序代码已更新以支持新字段
4. **幂等性**：迁移脚本设计为幂等的，可以安全地多次执行
5. **自动创建表**：`door_opened_logs` 表由应用程序在启动时自动创建，无需手动创建

## 迁移顺序

如果有多个迁移脚本，请按以下顺序执行：

1. `upgrade_v5.0_to_v5.2.sql` - 协议 v5.2 升级

## 故障排查

### 问题：字段已存在错误

**原因**：迁移脚本已经执行过

**解决**：迁移脚本是幂等的，这个错误可以忽略

### 问题：权限不足

**原因**：数据库用户没有 ALTER TABLE 权限

**解决**：使用具有足够权限的用户执行迁移，或授予权限：

```sql
GRANT ALTER, CREATE, INDEX ON database_name.* TO 'username'@'host';
```

### 问题：数据迁移失败

**原因**：`result` 字段包含意外值

**解决**：检查数据并手动修复：

```sql
-- 查看异常数据
SELECT * FROM unlock_logs WHERE result NOT IN (0, 1) AND result IS NOT NULL;

-- 手动修复
UPDATE unlock_logs SET status = 'fail' WHERE result NOT IN (0, 1) AND result IS NOT NULL;
```

## 联系方式

如有问题，请联系项目维护者或查看项目文档。
