# PDF Translator — แปล PDF เป็นภาษาไทย

A modern, web-based PDF translator that converts English PDFs to Thai with high-quality formatting and beautiful UI. Built with Flask, PyMuPDF, and Google Translate API.

![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.8+-blue)

## ✨ Features

- 🌐 **Automatic English → Thai Translation** — Uses Google Translate API for accurate translations
- 📄 **Smart PDF Processing** — Preserves original formatting, fonts, and layouts
- 🚀 **Real-time Progress** — Live translation progress updates via Server-Sent Events (SSE)
- 🎨 **Beautiful Web Interface** — Modern, responsive UI with animated background
- 🔤 **Thai Font Support** — Automatic cross-platform Thai font detection (Noto Sans Thai, LeelawUI, etc.)
- 💾 **Translation Caching** — Intelligent caching to speed up repeated translations
- ✅ **Smart Text Detection** — Automatically skips text that's already in Thai
- 📱 **Mobile Responsive** — Works seamlessly on desktop and mobile devices
- ⚡ **Parallel Processing** — Multi-threaded batch translation for faster processing

## 📋 System Requirements

- **Python** 3.8 or higher
- **Thai Fonts** — For rendering Thai text (auto-detected):
  - Linux: Noto Sans Thai (`noto-fonts-extra`)
  - Windows: LeelawUI (usually pre-installed)
  - macOS: Thonburi (usually pre-installed)

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/kanomoo/translate-pdf.git
cd translate-pdf
```

### 2. Create Virtual Environment

```bash
# Create Python virtual environment
python3 -m venv .venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Thai Fonts (Linux only)

```bash
# Debian/Ubuntu
sudo apt-get install fonts-noto-cjk fonts-noto-cjk-extra fonts-noto-cjk-color-emoji

# Fedora
sudo dnf install google-noto-sans-thai-fonts
```

### 5. Run the Application

```bash
python app.py
```

The app will start at `http://localhost:5000`

## 🎯 Usage

1. **Open** http://localhost:5000 in your browser
2. **Select** an English PDF file
3. **Click** "Upload & Translate" to start translation
4. **Watch** the real-time progress in the progress bar
5. **Download** your translated Thai PDF when complete

## 📁 Project Structure

```
translate-pdf/
├── app.py                 # Flask web application
├── translate_pdf.py       # Standalone translation script
├── requirements.txt       # Python dependencies
├── .gitignore            # Git ignore rules
├── README.md             # This file
├── static/               # Frontend assets
│   ├── style.css         # Styling
│   └── app.js            # JavaScript
├── templates/            # HTML templates
│   └── index.html        # Main UI
├── uploads/              # Temporary upload storage
├── output/               # Translated PDF output
└── cache/                # Translation cache
```

## 🔧 Configuration

### File Size Limits

Edit the `MAX_CONTENT_LENGTH` in `app.py` to change the maximum upload size (default: 100 MB):

```python
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB
```

### Translation Batch Size

Adjust the batch size in `run_translation()` function (default: max 24 items or 3500 characters):

```python
if current and (len(current) >= 24 or current_chars + text_len > 3500):
    batches.append(current)
```

### Font Selection

Fonts are auto-detected for your platform. To manually specify fonts, edit `FONT_REG` and `FONT_BOLD` in `app.py`:

```python
FONT_REG = "/path/to/your/font.ttf"
FONT_BOLD = "/path/to/your/bold-font.ttf"
```

## 🌐 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main web interface |
| `/upload` | POST | Upload and start translation job |
| `/progress/<job_id>` | GET | SSE endpoint for real-time progress |
| `/download/<job_id>/<filename>` | GET | Download translated PDF |
| `/preview/<job_id>/<page>` | GET | Preview translated page as PNG |

## 📦 Dependencies

- **Flask 3.1+** — Web framework
- **PyMuPDF 1.28+** — PDF processing
- **urllib** — For Google Translate API calls (built-in)

See [requirements.txt](requirements.txt) for full dependency list.

## 🎨 Customization

### Change UI Colors

Edit `/static/style.css` to customize colors, fonts, and layout.

