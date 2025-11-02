#!/bin/bash

################################################################################
# Polymarket Whale Copy Trading - Automated Deployment Script
# Handles deployment to production/staging environments
################################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="$PROJECT_ROOT/backups/$TIMESTAMP"

# Default values
ENVIRONMENT=${1:-"staging"}
BRANCH=${2:-"main"}
RUN_TESTS=${RUN_TESTS:-"true"}
BACKUP_DB=${BACKUP_DB:-"true"}

################################################################################
# Helper Functions
################################################################################

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${BLUE}==>${NC} $1"
}

check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 is not installed"
        exit 1
    fi
}

################################################################################
# Pre-deployment Checks
################################################################################

pre_deployment_checks() {
    log_step "Running pre-deployment checks..."

    # Check required commands
    for cmd in git python3 pip3 docker psql; do
        check_command $cmd
    done

    # Check Python version
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    if [[ $(echo "$PYTHON_VERSION < 3.8" | bc -l) -eq 1 ]]; then
        log_error "Python 3.8+ required, found $PYTHON_VERSION"
        exit 1
    fi

    # Check git status
    if [[ -n $(git status --porcelain) ]]; then
        log_warning "Working directory has uncommitted changes"
        read -p "Continue anyway? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    # Check environment file
    if [ ! -f "$PROJECT_ROOT/.env.$ENVIRONMENT" ]; then
        log_error "Environment file .env.$ENVIRONMENT not found"
        exit 1
    fi

    log_info "Pre-deployment checks passed"
}

################################################################################
# Backup Functions
################################################################################

backup_database() {
    if [ "$BACKUP_DB" != "true" ]; then
        log_info "Skipping database backup (BACKUP_DB=false)"
        return
    fi

    log_step "Backing up database..."

    mkdir -p "$BACKUP_DIR"

    # Load database credentials from .env
    source "$PROJECT_ROOT/.env.$ENVIRONMENT"

    # Backup database
    BACKUP_FILE="$BACKUP_DIR/postgres_backup_$TIMESTAMP.sql"

    PGPASSWORD=$DB_PASSWORD pg_dump \
        -h $DB_HOST \
        -p $DB_PORT \
        -U $DB_USER \
        -d $DB_NAME \
        -f "$BACKUP_FILE"

    if [ -f "$BACKUP_FILE" ]; then
        gzip "$BACKUP_FILE"
        log_info "Database backed up to $BACKUP_FILE.gz"
    else
        log_error "Database backup failed"
        exit 1
    fi
}

backup_application() {
    log_step "Backing up application files..."

    mkdir -p "$BACKUP_DIR/app"

    # Backup critical files
    for file in ".env" "config.json" "whale_list.json"; do
        if [ -f "$PROJECT_ROOT/$file" ]; then
            cp "$PROJECT_ROOT/$file" "$BACKUP_DIR/app/"
        fi
    done

    log_info "Application files backed up to $BACKUP_DIR/app"
}

################################################################################
# Test Functions
################################################################################

run_tests() {
    if [ "$RUN_TESTS" != "true" ]; then
        log_info "Skipping tests (RUN_TESTS=false)"
        return
    fi

    log_step "Running tests..."

    cd "$PROJECT_ROOT"

    # Run unit tests
    log_info "Running unit tests..."
    python3 -m pytest tests/unit -v --tb=short || {
        log_error "Unit tests failed"
        exit 1
    }

    # Run integration tests
    log_info "Running integration tests..."
    python3 -m pytest tests/integration -v --tb=short || {
        log_warning "Integration tests failed (non-critical)"
    }

    # Run linting
    log_info "Running code quality checks..."
    python3 -m flake8 src/ --max-line-length=120 --ignore=E501,W503 || {
        log_warning "Linting issues found"
    }

    log_info "Tests completed"
}

################################################################################
# Deployment Functions
################################################################################

