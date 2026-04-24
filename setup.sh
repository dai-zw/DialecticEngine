#!/bin/bash
# ============================================================
# 哲学推理引擎 (DialecticEngine) - 一键安装部署脚本
# 功能：自动安装 MongoDB + Python 依赖 + 启动项目
# 支持：Ubuntu/Debian, CentOS/RHEL, macOS
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[哲学推理引擎]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[哲学推理引擎]${NC} $1"; }
log_error() { echo -e "${RED}[哲学推理引擎]${NC} $1"; }

# --------------------------------------------------------
# 1. 检测操作系统
# --------------------------------------------------------
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    elif [[ "$(uname)" == "Darwin" ]]; then
        OS="macos"
    else
        OS="unknown"
    fi
    log_info "检测到操作系统: $OS $OS_VERSION"
}

# --------------------------------------------------------
# 2. 检测 MongoDB 是否已安装
# --------------------------------------------------------
check_mongodb() {
    if command -v mongod &>/dev/null; then
        MONGO_VERSION=$(mongod --version 2>/dev/null | head -1)
        log_info "MongoDB 已安装: $MONGO_VERSION"
        return 0
    elif command -v docker &>/dev/null && command -v docker-compose &>/dev/null; then
        log_info "未检测到 MongoDB，但发现 Docker，可使用 Docker 方式启动"
        return 1
    else
        return 2
    fi
}

# --------------------------------------------------------
# 3. 安装 MongoDB（Ubuntu/Debian）
# --------------------------------------------------------
install_mongodb_ubuntu() {
    log_info "正在安装 MongoDB 8.0 (Ubuntu/Debian)..."
    
    # 导入 MongoDB GPG 密钥（带重试）
    for i in 1 2 3; do
        curl -fsSL --retry 3 --connect-timeout 10 https://www.mongodb.org/static/pgp/server-8.0.asc -o /tmp/mongodb-key.asc && break
        echo "GPG 密钥下载失败，第 $i 次重试..."
        sleep 2
    done
    if [[ ! -f /tmp/mongodb-key.asc ]]; then
        log_error "GPG 密钥下载失败，请检查网络连接"
        exit 1
    fi
    sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-8.0.gpg /tmp/mongodb-key.asc 2>/dev/null || \
        sudo apt-key add /tmp/mongodb-key.asc 2>/dev/null || true
    rm -f /tmp/mongodb-key.asc
    
    # 添加 MongoDB 源
    echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/8.0 multiverse" | \
        sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list
    
    # 安装
    sudo apt-get update
    sudo apt-get install -y mongodb-org
    
    # 启动服务
    sudo systemctl daemon-reload
    sudo systemctl enable mongod
    sudo systemctl start mongod
    
    log_info "MongoDB 8.0 安装并启动成功！"
}

