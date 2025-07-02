# Medical Data Validator - Deployment Guide

## Overview

This guide covers deploying the Medical Data Validator in various environments, from development to production.

## 🐳 Docker Deployment (Recommended)

### Quick Start
```bash
# Clone the repository
git clone https://github.com/RanaEhtashamAli/medical-data-validator.git
cd medical-data-validator

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f medical-validator-api
```

### Production Deployment
```bash
# Production with load balancer and Redis
docker-compose --profile production up -d

# Scale API service
docker-compose up -d --scale medical-validator-api=4

# Update services
docker-compose pull
docker-compose up -d
```

### Environment Configuration
Create a `.env` file for environment-specific settings:
```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_DEBUG=false

# Security
SECRET_KEY=your-super-secret-key-here
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com

# Database (if using)
DATABASE_URL=postgresql://user:pass@localhost/medical_validator

# Redis (for caching)
REDIS_URL=redis://localhost:6379

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/api.log
```

## ☁️ Cloud Deployment

### AWS Deployment

#### Using AWS ECS
```bash
# Build and push Docker image
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin your-account.dkr.ecr.us-east-1.amazonaws.com
docker build -t medical-validator .
docker tag medical-validator:latest your-account.dkr.ecr.us-east-1.amazonaws.com/medical-validator:latest
docker push your-account.dkr.ecr.us-east-1.amazonaws.com/medical-validator:latest

# Deploy to ECS
aws ecs create-service \
    --cluster medical-validator-cluster \
    --service-name medical-validator-api \
    --task-definition medical-validator:1 \
    --desired-count 2
```

#### Using AWS Lambda (Serverless)
```bash
# Package for Lambda
pip install -r requirements.txt -t package/
cd package
zip -r ../medical-validator-lambda.zip .
cd ..
zip -g medical-validator-lambda.zip lambda_function.py

# Deploy to Lambda
aws lambda create-function \
    --function-name medical-validator \
    --runtime python3.11 \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://medical-validator-lambda.zip
```

### Google Cloud Platform

#### Using Google Cloud Run
```bash
# Build and deploy
gcloud builds submit --tag gcr.io/your-project/medical-validator
gcloud run deploy medical-validator \
    --image gcr.io/your-project/medical-validator \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated
```

#### Using Google Kubernetes Engine
```bash
# Create cluster
gcloud container clusters create medical-validator-cluster \
    --num-nodes=3 \
    --zone=us-central1-a

# Deploy application
kubectl apply -f k8s/
```

### Azure Deployment

#### Using Azure Container Instances
```bash
# Build and push to Azure Container Registry
az acr build --registry yourregistry --image medical-validator .

# Deploy to Container Instances
az container create \
    --resource-group your-rg \
    --name medical-validator \
    --image yourregistry.azurecr.io/medical-validator:latest \
    --ports 8000
```

## 🏢 On-Premises Deployment

### Traditional Server Setup
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv nginx

# Create application directory
sudo mkdir -p /opt/medical-validator
sudo chown $USER:$USER /opt/medical-validator

# Clone and setup application
cd /opt/medical-validator
git clone https://github.com/RanaEhtashamAli/medical-data-validator.git .
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-api.txt

# Create systemd service
sudo tee /etc/systemd/system/medical-validator.service << EOF
[Unit]
Description=Medical Data Validator API
After=network.target