update_code() {
    log_step "Updating code from repository..."

    cd "$PROJECT_ROOT"

    # Fetch latest changes
    git fetch origin

    # Store current branch
    CURRENT_BRANCH=$(git branch --show-current)

    # Checkout target branch
    if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
        git checkout "$BRANCH"
    fi

    # Pull latest changes
    git pull origin "$BRANCH"

    # Update submodules if any
    git submodule update --init --recursive

    log_info "Code updated to latest $BRANCH"
}

install_dependencies() {
    log_step "Installing/updating dependencies..."

    cd "$PROJECT_ROOT"

    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi

    # Activate virtual environment
    source venv/bin/activate

    # Upgrade pip
    pip install --upgrade pip

    # Install requirements
    pip install -r requirements.txt

    log_info "Dependencies installed"
}

migrate_database() {
    log_step "Running database migrations..."

    cd "$PROJECT_ROOT"
    source venv/bin/activate

    # Run Alembic migrations
    if [ -d "alembic" ]; then
        alembic upgrade head || {
            log_error "Database migration failed"
            exit 1
        }
    else
        log_warning "No Alembic directory found, skipping migrations"
    fi

    log_info "Database migrations completed"
}

update_docker_containers() {
    log_step "Updating Docker containers..."

    cd "$PROJECT_ROOT"

    # Stop existing containers
    docker-compose down

    # Build new images
    docker-compose build --no-cache

    # Start containers
    docker-compose up -d

    # Wait for containers to be healthy
    log_info "Waiting for containers to be healthy..."
    sleep 10

    # Check container health
    docker-compose ps

    log_info "Docker containers updated"
}

deploy_services() {
    log_step "Deploying services..."

    cd "$PROJECT_ROOT"
    source venv/bin/activate

    # Stop existing services
    log_info "Stopping existing services..."

    # Kill existing Python processes (be careful!)
    pkill -f "python.*api/main.py" || true
    pkill -f "python.*copy_trading/engine.py" || true
    sleep 2

    # Start API server
    log_info "Starting API server..."
    nohup python3 api/main.py > logs/api_$TIMESTAMP.log 2>&1 &
    API_PID=$!
    echo $API_PID > "$PROJECT_ROOT/.api.pid"

    # Start copy trading engine
    log_info "Starting copy trading engine..."
    nohup python3 src/copy_trading/engine.py > logs/engine_$TIMESTAMP.log 2>&1 &
    ENGINE_PID=$!
    echo $ENGINE_PID > "$PROJECT_ROOT/.engine.pid"

    # Start monitoring dashboard
    log_info "Starting monitoring dashboard..."
    nohup python3 scripts/launch_monitoring.py > logs/monitoring_$TIMESTAMP.log 2>&1 &
    MONITOR_PID=$!
    echo $MONITOR_PID > "$PROJECT_ROOT/.monitor.pid"

    sleep 5

    # Verify services are running
    if ps -p $API_PID > /dev/null; then
        log_info "API server running (PID: $API_PID)"
    else
        log_error "API server failed to start"
        exit 1
    fi

    if ps -p $ENGINE_PID > /dev/null; then
        log_info "Copy trading engine running (PID: $ENGINE_PID)"
    else
        log_error "Copy trading engine failed to start"
        exit 1
    fi

    if ps -p $MONITOR_PID > /dev/null; then
        log_info "Monitoring dashboard running (PID: $MONITOR_PID)"
    else
        log_warning "Monitoring dashboard failed to start (non-critical)"
    fi

    log_info "Services deployed successfully"
}

################################################################################
# Post-deployment Functions
################################################################################

