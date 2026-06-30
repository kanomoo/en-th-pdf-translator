# Contributing to PDF Translator

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## 🎯 How to Contribute

### 1. Fork and Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR_USERNAME/translate-pdf.git
cd translate-pdf
```

### 2. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or for bug fixes:
git checkout -b fix/your-bug-fix-name
```

### 3. Make Your Changes

- Keep commits atomic and well-documented
- Follow PEP 8 for Python code style
- Update tests if needed

### 4. Test Your Changes

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Test imports
python -c "import flask; import fitz; print('✓ OK')"
```

### 5. Commit and Push

```bash
git add .
git commit -m "feat: add your feature description"
git push origin feature/your-feature-name
```

### 6. Create a Pull Request

- Go to GitHub and create a pull request
- Provide a clear title and description
- Link related issues if applicable

## 📝 Commit Message Guidelines

Use conventional commits for clarity:

```
feat: add new feature
fix: fix a bug
docs: update documentation
style: fix code style
refactor: refactor code
test: add or update tests
chore: update dependencies
```

Example:
```
feat: add support for PDF bookmarks translation
```

## 🐛 Reporting Bugs

When reporting bugs, please include:

1. **Description** — What went wrong?
2. **Steps to Reproduce** — How to replicate the issue?
3. **Expected Behavior** — What should happen?
4. **Actual Behavior** — What actually happened?
5. **Environment** — OS, Python version, etc.
6. **Attachments** — Error logs, screenshots, PDF samples (if possible)

Example:
```markdown
**Description:** Thai text appears garbled in output PDF

**Steps to Reproduce:**
1. Upload English PDF
2. Wait for translation to complete
3. Download translated PDF
4. Open in Adobe Reader

**Expected:** Thai text displays correctly
**Actual:** Thai text shows as squares/boxes

**Environment:** Ubuntu 22.04, Python 3.10
```

## 💡 Feature Requests

When suggesting features, please:

1. **Describe the feature** — What would you like to add?
2. **Explain the use case** — Why is this useful?
3. **Provide examples** — Show how it would work
4. **Consider impact** — Performance, complexity, etc.

Example:
```markdown
**Feature:** Support for batch processing multiple PDFs

**Use Case:** Users want to translate multiple documents at once

**Example:**
- Upload folder with 10 PDFs
- System translates all in parallel
- Download as ZIP with all translated files

**Benefits:** Save time, better workflow
```

## 🎨 Code Style

### Python

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use 4 spaces for indentation
- Line length: 80-100 characters
- Use descriptive variable names

Example:
```python
def extract_text_from_pdf(pdf_path):
    """Extract text content from a PDF file.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        List of text blocks with metadata
    """
    doc = fitz.open(str(pdf_path))
    items = []
    for page_number, page in enumerate(doc):
        # Extract text
        pass
    return items
```

### JavaScript

- Use clear variable names
- Add comments for complex logic
- Use const/let instead of var
- Include JSDoc comments for functions

### HTML/CSS

- Use semantic HTML5 elements
- Follow BEM naming for CSS classes
- Keep styles organized and documented

## 🧪 Testing

### Running Tests

```bash
# Test imports
python -c "import flask; import fitz"

# Lint code
pip install flake8
flake8 app.py
```

### Adding Tests

Create test file `tests/test_app.py`:

```python
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index_page(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'PDF Translator' in response.data
```

Run with: `pytest tests/`

## 📚 Documentation

When adding features, update relevant documentation:

- `README.md` — For user-facing features
- `GETTING_STARTED.md` — For setup instructions
- Code comments — For implementation details
- Docstrings — For functions and classes

Example docstring:
```python
def translate_batch(batch):
    """Translate a batch of text items to Thai.
    
    Groups text with markers, sends to Google Translate API,
    and parses translated results.
    
    Args:
        batch: List of (index, text) tuples
        
    Returns:
        Dict mapping original text to Thai translation
        
    Raises:
        RuntimeError: If translation parsing fails
    """
```

## 🚀 Release Process

1. Update version in relevant files
2. Update CHANGELOG.md
3. Create GitHub release with notes
4. Tag release: `git tag v1.0.0`

## 📋 Development Checklist

Before submitting a PR, ensure:

- [ ] Code follows project style
- [ ] All tests pass
- [ ] Documentation is updated
- [ ] Commit messages are clear
- [ ] No unnecessary dependencies added
- [ ] Code is tested locally
- [ ] PR description is detailed

## 🤝 Code Review Process

1. **Submission** — Create PR with description
2. **Review** — Team reviews and provides feedback
3. **Revision** — Make requested changes
4. **Approval** — PR gets approved
5. **Merge** — Merge to main branch

## 💬 Communication

- **Issues** — For bugs and features
- **Discussions** — For questions
- **Pull Requests** — For code changes
- **Email** — For private discussions

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🙏 Thank You

Thank you for contributing to make PDF Translator better!

---

**Happy Contributing! 🎉**
