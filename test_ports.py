import requests

# Test port 5000 (Flask server)
try:
    response = requests.get('http://localhost:5000/api/health', timeout=5)
    print(f'Port 5000 status: {response.status_code}')
except Exception as e:
    print(f'Port 5000 error: {e}')

# Test port 8000 (test server)
try:
    response = requests.get('http://localhost:8000/api/health', timeout=5)
    print(f'Port 8000 status: {response.status_code}')
except Exception as e:
    print(f'Port 8000 error: {e}') 