[Service]
Type=simple
User=medical-validator
WorkingDirectory=/opt/medical-validator
Environment=PATH=/opt/medical-validator/venv/bin
ExecStart=/opt/medical-validator/venv/bin/python api.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Start service
sudo systemctl enable medical-validator
sudo systemctl start medical-validator
```

### Nginx Configuration
```nginx
upstream medical_validator {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

server {
    listen 80;
    server_name api.medical-validator.com;

    location / {
        proxy_pass http://medical_validator;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://medical_validator;
    }
}
```

## 🔒 Security Configuration

### SSL/TLS Setup
```bash
# Using Let's Encrypt
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d api.medical-validator.com

# Using self-signed certificates (development)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

### Firewall Configuration
```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# iptables (CentOS/RHEL)
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo service iptables save
```

### Database Security
```bash
# PostgreSQL security
sudo -u postgres psql
CREATE DATABASE medical_validator;
CREATE USER medical_validator WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE medical_validator TO medical_validator;
\q
```

## 📊 Monitoring & Logging

### Application Monitoring
```bash
# Install monitoring tools
pip install prometheus_client
pip install statsd

# Configure logging
mkdir -p /var/log/medical-validator
chown medical-validator:medical-validator /var/log/medical-validator
```

### Log Rotation
```bash
# Configure logrotate
sudo tee /etc/logrotate.d/medical-validator << EOF
/var/log/medical-validator/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 medical-validator medical-validator
    postrotate
        systemctl reload medical-validator
    endscript
}
EOF
```

### Health Checks
```bash
# Create health check script
cat > /opt/medical-validator/health_check.sh << 'EOF'
#!/bin/bash
curl -f http://localhost:8000/api/health > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Health check failed"
    systemctl restart medical-validator
fi
EOF

chmod +x /opt/medical-validator/health_check.sh

# Add to crontab
echo "*/5 * * * * /opt/medical-validator/health_check.sh" | crontab -
```

## 🔄 CI/CD Pipeline

### GitHub Actions
```yaml
name: Deploy Medical Validator

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Build Docker image
      run: docker build -t medical-validator .
    
    - name: Push to registry
      run: |
        echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
        docker tag medical-validator your-registry/medical-validator:latest
        docker push your-registry/medical-validator:latest
    
    - name: Deploy to production
      run: |
        ssh ${{ secrets.SERVER_USER }}@${{ secrets.SERVER_HOST }} << 'EOF'
          docker pull your-registry/medical-validator:latest
          docker-compose down
          docker-compose up -d
        EOF
```

### GitLab CI
```yaml
stages:
  - build
  - deploy

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t medical-validator .
    - docker tag medical-validator $CI_REGISTRY_IMAGE:latest
    - docker push $CI_REGISTRY_IMAGE:latest

deploy:
  stage: deploy
  script:
    - apt-get update -qq && apt-get install -y -qq openssh-client
    - eval $(ssh-agent -s)
    - echo "$SSH_PRIVATE_KEY" | tr -d '\r' | ssh-add -
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
    - ssh $SERVER_USER@$SERVER_HOST "docker pull $CI_REGISTRY_IMAGE:latest && docker-compose up -d"
```

## 🚀 Performance Optimization

### Load Balancing
```bash
# Using HAProxy
sudo apt-get install haproxy

# HAProxy configuration
sudo tee /etc/haproxy/haproxy.cfg << EOF
global
    daemon
    maxconn 4096

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms

frontend medical_validator_frontend
    bind *:80
    default_backend medical_validator_backend

backend medical_validator_backend
    balance roundrobin
    server api1 127.0.0.1:8000 check
    server api2 127.0.0.1:8001 check
    server api3 127.0.0.1:8002 check
EOF
```

### Caching
```bash
# Redis configuration
sudo apt-get install redis-server

# Redis configuration
sudo tee /etc/redis/redis.conf << EOF
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
EOF
```

## 🔧 Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check logs
sudo journalctl -u medical-validator -f

# Check port availability
sudo netstat -tlnp | grep :8000

# Check permissions
ls -la /opt/medical-validator/
```

#### Performance Issues
```bash
# Monitor resource usage
htop
iotop
netstat -i

# Check application metrics
curl http://localhost:8000/api/health
```

#### SSL Issues
```bash
# Test SSL configuration
openssl s_client -connect api.medical-validator.com:443

# Check certificate validity
openssl x509 -in cert.pem -text -noout
```

## 📞 Support

For deployment support:
- **Documentation**: [GitHub Wiki](https://github.com/RanaEhtashamAli/medical-data-validator/wiki)
- **Issues**: [GitHub Issues](https://github.com/RanaEhtashamAli/medical-data-validator/issues)
- **Email**: ranaehtashamali1@gmail.com

---

**Last Updated**: January 2024  
**Version**: 1.0 