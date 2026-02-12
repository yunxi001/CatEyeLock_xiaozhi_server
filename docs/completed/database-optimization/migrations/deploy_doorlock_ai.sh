#!/bin/bash
################################################################################
# 智能门锁AI功能部署脚本
#
# 此脚本会执行以下操作：
# 1. 检查环境和依赖
# 2. 备份数据库
# 3. 执行数据库迁移
# 4. 验证迁移结果
# 5. 检查配置文件
# 6. 可选：重启服务
#
# 用法：
#   ./deploy_doorlock_ai.sh --db-host localhost --db-user root --db-password xxx --db-name xiaozhi_db
#
# 选项：
#   --db-host        数据库主机（默认: localhost）
#   --db-port        数据库端口（默认: 3306）
#   --db-user        数据库用户（必填）
#   --db-password    数据库密码（必填）
#   --db-name        数据库名称（必填）
#   --skip-backup    跳过数据库备份
#   --skip-restart   跳过服务重启
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
DB_HOST="localhost"
DB_PORT="3306"
DB_USER=""
DB_PASSWORD=""
DB_NAME=""
SKIP_BACKUP=false
SKIP_RESTART=false

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
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
智能门锁AI功能部署脚本

用法:
    $0 --db-user USER --db-password PASSWORD --db-name DATABASE [OPTIONS]

必填参数:
    --db-user USER          数据库用户
    --db-password PASSWORD  数据库密码
    --db-name DATABASE      数据库名称

可选参数:
    --db-host HOST          数据库主机（默认: localhost）
    --db-port PORT          数据库端口（默认: 3306）
    --skip-backup           跳过数据库备份
    --skip-restart          跳过服务重启
    --help                  显示此帮助信息

示例:
    $0 --db-user root --db-password mypassword --db-name xiaozhi_db
    $0 --db-user root --db-password mypassword --db-name xiaozhi_db --skip-restart

EOF
    exit 0
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
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
            --skip-backup)
                SKIP_BACKUP=true
                shift
                ;;
            --skip-restart)
                SKIP_RESTART=true
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
    if [[ -z "$DB_USER" ]] || [[ -z "$DB_PASSWORD" ]] || [[ -z "$DB_NAME" ]]; then
        print_error "缺少必填参数"
        echo "使用 --help 查看帮助信息"
        exit 1
    fi
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "命令 $1 未找到，请先安装"
        exit 1
    fi
}

