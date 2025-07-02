---
name: Bug report
about: Create a report to help us improve
title: '[BUG] '
labels: ['bug']
assignees: ''

---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Actual behavior**
A clear and concise description of what actually happened.

**Environment:**
 - OS: [e.g. Ubuntu 20.04, Windows 10, macOS 12]
 - Python version: [e.g. 3.8, 3.9, 3.10, 3.11]
 - Medical Data Validator version: [e.g. 0.1.0]
 - Pandas version: [e.g. 1.5.0]

**Sample Data**
Please provide a minimal example of the data that causes the issue (anonymized if necessary):

```python
import pandas as pd
from medical_data_validator import MedicalDataValidator

# Your code here
data = pd.DataFrame({
    # Your data here
})

validator = MedicalDataValidator()
result = validator.validate(data)
```

**Error Messages**
If applicable, add error messages or stack traces:

```
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  ...
```

**Additional context**
Add any other context about the problem here.

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Checklist**
- [ ] I have searched existing issues to avoid duplicates
- [ ] I have provided a minimal reproducible example
- [ ] I have included all relevant environment information
- [ ] I have anonymized any sensitive data in my examples 