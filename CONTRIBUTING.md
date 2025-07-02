# Contributing to Medical Data Validator

Thank you for your interest in contributing to the Medical Data Validator project! This document provides guidelines for contributing to the project.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- pip or conda

### Development Setup

1. **Fork the repository** on GitHub
2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/medical-data-validator.git
   cd medical-data-validator
   ```

3. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install development dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

5. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   ```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

- Follow the coding standards (see below)
- Write tests for new functionality
- Update documentation as needed

### 3. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=medical_data_validator

# Run specific test file
pytest tests/test_core.py
```

### 4. Code Quality Checks

```bash
# Format code
black medical_data_validator tests

# Sort imports
isort medical_data_validator tests

# Lint code
flake8 medical_data_validator tests

# Type checking
mypy medical_data_validator

# Security checks
bandit -r medical_data_validator
```

### 5. Commit Your Changes

```bash
git add .
git commit -m "feat: add new validation rule for medical codes"
```

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Coding Standards

### Python Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use type hints for all function parameters and return values
- Write docstrings for all public functions and classes
- Keep functions small and focused

### Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Maintenance tasks

### Example Commit Messages

```
feat(validators): add ICD-11 code validation support
fix(core): handle empty dataframes in validation
docs(readme): update installation instructions
test(validators): add tests for new PHI detection rules
```

## Testing Guidelines

### Writing Tests

- Write tests for all new functionality
- Use descriptive test names
- Test both success and failure cases
- Mock external dependencies
- Use fixtures for common test data

### Test Structure

```python
def test_validator_with_valid_data():
    """Test that validator accepts valid medical data."""
    # Arrange
    data = create_test_data()
    validator = MedicalDataValidator()
    
    # Act
    result = validator.validate(data)
    
    # Assert
    assert result.is_valid
    assert len(result.issues) == 0
```

## Documentation

### Code Documentation

- Use Google-style docstrings
- Include type hints
- Document exceptions that may be raised
- Provide usage examples

### Example Docstring

```python
def validate_icd10_code(code: str) -> ValidationResult:
    """Validate an ICD-10 diagnosis code.
    
    Args:
        code: The ICD-10 code to validate
        
    Returns:
        ValidationResult with validation status and any issues
        
    Raises:
        ValueError: If code format is invalid
        
    Example:
        >>> result = validate_icd10_code("E11.9")
        >>> result.is_valid
        True
    """
```

## Pull Request Guidelines

### Before Submitting

1. **Ensure all tests pass**
2. **Run code quality checks**
3. **Update documentation**
4. **Add changelog entry** (if applicable)

### Pull Request Template

Use this template when creating a PR:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing
- [ ] Tests added/updated
- [ ] All tests pass
- [ ] Manual testing completed

## Documentation
- [ ] Code documented
- [ ] README updated
- [ ] API docs updated

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] No breaking changes
```

## Issue Reporting

### Bug Reports

When reporting bugs, include:

1. **Environment details** (OS, Python version, package versions)
2. **Steps to reproduce**
3. **Expected vs actual behavior**
4. **Error messages and stack traces**
5. **Sample data** (if applicable)

### Feature Requests

When requesting features, include:

1. **Use case description**
2. **Expected functionality**
3. **Proposed implementation** (if any)
4. **Priority level**

## Getting Help

- **GitHub Issues**: For bug reports and feature requests
- **Email**: ranaehtashamali1@gmail.com
- **LinkedIn**: https://www.linkedin.com/in/ranaehtashamali/

## License

By contributing to this project, you agree that your contributions will be licensed under the MIT License. 