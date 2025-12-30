# Testing & Quality Assurance

## Overview

Comprehensive testing strategy for the AI Invoice Summarizer including unit tests, integration tests, performance tests, and production monitoring.

## Test Structure

```
tests/
├── unit/                    # Unit tests (isolated components)
├── integration/             # Integration tests (multiple services)
├── e2e/                    # End-to-end tests (full workflows)
├── performance/            # Load and stress tests
├── security/               # Security tests
└── fixtures/               # Test data and mocks
```

## Unit Tests

### Running Unit Tests

```bash
cd backend
pytest tests/unit/ -v
pytest tests/unit/ --cov=. --cov-report=html
```

### Coverage Requirements

- **Minimum**: 70% line coverage
- **Target**: 85% line coverage
- **Critical paths**: 100% coverage

### Example Unit Test

```python
# tests/unit/test_invoice_extraction.py
import pytest
from extraction_service.extractors import InvoiceExtractor

@pytest.fixture
def extractor():
    return InvoiceExtractor()

def test_extract_vendor_name(extractor):
    """Test vendor name extraction."""
    text = "Invoice from Acme Corporation"
    result = extractor.extract_vendor_name(text)
    assert result == "Acme Corporation"

def test_extract_vendor_name_edge_cases(extractor):
    """Test vendor extraction with edge cases."""
    test_cases = [
        ("", None),  # Empty text
        ("FROM: Company Inc", "Company Inc"),
        ("    Whitespace Corp    ", "Whitespace Corp"),
    ]
    
    for text, expected in test_cases:
        assert extractor.extract_vendor_name(text) == expected
```

## Integration Tests

### Running Integration Tests

```bash
cd backend
docker-compose up -d postgres redis
pytest tests/integration/ -v
docker-compose down
```

### Example Integration Test

```python
# tests/integration/test_invoice_workflow.py
import pytest
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_upload_and_extract(client, uploaded_file):
    """Test complete upload and extraction workflow."""
    # Upload invoice
    response = client.post(
        "/api/v1/upload",
        files={"file": uploaded_file}
    )
    assert response.status_code == 200
    document_id = response.json()["data"]["document_id"]
    
    # Verify extraction
    response = client.get(f"/api/v1/invoices/{document_id}")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "extracted"
```

## End-to-End Tests

### Running E2E Tests

```bash
# Start full stack
docker-compose up -d

# Run E2E tests
pytest tests/e2e/ -v --timeout=60

# Stop stack
docker-compose down
```

### Test Scenarios

1. **Happy Path**: Upload → Extract → Review → Approve → Pay
2. **Error Handling**: Invalid file → Rejection → Vendor notification
3. **Anomaly Detection**: Suspicious invoice → Escalation → Review
4. **Concurrent Operations**: Multiple users, invoices simultaneously
5. **Approval Workflows**: Different approval rules and escalations

## Performance Tests

### Load Testing with Locust

```bash
pip install locust

# Create load test
cat > tests/performance/locustfile.py << 'EOF'
from locust import HttpUser, task, between

class InvoiceUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def list_invoices(self):
        self.client.get("/api/v1/invoices?page=1")
    
    @task(1)
    def upload_invoice(self):
        with open("tests/fixtures/sample.pdf", "rb") as f:
            self.client.post(
                "/api/v1/upload",
                files={"file": f}
            )
EOF

# Run load test
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  -u 100 \
  -r 10 \
  --run-time 5m
```

### Expected Performance Targets

```
Operation                   | Target P50 | Target P95 | Target P99
----------------------------|-----------|-----------|----------
GET /invoices              | 50ms      | 100ms     | 200ms
POST /upload               | 200ms     | 500ms     | 1000ms
GET /invoices/{id}         | 50ms      | 100ms     | 200ms
POST /approve              | 100ms     | 200ms     | 500ms
```

## Security Testing

### OWASP Top 10 Tests

```bash
# SQL Injection
curl "http://localhost:8000/api/v1/invoices?vendor='; DROP TABLE invoices;--"

# XSS
curl -X POST http://localhost:8000/api/v1/upload \
  -F "vendor_name=<script>alert('xss')</script>"

# CSRF - Token validation
curl -X POST http://localhost:8000/api/v1/invoices/123/approve \
  -H "Origin: http://evil.com"
```

