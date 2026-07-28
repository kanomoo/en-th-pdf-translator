import re

with open('design/translator-pdf-prototype.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract CSS
style_match = re.search(r'<style>(.*?)</style>', content, re.DOTALL)
if style_match:
    css_content = style_match.group(1).strip()
    with open('static/style.css', 'w', encoding='utf-8') as f:
        f.write(css_content)

# Extract body for HTML
body_match = re.search(r'(<body.*?>.*?</body>)', content, re.DOTALL)
if body_match:
    body_content = body_match.group(1)
    
    # Remove script tag from body
    body_content = re.sub(r'<script>.*?</script>', '', body_content, flags=re.DOTALL)
    
    html_template = f'''<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PDF Translator</title>
  <link rel="stylesheet" href="{{{{ url_for('static', filename='style.css') }}}}">
</head>
{body_content}
<script src="{{{{ url_for('static', filename='app.js') }}}}"></script>
</html>'''
    
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(html_template)

# Extract JS
script_match = re.search(r'<script>(.*?)</script>', content, re.DOTALL)
if script_match:
    js_content = script_match.group(1).strip()
    with open('static/app.js', 'w', encoding='utf-8') as f:
        f.write(js_content)
