# Medical Data Validator v1.2 Deployment Guide

## Overview

This guide covers deploying the Medical Data Validator v1.2 with advanced compliance features, analytics, and monitoring capabilities.

## Quick Start

### Production URLs
- **Dashboard**: https://medical-data-validator-production.up.railway.app/home
- **API**: https://medical-data-validator-production.up.railway.app/api

### Docker Deployment

```bash
# Clone the repository
git clone https://github.com/RanaEhtashamAli/medical-data-validator.git
cd medical-data-validator

# Build and run with Docker Compose
docker-compose up -d

# Access the application
# - Dashboard: https://medical-data-validator-production.up.railway.app/home
# - API: https://medical-data-validator-production.up.railway.app/api
```

## Environment Configuration

### Required Environment Variables

```bash
# Application Settings
FLASK_ENV=production
SECRET_KEY=your-secret-key-here
DEBUG=false

# Database (if using external database)
DATABASE_URL=postgresql://user:password@host:port/dbname

# Security
ALLOWED_ORIGINS=https://medical-data-validator-production.up.railway.app
CORS_ORIGINS=https://medical-data-validator-production.up.railway.app

# v1.2 Features
ENABLE_COMPLIANCE=true
ENABLE_ANALYTICS=true
ENABLE_MONITORING=true
COMPLIANCE_TEMPLATE=clinical_trials

# Performance
MAX_FILE_SIZE=16777216  # 16MB
WORKER_PROCESSES=4
TIMEOUT=300
```

### Optional Environment Variables

```bash
# Monitoring
ENABLE_ALERTS=true
ALERT_EMAIL=admin@yourdomain.com
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Compliance Templates
COMPLIANCE_TEMPLATES_DIR=/app/compliance_templates
CUSTOM_RULES_FILE=/app/custom_rules.json

# Analytics
ANALYTICS_RETENTION_DAYS=90
QUALITY_THRESHOLD=80

# Security
RATE_LIMIT=100
SESSION_TIMEOUT=3600
```

## API Testing

### Health Check

```bash
curl https://medical-data-validator-production.up.railway.app/api/health
```

### v1.2 Compliance Validation

```bash
curl -X POST https://medical-data-validator-production.up.railway.app/api/compliance/v1.2 \
  -F "file=@medical_data.csv" \
  -F "compliance_template=clinical_trials" \
  -F "risk_assessment=true"
```

### Analytics

```bash
curl -X POST https://medical-data-validator-production.up.railway.app/api/analytics \
  -F "file=@medical_data.csv"
```

### Monitoring

```bash
# Health check
curl https://medical-data-validator-production.up.railway.app/api/health

# Dashboard health
curl https://medical-data-validator-production.up.railway.app/health

# System monitoring
curl https://medical-data-validator-production.up.railway.app/api/monitoring/stats

# Active alerts
curl https://medical-data-validator-production.up.railway.app/api/monitoring/alerts

# Quality trends
curl https://medical-data-validator-production.up.railway.app/api/monitoring/trends/compliance_score
```

## Production Deployment

### Railway Deployment

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize project
railway init

# Set environment variables
railway variables set FLASK_ENV=production
railway variables set SECRET_KEY=your-secret-key
railway variables set ENABLE_COMPLIANCE=true

# Deploy
railway up
```

### Docker Compose Production

```yaml
version: '3.8'

services:
  medical-validator:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=${SECRET_KEY}
      - ENABLE_COMPLIANCE=true
      - ENABLE_ANALYTICS=true
      - ENABLE_MONITORING=true
    volumes:
      - ./compliance_templates:/app/compliance_templates
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "https://medical-data-validator-production.up.railway.app/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - medical-validator
    restart: unless-stopped
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: medical-validator
spec:
  replicas: 3
  selector:
    matchLabels:
      app: medical-validator
  template:
    metadata:
      labels:
        app: medical-validator
    spec:
      containers:
      - name: medical-validator
        image: medical-validator:latest
        ports:
        - containerPort: 8000
        env:
        - name: FLASK_ENV
          value: "production"
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: medical-validator-secrets
              key: secret-key
        - name: ENABLE_COMPLIANCE
          value: "true"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: medical-validator-service
