# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2024-06-30

### Added

- Initial release of PDF Translator
- Web-based interface for uploading and translating PDFs
- English to Thai translation using Google Translate API
- Real-time progress tracking via Server-Sent Events (SSE)
- Smart Thai text detection to skip already-translated content
- Translation caching for improved performance
- Parallel batch processing for faster translation
- Cross-platform Thai font support
- Beautiful, responsive UI with animated backgrounds
- PDF preview functionality
- Support for up to 100MB file uploads
- Automatic font detection for Linux, Windows, and macOS
- Bullet character substitution and text cleaning
- Comprehensive error handling and user feedback

### Features

- 🌐 Automatic English → Thai Translation
- 📄 Smart PDF Processing with format preservation
- 🚀 Real-time progress updates
- 🎨 Beautiful, responsive web interface
- 🔤 Cross-platform Thai font support
- 💾 Translation caching
- ✅ Intelligent Thai text detection
- 📱 Mobile responsive design
- ⚡ Parallel processing for speed

### Technical Details

- **Backend:** Flask 3.1+
- **PDF Processing:** PyMuPDF 1.28+
- **Translation:** Google Translate API (free tier)
- **Frontend:** HTML5, CSS3, JavaScript (vanilla)
- **Platform Support:** Linux, Windows, macOS
- **Python:** 3.8+

## Future Roadmap

### Planned Features

- [ ] Support for other language pairs (Thai to English, Thai to other languages)
- [ ] Batch processing API for multiple PDFs
- [ ] Docker containerization
- [ ] Cloud deployment templates (AWS, Google Cloud, Azure)
- [ ] Desktop GUI application
- [ ] Custom translation engine support (OpenAI, DeepL)
- [ ] PDF annotation and bookmark preservation
- [ ] Automatic table of contents generation
- [ ] Advanced text formatting preservation
- [ ] User authentication and history
- [ ] Job scheduling and queue management
- [ ] Email notification on completion

### Known Limitations

- Dependent on Google Translate API free tier (rate limiting may apply)
- Complex PDF layouts with special fonts may not render perfectly
- Very large PDFs (>500MB) may encounter memory issues
- No support for encrypted/password-protected PDFs

---

## How to View Changes

- See [commits](https://github.com/kanomoo/translate-pdf/commits/main) for detailed changes
- Check [pull requests](https://github.com/kanomoo/translate-pdf/pulls) for feature discussions
- Read [issues](https://github.com/kanomoo/translate-pdf/issues) for known problems

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute to this project.
