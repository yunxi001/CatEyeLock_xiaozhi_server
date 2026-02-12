#!/bin/bash
################################################################################
# 智能门锁AI功能回滚脚本
#
# 此脚本会执行以下操作：
# 1. 验证备份文件
# 2. 备份当前数据库状态
# 3. 恢复数据库到备份状态
# 4. 验证回滚结果
#
# 用法：
#   ./rollback_doorlock_ai.sh --backup-file backups/doorlock_backup_20260209_143022.sql \
#                              --db-host localhost --db-user root --db-password xxx --db-name xiaozhi_db
#
# 选项：
#   --backup-file    备份文件路径（必填）
#   --db-host        数据库主机（默认: localhost）
#   --db-port        数据库端口（默认: 3306）
#   --db-user        数据库用户（必填）
#   --db-password    数据库密码（必填）
#   --db-name        数据库名称（必填）
#   --force          强制回滚，不进行确认
#   --help           显示帮助信息
#
################################################################################

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认参数
BACKUP_FILE=""
DB_HOST="localhost"
DB_PORT="3306"
DB_USER=""
DB_PASSWORD=""
DB_NAME=""
FORCE=false

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

################################################################################
# 函数定义
################################################################################

# 打印信息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# 打印成功
print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# 打印警告
print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# 打印错误
print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 打印分隔线
print_separator() {
    echo "========================================================================"
}

# 显示帮助信息
show_help() {
    cat << EOF
智能门锁AI功能回滚脚本

用法:
    $0 --backup-file FILE --db-user USER --db-password PASSWORD --db-name DATABASE [OPTIONS]

必填参数:
    --backup-file FILE      备份文件路径
    --db-user USER          数据库用户
    --db-password PASSWORD  数据库密码
    --db-name DATABASE      数据库名称

可选参数:
    --db-host HOST          数据库主机（默认: localhost）
    --db-port PORT          数据库端口（默认: 3306）
    --force                 强制回滚，不进行确认
    --help                  显示此帮助信息

示例:
    $0 --backup-file backups/doorlock_backup_20260209_143022.sql \\
       --db-user root --db-password mypassword --db-name xiaozhi_db

EOF
    exit 0
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --backup-file)
                BACKUP_FILE="$2"
                shift 2
                ;;
            --db-host)
                DB_HOST="$2"
                shift 2
                ;;
            --db-port)
                DB_PORT="$2"
                shift 2
                ;;
            --db-user)
                DB_USER="$2"
                shift 2
                ;;
            --db-password)
                DB_PASSWORD="$2"
                shift 2
                ;;
            --db-name)
                DB_NAME="$2"
                shift 2
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --help)
                show_help
                ;;
            *)
                print_error "未知参数: $1"
                echo "使用 --help 查看帮助信息"
                exit 1
                ;;
        esac
    done

    # 验证必填参数
    if [[ -z "$BACKUP_FILE" ]] || [[ -z "$DB_USER" ]] || [[ -z "$DB_PASSWORD" ]] || [[ -z "$DB_NAME" ]]; then
        print_error "缺少必填参数"
        echo "使用 --help 查看帮助信息"
        exit 1
    fi
}

# 验证备份文件
verify_backup_file() {
    print_separator
    print_info "步骤 1/4: 验证备份文件"
    print_separator
    
    if [[ ! -f "$BACKUP_FILE" ]]; then
        print_error "✗ 备份文件不存在: $BACKUP_FILE"
        exit 1
    fi
    
    print_success "✓ 备份文件存在: $BACKUP_FILE"
    
    # 检查文件大小
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    print_info "  文件大小: $BACKUP_SIZE"
    
    # 检查文件内容
    if head -n 1 "$BACKUP_FILE" | grep -q "MySQL dump"; then
        print_success "✓ 备份文件格式正确"
    else
        print_error "✗ 备份文件格式不正确"
        exit 1
    fi
    
    # 测试数据库连接
    print_info "测试数据库连接..."
    if mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" -e "USE $DB_NAME" 2>/dev/null; then
        print_success "✓ 数据库连接成功"
    else
        print_error "✗ 数据库连接失败"
        exit 1
    fi
    
    echo ""
}

