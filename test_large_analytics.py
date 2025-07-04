import requests
import pandas as pd
from io import StringIO

# Create large test dataset (same as the failing test)
large_data = {
    'id': [str(i) for i in range(1000)],
    'value': list(range(1000)),
    'category': ['A', 'B'] * 500,
    'date': [f'2024-01-{(i % 30) + 1:02d}' for i in range(1000)]
}

df = pd.DataFrame(large_data)
csv_data = df.to_csv(index=False)

files = {'file': ('large_data.csv', StringIO(csv_data), 'text/csv')}
data = {'time_column': 'date'}

print("Testing analytics endpoint with large data...")
response = requests.post('http://localhost:5000/api/analytics', files=files, data=data)

print(f'Status: {response.status_code}')
print(f'Response: {response.text[:1000]}')

if response.status_code != 200:
    print(f'Full response: {response.text}') 