#!/bin/bash

# Sofia V2 Production Deployment Script
# Zero-downtime deployment with health checks and rollback

set -e

# Configuration
ENVIRONMENT=${1:-production}
VERSION=${2:-latest}
ROLLBACK=${3:-false}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging
log() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"; }
error() { echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2; }
warning() { echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"; }
info() { echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"; }

# Pre-deployment checks
pre_deploy_checks() {
    log "Running pre-deployment checks..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose not installed"
        exit 1
    fi
    
    # Check environment file
    if [ ! -f ".env.${ENVIRONMENT}" ]; then
        error "Environment file .env.${ENVIRONMENT} not found"
        exit 1
    fi
    
    # Check disk space
    DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ $DISK_USAGE -gt 80 ]; then
        warning "Disk usage is high: ${DISK_USAGE}%"
    fi
    
    # Check memory
    MEM_USAGE=$(free | grep Mem | awk '{print int($3/$2 * 100)}')
    if [ $MEM_USAGE -gt 80 ]; then
        warning "Memory usage is high: ${MEM_USAGE}%"
    fi
    
    log "Pre-deployment checks passed"
}

# Backup current deployment
backup_current() {
    log "Creating backup of current deployment..."
    
    BACKUP_DIR="backups/deploy_$(date +%Y%m%d_%H%M%S)"
    mkdir -p $BACKUP_DIR
    
    # Backup database
    docker-compose exec -T postgres pg_dump -U sofia sofia > $BACKUP_DIR/database.sql
    
    # Backup volumes
    docker run --rm -v sofia-v2_postgres-data:/data -v $(pwd)/$BACKUP_DIR:/backup \
        alpine tar czf /backup/postgres-data.tar.gz -C /data .
    
    # Save current docker images
    docker-compose config | grep 'image:' | awk '{print $2}' | while read img; do
        docker save $img | gzip > $BACKUP_DIR/$(echo $img | tr '/' '_').tar.gz
    done
    
    # Create manifest
    cat > $BACKUP_DIR/manifest.json <<EOF
{
    "timestamp": "$(date -Iseconds)",
    "version": "$(git rev-parse HEAD)",
    "environment": "${ENVIRONMENT}",
    "containers": $(docker-compose ps --format json)
}
EOF
    
    log "Backup created at $BACKUP_DIR"
}

# Build and test new version
build_and_test() {
    log "Building new version..."
    
    # Build images
    docker-compose -f docker-compose.yml -f docker-compose.${ENVIRONMENT}.yml build
    
    # Run tests
    log "Running tests..."
    docker-compose -f docker-compose.test.yml up --abort-on-container-exit
    TEST_EXIT_CODE=$?
    
    if [ $TEST_EXIT_CODE -ne 0 ]; then
        error "Tests failed"
        docker-compose -f docker-compose.test.yml down
        exit 1
    fi
    
    docker-compose -f docker-compose.test.yml down
    log "Tests passed"
}

# Deploy with blue-green strategy
deploy_blue_green() {
    log "Starting blue-green deployment..."
    
    # Start new containers (green)
    docker-compose -f docker-compose.yml -f docker-compose.${ENVIRONMENT}.yml \
        up -d --no-deps --scale app=2 --scale worker=2
    
    # Wait for new containers to be healthy
    log "Waiting for new containers to be healthy..."
    sleep 30
    
    # Health check
    HEALTH_CHECK_URL="http://localhost:8000/health"
    MAX_RETRIES=30
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if curl -f $HEALTH_CHECK_URL > /dev/null 2>&1; then
            log "Health check passed"
            break
        fi
        RETRY_COUNT=$((RETRY_COUNT + 1))
        sleep 2
    done
    
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        error "Health check failed after $MAX_RETRIES attempts"
        rollback
        exit 1
    fi
    
    # Run database migrations
    log "Running database migrations..."
    docker-compose exec -T app alembic upgrade head
    
    # Switch traffic to new containers
    log "Switching traffic to new containers..."
    docker-compose exec -T nginx nginx -s reload
    
    # Stop old containers
    log "Stopping old containers..."
    OLD_CONTAINERS=$(docker ps --filter "label=com.docker.compose.version!=2" --format "{{.ID}}")
    if [ ! -z "$OLD_CONTAINERS" ]; then
        docker stop $OLD_CONTAINERS
        docker rm $OLD_CONTAINERS
    fi
    
    log "Blue-green deployment completed"
}

# Deploy with rolling update
deploy_rolling() {
    log "Starting rolling deployment..."
    
    # Get current replica count
    CURRENT_REPLICAS=$(docker-compose ps app | grep -c "Up" || true)
    if [ $CURRENT_REPLICAS -eq 0 ]; then
        CURRENT_REPLICAS=1
    fi
    
    # Deploy one replica at a time
    for i in $(seq 1 $CURRENT_REPLICAS); do
        log "Updating replica $i of $CURRENT_REPLICAS..."
        
        # Start new container
        docker-compose -f docker-compose.yml -f docker-compose.${ENVIRONMENT}.yml \
            up -d --no-deps --scale app=$((CURRENT_REPLICAS + 1))
        
        # Wait for health check
        sleep 20
        
        # Remove old container
        OLD_CONTAINER=$(docker-compose ps app | grep "Up" | head -1 | awk '{print $1}')
        docker stop $OLD_CONTAINER
        docker rm $OLD_CONTAINER
        
        # Scale back
        docker-compose -f docker-compose.yml -f docker-compose.${ENVIRONMENT}.yml \
            up -d --no-deps --scale app=$CURRENT_REPLICAS
    done
    
    log "Rolling deployment completed"
}

# Rollback deployment
rollback() {
    error "Rolling back deployment..."
    
    # Get last backup
    LAST_BACKUP=$(ls -t backups/deploy_* | head -1)
    
    if [ -z "$LAST_BACKUP" ]; then
        error "No backup found to rollback"
        exit 1
    fi
    
    log "Rolling back to $LAST_BACKUP..."
    
    # Stop current containers
    docker-compose down
    
    # Restore database
    docker-compose up -d postgres
    sleep 10
    docker-compose exec -T postgres psql -U sofia sofia < $LAST_BACKUP/database.sql
    
    # Restore volumes
    docker run --rm -v sofia-v2_postgres-data:/data -v $(pwd)/$LAST_BACKUP:/backup \
        alpine tar xzf /backup/postgres-data.tar.gz -C /data
    
    # Load and start old images
    for img in $LAST_BACKUP/*.tar.gz; do
        if [ -f "$img" ]; then
            docker load < $img
        fi
    done
    
    # Start services
    docker-compose up -d
    
    log "Rollback completed"
}

# Post-deployment tasks
post_deploy() {
    log "Running post-deployment tasks..."
    
    # Clear caches
    docker-compose exec -T redis redis-cli FLUSHALL
    
    # Warm up application
    curl -s http://localhost:8000/health > /dev/null
    
    # Run smoke tests
    log "Running smoke tests..."
    ./scripts/smoke_tests.sh
    
    # Update monitoring
    curl -X POST http://localhost:9090/-/reload
    
    # Send notification
    if [ ! -z "$SLACK_WEBHOOK" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"Deployment completed successfully to ${ENVIRONMENT}\"}" \
            $SLACK_WEBHOOK
    fi
    
    log "Post-deployment tasks completed"
}

# Monitor deployment
monitor_deployment() {
    log "Monitoring deployment for 5 minutes..."
    
    END_TIME=$(($(date +%s) + 300))
    ERROR_COUNT=0
    
    while [ $(date +%s) -lt $END_TIME ]; do
        # Check health
        if ! curl -f http://localhost:8000/health > /dev/null 2>&1; then
            ERROR_COUNT=$((ERROR_COUNT + 1))
            warning "Health check failed (count: $ERROR_COUNT)"
            
            if [ $ERROR_COUNT -gt 5 ]; then
                error "Too many health check failures"
                rollback
                exit 1
            fi
        else
            ERROR_COUNT=0
        fi
        
        # Check error rate
        ERROR_RATE=$(docker-compose logs --tail=100 app | grep -c ERROR || true)
        if [ $ERROR_RATE -gt 10 ]; then
            warning "High error rate detected: $ERROR_RATE errors in last 100 lines"
        fi
        
        sleep 10
    done
    
    log "Deployment monitoring completed successfully"
}

# Main deployment flow
main() {
    info "Starting deployment to ${ENVIRONMENT} with version ${VERSION}"
    
    # Change to project directory
    cd /opt/sofia-v2
    
    # Load environment
    export $(cat .env.${ENVIRONMENT} | xargs)
    
    if [ "$ROLLBACK" = "true" ]; then
        rollback
        exit 0
    fi
    
    # Run deployment steps
    pre_deploy_checks
    backup_current
    build_and_test
    
    # Choose deployment strategy
    if [ "$ENVIRONMENT" = "production" ]; then
        deploy_blue_green
    else
        deploy_rolling
    fi
    
    post_deploy
    monitor_deployment
    
    log "Deployment completed successfully!"
    
    # Generate deployment report
    cat <<EOF

===== DEPLOYMENT REPORT =====
Environment: ${ENVIRONMENT}
Version: ${VERSION}
Timestamp: $(date)
Status: SUCCESS

Running Containers:
$(docker-compose ps)

Resource Usage:
- CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')
- Memory: $(free -h | grep Mem | awk '{print $3 "/" $2}')
- Disk: $(df -h / | awk 'NR==2 {print $3 "/" $2}')

Health Check: PASSED
============================
EOF
}

# Handle errors
trap 'error "Deployment failed"; rollback' ERR

# Run main function
main "$@"