# --------------------------------------------------------
# 4. 安装 MongoDB（CentOS/RHEL）
# --------------------------------------------------------
install_mongodb_centos() {
    log_info "正在安装 MongoDB 8.0 (CentOS/RHEL)..."
    
    for i in 1 2 3; do
        curl -fsSL --retry 3 --connect-timeout 10 https://www.mongodb.org/static/pgp/server-8.0.asc -o /tmp/mongodb-key.asc && break
        sleep 2
    done
    
    sudo tee /etc/yum.repos.d/mongodb-org-8.0.repo << EOF
[mongodb-org-8.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/\$releasever/mongodb-org/8.0/\$basearch/
gpgcheck=1
enabled=1
gpgkey=https://www.mongodb.org/static/pgp/server-8.0.asc
EOF
    
    sudo yum install -y mongodb-org
    sudo systemctl daemon-reload
    sudo systemctl enable mongod
    sudo systemctl start mongod
    
    log_info "MongoDB 8.0 安装并启动成功！"
}

# --------------------------------------------------------
# 5. 安装 MongoDB（macOS）
# --------------------------------------------------------
install_mongodb_macos() {
    log_info "正在安装 MongoDB (macOS via Homebrew)..."
    
    if ! command -v brew &>/dev/null; then
        log_error "未检测到 Homebrew，请先安装 Homebrew: https://brew.sh"
        exit 1
    fi
    
    brew install mongodb-community
    brew services start mongodb-community
    
    log_info "MongoDB 安装并启动成功！"
}

# --------------------------------------------------------
# 6. Docker 方式启动 MongoDB
# --------------------------------------------------------
start_mongodb_docker() {
    log_info "使用 Docker 启动 MongoDB..."
    
    if [[ ! -f docker-compose.yml ]]; then
        log_error "未找到 docker-compose.yml，请在哲学推理引擎项目根目录执行此脚本"
        exit 1
    fi
    
    docker-compose up -d
    
    # 等待 MongoDB 就绪
    log_info "等待 MongoDB 启动..."
    for i in $(seq 1 10); do
        if docker exec daoshu-mongodb mongosh --eval "db.runCommand('ping')" &>/dev/null; then
            log_info "MongoDB 已就绪！"
            return 0
        fi
        sleep 2
    done
    
    log_error "MongoDB 启动超时，请检查 Docker 日志"
    exit 1
}

# --------------------------------------------------------
# 7. 安装 Python 依赖
# --------------------------------------------------------
install_python_deps() {
    log_info "正在安装 Python 依赖..."
    
    if command -v conda &>/dev/null; then
        # 使用 conda 环境
        ENV_NAME="daoshu"
        if conda env list | grep -q "^${ENV_NAME} "; then
            log_info "Conda 环境 '$ENV_NAME' 已存在"
        else
            log_info "创建 Conda 环境 '$ENV_NAME' (Python 3.10)..."
            conda create -n "$ENV_NAME" python=3.10 -y
        fi
        
        eval "$(conda shell.bash hook)"
        conda activate "$ENV_NAME"
        pip install -r requirements.txt
        log_info "Python 依赖安装完成！"
    elif command -v pip3 &>/dev/null; then
        pip3 install -r requirements.txt
        log_info "Python 依赖安装完成！"
    else
        log_error "未找到 pip 或 conda，请先安装 Python 环境"
        exit 1
    fi
}

# --------------------------------------------------------
# 8. 配置 .env
# --------------------------------------------------------
setup_env() {
    if [[ ! -f .env ]]; then
        log_warn ".env 文件不存在，正在创建模板..."
        cp .env.example .env 2>/dev/null || {
            cat > .env << 'EOF'
# DeepSeek API 配置
DEEPSEEK_API_KEY=sk-your-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com

# MongoDB 配置（默认本地）
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB_NAME=daoist_agent
EOF
            log_info "已创建 .env 模板，请编辑并填入你的 API Key"
        }
    else
        log_info ".env 文件已存在"
    fi
}

# --------------------------------------------------------
# 9. 主流程
# --------------------------------------------------------
main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║           哲学推理引擎 (DaoShu) · 一键部署脚本               ║"
    echo "║     道家多面向智能体系统 - https://github.com/...    ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo ""
    
    detect_os
    
    # 检查 MongoDB
    if check_mongodb; then
        log_info "MongoDB 已就绪，跳过安装"
    else
        INSTALL_METHOD=$?
        
        if [[ $INSTALL_METHOD -eq 2 ]] && [[ -f docker-compose.yml ]]; then
            # 没有 MongoDB 也没有 Docker，提供选项
            echo ""
            echo "请选择 MongoDB 安装方式："
            echo "  1) 使用 Docker Compose 启动（推荐，一行命令）"
            echo "  2) 直接安装 MongoDB 到本机"
            echo "  3) 跳过 MongoDB（使用文件备份模式，功能受限）"
            echo ""
            read -p "请输入选项 (1/2/3): " choice
            
            case $choice in
                1)
                    if command -v docker &>/dev/null; then
                        start_mongodb_docker
                    else
                        log_error "未安装 Docker，请先安装: https://docs.docker.com/get-docker/"
                        exit 1
                    fi
                    ;;
                2)
                    case $OS in
                        ubuntu|debian) install_mongodb_ubuntu ;;
                        centos|rhel|fedora|rocky|almalinux) install_mongodb_centos ;;
                        macos) install_mongodb_macos ;;
                        *)
                            log_error "不支持的操作系统: $OS"
                            echo "请手动安装 MongoDB: https://www.mongodb.com/docs/manual/installation/"
                            exit 1
                            ;;
                    esac
                    ;;
                3)
                    log_warn "跳过 MongoDB，系统将使用文件备份模式"
                    ;;
                *)
                    log_error "无效选项"
                    exit 1
                    ;;
            esac
        elif [[ $INSTALL_METHOD -eq 1 ]]; then
            # 有 Docker
            echo ""
            echo "检测到 Docker，是否使用 Docker 启动 MongoDB？"
            read -p "(y/n): " use_docker
            if [[ "$use_docker" == "y" ]]; then
                start_mongodb_docker
            else
                case $OS in
                    ubuntu|debian) install_mongodb_ubuntu ;;
                    centos|rhel|fedora|rocky|almalinux) install_mongodb_centos ;;
                    macos) install_mongodb_macos ;;
                    *) log_error "不支持的操作系统"; exit 1 ;;
                esac
            fi
        fi
    fi
    
    # 安装 Python 依赖
    echo ""
    install_python_deps
    
    # 配置 .env
    echo ""
    setup_env
    
    # 完成
    echo ""
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║                   部署完成！                          ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo ""
    echo "启动方式："
    echo "  python main.py"
    echo ""
    echo "如有问题，请查看文档: https://github.com/..."
    echo ""
}

main "$@"