spec:
  selector:
    app: medical-validator
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

## Monitoring & Alerts

### Health Monitoring

```bash
# Check API health
curl https://medical-data-validator-production.up.railway.app/api/health

# Check dashboard health
curl https://medical-data-validator-production.up.railway.app/health

# Check specific service health
curl https://medical-data-validator-production.up.railway.app/api/v1.2/health
```

### System Monitoring

```bash
# Get system statistics
curl https://medical-data-validator-production.up.railway.app/api/monitoring/stats

# Get active alerts
curl https://medical-data-validator-production.up.railway.app/api/monitoring/alerts

# Get quality trends
curl https://medical-data-validator-production.up.railway.app/api/monitoring/trends/compliance_score
```

### Alert Configuration

```python
# Example alert configuration
ALERT_CONFIG = {
    'compliance_threshold': 80,
    'response_time_threshold': 5000,  # ms
    'error_rate_threshold': 0.05,
    'notification_channels': ['email', 'slack']
}
```

## Security Considerations

### CORS Configuration

```python
# Configure CORS for production
CORS_ORIGINS = [
    'https://medical-data-validator-production.up.railway.app',
    'https://yourdomain.com'
]
```

### Rate Limiting

```python
# Configure rate limiting
RATE_LIMIT = {
    'default': '100 per minute',
    'upload': '10 per minute',
    'api': '1000 per hour'
}
```

### SSL/TLS Configuration

```nginx
# Nginx SSL configuration
server {
    listen 443 ssl;
    server_name medical-data-validator-production.up.railway.app;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    location / {
        proxy_pass http://medical-validator:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Troubleshooting

### Common Issues

1. **CORS Errors**: Ensure `ALLOWED_ORIGINS` includes your domain
2. **File Upload Failures**: Check `MAX_FILE_SIZE` and file permissions
3. **Compliance Validation Errors**: Verify compliance templates are accessible
4. **Performance Issues**: Monitor worker processes and database connections

### Logs

```bash
# View application logs
docker logs medical-validator

# View nginx logs
docker logs nginx

# View system logs
journalctl -u medical-validator
```

### Debug Mode

```bash
# Enable debug mode temporarily
export FLASK_ENV=development
export DEBUG=true

# Restart application
docker-compose restart medical-validator
```

## Performance Optimization

### Caching

```python
# Redis caching configuration
CACHE_CONFIG = {
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': 'redis://localhost:6379/0',
    'CACHE_DEFAULT_TIMEOUT': 300
}
```

### Database Optimization

```sql
-- Create indexes for better performance
CREATE INDEX idx_validation_results_timestamp ON validation_results(timestamp);
CREATE INDEX idx_compliance_violations_severity ON compliance_violations(severity);
```

### Load Balancing

```nginx
# Nginx load balancer configuration
upstream medical_validator {
    server medical-validator-1:8000;
    server medical-validator-2:8000;
    server medical-validator-3:8000;
}

server {
    listen 80;
    location / {
        proxy_pass http://medical_validator;
    }
}
```

## Backup & Recovery

### Database Backup

```bash
# Backup compliance templates
tar -czf compliance_templates_backup.tar.gz compliance_templates/

# Backup configuration
cp .env .env.backup

# Backup logs
tar -czf logs_backup.tar.gz logs/
```

### Disaster Recovery

```bash
# Restore from backup
tar -xzf compliance_templates_backup.tar.gz
cp .env.backup .env
tar -xzf logs_backup.tar.gz

# Restart services
docker-compose restart
```

## Support

- **Documentation**: https://medical-data-validator-production.up.railway.app/docs
- **API Documentation**: https://medical-data-validator-production.up.railway.app/api/docs
- **Health Check**: https://medical-data-validator-production.up.railway.app/api/health
- **Issues**: [GitHub Issues](https://github.com/RanaEhtashamAli/medical-data-validator/issues)

---

**Medical Data Validator v1.2 - Production Ready Deployment** 