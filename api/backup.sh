#!/bin/bash

# =============================================================================
# YM Academy Backup Script
# =============================================================================
# This script creates automated backups of the database and uploaded files.
# Supports three backup types with different retention policies:
#   - daily:  Local + Cloud, 30 days retention
#   - weekly: Cloud only, 90 days retention  
#   - monthly: Cloud only (Cold Storage), 1 year retention
# 
# Usage: 
#   ./backup.sh daily    # Daily backup (2:00 AM)
#   ./backup.sh weekly   # Weekly backup (Sunday 3:00 AM)
#   ./backup.sh monthly  # Monthly backup (1st of month 4:00 AM)
#
# Run inside container: docker exec api bash /api/backup.sh [daily|weekly|monthly]
# =============================================================================

# Configuration
SCRIPT_DIR="/api"
BACKUP_DIR="${SCRIPT_DIR}/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="db1010"
DB_USER="root"
CONTAINER_NAME="database"

# Default backup type is daily
BACKUP_TYPE="${1:-daily}"

# Retention and storage settings based on backup type
case "$BACKUP_TYPE" in
    daily)
        RETENTION_DAYS=30
        KEEP_LOCAL=true
        GCS_FOLDER="daily"
        GCS_STORAGE_CLASS=""
        ;;
    weekly)
        RETENTION_DAYS=90
        KEEP_LOCAL=false
        GCS_FOLDER="weekly"
        GCS_STORAGE_CLASS=""
        ;;
    monthly)
        RETENTION_DAYS=365
        KEEP_LOCAL=false
        GCS_FOLDER="monthly"
        GCS_STORAGE_CLASS="COLDLINE"
        ;;
    *)
        echo "Invalid backup type: $1. Usage: daily|weekly|monthly"
        exit 1
        ;;
esac

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

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

log "=========================================="
log "Starting $BACKUP_TYPE backup process..."
log "Retention: $RETENTION_DAYS days"
log "GCS Folder: $GCS_FOLDER"
if [ -n "$GCS_STORAGE_CLASS" ]; then
    log "GCS Storage Class: $GCS_STORAGE_CLASS"
fi
log "=========================================="

# Create backup directory if not exists
mkdir -p "$BACKUP_DIR"

# =============================================================================
# 1. Backup Database
# =============================================================================
log "Backing up database: $DB_NAME..."

# Check if database container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    # Try using container name from docker-compose
    if ! docker ps --format '{{.Names}}' | grep -q "database"; then
        error "Database container is not running!"
        exit 1
    fi
    CONTAINER_NAME="database"
fi

# Create database dump and compress it
DB_BACKUP_FILE="$BACKUP_DIR/db_backup_${BACKUP_TYPE}_$DATE.sql.gz"

if docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$DB_BACKUP_FILE" 2>/dev/null; then
    DB_SIZE=$(du -h "$DB_BACKUP_FILE" | cut -f1)
    log "Database backup created: db_backup_${BACKUP_TYPE}_$DATE.sql.gz ($DB_SIZE)"
else
    error "Failed to create database backup!"
    exit 1
fi

# =============================================================================
# 2. Backup Uploaded Files
# =============================================================================
log "Backing up uploaded files..."

UPLOADS_DIR="${SCRIPT_DIR}/uploads"

if [ -d "$UPLOADS_DIR" ]; then
    UPLOADS_BACKUP_FILE="$BACKUP_DIR/uploads_backup_${BACKUP_TYPE}_$DATE.tar.gz"
    
    # Create compressed tar archive of uploads directory
    tar -czf "$UPLOADS_BACKUP_FILE" -C "$SCRIPT_DIR" uploads/ 2>/dev/null
    
    if [ $? -eq 0 ]; then
        UPLOADS_SIZE=$(du -h "$UPLOADS_BACKUP_FILE" | cut -f1)
        log "Uploads backup created: uploads_backup_${BACKUP_TYPE}_$DATE.tar.gz ($UPLOADS_SIZE)"
    else
        warning "Failed to create uploads backup!"
    fi
else
    warning "Uploads directory not found: $UPLOADS_DIR"
fi

# =============================================================================
# 3. Backup Environment File (for disaster recovery)
# =============================================================================
log "Backing up environment configuration..."