# 检查环境和依赖
check_environment() {
    print_separator
    print_info "步骤 1/7: 检查环境和依赖"
    print_separator
    
    # 检查 Python
    check_command python3
    print_success "✓ Python3 已安装: $(python3 --version)"
    
    # 检查 pip
    check_command pip3
    print_success "✓ pip3 已安装"
    
    # 检查 MySQL 客户端
    check_command mysql
    print_success "✓ MySQL 客户端已安装: $(mysql --version)"
    
    # 检查 mysqldump
    check_command mysqldump
    print_success "✓ mysqldump 已安装"
    
    # 检查 Python 依赖
    print_info "检查 Python 依赖..."
    if python3 -c "import pymysql" 2>/dev/null; then
        print_success "✓ pymysql 已安装"
    else
        print_warning "⚠ pymysql 未安装，正在安装..."
        pip3 install pymysql
    fi
    
    if python3 -c "import loguru" 2>/dev/null; then
        print_success "✓ loguru 已安装"
    else
        print_warning "⚠ loguru 未安装，正在安装..."
        pip3 install loguru
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

# 备份数据库
backup_database() {
    if [[ "$SKIP_BACKUP" == true ]]; then
        print_separator
        print_info "步骤 2/7: 备份数据库（已跳过）"
        print_separator
        print_warning "⚠ 已跳过数据库备份"
        echo ""
        return
    fi
    
    print_separator
    print_info "步骤 2/7: 备份数据库"
    print_separator
    
    # 创建备份目录
    mkdir -p "$BACKUP_DIR"
    
    BACKUP_FILE="$BACKUP_DIR/doorlock_backup_${TIMESTAMP}.sql"
    
    print_info "备份文件: $BACKUP_FILE"
    print_info "正在备份数据库..."
    
    # 备份相关表
    if mysqldump -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" \
        "$DB_NAME" \
        persons doorlock_config doorlock_visitor_intents doorlock_package_alerts \
        --single-transaction \
        --routines \
        --triggers \
        > "$BACKUP_FILE" 2>/dev/null; then
        
        BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        print_success "✓ 数据库备份成功"
        print_info "  备份文件: $BACKUP_FILE"
        print_info "  文件大小: $BACKUP_SIZE"
    else
        print_error "✗ 数据库备份失败"
        exit 1
    fi
    
    echo ""
}

# 执行数据库迁移
execute_migration() {
    print_separator
    print_info "步骤 3/7: 执行数据库迁移"
    print_separator
    
    MIGRATION_SCRIPT="$SCRIPT_DIR/run_doorlock_ai_migration.py"
    
    if [[ ! -f "$MIGRATION_SCRIPT" ]]; then
        print_error "✗ 迁移脚本不存在: $MIGRATION_SCRIPT"
        exit 1
    fi
    
    print_info "执行迁移脚本..."
    
    if python3 "$MIGRATION_SCRIPT" \
        --host "$DB_HOST" \
        --port "$DB_PORT" \
        --user "$DB_USER" \
        --password "$DB_PASSWORD" \
        --database "$DB_NAME"; then
        
        print_success "✓ 数据库迁移执行成功"
    else
        print_error "✗ 数据库迁移执行失败"
        print_error "如需回滚，请运行: ./rollback_doorlock_ai.sh --backup-file $BACKUP_FILE"
        exit 1
    fi
    
    echo ""
}

# 验证迁移结果
verify_migration() {
    print_separator
    print_info "步骤 4/7: 验证迁移结果"
    print_separator
    
    VERIFY_SCRIPT="$SCRIPT_DIR/verify_doorlock_ai_migration.py"
    
    if [[ ! -f "$VERIFY_SCRIPT" ]]; then
        print_error "✗ 验证脚本不存在: $VERIFY_SCRIPT"
        exit 1
    fi
    
    print_info "执行验证脚本..."
    
    if python3 "$VERIFY_SCRIPT" \
        --host "$DB_HOST" \
        --port "$DB_PORT" \
        --user "$DB_USER" \
        --password "$DB_PASSWORD" \
        --database "$DB_NAME"; then
        
        print_success "✓ 迁移验证通过"
    else
        print_error "✗ 迁移验证失败"
        print_error "如需回滚，请运行: ./rollback_doorlock_ai.sh --backup-file $BACKUP_FILE"
        exit 1
    fi
    
    echo ""
}

# 检查配置文件
check_config_files() {
    print_separator
    print_info "步骤 5/7: 检查配置文件"
    print_separator
    
    # 检查 config.yaml
    CONFIG_FILE="$PROJECT_ROOT/config.yaml"
    if [[ -f "$CONFIG_FILE" ]]; then
        print_success "✓ config.yaml 存在"
        
        # 检查是否包含 doorlock 配置段
        if grep -q "doorlock:" "$CONFIG_FILE"; then
            print_success "✓ config.yaml 包含 doorlock 配置段"
        else
            print_warning "⚠ config.yaml 未包含 doorlock 配置段"
            print_info "  请参考文档添加配置: docs/my_docs/smart-doorlock-usage-guide.md"
        fi
    else
        print_error "✗ config.yaml 不存在"
        exit 1
    fi
    
    # 检查 doorlock_prompts.yaml
    PROMPTS_FILE="$PROJECT_ROOT/config/doorlock_prompts.yaml"
    if [[ -f "$PROMPTS_FILE" ]]; then
        print_success "✓ doorlock_prompts.yaml 存在"
    else
        print_error "✗ doorlock_prompts.yaml 不存在"
        print_info "  请从模板创建: cp config/doorlock_prompts.yaml.example config/doorlock_prompts.yaml"
        exit 1
    fi
    
    # 检查基准图片目录
    BASELINE_DIR="$PROJECT_ROOT/data/face_recognition/package_baseline"
    if [[ -d "$BASELINE_DIR" ]]; then
        print_success "✓ 基准图片目录存在"
    else
        print_info "创建基准图片目录..."
        mkdir -p "$BASELINE_DIR"
        print_success "✓ 基准图片目录已创建: $BASELINE_DIR"
    fi
    
    echo ""
}

# 检查依赖安装
check_dependencies() {
    print_separator
    print_info "步骤 6/7: 检查项目依赖"
    print_separator
    
    REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
    
    if [[ -f "$REQUIREMENTS_FILE" ]]; then
        print_info "检查 requirements.txt 中的依赖..."
        
        # 检查关键依赖
        REQUIRED_PACKAGES=("aiohttp" "pymysql" "loguru" "ruamel.yaml")
        ALL_INSTALLED=true
        
        for package in "${REQUIRED_PACKAGES[@]}"; do
            if python3 -c "import $package" 2>/dev/null; then
                print_success "✓ $package 已安装"
            else
                print_warning "⚠ $package 未安装"
                ALL_INSTALLED=false
            fi
        done
        
        if [[ "$ALL_INSTALLED" == false ]]; then
            print_info "安装缺失的依赖..."
            pip3 install -r "$REQUIREMENTS_FILE"
            print_success "✓ 依赖安装完成"
        fi
    else
        print_warning "⚠ requirements.txt 不存在，跳过依赖检查"
    fi
    
    echo ""
}

# 重启服务
restart_service() {
    if [[ "$SKIP_RESTART" == true ]]; then
        print_separator
        print_info "步骤 7/7: 重启服务（已跳过）"
        print_separator
        print_warning "⚠ 已跳过服务重启"
        print_info "请手动重启 xiaozhi-server 服务以应用更改"
        echo ""
        return
    fi
    
    print_separator
    print_info "步骤 7/7: 重启服务"
    print_separator
    
    print_warning "⚠ 此步骤需要手动执行"
    print_info "请使用以下命令重启 xiaozhi-server 服务:"
    echo ""
    echo "  cd $PROJECT_ROOT"
    echo "  # 停止现有服务（如果正在运行）"
    echo "  pkill -f 'python.*app.py' || true"
    echo "  # 启动服务"
    echo "  python3 app.py"
    echo ""
    
    read -p "是否现在重启服务？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "正在重启服务..."
        cd "$PROJECT_ROOT"
        
        # 停止现有服务
        pkill -f 'python.*app.py' || true
        sleep 2
        
        # 启动服务（后台运行）
        nohup python3 app.py > logs/app.log 2>&1 &
        
        sleep 3
        
        # 检查服务是否启动
        if pgrep -f 'python.*app.py' > /dev/null; then
            print_success "✓ 服务重启成功"
        else
            print_error "✗ 服务启动失败，请检查日志: logs/app.log"
        fi
    else
        print_info "已跳过服务重启"
    fi
    
    echo ""
}

# 打印部署总结
print_summary() {
    print_separator
    print_success "部署完成！"
    print_separator
    
    echo ""
    echo "部署内容:"
    echo "  ✓ 数据库迁移已执行"
    echo "  ✓ 迁移结果已验证"
    echo "  ✓ 配置文件已检查"
    echo ""
    
    if [[ "$SKIP_BACKUP" == false ]]; then
        echo "备份信息:"
        echo "  备份文件: $BACKUP_FILE"
        echo "  如需回滚: ./rollback_doorlock_ai.sh --backup-file $BACKUP_FILE"
        echo ""
    fi
    
    echo "下一步:"
    echo "  1. 查看使用指南: docs/my_docs/smart-doorlock-usage-guide.md"
    echo "  2. 查看 API 文档: docs/my_docs/doorlock-api-documentation.md"
    echo "  3. 配置设备: 通过 API 或数据库初始化设备配置"
    echo "  4. 测试功能: 参考测试指南进行功能测试"
    echo ""
    
    print_separator
}

################################################################################
# 主流程
################################################################################

main() {
    # 解析参数
    parse_args "$@"
    
    # 打印部署信息
    print_separator
    print_info "智能门锁AI功能部署脚本"
    print_separator
    echo ""
    echo "数据库配置:"
    echo "  主机: $DB_HOST:$DB_PORT"
    echo "  用户: $DB_USER"
    echo "  数据库: $DB_NAME"
    echo ""
    echo "部署选项:"
    echo "  跳过备份: $SKIP_BACKUP"
    echo "  跳过重启: $SKIP_RESTART"
    echo ""
    
    # 确认部署
    read -p "确认开始部署？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "部署已取消"
        exit 0
    fi
    
    echo ""
    
    # 执行部署步骤
    check_environment
    backup_database
    execute_migration
    verify_migration
    check_config_files
    check_dependencies
    restart_service
    
    # 打印总结
    print_summary
}

# 执行主流程
main "$@"
