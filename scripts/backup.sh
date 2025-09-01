#!/bin/bash

# Sofia V2 Backup Script
# Runs every 2 hours via cron

set -e

# Configuration
BACKUP_DIR="/backups"
S3_BUCKET="${S3_BUCKET:-sofia-backups}"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Create backup directory
mkdir -p ${BACKUP_DIR}/{database,configs,logs,trades}

# 1. Database Backup
backup_database() {
    log "Starting database backup..."
    
    # PostgreSQL backup
    docker exec sofia-postgres pg_dump -U sofia -d sofia \
        --no-owner --no-acl --clean --if-exists \
        > ${BACKUP_DIR}/database/sofia_${TIMESTAMP}.sql
    
    # Compress backup
    gzip ${BACKUP_DIR}/database/sofia_${TIMESTAMP}.sql
    
    # Create checksum
    sha256sum ${BACKUP_DIR}/database/sofia_${TIMESTAMP}.sql.gz \
        > ${BACKUP_DIR}/database/sofia_${TIMESTAMP}.sql.gz.sha256
    
    log "Database backup completed: sofia_${TIMESTAMP}.sql.gz"
}

# 2. Configuration Backup
backup_configs() {
    log "Backing up configurations..."
    
    # Create config archive
    tar -czf ${BACKUP_DIR}/configs/configs_${TIMESTAMP}.tar.gz \
        --exclude='*.pyc' \
        --exclude='__pycache__' \
        --exclude='.env' \
        ./src/config \
        ./docker-compose.yml \
        ./nginx \
        ./monitoring
    
    log "Configuration backup completed"
}

# 3. Trade History Backup
backup_trades() {
    log "Backing up trade history..."
    
    # Export trades from database
    docker exec sofia-postgres psql -U sofia -d sofia -c \
        "COPY (SELECT * FROM trades WHERE created_at >= NOW() - INTERVAL '24 hours') 
         TO STDOUT WITH CSV HEADER" \
        > ${BACKUP_DIR}/trades/trades_${TIMESTAMP}.csv
    
    # Compress trades
    gzip ${BACKUP_DIR}/trades/trades_${TIMESTAMP}.csv
    
    log "Trade history backup completed"
}

