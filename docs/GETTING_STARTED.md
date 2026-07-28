# Getting Started with PDF Translator

## วิธีที่ง่ายที่สุด — 1-Click Double Click

### Windows
1. ดับเบิลคลิกไฟล์ **`run.bat`** (หรือ `setup.bat`)
2. ระบบจะรัน Python และเปิดเบราว์เซอร์ไปที่ **http://localhost:5000** ให้อัตโนมัติทันที

---

## วิธีติดตั้งเอง (Manual Setup)

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
   # Windows:
   python -m venv .venv
   .venv\Scripts\activate

   # Linux/macOS:
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python app.py
   ```

5. **Open in browser:**
   - Visit: http://localhost:5000