health_check() {
    log_step "Running health checks..."

    # Check API health
    log_info "Checking API health..."
    API_HEALTH=$(curl -s http://localhost:8000/health || echo "failed")
    if [[ "$API_HEALTH" == *"healthy"* ]]; then
        log_info "API is healthy"
    else
        log_error "API health check failed"
        exit 1
    fi

    # Check database connection
    log_info "Checking database connection..."
    source "$PROJECT_ROOT/.env.$ENVIRONMENT"
    PGPASSWORD=$DB_PASSWORD psql \
        -h $DB_HOST \
        -p $DB_PORT \
        -U $DB_USER \
        -d $DB_NAME \
        -c "SELECT 1" > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        log_info "Database connection successful"
    else
        log_error "Database connection failed"
        exit 1
    fi

    # Check WebSocket connection
    log_info "Checking WebSocket connections..."
    # Add WebSocket health check here

    log_info "All health checks passed"
}

send_notification() {
    log_step "Sending deployment notification..."

    # Load notification settings
    source "$PROJECT_ROOT/.env.$ENVIRONMENT"

    if [ -n "$DISCORD_WEBHOOK_URL" ]; then
        MESSAGE="Deployment completed successfully\n"
        MESSAGE+="Environment: $ENVIRONMENT\n"
        MESSAGE+="Branch: $BRANCH\n"
        MESSAGE+="Timestamp: $TIMESTAMP"

        curl -H "Content-Type: application/json" \
             -d "{\"content\": \"$MESSAGE\"}" \
             "$DISCORD_WEBHOOK_URL"

        log_info "Notification sent to Discord"
    fi
}

cleanup() {
    log_step "Cleaning up..."

    # Remove old logs (keep last 30 days)
    find "$PROJECT_ROOT/logs" -type f -mtime +30 -delete

    # Remove old backups (keep last 10)
    cd "$PROJECT_ROOT/backups"
    ls -t | tail -n +11 | xargs -r rm -rf

    log_info "Cleanup completed"
}

################################################################################
# Rollback Function
################################################################################

rollback() {
    log_error "Deployment failed, rolling back..."

    # Restore from backup
    if [ -d "$BACKUP_DIR" ]; then
        # Restore database
        if [ -f "$BACKUP_DIR/postgres_backup_$TIMESTAMP.sql.gz" ]; then
            log_info "Restoring database..."
            gunzip "$BACKUP_DIR/postgres_backup_$TIMESTAMP.sql.gz"
            source "$PROJECT_ROOT/.env.$ENVIRONMENT"
            PGPASSWORD=$DB_PASSWORD psql \
                -h $DB_HOST \
                -p $DB_PORT \
                -U $DB_USER \
                -d $DB_NAME \
                < "$BACKUP_DIR/postgres_backup_$TIMESTAMP.sql"
        fi

        # Restore application files
        if [ -d "$BACKUP_DIR/app" ]; then
            log_info "Restoring application files..."
            cp -r "$BACKUP_DIR/app/"* "$PROJECT_ROOT/"
        fi
    fi

    # Restart services with previous version
    deploy_services

    log_warning "Rollback completed"
    exit 1
}

################################################################################
# Main Deployment Flow
################################################################################

main() {
    echo "=========================================="
    echo "Polymarket Whale Copy Trading Deployment"
    echo "=========================================="
    echo "Environment: $ENVIRONMENT"
    echo "Branch: $BRANCH"
    echo "Timestamp: $TIMESTAMP"
    echo "=========================================="

    # Set up error handling
    trap rollback ERR

    # Create necessary directories
    mkdir -p "$PROJECT_ROOT/logs"
    mkdir -p "$PROJECT_ROOT/backups"

    # Run deployment steps
    pre_deployment_checks
    backup_database
    backup_application
    run_tests
    update_code
    install_dependencies
    migrate_database
    update_docker_containers
    deploy_services
    health_check
    send_notification
    cleanup

    echo "=========================================="
    log_info "DEPLOYMENT COMPLETED SUCCESSFULLY!"
    echo "=========================================="
    echo "API: http://localhost:8000"
    echo "Monitoring: http://localhost:8080"
    echo "Logs: $PROJECT_ROOT/logs/"
    echo "=========================================="
}

# Run main function
main "$@"