# 4. Logs Backup
backup_logs() {
    log "Backing up logs..."
    
    # Collect logs from containers
    docker logs sofia-app --since 24h > ${BACKUP_DIR}/logs/app_${TIMESTAMP}.log 2>&1
    docker logs sofia-worker --since 24h > ${BACKUP_DIR}/logs/worker_${TIMESTAMP}.log 2>&1
    docker logs sofia-nginx --since 24h > ${BACKUP_DIR}/logs/nginx_${TIMESTAMP}.log 2>&1
    
    # Compress logs
    tar -czf ${BACKUP_DIR}/logs/logs_${TIMESTAMP}.tar.gz \
        ${BACKUP_DIR}/logs/*_${TIMESTAMP}.log
    
    # Remove uncompressed logs
    rm ${BACKUP_DIR}/logs/*_${TIMESTAMP}.log
    
    log "Logs backup completed"
}

# 5. Upload to S3
upload_to_s3() {
    log "Uploading backups to S3..."
    
    # Check if AWS CLI is available
    if ! command -v aws &> /dev/null; then
        warning "AWS CLI not found, using rclone instead"
        
        # Upload with rclone
        rclone copy ${BACKUP_DIR}/database/sofia_${TIMESTAMP}.sql.gz \
            s3:${S3_BUCKET}/database/
        rclone copy ${BACKUP_DIR}/configs/configs_${TIMESTAMP}.tar.gz \
            s3:${S3_BUCKET}/configs/
        rclone copy ${BACKUP_DIR}/trades/trades_${TIMESTAMP}.csv.gz \
            s3:${S3_BUCKET}/trades/
        rclone copy ${BACKUP_DIR}/logs/logs_${TIMESTAMP}.tar.gz \
            s3:${S3_BUCKET}/logs/
    else
        # Upload with AWS CLI
        aws s3 cp ${BACKUP_DIR}/database/sofia_${TIMESTAMP}.sql.gz \
            s3://${S3_BUCKET}/database/ --storage-class STANDARD_IA
        aws s3 cp ${BACKUP_DIR}/configs/configs_${TIMESTAMP}.tar.gz \
            s3://${S3_BUCKET}/configs/ --storage-class STANDARD_IA
        aws s3 cp ${BACKUP_DIR}/trades/trades_${TIMESTAMP}.csv.gz \
            s3://${S3_BUCKET}/trades/ --storage-class STANDARD_IA
        aws s3 cp ${BACKUP_DIR}/logs/logs_${TIMESTAMP}.tar.gz \
            s3://${S3_BUCKET}/logs/ --storage-class STANDARD_IA
    fi
    
    log "S3 upload completed"
}

# 6. Cleanup old backups
cleanup_old_backups() {
    log "Cleaning up old backups..."
    
    # Local cleanup
    find ${BACKUP_DIR}/database -name "*.sql.gz" -mtime +${RETENTION_DAYS} -delete
    find ${BACKUP_DIR}/configs -name "*.tar.gz" -mtime +${RETENTION_DAYS} -delete
    find ${BACKUP_DIR}/trades -name "*.csv.gz" -mtime +${RETENTION_DAYS} -delete
    find ${BACKUP_DIR}/logs -name "*.tar.gz" -mtime +${RETENTION_DAYS} -delete
    
    # S3 cleanup (if using AWS CLI)
    if command -v aws &> /dev/null; then
        aws s3 ls s3://${S3_BUCKET}/database/ --recursive \
            | while read -r line; do
                createDate=$(echo $line | awk {'print $1" "$2'})
                createDate=$(date -d "$createDate" +%s)
                olderThan=$(date -d "${RETENTION_DAYS} days ago" +%s)
                if [[ $createDate -lt $olderThan ]]; then
                    fileName=$(echo $line | awk {'print $4'})
                    aws s3 rm s3://${S3_BUCKET}/$fileName
                fi
            done
    fi
    
    log "Cleanup completed"
}

# 7. Verify backups
verify_backups() {
    log "Verifying backups..."
    
    # Check database backup
    if [ ! -f ${BACKUP_DIR}/database/sofia_${TIMESTAMP}.sql.gz ]; then
        error "Database backup verification failed"
        return 1
    fi
    
    # Verify checksum
    cd ${BACKUP_DIR}/database
    sha256sum -c sofia_${TIMESTAMP}.sql.gz.sha256 || {
        error "Database backup checksum verification failed"
        return 1
    }
    
    log "Backup verification completed"
}

# 8. Send notification
send_notification() {
    status=$1
    message=$2
    
    # Slack notification
    if [ ! -z "${SLACK_WEBHOOK}" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"Backup ${status}: ${message}\"}" \
            ${SLACK_WEBHOOK}
    fi
    
    # Email notification (using sendmail if available)
    if command -v sendmail &> /dev/null && [ ! -z "${ADMIN_EMAIL}" ]; then
        echo "Subject: Sofia Backup ${status}
        
        ${message}
        
        Timestamp: ${TIMESTAMP}
        " | sendmail ${ADMIN_EMAIL}
    fi
}

# Main execution
main() {
    log "Starting Sofia V2 backup process..."
    
    # Run backups
    backup_database || { error "Database backup failed"; exit 1; }
    backup_configs || { error "Config backup failed"; exit 1; }
    backup_trades || { error "Trade backup failed"; exit 1; }
    backup_logs || { error "Log backup failed"; exit 1; }
    
    # Upload to S3
    upload_to_s3 || { error "S3 upload failed"; exit 1; }
    
    # Verify
    verify_backups || { error "Backup verification failed"; exit 1; }
    
    # Cleanup
    cleanup_old_backups
    
    # Get backup sizes
    db_size=$(du -h ${BACKUP_DIR}/database/sofia_${TIMESTAMP}.sql.gz | cut -f1)
    config_size=$(du -h ${BACKUP_DIR}/configs/configs_${TIMESTAMP}.tar.gz | cut -f1)
    trades_size=$(du -h ${BACKUP_DIR}/trades/trades_${TIMESTAMP}.csv.gz | cut -f1)
    logs_size=$(du -h ${BACKUP_DIR}/logs/logs_${TIMESTAMP}.tar.gz | cut -f1)
    
    # Send success notification
    send_notification "SUCCESS" "Backup completed successfully
    - Database: ${db_size}
    - Configs: ${config_size}
    - Trades: ${trades_size}
    - Logs: ${logs_size}"
    
    log "Backup process completed successfully"
}

# Run main function
main "$@"