ENV_FILE="${SCRIPT_DIR}/.env"
if [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" "$BACKUP_DIR/env_backup_${BACKUP_TYPE}_$DATE.env"
    log "Environment config backed up: env_backup_${BACKUP_TYPE}_$DATE.env"
else
    warning "Environment file not found - skipping"
fi

# =============================================================================
# 4. Upload to Google Cloud Storage
# =============================================================================
if [ -n "$GCS_BUCKET_NAME" ] && [ -n "$GCS_CREDENTIALS_PATH" ]; then
    log "Uploading ${BACKUP_TYPE} backups to GCS folder: ${GCS_FOLDER}/"
    cd "$SCRIPT_DIR"
    
    # Set storage class for monthly backups if specified
    if [ -n "$GCS_STORAGE_CLASS" ]; then
        export GCS_STORAGE_CLASS="$GCS_STORAGE_CLASS"
    fi
    
    # Upload with folder path
    python3 gcs_backup.py --upload --folder "$GCS_FOLDER"
    
    # Cleanup old GCS backups based on backup type retention
    log "Cleaning up old GCS backups (older than $RETENTION_DAYS days)..."
    python3 gcs_backup.py --cleanup "$RETENTION_DAYS" --folder "$GCS_FOLDER"
else
    warning "GCS not configured (set GCS_BUCKET_NAME and GCS_CREDENTIALS_PATH env vars)"
fi

# =============================================================================
# 5. Handle Local Backups Based on Type
# =============================================================================
if [ "$KEEP_LOCAL" = "true" ]; then
    log "Cleaning up old local backups (retention: $RETENTION_DAYS days)..."
    
    # Find and remove old database backups (any type)
    OLD_DB_BACKUPS=$(find "$BACKUP_DIR" -name "db_backup_*.sql.gz" -mtime +$RETENTION_DAYS 2>/dev/null)
    if [ -n "$OLD_DB_BACKUPS" ]; then
        echo "$OLD_DB_BACKUPS" | xargs rm -f
        log "Removed old database backups"
    fi
    
    # Find and remove old uploads backups
    OLD_UPLOADS_BACKUPS=$(find "$BACKUP_DIR" -name "uploads_backup_*.tar.gz" -mtime +$RETENTION_DAYS 2>/dev/null)
    if [ -n "$OLD_UPLOADS_BACKUPS" ]; then
        echo "$OLD_UPLOADS_BACKUPS" | xargs rm -f
        log "Removed old uploads backups"
    fi
    
    # Find and remove old env backups
    OLD_ENV_BACKUPS=$(find "$BACKUP_DIR" -name "env_backup_*.env" -mtime +$RETENTION_DAYS 2>/dev/null)
    if [ -n "$OLD_ENV_BACKUPS" ]; then
        echo "$OLD_ENV_BACKUPS" | xargs rm -f
        log "Removed old environment backups"
    fi
else
    # For weekly/monthly, remove local copies after upload
    log "Removing local copies (cloud-only backup)..."
    
    if [ -f "$DB_BACKUP_FILE" ]; then
        rm -f "$DB_BACKUP_FILE"
        log "Removed local database backup"
    fi
    
    if [ -f "$UPLOADS_BACKUP_FILE" ]; then
        rm -f "$UPLOADS_BACKUP_FILE"
        log "Removed local uploads backup"
    fi
fi

# =============================================================================
# 6. Summary
# =============================================================================
log "=========================================="
log "$BACKUP_TYPE backup completed successfully!"
log "=========================================="
log "Backup type: $BACKUP_TYPE"
log "Retention: $RETENTION_DAYS days"

if [ "$KEEP_LOCAL" = "true" ]; then
    log "Backup location: $BACKUP_DIR"
    log ""
    log "Recent local backups:"
    ls -lh "$BACKUP_DIR" | tail -5
    
    # Calculate total backup size
    TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
    log "Total local backup size: $TOTAL_SIZE"
else
    log "Backup location: Google Cloud Storage ($GCS_BUCKET_NAME/${GCS_FOLDER}/)"
fi

log ""
log "Scheduled backups:"
log "  - Daily (2:00 AM): Local + Cloud, 30 days"
log "  - Weekly (Sunday 3:00 AM): Cloud only, 90 days"
log "  - Monthly (1st 4:00 AM): Cloud only (Cold), 1 year"

exit 0
