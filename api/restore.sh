#!/bin/bash

# =============================================================================
# YM Academy Restore Script
# =============================================================================
# This script restores the database and uploaded files from backups.
# 
# Run inside container: docker exec api bash /api/restore.sh
# =============================================================================

# Configuration
SCRIPT_DIR="/api"
BACKUP_DIR="${SCRIPT_DIR}/backups"
DB_NAME="db1010"
DB_USER="root"
CONTAINER_NAME="database"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Show usage
usage() {
    echo -e "${BLUE}Usage:${NC}"
    echo "  $0 db <backup_file>           - Restore database"
    echo "  $0 uploads <backup_file>      - Restore uploaded files"
    echo "  $0 env <backup_file>          - Restore environment config"
    echo "  $0 list                       - List available backups"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 db db_backup_20260406_020000.sql.gz"
    echo "  $0 uploads uploads_backup_20260406_020000.tar.gz"
}

# List available backups
list_backups() {
    log "Available backups in $BACKUP_DIR:"
    echo ""
    echo -e "${BLUE}Database Backups:${NC}"
    ls -lh "$BACKUP_DIR"/db_backup_*.sql.gz 2>/dev/null | awk '{print $9, "-", $5}' || echo "  None found"
    echo ""
    echo -e "${BLUE}Uploads Backups:${NC}"
    ls -lh "$BACKUP_DIR"/uploads_backup_*.tar.gz 2>/dev/null | awk '{print $9, "-", $5}' || echo "  None found"
    echo ""
    echo -e "${BLUE}Environment Backups:${NC}"
    ls -lh "$BACKUP_DIR"/env_backup_*.env 2>/dev/null | awk '{print $9, "-", $5}' || echo "  None found"
}

# Restore database
restore_db() {
    BACKUP_FILE="$1"
    
    if [ -z "$BACKUP_FILE" ]; then
        error "Please specify a backup file"
        echo "  Example: $0 db db_backup_20260406_020000.sql.gz"
        exit 1
    fi
    
    # Check if file exists
    FULL_PATH="$BACKUP_DIR/$BACKUP_FILE"
    if [ ! -f "$FULL_PATH" ]; then
        error "Backup file not found: $FULL_PATH"
        exit 1
    fi
    
    log "Preparing to restore database from: $BACKUP_FILE"
    warning "This will REPLACE all existing data in the database!"
    
    read -p "Are you sure you want to continue? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        log "Restore cancelled."
        exit 0
    fi
    
    # Check if database container is running
    if ! docker ps --format '{{.Names}}' | grep -q "database"; then
        error "Database container is not running!"
        exit 1
    fi
    
    log "Stopping API service..."
    docker compose stop api 2>/dev/null || pkill -f "uvicorn" || true
    
    log "Restoring database..."
    if gunzip -c "$FULL_PATH" | docker exec -i database psql -U "$DB_USER" -d "$DB_NAME" 2>/dev/null; then
        log "Database restored successfully!"
    else
        error "Failed to restore database!"
        docker compose start api 2>/dev/null || true
        exit 1
    fi
    
    log "Starting API service..."
    docker compose start api 2>/dev/null || true
    
    log "Database restore complete!"
}

# Restore uploaded files
restore_uploads() {
    BACKUP_FILE="$1"
    
    if [ -z "$BACKUP_FILE" ]; then
        error "Please specify a backup file"
        echo "  Example: $0 uploads uploads_backup_20260406_020000.tar.gz"
        exit 1
    fi
    
    # Check if file exists
    FULL_PATH="$BACKUP_DIR/$BACKUP_FILE"
    if [ ! -f "$FULL_PATH" ]; then
        error "Backup file not found: $FULL_PATH"
        exit 1
    fi
    
    log "Preparing to restore uploads from: $BACKUP_FILE"
    warning "This will REPLACE all existing uploaded files!"
    
    read -p "Are you sure you want to continue? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        log "Restore cancelled."
        exit 0
    fi
    
    UPLOADS_DIR="${SCRIPT_DIR}/uploads"
    
    # Create backup of current uploads
    if [ -d "$UPLOADS_DIR" ]; then
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        log "Creating backup of current uploads..."
        tar -czf "$BACKUP_DIR/uploads_pre_restore_$TIMESTAMP.tar.gz" -C "$SCRIPT_DIR" uploads/
    fi
    
    log "Restoring uploaded files..."
    tar -xzf "$FULL_PATH" -C "$SCRIPT_DIR"
    
    if [ $? -eq 0 ]; then
        log "Uploaded files restored successfully!"
    else
        error "Failed to restore uploaded files!"
        exit 1
    fi
    
    log "Uploaded files restore complete!"
}

# Restore environment config
restore_env() {
    BACKUP_FILE="$1"
    
    if [ -z "$BACKUP_FILE" ]; then
        error "Please specify a backup file"
        echo "  Example: $0 env env_backup_20260406_020000.env"
        exit 1
    fi
    
    # Check if file exists
    FULL_PATH="$BACKUP_DIR/$BACKUP_FILE"
    if [ ! -f "$FULL_PATH" ]; then
        error "Backup file not found: $FULL_PATH"
        exit 1
    fi
    
    log "Preparing to restore environment config from: $BACKUP_FILE"
    warning "This will REPLACE your current .env file!"
    
    read -p "Are you sure you want to continue? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        log "Restore cancelled."
        exit 0
    fi
    
    # Create backup of current .env
    if [ -f "${SCRIPT_DIR}/.env" ]; then
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        cp "${SCRIPT_DIR}/.env" "${SCRIPT_DIR}/.env.backup_$TIMESTAMP"
        log "Current .env backed up to .env.backup_$TIMESTAMP"
    fi
    
    log "Restoring environment config..."
    cp "$FULL_PATH" "${SCRIPT_DIR}/.env"
    
    if [ $? -eq 0 ]; then
        log "Environment config restored successfully!"
    else
        error "Failed to restore environment config!"
        exit 1
    fi
    
    log "Environment config restore complete!"
    warning "You may need to restart the containers for changes to take effect."
}

# Main
case "$1" in
    db)
        restore_db "$2"
        ;;
    uploads)
        restore_uploads "$2"
        ;;
    env)
        restore_env "$2"
        ;;
    list)
        list_backups
        ;;
    *)
        usage
        ;;
esac