# 备份当前状态
backup_current_state() {
    print_separator
    print_info "步骤 2/4: 备份当前数据库状态"
    print_separator
    
    # 创建备份目录
    mkdir -p "$BACKUP_DIR"
    
    CURRENT_BACKUP_FILE="$BACKUP_DIR/doorlock_before_rollback_${TIMESTAMP}.sql"
    
    print_info "备份文件: $CURRENT_BACKUP_FILE"
    print_info "正在备份当前数据库状态..."
    
    # 备份相关表
    if mysqldump -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" \
        "$DB_NAME" \
        persons doorlock_config doorlock_visitor_intents doorlock_package_alerts \
        --single-transaction \
        --routines \
        --triggers \
        > "$CURRENT_BACKUP_FILE" 2>/dev/null; then
        
        CURRENT_BACKUP_SIZE=$(du -h "$CURRENT_BACKUP_FILE" | cut -f1)
        print_success "✓ 当前状态备份成功"
        print_info "  备份文件: $CURRENT_BACKUP_FILE"
        print_info "  文件大小: $CURRENT_BACKUP_SIZE"
    else
        print_error "✗ 当前状态备份失败"
        exit 1
    fi
    
    echo ""
}

# 恢复数据库
restore_database() {
    print_separator
    print_info "步骤 3/4: 恢复数据库"
    print_separator
    
    print_warning "⚠ 警告: 此操作将覆盖当前数据库中的相关表"
    print_info "备份文件: $BACKUP_FILE"
    
    if [[ "$FORCE" == false ]]; then
        read -p "确认恢复数据库？(y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "回滚已取消"
            exit 0
        fi
    fi
    
    print_info "正在恢复数据库..."
    
    # 恢复数据库
    if mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < "$BACKUP_FILE" 2>/dev/null; then
        print_success "✓ 数据库恢复成功"
    else
        print_error "✗ 数据库恢复失败"
        print_error "如需恢复到回滚前状态，请使用: $CURRENT_BACKUP_FILE"
        exit 1
    fi
    
    echo ""
}

# 验证回滚结果
verify_rollback() {
    print_separator
    print_info "步骤 4/4: 验证回滚结果"
    print_separator
    
    print_info "检查表结构..."
    
    # 检查关键表是否存在
    TABLES=("persons" "doorlock_config" "doorlock_visitor_intents" "doorlock_package_alerts")
    ALL_OK=true
    
    for table in "${TABLES[@]}"; do
        if mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" \
            -e "SHOW TABLES LIKE '$table'" 2>/dev/null | grep -q "$table"; then
            print_success "✓ 表 $table 存在"
        else
            print_warning "⚠ 表 $table 不存在（可能在备份时不存在）"
        fi
    done
    
    print_success "✓ 回滚验证完成"
    
    echo ""
}

# 打印回滚总结
print_summary() {
    print_separator
    print_success "回滚完成！"
    print_separator
    
    echo ""
    echo "回滚信息:"
    echo "  ✓ 数据库已恢复到备份状态"
    echo "  ✓ 回滚前状态已备份: $CURRENT_BACKUP_FILE"
    echo ""
    
    echo "备份文件:"
    echo "  原始备份: $BACKUP_FILE"
    echo "  回滚前备份: $CURRENT_BACKUP_FILE"
    echo ""
    
    echo "下一步:"
    echo "  1. 检查数据库状态是否正确"
    echo "  2. 如需重新部署，请运行: ./deploy_doorlock_ai.sh"
    echo "  3. 如需恢复到回滚前状态: ./rollback_doorlock_ai.sh --backup-file $CURRENT_BACKUP_FILE ..."
    echo ""
    
    print_separator
}

################################################################################
# 主流程
################################################################################

main() {
    # 解析参数
    parse_args "$@"
    
    # 打印回滚信息
    print_separator
    print_info "智能门锁AI功能回滚脚本"
    print_separator
    echo ""
    echo "数据库配置:"
    echo "  主机: $DB_HOST:$DB_PORT"
    echo "  用户: $DB_USER"
    echo "  数据库: $DB_NAME"
    echo ""
    echo "备份文件:"
    echo "  $BACKUP_FILE"
    echo ""
    
    # 确认回滚
    if [[ "$FORCE" == false ]]; then
        print_warning "⚠ 警告: 回滚操作将覆盖当前数据库状态"
        read -p "确认开始回滚？(y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "回滚已取消"
            exit 0
        fi
    fi
    
    echo ""
    
    # 执行回滚步骤
    verify_backup_file
    backup_current_state
    restore_database
    verify_rollback
    
    # 打印总结
    print_summary
}

# 执行主流程
main "$@"
