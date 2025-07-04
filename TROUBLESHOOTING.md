# Medical Data Validator Troubleshooting Guide

## Overview

This guide helps you resolve common issues when using the Medical Data Validator v1.2. If you encounter problems not covered here, please check our [documentation](https://medical-data-validator-production.up.railway.app/docs) or [open an issue](https://github.com/RanaEhtashamAli/medical-data-validator/issues).

## 🚀 Quick Health Check

### System Status
```bash
# Check API health
curl https://medical-data-validator-production.up.railway.app/api/health

# Check dashboard health
curl https://medical-data-validator-production.up.railway.app/health

# Check v1.2 specific health
curl https://medical-data-validator-production.up.railway.app/api/v1.2/health
```

### Expected Responses
```json
{
  "status": "healthy",
  "version": "1.2.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "features": ["compliance", "analytics", "monitoring"]
}
```

## 🔧 Common Issues

### 1. Installation Problems

#### Python Version Issues
**Problem**: `SyntaxError` or import errors
```bash
# Check Python version
python --version  # Should be 3.8+

# Update Python if needed
# Windows: Download from python.org
# macOS: brew install python@3.9
# Linux: sudo apt-get install python3.9
```

#### Dependency Conflicts
**Problem**: `ImportError` or version conflicts
```bash
# Create fresh virtual environment
python -m venv fresh_venv
source fresh_venv/bin/activate  # On Windows: fresh_venv\Scripts\activate

# Install with specific versions
pip install -r requirements.txt --no-cache-dir
```

#### Missing Dependencies
**Problem**: `ModuleNotFoundError`
```bash
# Install missing packages
pip install pandas numpy flask plotly

# Or reinstall all dependencies
pip install -r requirements.txt --force-reinstall
```

### 2. Web Interface Issues

#### Dashboard Not Loading
**Problem**: Dashboard shows blank page or errors
```bash
# Check if server is running
ps aux | grep python

# Restart the dashboard
python launch_dashboard.py

# Check logs
tail -f logs/app.log
```

#### File Upload Failures
**Problem**: Files not uploading or validation errors
```bash
# Check file size limits
ls -lh your_file.csv

# Check file format
file your_file.csv

# Try smaller test file
head -100 your_file.csv > test_file.csv
```

#### Chart Display Issues
**Problem**: Charts not showing or displaying incorrectly
```javascript
// Check browser console for errors
// Ensure JavaScript is enabled
// Try refreshing the page
// Clear browser cache
```

### 3. API Issues

#### Connection Refused
**Problem**: `ConnectionError` or `ConnectionRefused`
```bash
# Check if API server is running
curl https://medical-data-validator-production.up.railway.app/api/health

# Check port availability
netstat -tulpn | grep :8000

# Restart API server
python launch_api.py
```

#### 500 Internal Server Error
**Problem**: API returns 500 errors
```bash
# Check server logs
tail -f logs/error.log

# Check application logs
tail -f logs/app.log

# Restart with debug mode
export FLASK_ENV=development
export DEBUG=true
python launch_api.py
```

#### CORS Errors
**Problem**: Browser shows CORS errors
```python
# Check CORS configuration
ALLOWED_ORIGINS = [
    'https://medical-data-validator-production.up.railway.app',
    'https://yourdomain.com'
]

# Update CORS settings in your environment
export ALLOWED_ORIGINS=https://medical-data-validator-production.up.railway.app
```

### 4. Validation Issues

#### Data Format Problems
**Problem**: Validation fails due to data format
```python
# Check data format
import pandas as pd
data = pd.read_csv('your_file.csv')
print(data.dtypes)
print(data.head())

# Common fixes:
# - Remove BOM from CSV files
# - Ensure proper encoding (UTF-8)
# - Check for hidden characters
```

#### Compliance Validation Errors
**Problem**: Compliance checks failing
```python
# Check compliance template
from medical_data_validator import MedicalDataValidator

validator = MedicalDataValidator(
    enable_compliance=True,
    compliance_template='clinical_trials'
)

# Test with sample data
test_data = pd.DataFrame({
    'patient_id': ['001'],
    'diagnosis': ['E11.9']
})

result = validator.validate(test_data)
print(result.summary)
```

#### Performance Issues
**Problem**: Slow validation or timeouts
```bash
# Check system resources
htop
df -h
free -h

# Increase timeout
export TIMEOUT=600

# Use smaller datasets for testing
head -1000 large_file.csv > test_file.csv
```

### 5. Docker Issues

#### Container Not Starting
**Problem**: Docker container fails to start
```bash
# Check Docker logs
docker logs medical-validator

# Check container status
docker ps -a

# Rebuild container
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

#### Port Conflicts
**Problem**: Ports already in use
```bash
# Check port usage
netstat -tulpn | grep :8000
netstat -tulpn | grep :5000

# Kill processes using ports
sudo kill -9 $(lsof -t -i:8000)
sudo kill -9 $(lsof -t -i:5000)

# Or use different ports
docker-compose up -d -p 8001:8000 -p 5001:5000
```

#### Volume Mount Issues
**Problem**: Compliance templates not loading
```bash
# Check volume mounts
docker inspect medical-validator

# Ensure templates directory exists
ls -la compliance_templates/

# Fix permissions
chmod -R 755 compliance_templates/
```

## 🔍 Debugging Techniques

### Enable Debug Mode
```bash
# Set debug environment variables
export FLASK_ENV=development
export DEBUG=true
export LOG_LEVEL=DEBUG

# Start with debug logging
python -u launch_medical_validator_web_ui.py --debug
```

### Check Logs
```bash
# Application logs
tail -f logs/app.log

# Error logs
tail -f logs/error.log

# Access logs
tail -f logs/access.log

# System logs
journalctl -u medical-validator -f
```

### Network Diagnostics
```bash
# Test API connectivity
curl -v https://medical-data-validator-production.up.railway.app/api/health

# Check DNS resolution
nslookup medical-data-validator-production.up.railway.app

# Test port connectivity
telnet medical-data-validator-production.up.railway.app 443
```

### Performance Analysis
```bash
# Monitor system resources
htop
iotop
netstat -i

# Profile application
python -m cProfile -o profile.stats launch_api.py

# Analyze profile
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(10)"
```

## 🛠️ Advanced Troubleshooting

### Database Issues
```bash
# Check database connection
python -c "from medical_data_validator.database import db; print(db.engine.execute('SELECT 1').fetchone())"

# Reset database (if using SQLite)
rm medical_validator.db
python -c "from medical_data_validator.database import init_db; init_db()"
```

### Memory Issues
```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head

# Increase swap space
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### SSL/TLS Issues
```bash
# Check SSL certificate
openssl s_client -connect medical-data-validator-production.up.railway.app:443

# Test HTTPS connectivity
curl -I https://medical-data-validator-production.up.railway.app/api/health

# Check certificate validity
echo | openssl s_client -servername medical-data-validator-production.up.railway.app -connect medical-data-validator-production.up.railway.app:443 2>/dev/null | openssl x509 -noout -dates
```

## 📊 Monitoring and Alerts

### Health Monitoring
```bash
# Set up health checks
while true; do
    curl -f https://medical-data-validator-production.up.railway.app/api/health || echo "API down at $(date)"
    sleep 60
done
```

### Performance Monitoring
```bash
# Monitor response times
curl -w "@curl-format.txt" -o /dev/null -s https://medical-data-validator-production.up.railway.app/api/health

# Create curl format file
cat > curl-format.txt << EOF
     time_namelookup:  %{time_namelookup}\n
        time_connect:  %{time_connect}\n
     time_appconnect:  %{time_appconnect}\n
    time_pretransfer:  %{time_pretransfer}\n
       time_redirect:  %{time_redirect}\n
  time_starttransfer:  %{time_starttransfer}\n
                     ----------\n
          time_total:  %{time_total}\n
EOF
```

### Alert Configuration
```python
# Configure alerts for common issues
ALERT_CONFIG = {
    'compliance_threshold': 80,
    'response_time_threshold': 5000,  # ms
    'error_rate_threshold': 0.05,
    'notification_channels': ['email', 'slack']
}
```

## 🔧 Configuration Fixes

### Environment Variables
```bash
# Essential environment variables
export FLASK_ENV=production
export SECRET_KEY=your-secret-key-here
export ALLOWED_ORIGINS=https://medical-data-validator-production.up.railway.app
export ENABLE_COMPLIANCE=true
export ENABLE_ANALYTICS=true
export ENABLE_MONITORING=true

# Performance tuning
export WORKER_PROCESSES=4
export MAX_FILE_SIZE=16777216
export TIMEOUT=300
```

### Application Configuration
```python
# Flask configuration
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY'),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB
    UPLOAD_FOLDER='/tmp/uploads',
    ALLOWED_EXTENSIONS={'csv', 'xlsx', 'json', 'parquet'}
)

# CORS configuration
CORS(app, origins=[
    'https://medical-data-validator-production.up.railway.app',
    'https://yourdomain.com'
])
```

## 📞 Getting Help

### Before Contacting Support

1. **Check this guide** for your specific issue
2. **Review logs** for error messages
3. **Test with minimal data** to isolate the problem
4. **Check system requirements** and dependencies
5. **Try the health checks** above

### Contact Information

- **Documentation**: https://medical-data-validator-production.up.railway.app/docs
- **API Documentation**: https://medical-data-validator-production.up.railway.app/api/docs
- **Health Check**: https://medical-data-validator-production.up.railway.app/api/health
- **GitHub Issues**: [Report bugs and request features](https://github.com/RanaEhtashamAli/medical-data-validator/issues)
- **Email Support**: ranaehtashamali1@gmail.com

### When Reporting Issues

Please include:
- **Error messages** and stack traces
- **System information** (OS, Python version, etc.)
- **Steps to reproduce** the issue
- **Sample data** (if applicable)
- **Log files** (with sensitive information removed)

## 🎯 Quick Fixes

### Common Solutions

```bash
# Restart everything
docker-compose down
docker-compose up -d

# Clear cache
rm -rf __pycache__/
rm -rf .pytest_cache/

# Reset configuration
cp .env.example .env
# Edit .env with your settings

# Update dependencies
pip install -r requirements.txt --upgrade

# Check disk space
df -h
du -sh *

# Restart services
sudo systemctl restart medical-validator
```

---

**Medical Data Validator v1.2 - Troubleshooting Guide**

*For additional help, check our [documentation](https://medical-data-validator-production.up.railway.app/docs) or [contact support](mailto:ranaehtashamali1@gmail.com).* 