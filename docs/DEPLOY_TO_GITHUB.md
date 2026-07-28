# GitHub & Cloud Deployment Guide

This guide explains how to deploy the PDF Translator project to GitHub and Cloud hosting services (Render / Hugging Face).

## 📋 Pre-Deployment Checklist

- ✅ Project files organized in clean directory structure
- ✅ README.md with complete documentation
- ✅ requirements.txt with all dependencies
- ✅ Dockerfile for Cloud deployment
- ✅ LICENSE file (MIT)

## 🚀 Deployment Steps to Render (Free Cloud Hosting)

1. **Push changes to GitHub:**
   ```bash
   git add .
   git commit -m "Organize project structure and add deployment files"
   git push origin main
   ```

2. **Deploy on Render:**
   - Log in at [render.com](https://render.com) using GitHub.
   - Click **New +** → **Web Service**.
   - Select repository `kanomoo/translate-pdf`.
   - Runtime: **Docker**.
   - Instance Type: **Free ($0/month)**.
   - Click **Deploy Web Service**.
