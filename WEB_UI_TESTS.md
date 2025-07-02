# Web UI Tests for Medical Data Validator

This document describes the comprehensive web UI tests for the Medical Data Validator dashboard.

## Overview

The web UI tests use Selenium WebDriver to test both the UI elements and functionality of the web dashboard. These tests ensure that the web interface works correctly across different scenarios.

## Test Structure

### 1. TestWebUIElements
Tests the basic UI elements and layout:
- Navigation bar elements (brand, links)
- Header section (title, subtitle)
- Upload section (upload area, file input, buttons)
- Validation options (checkboxes for PHI detection, quality checks)
- Profile selection dropdown
- Validate button
- Footer elements

### 2. TestWebUIFunctionality
Tests user interactions and functionality:
- File upload via button click
- Toggling validation options
- Profile selection changes
- Navigation between pages (Home/About)

### 3. TestWebUIEndToEnd
Tests complete workflows:
- File upload and validation with mocked backend
- File type validation
- End-to-end validation process

### 4. TestWebUIAccessibility
Tests accessibility features:
- Semantic HTML structure
- Labels and accessibility attributes
- Keyboard navigation

## Installation

To run the web UI tests, install the required dependencies:

```bash
# Install with testing dependencies
pip install -e ".[test]"

# Or install manually
pip install selenium pytest webdriver-manager
```

## Running Tests

### Using the Test Runner
```bash
python run_web_ui_tests.py
```

### Using pytest directly
```bash
# Run all web UI tests
pytest tests/test_web_ui.py -v

# Run specific test class
pytest tests/test_web_ui.py::TestWebUIElements -v

# Run specific test method
pytest tests/test_web_ui.py::TestWebUIElements::test_navigation_bar -v
```

## Test Features

### Browser Automation
- Uses Chrome in headless mode for CI/CD compatibility
- Supports both headless and GUI modes for development
- Automatic WebDriver management

### Flask App Integration
- Starts Flask app in separate thread for each test class
- Uses different ports to avoid conflicts
- Proper cleanup after tests

### Mocking
- Mocks backend validation logic for isolated UI testing
- Tests UI behavior without requiring full backend setup
- Allows testing error scenarios

### File Handling
- Creates temporary test files
- Tests various file formats (CSV, Excel, etc.)
- Proper cleanup of temporary files

## Test Coverage

The web UI tests cover:

1. **UI Elements**: All major UI components are tested for presence and basic functionality
2. **User Interactions**: File uploads, form submissions, navigation
3. **Form Validation**: Client-side validation and error handling
4. **Accessibility**: Keyboard navigation, semantic HTML, labels
5. **Responsive Design**: Basic responsive elements
6. **Error Handling**: File type validation, upload errors
7. **End-to-End Workflows**: Complete validation processes

## Configuration

### Chrome Options
Tests use Chrome with the following options:
- `--headless`: Run without GUI
- `--no-sandbox`: Required for some CI environments
- `--disable-dev-shm-usage`: Prevents memory issues

### Test Ports
Each test class uses a different port:
- TestWebUIElements: 5001
- TestWebUIFunctionality: 5002
- TestWebUIEndToEnd: 5003
- TestWebUIAccessibility: 5004

## Troubleshooting

### Common Issues

1. **ChromeDriver not found**
   ```bash
   pip install webdriver-manager
   ```

2. **Port conflicts**
   - Ensure no other Flask apps are running on test ports
   - Wait for previous test runs to complete

3. **Headless mode issues**
   - Some tests may behave differently in headless mode
   - Use GUI mode for debugging: remove `--headless` option

4. **Selenium version compatibility**
   - Ensure Chrome and ChromeDriver versions match
   - Use `webdriver-manager` for automatic version management

### Debug Mode

To run tests with GUI for debugging:
```python
# In test setup, remove headless option
chrome_options = Options()
# chrome_options.add_argument("--headless")  # Comment out for GUI
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
```

## Continuous Integration

The web UI tests are designed to work in CI/CD environments:
- Headless browser mode
- Automatic dependency installation
- Proper cleanup and teardown
- Isolated test environments

## Future Enhancements

Potential improvements for the web UI tests:
1. Cross-browser testing (Firefox, Safari)
2. Visual regression testing
3. Performance testing
4. Mobile responsiveness testing
5. More comprehensive accessibility testing
6. Integration with real backend services

## Contributing

When adding new web UI tests:
1. Follow the existing test structure
2. Use descriptive test names
3. Include proper setup and teardown
4. Mock external dependencies
5. Add documentation for new test features 