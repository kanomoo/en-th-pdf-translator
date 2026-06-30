/**
 * PDF Translator — Frontend Logic
 * Handles file upload, SSE progress streaming, preview, and download.
 */

(function () {
    'use strict';

    // ---- DOM Elements ----
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const browseBtn = document.getElementById('browse-btn');

    const uploadSection = document.getElementById('upload-section');
    const fileInfoSection = document.getElementById('file-info-section');
    const progressSection = document.getElementById('progress-section');
    const completeSection = document.getElementById('complete-section');
    const errorSection = document.getElementById('error-section');

    const appSidebar = document.getElementById('app-sidebar');
    const sidebarToggleBtn = document.getElementById('sidebar-toggle-btn');
    const sidebarCloseBtn = document.getElementById('sidebar-close-btn');
    const newTranslationBtn = document.getElementById('new-translation-btn');
    const historyList = document.getElementById('history-list');
    const refreshHistoryBtn = document.getElementById('refresh-history-btn');

    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');
    const filePages = document.getElementById('file-pages');
    const removeFileBtn = document.getElementById('remove-file-btn');
    const translateBtn = document.getElementById('translate-btn');

    const progressStage = document.getElementById('progress-stage');
    const progressDetail = document.getElementById('progress-detail');
    const progressFill = document.getElementById('progress-fill');
    const progressPercent = document.getElementById('progress-percent');

    const completeDetail = document.getElementById('complete-detail');
    const downloadBtn = document.getElementById('download-btn');
    const newFileBtn = document.getElementById('new-file-btn');

    const previewSection = document.getElementById('preview-section');
    const previewImg = document.getElementById('preview-img');
    const pageIndicator = document.getElementById('page-indicator');
    const prevPageBtn = document.getElementById('prev-page-btn');
    const nextPageBtn = document.getElementById('next-page-btn');

    const errorMessage = document.getElementById('error-message');
    const retryBtn = document.getElementById('retry-btn');

    // ---- State ----
    let selectedFile = null;
    let currentJobId = null;
    let totalPages = 0;
    let currentPreviewPage = 0;
    let eventSource = null;

    // ---- Helpers ----
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function showSection(section) {
        [uploadSection, fileInfoSection, progressSection, completeSection, errorSection]
            .forEach(s => {
                if (s === section) {
                    s.classList.remove('hidden');
                    s.style.animation = 'none';
                    // Force reflow
                    void s.offsetHeight;
                    s.style.animation = '';
                } else {
                    s.classList.add('hidden');
                }
            });
    }

    function setStageActive(stageName) {
        const stages = ['extracting', 'translating', 'building'];
        const stageItems = document.querySelectorAll('.stage-item');
        const connectors = document.querySelectorAll('.stage-connector');

        const activeIndex = stages.indexOf(stageName);
        stageItems.forEach((item, i) => {
            item.classList.remove('active', 'done');
            if (i < activeIndex) item.classList.add('done');
            else if (i === activeIndex) item.classList.add('active');
        });
        connectors.forEach((conn, i) => {
            conn.classList.toggle('done', i < activeIndex);
        });
    }

    // ---- Sidebar Toggle (Mobile) ----
    if (sidebarToggleBtn) {
        sidebarToggleBtn.addEventListener('click', () => {
            appSidebar.classList.toggle('open');
        });
    }

    if (sidebarCloseBtn) {
        sidebarCloseBtn.addEventListener('click', () => {
            appSidebar.classList.remove('open');
        });
    }

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', (e) => {
        if (appSidebar && appSidebar.classList.contains('open') && 
            !appSidebar.contains(e.target) && 
            !sidebarToggleBtn.contains(e.target)) {
            appSidebar.classList.remove('open');
        }
    });

    // ---- New Translation ----
    if (newTranslationBtn) {
        newTranslationBtn.addEventListener('click', () => {
            currentJobId = null;
            selectedFile = null;
            fileInput.value = '';
            totalPages = 0;
            currentPreviewPage = 0;
            previewSection.classList.add('hidden');
            
            // clear active state from history items
            document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
            
            showSection(uploadSection);
            if (window.innerWidth <= 860) {
                appSidebar.classList.remove('open');
            }
        });
    }

    // ---- Drag & Drop ----
    ['dragenter', 'dragover'].forEach(event => {
        dropZone.addEventListener(event, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(event => {
        dropZone.addEventListener(event, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drag-over');
        });
    });

    dropZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) handleFileSelect(files[0]);
    });

    dropZone.addEventListener('click', (e) => {
        if (e.target.closest('#browse-btn') || e.target === dropZone || e.target.closest('.drop-zone-content')) {
            fileInput.click();
        }
    });

    browseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) handleFileSelect(fileInput.files[0]);
    });

    // ---- File Selection ----
    function handleFileSelect(file) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            showError('กรุณาเลือกไฟล์ PDF เท่านั้น');
            return;
        }
        if (file.size > 100 * 1024 * 1024) {
            showError('ไฟล์ใหญ่เกินไป (สูงสุด 100 MB)');
            return;
        }

        selectedFile = file;
        fileName.textContent = file.name;
        fileSize.textContent = formatFileSize(file.size);
        filePages.textContent = 'กำลังอ่าน...';

        showSection(fileInfoSection);
    }

    removeFileBtn.addEventListener('click', () => {
        selectedFile = null;
        fileInput.value = '';
        showSection(uploadSection);
    });

    // ---- Translation ----
    translateBtn.addEventListener('click', () => {
        if (!selectedFile) return;
        uploadAndTranslate(selectedFile);
    });

    async function uploadAndTranslate(file) {
        showSection(progressSection);
        progressFill.style.width = '0%';
        progressPercent.textContent = '0%';
        progressStage.textContent = 'กำลังอัปโหลด...';
        progressDetail.textContent = 'กำลังส่งไฟล์ไปยังเซิร์ฟเวอร์';
        setStageActive('');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                showError(data.error || 'เกิดข้อผิดพลาดในการอัปโหลด');
                return;
            }

            currentJobId = data.job_id;
            totalPages = data.pages || 0;
            filePages.textContent = totalPages + ' หน้า';

            // Connect to SSE progress
            connectProgress(data.job_id);

        } catch (err) {
            showError('ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์: ' + err.message);
        }
    }

    function connectProgress(jobId) {
        if (eventSource) {
            eventSource.close();
        }

        eventSource = new EventSource('/progress/' + jobId);

        eventSource.addEventListener('stage', (e) => {
            const data = JSON.parse(e.data);
            progressStage.textContent = data.message || data.stage;
            setStageActive(data.stage);

            if (data.stage === 'extracting') {
                progressDetail.textContent = 'กำลังอ่านข้อความจากไฟล์ PDF';
            } else if (data.stage === 'translating') {
                progressDetail.textContent = 'กำลังแปลข้อความเป็นภาษาไทย';
            } else if (data.stage === 'building') {
                progressDetail.textContent = 'กำลังสร้างไฟล์ PDF ใหม่';
            }
        });

        eventSource.addEventListener('info', (e) => {
            const data = JSON.parse(e.data);
            if (data.pages) {
                totalPages = data.pages;
                filePages.textContent = totalPages + ' หน้า';
            }
        });

        eventSource.addEventListener('progress', (e) => {
            const data = JSON.parse(e.data);
            let pct = data.percent || 0;

            // Map sub-step percentages to overall progress
            if (data.step === 'translate') {
                pct = Math.round(pct * 0.6);  // Translation is 0-60%
            } else if (data.step === 'build_redact') {
                pct = 60 + Math.round(pct * 0.2);  // Redaction is 60-80%
            } else if (data.step === 'build_insert') {
                pct = 80 + Math.round(pct * 0.2);  // Insertion is 80-100%
            }

            progressFill.style.width = pct + '%';
            progressPercent.textContent = pct + '%';

            if (data.step === 'translate') {
                progressDetail.textContent = `แปลแล้ว ${data.current}/${data.total} ชุด`;
            } else if (data.step === 'build_redact') {
                progressDetail.textContent = `ลบข้อความเดิม หน้า ${data.current}/${data.total}`;
            } else if (data.step === 'build_insert') {
                progressDetail.textContent = `แทรกข้อความไทย ${data.current}/${data.total}`;
            }
        });

        eventSource.addEventListener('complete', (e) => {
            const data = JSON.parse(e.data);
            eventSource.close();
            eventSource = null;

            totalPages = data.pages || totalPages;
            currentPreviewPage = 0;

            completeDetail.textContent = `แปลสำเร็จ ${totalPages} หน้า`;
            if (data.shrunk > 0 || data.clipped > 0) {
                completeDetail.textContent += ` (ปรับขนาด ${data.shrunk}, ตัดข้อความ ${data.clipped})`;
            }

            const dlName = data.filename || 'translated.pdf';
            downloadBtn.href = '/download/' + currentJobId + '/' + encodeURIComponent(dlName);
            downloadBtn.target = '_blank';

            showSection(completeSection);

            // Show preview
            if (totalPages > 0) {
                previewSection.classList.remove('hidden');
                loadPreview(0);
                updatePageIndicator();
            }
        });

        eventSource.addEventListener('error', (e) => {
            let msg = 'เกิดข้อผิดพลาดในระหว่างการแปล';
            try {
                const data = JSON.parse(e.data);
                msg = data.message || msg;
            } catch (_) {}
            eventSource.close();
            eventSource = null;
            showError(msg);
        });

        eventSource.onerror = () => {
            // SSE connection lost
            if (eventSource) {
                eventSource.close();
                eventSource = null;
                showError('การเชื่อมต่อกับเซิร์ฟเวอร์ขาดหาย');
            }
        };
    }

    // ---- Preview ----
    function loadPreview(page = 0) {
        if (!currentJobId || totalPages === 0) return;
        
        const container = document.getElementById('preview-scroll-container');
        const dropdown = document.getElementById('page-dropdown');
        
        if (container.children.length === 0) {
            container.innerHTML = '';
            dropdown.innerHTML = '';
            
            for (let i = 0; i < totalPages; i++) {
                const opt = document.createElement('option');
                opt.value = i;
                opt.textContent = `หน้า ${i + 1} / ${totalPages}`;
                dropdown.appendChild(opt);
                
                const imgContainer = document.createElement('div');
                imgContainer.className = 'preview-img-wrapper';
                imgContainer.id = `preview-page-${i}`;
                
                const img = document.createElement('img');
                img.src = '/preview/' + currentJobId + '/' + i + '?t=' + Date.now();
                img.className = 'preview-img';
                img.loading = 'lazy';
                img.alt = `หน้า ${i + 1}`;
                
                imgContainer.appendChild(img);
                container.appendChild(imgContainer);
            }
            
            const frame = document.getElementById('preview-frame');
            frame.addEventListener('scroll', () => {
                let activePage = currentPreviewPage;
                const wrappers = document.querySelectorAll('.preview-img-wrapper');
                const frameRect = frame.getBoundingClientRect();
                const center = frameRect.top + frameRect.height / 2;
                
                wrappers.forEach(w => {
                    const rect = w.getBoundingClientRect();
                    if (rect.top <= center && rect.bottom >= center) {
                        activePage = parseInt(w.id.replace('preview-page-', ''));
                    }
                });
                
                if (currentPreviewPage !== activePage) {
                    currentPreviewPage = activePage;
                    updatePageIndicator();
                }
            });
            
            dropdown.addEventListener('change', (e) => {
                const targetPage = parseInt(e.target.value);
                const targetEl = document.getElementById(`preview-page-${targetPage}`);
                if (targetEl) targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        }
        
        const targetEl = document.getElementById(`preview-page-${page}`);
        if (targetEl) targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        
        currentPreviewPage = page;
        updatePageIndicator();
    }

    function updatePageIndicator() {
        document.getElementById('current-page').textContent = currentPreviewPage + 1;
        document.getElementById('total-pages').textContent = totalPages;
        document.getElementById('page-dropdown').value = currentPreviewPage;
        prevPageBtn.disabled = currentPreviewPage <= 0;
        nextPageBtn.disabled = currentPreviewPage >= totalPages - 1;
    }

    prevPageBtn.addEventListener('click', () => {
        if (currentPreviewPage > 0) loadPreview(currentPreviewPage - 1);
    });

    nextPageBtn.addEventListener('click', () => {
        if (currentPreviewPage < totalPages - 1) loadPreview(currentPreviewPage + 1);
    });

    // ---- Error Handling ----
    function showError(message) {
        errorMessage.textContent = message;
        showSection(errorSection);
    }

    retryBtn.addEventListener('click', () => {
        showSection(uploadSection);
        selectedFile = null;
        fileInput.value = '';
    });

    // ---- New File ----
    newFileBtn.addEventListener('click', () => {
        currentJobId = null;
        selectedFile = null;
        fileInput.value = '';
        totalPages = 0;
        currentPreviewPage = 0;
        previewSection.classList.add('hidden');
        showSection(uploadSection);
    });

    // ---- History ----
    async function loadHistory() {
        historyList.innerHTML = '<div class="history-loading">กำลังโหลด...</div>';
        try {
            const response = await fetch('/history');
            const data = await response.json();
            
            if (!data.history || data.history.length === 0) {
                historyList.innerHTML = '<div class="history-empty">ไม่มีประวัติการแปล</div>';
                return;
            }
            
            historyList.innerHTML = '';
            data.history.forEach(item => {
                const li = document.createElement('li');
                li.className = 'history-item';
                
                const date = new Date(item.created_at * 1000).toLocaleString('th-TH');
                
                li.innerHTML = `
                    <div class="history-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                            <line x1="16" y1="13" x2="8" y2="13"></line>
                            <line x1="16" y1="17" x2="8" y2="17"></line>
                            <polyline points="10 9 9 9 8 9"></polyline>
                        </svg>
                    </div>
                    <div class="history-details">
                        <div class="history-filename">${item.filename || item.job_id}</div>
                        <div class="history-meta">
                            <span>${date}</span>
                            <span>${item.pages || '?'} หน้า</span>
                        </div>
                    </div>
                `;
                
                li.addEventListener('click', () => {
                    openHistoryItem(item);
                    document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
                    li.classList.add('active');
                });
                
                historyList.appendChild(li);
            });
            
        } catch (err) {
            historyList.innerHTML = '<div class="history-empty" style="color:var(--error)">เกิดข้อผิดพลาดในการโหลดข้อมูล</div>';
        }
    }

    function openHistoryItem(item) {
        currentJobId = item.job_id;
        totalPages = item.pages || 0;
        eventSource = null; // Ensure we don't have dangling connections
        
        completeDetail.textContent = `เปิดจากประวัติการแปล (${totalPages} หน้า)`;
        
        const dlName = item.filename ? item.filename.replace(/\.pdf$/i, '') + '_TH.pdf' : 'translated.pdf';
        downloadBtn.href = '/download/' + currentJobId + '/' + encodeURIComponent(dlName);
        downloadBtn.target = '_blank';
        
        showSection(completeSection);
        
        const container = document.getElementById('preview-scroll-container');
        if (container) container.innerHTML = ''; // reset preview
        
        if (totalPages > 0) {
            previewSection.classList.remove('hidden');
            loadPreview(0);
        } else {
            previewSection.classList.add('hidden');
        }
        
        if (window.innerWidth <= 860) {
            appSidebar.classList.remove('open');
        }
    }
    
    if (refreshHistoryBtn) {
        refreshHistoryBtn.addEventListener('click', () => {
            loadHistory();
        });
    }

    // Load history on initial load
    loadHistory();

})();