### Security Scanning

```bash
# Install security scanners
pip install bandit safety

# Check for security issues
bandit -r backend/

# Check dependencies
safety check
```

## Data Quality Validation

### OCR Quality Metrics

```python
# tests/integration/test_ocr_quality.py
def test_ocr_confidence_scores():
    """Verify OCR produces valid confidence scores."""
    ocr_result = extract_text("path/to/invoice.pdf")
    
    # Overall confidence should be 0-1
    assert 0 <= ocr_result.overall_confidence <= 1
    
    # Per-region confidence should be valid
    for region in ocr_result.regions:
        assert 0 <= region.confidence <= 1
        assert len(region.text) > 0
```

### Extraction Accuracy

```python
def test_extraction_accuracy():
    """Compare extracted values against ground truth."""
    test_invoices = [
        {
            "file": "tests/fixtures/inv_001.pdf",
            "expected": {
                "vendor": "Acme Corporation",
                "invoice_number": "INV-2024-001",
                "total_amount": 5000.00,
            }
        }
    ]
    
    for test in test_invoices:
        result = extract_invoice(test["file"])
        assert result.vendor == test["expected"]["vendor"]
        assert result.total_amount == test["expected"]["total_amount"]
```

## Regression Tests

Ensure new changes don't break existing functionality:

```bash
# Run regression test suite
pytest tests/regression/ -v

# Compare against baseline
pytest tests/regression/ --html=report.html
```

## Continuous Integration

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/psf/black
    rev: 23.11.0
    hooks:
      - id: black
  
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix]
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
EOF

# Install hooks
pre-commit install
```

### Automated Testing Pipeline

GitHub Actions (.github/workflows/tests.yml):

```yaml
name: Tests
on: [push, pull_request]

jobs:
  tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - run: pip install -r requirements.txt pytest pytest-cov
      - run: pytest tests/ --cov=. --cov-report=xml
      - uses: codecov/codecov-action@v3
```

## Test Data Management

### Fixture Files

```python
# tests/fixtures/invoices.py
@pytest.fixture
def sample_invoice_pdf():
    """Load sample invoice PDF."""
    with open("tests/fixtures/sample_invoice.pdf", "rb") as f:
        return f.read()

@pytest.fixture
def sample_ocr_result():
    """Create mock OCR result."""
    return OCRResult(
        raw_text="ACME Corporation Invoice INV-001...",
        regions=[...],
        overall_confidence=0.92
    )
```

## Monitoring & Observability

### Production Health Checks

```python
# tests/production/health_checks.py
import httpx

async def check_api_health():
    """Verify API is responsive."""
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.invoicesummarizer.com/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

async def check_database_connectivity():
    """Verify database is accessible."""
    # Implementation specific to your monitoring service
    pass

async def check_cache_performance():
    """Verify Redis cache is responsive."""
    # Implementation
    pass
```

## Automated Testing Schedule

```
Every commit:    - Unit tests, linting, type checking
Every push:      - Integration tests, security scans
Daily:           - Full E2E test suite, performance tests
Weekly:          - Load tests, compliance checks
Monthly:         - Penetration testing, disaster recovery drills
```

## Test Reporting

### Coverage Report

```bash
pytest tests/ --cov=. --cov-report=html --cov-report=term-missing
open htmlcov/index.html
```

### Metrics Dashboard

```
Test Coverage: 85%
├── Unit: 90%
├── Integration: 80%
└── E2E: 75%

Test Execution Time: 12 minutes
├── Unit: 2 min
├── Integration: 5 min
└── E2E: 5 min

Failed Tests: 0
Flaky Tests: 0
```

## Known Issues & Workarounds

### Tesseract OCR on Mac M1

```bash
brew install tesseract --HEAD
export TESSDATA_PREFIX=/usr/local/Cellar/tesseract-ocr/5.x.x/share/tessdata
```

### Database Lock Timeouts in Tests

```python
@pytest.fixture
def db_session():
    # Use shorter timeout for testing
    os.environ["DATABASE_STATEMENT_TIMEOUT"] = "10000"
    yield
    os.environ["DATABASE_STATEMENT_TIMEOUT"] = "30000"
```

## References

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/advanced/testing-databases/)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
- [Performance Testing Guide](https://performance.dev/)
