# Medical Data Validator - Troubleshooting Guide

## Common Issues and Solutions

### Import Errors

#### "attempted relative import with no known parent package"

**Problem**: This error occurs when trying to run Python files directly that use relative imports.

**Solution**: Use the provided launcher scripts instead of running files directly:

```bash
# ❌ Don't do this:
python medical_data_validator/dashboard/app.py

# ✅ Do this instead:
python launch_dashboard.py
python launch_api.py
```

#### "ModuleNotFoundError: No module named 'medical_data_validator'"

**Problem**: Python can't find the medical_data_validator package.

**Solution**: 
1. Make sure you're in the project root directory
2. Install the package in development mode:
   ```bash
   pip install -e .
   ```
3. Or use the launcher scripts which handle path setup automatically

#### "ImportError: cannot import name 'ValidationResult'"

**Problem**: Core module imports are failing.

**Solution**:
1. Check that all dependencies are installed:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-api.txt
   ```
2. Verify the package structure is correct
3. Try reinstalling the package:
   ```bash
   pip uninstall medical-data-validator
   pip install -e .
   ```

### Flask/Dash Import Issues

#### "ModuleNotFoundError: No module named 'flask'"

**Problem**: Flask is not installed.

**Solution**:
```bash
pip install flask
pip install dash
pip install dash-bootstrap-components
```

#### "ModuleNotFoundError: No module named 'plotly'"

**Problem**: Plotly is not installed (optional dependency).

**Solution**:
```bash
pip install plotly
```

**Note**: Plotly is optional. The application will work without it, but charts won't be generated.

### File Upload Issues

#### "File type not allowed"

**Problem**: Uploaded file format is not supported.

**Solution**: 
- Supported formats: CSV (.csv), Excel (.xlsx, .xls), JSON (.json), Parquet (.parquet)
- Check file extension and content
- Ensure file is not corrupted

#### "File too large"

**Problem**: File exceeds the 16MB limit.

**Solution**:
- Reduce file size by removing unnecessary columns
- Split large files into smaller chunks
- Use data compression if possible

### API Issues

#### "500 Internal Server Error"

**Problem**: Server-side error in API processing.

**Solution**:
1. Check the logs for detailed error messages
2. Verify input data format
3. Ensure all required dependencies are installed
4. Try with smaller datasets first

#### "Connection refused"

**Problem**: API server is not running or port is blocked.

**Solution**:
1. Start the API server:
   ```bash
   python launch_api.py
   ```
2. Check if port 8000 is available
3. Verify firewall settings

### Performance Issues

#### "Validation is slow"

**Problem**: Large datasets take too long to validate.

**Solution**:
1. Use smaller datasets for testing
2. Enable caching if available
3. Consider using the CLI for batch processing
4. Check system resources (CPU, memory)

#### "Memory error"

**Problem**: Not enough memory to process large files.

**Solution**:
1. Increase system memory
2. Process files in smaller chunks
3. Use streaming validation for very large files
4. Close other applications to free memory

### Security Issues

#### "SSL certificate errors"

**Problem**: HTTPS certificate validation fails.

**Solution**:
1. For development: Use HTTP or disable SSL verification
2. For production: Install valid SSL certificates
3. Update certificate authorities

#### "Permission denied"

**Problem**: File system permissions prevent access.

**Solution**:
1. Check file and directory permissions
2. Run with appropriate user privileges
3. Ensure temporary directories are writable

### Database Issues

#### "Database connection failed"

**Problem**: Cannot connect to database (if using one).

**Solution**:
1. Check database server status
2. Verify connection credentials
3. Ensure database exists and is accessible
4. Check network connectivity

### Network Issues

#### "CORS errors"

**Problem**: Cross-origin requests are blocked.

**Solution**:
1. Configure CORS settings in the application
2. Use same-origin requests when possible
3. Set appropriate headers for cross-origin requests

#### "Timeout errors"

**Problem**: Requests take too long and timeout.

**Solution**:
1. Increase timeout settings
2. Optimize validation performance
3. Use smaller datasets
4. Check network connectivity

## Debugging Tips

### Enable Debug Mode

```bash
# For dashboard
python launch_dashboard.py --debug

# For API
python launch_api.py --debug
```

### Check Logs

```bash
# View application logs
tail -f logs/api.log
tail -f logs/dashboard.log

# Check system logs
journalctl -u medical-validator -f
```

### Test Individual Components

```bash
# Test imports
python test_imports.py

# Test API endpoints
curl http://localhost:8000/api/health

# Test file upload
curl -X POST -F "file=@test_data.csv" http://localhost:8000/api/validate/file
```

### Verify Installation

```bash
# Check installed packages
pip list | grep medical

# Check package structure
python -c "import medical_data_validator; print(medical_data_validator.__file__)"

# Run tests
python -m pytest tests/
```

## Getting Help

If you're still experiencing issues:

1. **Check the logs** for detailed error messages
2. **Search existing issues** on GitHub
3. **Create a new issue** with:
   - Error message and traceback
   - Steps to reproduce
   - System information (OS, Python version)
   - Package versions
4. **Contact support**: ranaehtashamali1@gmail.com

## System Requirements

### Minimum Requirements
- Python 3.8+
- 4GB RAM
- 100MB disk space
- Internet connection for package installation

### Recommended Requirements
- Python 3.11+
- 8GB RAM
- 500MB disk space
- SSD storage for better performance

### Supported Platforms
- Windows 10/11
- macOS 10.15+
- Ubuntu 18.04+
- CentOS 7+

---

**Last Updated**: January 2024  
**Version**: 1.0 