# Getting Started with PDF Translator

## For First-Time Users

Welcome to the PDF Translator project! This guide will help you get started quickly.

### Prerequisites

- Python 3.8 or later
- Git

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/kanomoo/translate-pdf.git
   cd translate-pdf
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Thai fonts (Linux only):**
   ```bash
   sudo apt-get install fonts-noto-cjk fonts-noto-cjk-extra
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```

6. **Open in browser:**
   - Visit: http://localhost:5000

### Basic Usage

1. Click the upload area to select a PDF file
2. The app will automatically translate and process it
3. Watch the real-time progress updates
4. Click "Download" when complete

## For Developers

### Project Structure

- `app.py` — Main Flask application with all endpoints
- `translate_pdf.py` — Standalone translation script
- `templates/index.html` — Web interface
- `static/` — CSS and JavaScript files
- `uploads/`, `output/`, `cache/` — Temporary storage

### Key Features

- **Real-time progress** via Server-Sent Events
- **Translation caching** for performance
- **Parallel batch processing** for speed
- **Smart Thai detection** to skip already-translated text
- **Cross-platform font support** for Thai rendering

### Running Tests

```bash
# Run basic import test
python -c "import flask; import fitz; print('✓ OK')"

# Run with flake8
pip install flake8
flake8 app.py
```

### Common Development Tasks

**Change the port:**
```python
# In app.py, bottom of file:
app.run(debug=True, port=8000)
```

**Adjust file size limit:**
```python
# In app.py, around line 40:
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB
```

**Modify translation language:**
Search for `tl=th` in `app.py` and change `th` to your language code:
- `tl=es` for Spanish
- `tl=de` for German
- etc.

## Troubleshooting

### Port already in use
```bash
lsof -i :5000  # Find process
kill -9 <PID>  # Kill it
```

### Thai fonts not found
```bash
# Ubuntu/Debian
sudo apt-get install fonts-noto-cjk fonts-noto-cjk-extra

# Fedora
sudo dnf install google-noto-sans-thai-fonts

# macOS
brew install font-noto-sans-thai
```

### Translation not working
1. Check internet connection (uses Google Translate API)
2. Try a smaller PDF file first
3. Check browser console for errors (F12)

## Next Steps

- Read the [README.md](../README.md) for full documentation
- Check out [CONTRIBUTING.md](CONTRIBUTING.md) if you want to contribute
- Visit the [GitHub Issues](https://github.com/kanomoo/translate-pdf/issues) page for known issues

## Questions?

- Check the README troubleshooting section
- Open a GitHub issue
- Create a discussion on GitHub