### Add Different Translation Languages

Modify the translation endpoint in `translate_payload()` function in `app.py`:

```python
url = (
    "https://translate.googleapis.com/translate_a/single"
    "?client=gtx&sl=auto&tl=th&dt=t&q="  # Change 'th' to desired language code
    + urllib.parse.quote(payload)
)
```

### Modify UI Text

Edit `/templates/index.html` to change interface text and styling.

## ⚠️ Important Notes

- **No API Key Required** — Uses free Google Translate API (community-supported)
- **Rate Limiting** — May encounter rate limiting on large batches; the app retries automatically
- **Font Availability** — If Thai fonts aren't found, the app will warn you and use system fallback
- **Cache Files** — Translation cache is stored locally in the `cache/` directory
- **Temporary Files** — Uploaded and translated files are stored in `uploads/` and `output/` directories

## 🐛 Troubleshooting

### Issue: "No Thai font found" warning

**Solution:** Install Thai fonts for your OS:
```bash
# Linux (Ubuntu/Debian)
sudo apt-get install fonts-noto-cjk fonts-noto-cjk-extra

# macOS
brew install font-noto-sans-thai

# Windows
# Download from: https://fonts.google.com/noto/specimen/Noto+Sans+Thai
```

### Issue: Translation fails with timeout error

**Solution:** The free Google Translate API has rate limits. Try:
1. Wait a few minutes and retry
2. Reduce PDF size or split it into smaller files
3. Reduce batch size in `run_translation()` function

### Issue: Thai text is garbled or missing

**Solution:** 
1. Ensure Thai fonts are installed
2. Check that `FONT_REG` and `FONT_BOLD` paths exist
3. Try regenerating the PDF with font embedding enabled

### Issue: Port 5000 already in use

**Solution:** Change the port in the `if __name__ == "__main__"` block:
```bash
python app.py --port 8000
```

Or modify `app.py`:
```python
if __name__ == "__main__":
    app.run(debug=True, port=8000)
```

## 📊 Performance Tips

- **Large PDFs** (>50 pages): May take 2-10 minutes depending on internet speed
- **Repeated Translations**: Use translation cache to speed up similar documents
- **Batch Processing**: The app automatically optimizes batch sizes for parallel processing
- **Memory Usage**: Each PDF processing may use 100-500MB of RAM

## 🔒 Security Considerations

- **File Validation** — Only PDF files are accepted
- **Size Limits** — Default 100MB maximum file size
- **Temporary Storage** — Files are kept in `uploads/` and `output/` directories
- **Cache Cleanup** — Periodically clean `cache/` directory for old entries

## 📝 Development

### Running in Debug Mode

```bash
# Set Flask to debug mode
export FLASK_ENV=development
export FLASK_DEBUG=1
python app.py
```

### Building PDF Output

The app uses PyMuPDF's HTML rendering engine:
```python
page.insert_htmlbox(rect, html, scale_low=0.30)
```

### Testing

Create a test file `test_app.py`:
```python
import pytest
from app import app

def test_index():
    with app.test_client() as client:
        response = client.get('/')
        assert response.status_code == 200
```

Run with: `pytest test_app.py`

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request with:
- Bug fixes
- Feature additions
- Documentation improvements
- Language support additions

## 💬 Support

If you encounter issues or have suggestions:
1. Check the [Troubleshooting](#-troubleshooting) section
2. Open an issue on GitHub
3. Feel free to reach out

## 🙏 Acknowledgments

- Google Translate API (free tier)
- PyMuPDF/fitz for PDF processing
- Flask for the web framework
- Noto Sans Thai font from Google Fonts

## 🗺️ Roadmap

- [ ] Support for other language pairs
- [ ] Batch job processing API
- [ ] Docker containerization
- [ ] AWS/Cloud deployment templates
- [ ] GUI application (desktop version)
- [ ] Custom translation engine support (OpenAI, DeepL, etc.)
- [ ] PDF annotation preservation
- [ ] Table of contents generation
- [ ] Advanced text formatting preservation

---

**Made with ❤️ for Thai language support**
