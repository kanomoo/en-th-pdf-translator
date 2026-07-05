/**
 * PDF Translator — Frontend Logic (Next.js B&W Theme)
 */

(function () {
    'use strict';

    // ---- DOM Elements ----
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    const uploadScreen = document.getElementById('upload-screen');
    const processingScreen = document.getElementById('processing-screen');
    const splitScreen = document.getElementById('split-screen');

    const sidebarPane = document.getElementById('sidebar-pane');
    const historyContainer = document.getElementById('history-group-container');

    const headerDocName = document.getElementById('header-doc-name');
    const downloadBtn = document.getElementById('download-btn');

    const progressStage = document.getElementById('progress-stage');
    const progressDetail = document.getElementById('progress-detail');
    const progressFill = document.getElementById('progress-bar');
    
    const step1 = document.getElementById('step-1');
    const step2 = document.getElementById('step-2');
    const step3 = document.getElementById('step-3');

    const previewScrollContainerEn = document.getElementById('preview-scroll-container-en');
    const previewScrollContainerTh = document.getElementById('preview-scroll-container-th');
    const reloadBtn = document.getElementById('reload-btn');

    // ---- State ----
    let currentJobId = null;
    let currentOrigFilename = null;
    let currentDlFilename = null;
    let totalPages = 0;
    let eventSource = null;

    // ---- Helpers ----
    window.showToast = function(msg) {
        const toast = document.getElementById('toast-notif');
        document.getElementById('toast-message').textContent = msg;
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, 2200);
    };

    function setStep(stepNum, status) {
        const el = document.getElementById('step-' + stepNum);
        if (!el) return;
        el.className = 'step-item ' + status;
        const dot = el.querySelector('.step-dot');
        dot.innerHTML = status === 'completed' ? '✓' : '';
    }

    // ---- Sidebar Toggle ----
    window.toggleSidebar = function() {
        sidebarPane.classList.toggle('collapsed');
        showToast(sidebarPane.classList.contains('collapsed') ? 'Sidebar hidden' : 'Sidebar visible');
    };

    window.resetToUpload = function() {
        currentJobId = null;
        totalPages = 0;
        fileInput.value = '';
        if(eventSource) {
            eventSource.close();
            eventSource = null;
        }

        splitScreen.style.display = 'none';
        processingScreen.style.display = 'none';
        uploadScreen.style.display = 'flex';
        headerDocName.textContent = 'No Document Loaded';
        downloadBtn.style.display = 'none';
        if (reloadBtn) reloadBtn.style.display = 'none';
        
        document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
    };

    // Initialize UI
    resetToUpload();

    // ---- Drag & Drop ----
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        });
    });

    dropZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) handleFileSelect(files[0]);
    });

    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) handleFileSelect(fileInput.files[0]);
    });

    function handleFileSelect(file) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            showToast('กรุณาเลือกไฟล์ PDF เท่านั้น');
            return;
        }
        if (file.size > 100 * 1024 * 1024) {
            showToast('ไฟล์ใหญ่เกินไป (สูงสุด 100 MB)');
            return;
        }
        uploadAndTranslate(file);
    }

    // ---- Translation Flow ----
    async function uploadAndTranslate(file) {
        uploadScreen.style.display = 'none';
        splitScreen.style.display = 'none';
        processingScreen.style.display = 'flex';
        downloadBtn.style.display = 'none';
        headerDocName.textContent = file.name;

        progressFill.style.width = '5%';
        progressStage.textContent = 'กำลังอัปโหลด...';
        progressDetail.textContent = 'กำลังส่งไฟล์ไปยังเซิร์ฟเวอร์';
        
        setStep(1, 'active');
        setStep(2, '');
        setStep(3, '');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                showToast(data.error || 'เกิดข้อผิดพลาดในการอัปโหลด');
                resetToUpload();
                return;
            }

            currentJobId = data.job_id;
            totalPages = data.pages || 0;
            
            // Connect to SSE progress
            connectProgress(data.job_id, file.name);

        } catch (err) {
            showToast('ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์');
            resetToUpload();
        }
    }

    function connectProgress(jobId, filename) {
        if (eventSource) eventSource.close();

        eventSource = new EventSource('/progress/' + jobId);

        eventSource.addEventListener('stage', (e) => {
            const data = JSON.parse(e.data);
            progressStage.textContent = data.message || data.stage;

            if (data.stage === 'extracting') {
                setStep(1, 'active');
            } else if (data.stage === 'translating') {
                setStep(1, 'completed');
                setStep(2, 'active');
            } else if (data.stage === 'building') {
                setStep(2, 'completed');
                setStep(3, 'active');
            }
        });

        eventSource.addEventListener('info', (e) => {
            const data = JSON.parse(e.data);
            if (data.pages) totalPages = data.pages;
        });

        eventSource.addEventListener('progress', (e) => {
            const data = JSON.parse(e.data);
            let pct = data.percent || 0;

            // Map backend percent (0-100% total)
            progressFill.style.width = pct + '%';

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
            setStep(3, 'completed');
            progressFill.style.width = '100%';
            progressStage.textContent = data.message;
            progressDetail.textContent = `แปลสำเร็จ ${totalPages} หน้า`;

            setTimeout(() => {
                showWorkspace(jobId, filename, data.filename || 'translated.pdf');
                loadHistory(); // refresh history
            }, 800);
        });

        eventSource.addEventListener('error', (e) => {
            let msg = 'เกิดข้อผิดพลาดในระหว่างการแปล';
            try {
                const data = JSON.parse(e.data);
                msg = data.message || msg;
            } catch (_) {}
            eventSource.close();
            eventSource = null;
            showToast(msg);
            resetToUpload();
        });
    }

    // ---- Workspace View (PDF.js Rendering for text selection) ----
    let currentRenderSession = 0;

    async function renderPDF(url, container, sessionId) {
        try {
            const loadingTask = pdfjsLib.getDocument(url);
            const pdf = await loadingTask.promise;
            
            // Calculate scale based on container width (accounting for padding)
            let containerWidth = container.clientWidth - 64; // 32px padding on left/right
            if (containerWidth <= 0) {
                // Fallback if clientWidth is 0 (e.g., container not fully visible yet)
                const rect = container.getBoundingClientRect();
                containerWidth = (rect.width || 600) - 64;
                if (containerWidth <= 0) containerWidth = 600;
            }

            for (let i = 1; i <= pdf.numPages; i++) {
                if (currentRenderSession !== sessionId) {
                    loadingTask.destroy();
                    return;
                }
                const page = await pdf.getPage(i);
                
                // Get unscaled viewport to calculate ratio
                const unscaledViewport = page.getViewport({ scale: 1.0 });
                const scale = containerWidth / unscaledViewport.width;
                const viewport = page.getViewport({ scale: scale });
                
                const pageDiv = document.createElement('div');
                pageDiv.className = 'pdf-page-container';
                pageDiv.style.position = 'relative';
                pageDiv.style.marginBottom = '20px';
                pageDiv.style.margin = '0 auto 20px auto';
                pageDiv.style.width = viewport.width + 'px';
                pageDiv.style.height = viewport.height + 'px';
                pageDiv.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
                pageDiv.style.backgroundColor = 'white'; // Ensure PDF background is white
                
                const outputScale = window.devicePixelRatio || 1;

                const canvas = document.createElement('canvas');
                canvas.width = Math.floor(viewport.width * outputScale);
                canvas.height = Math.floor(viewport.height * outputScale);
                canvas.style.display = 'block';
                canvas.style.width = viewport.width + 'px';
                canvas.style.height = viewport.height + 'px';
                pageDiv.appendChild(canvas);
                
                const context = canvas.getContext('2d');
                const transform = outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null;
                const renderContext = {
                    canvasContext: context,
                    transform: transform,
                    viewport: viewport
                };
                
                // Render canvas
                page.render(renderContext);
                
                // Render text layer
                const textContent = await page.getTextContent();
                const textLayerDiv = document.createElement('div');
                textLayerDiv.setAttribute('class', 'textLayer');
                textLayerDiv.style.width = viewport.width + 'px';
                textLayerDiv.style.height = viewport.height + 'px';
                pageDiv.appendChild(textLayerDiv);
                
                pdfjsLib.renderTextLayer({
                    textContentSource: textContent,
                    container: textLayerDiv,
                    viewport: viewport,
                    textDivs: []
                });
                
                container.appendChild(pageDiv);
            }
        } catch (err) {
            console.error('Error rendering PDF:', err);
            container.innerHTML = '<div style="color:var(--fg-muted);">Cannot load PDF preview.</div>';
        }
    }

    function showWorkspace(jobId, origFilename, dlFilename) {
        uploadScreen.style.display = 'none';
        processingScreen.style.display = 'none';
        splitScreen.style.display = 'flex';
        
        currentJobId = jobId;
        currentOrigFilename = origFilename;
        currentDlFilename = dlFilename;
        headerDocName.textContent = origFilename;

        downloadBtn.style.display = 'flex';
        if (reloadBtn) reloadBtn.style.display = 'flex';
        downloadBtn.href = '/download/' + jobId + '/' + encodeURIComponent(dlFilename);

        previewScrollContainerEn.innerHTML = '';
        previewScrollContainerTh.innerHTML = '';

        currentRenderSession++;
        const sessionId = currentRenderSession;

        // Wait a frame to ensure DOM is fully laid out so clientWidth is correct!
        // 400ms ensures any 350ms CSS transitions on the layout are complete.
        setTimeout(() => {
            if (currentRenderSession !== sessionId) return;
            // Load original and translated PDFs using PDF.js
            renderPDF('/download_original/' + jobId, previewScrollContainerEn, sessionId);
            renderPDF('/download/' + jobId + '/' + encodeURIComponent(dlFilename), previewScrollContainerTh, sessionId);
        }, 400);
    }

    window.reloadWorkspace = function() {
        if (currentJobId && currentOrigFilename && currentDlFilename) {
            showWorkspace(currentJobId, currentOrigFilename, currentDlFilename);
        }
    };

    // ---- History ----
    async function loadHistory() {
        try {
            const response = await fetch('/history');
            const data = await response.json();
            
            if (!data.history || data.history.length === 0) {
                historyContainer.innerHTML = '<div class="history-loading" style="font-size: 12px; padding: 10px; color: var(--fg-muted);">ไม่มีประวัติการแปล</div>';
                return;
            }
            
            historyContainer.innerHTML = '';
            data.history.forEach((item, index) => {
                const dateStr = new Date(item.created_at * 1000).toLocaleTimeString('en-US', {hour: '2-digit', minute:'2-digit'});
                const isActive = (item.job_id === currentJobId) ? 'active' : '';
                
                const div = document.createElement('div');
                div.className = `history-item ${isActive}`;
                div.innerHTML = `
                    <div class="history-item-info">
                        <svg class="history-item-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                        <span class="history-item-title">${item.filename}</span>
                    </div>
                    <div class="history-item-actions">
                        <span class="history-item-meta">${dateStr}</span>
                        <button class="delete-history-btn" title="ลบประวัติ" aria-label="Delete">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                    </div>
                `;
                
                div.addEventListener('click', () => {
                    document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
                    div.classList.add('active');
                    
                    const dlName = item.filename.replace(/\.pdf$/i, '') + '_TH.pdf';
                    totalPages = item.pages;
                    showWorkspace(item.job_id, item.filename, dlName);
                    
                    if (window.innerWidth <= 768) {
                        sidebarPane.classList.add('collapsed');
                    }
                });
                
                const deleteBtn = div.querySelector('.delete-history-btn');
                deleteBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    if (confirm('คุณต้องการลบประวัติการแปลนี้ใช่หรือไม่?')) {
                        try {
                            const res = await fetch('/delete/' + item.job_id, { method: 'DELETE' });
                            const result = await res.json();
                            if (result.success) {
                                if (currentJobId === item.job_id) {
                                    resetToUpload();
                                }
                                loadHistory();
                            } else {
                                showToast(result.error || 'ไม่สามารถลบได้');
                            }
                        } catch (err) {
                            showToast('เกิดข้อผิดพลาดในการลบ');
                        }
                    }
                });
                
                historyContainer.appendChild(div);
            });
            
        } catch (err) {
            console.error(err);
        }
    }

    // Load history initially
    loadHistory();

    // ---- Scroll Sync ----
    const paneLeft = document.getElementById('pane-left');
    const paneRight = document.getElementById('pane-right');
    let isScrollSyncActive = true;
    let isSyncingLeft = false;
    let isSyncingRight = false;

    window.toggleScrollSync = function(active) {
        isScrollSyncActive = active;
        showToast(active ? 'Scroll synchronization enabled' : 'Scroll synchronization disabled');
    };

    function syncScrollLeft() {
        if (!isScrollSyncActive) return;
        if (isSyncingLeft) {
            isSyncingLeft = false;
            return;
        }
        isSyncingRight = true;
        paneRight.scrollTop = paneLeft.scrollTop;
    }

    function syncScrollRight() {
        if (!isScrollSyncActive) return;
        if (isSyncingRight) {
            isSyncingRight = false;
            return;
        }
        isSyncingLeft = true;
        paneLeft.scrollTop = paneRight.scrollTop;
    }

    paneLeft.addEventListener('scroll', syncScrollLeft);
    paneRight.addEventListener('scroll', syncScrollRight);

    // ---- Tweaks Config Panel ----
    window.toggleTweaks = function() {
        document.getElementById('tweaks-box').classList.toggle('show');
    };

    window.setTheme = function(theme) {
        document.body.className = '';
        document.body.classList.add('theme-' + theme);
        
        document.querySelectorAll('.tweak-theme-btn').forEach(btn => btn.classList.remove('active'));
        document.getElementById('theme-btn-' + theme).classList.add('active');
        showToast(`Theme changed to Next.js ${theme.toUpperCase()}`);
    };

    window.adjustSplitRatio = function(val) {
        document.documentElement.style.setProperty('--split-ratio', val + '%');
        document.getElementById('split-val-display').textContent = val + '%';
        const resizer = document.getElementById('split-handler');
        resizer.style.left = `calc(${val}% - 4px)`;
    };

    window.adjustPdfZoom = function(val) {
        const zoomLevel = val / 100.0;
        document.documentElement.style.setProperty('--pdf-zoom', zoomLevel);
        document.getElementById('zoom-val-display').textContent = val + '%';
    };

    // Split panel resizing drag handle
    const handler = document.getElementById('split-handler');
    let isDragging = false;

    handler.addEventListener('mousedown', function() {
        isDragging = true;
        handler.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
    });

    document.addEventListener('mousemove', function(e) {
        if (!isDragging) return;
        const containerWidth = document.querySelector('.split-pane-container').offsetWidth;
        let ratio = (e.clientX / containerWidth) * 100;
        if (ratio < 20) ratio = 20;
        if (ratio > 80) ratio = 80;
        window.adjustSplitRatio(Math.round(ratio));
    });

    document.addEventListener('mouseup', function() {
        if (isDragging) {
            isDragging = false;
            handler.classList.remove('dragging');
            document.body.style.cursor = '';
        }
    });

    // Mouse Spotlight
    document.addEventListener('mousemove', (e) => {
        document.querySelectorAll('.glow-card-target').forEach(card => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            card.style.setProperty('--mouse-x', `${x}px`);
            card.style.setProperty('--mouse-y', `${y}px`);
        });
    });

    // Sidebar resize handler
    const sidebarHandler = document.getElementById('sidebar-handler');
    let isDraggingSidebar = false;

    if (sidebarHandler) {
        sidebarHandler.addEventListener('mousedown', function() {
            isDraggingSidebar = true;
            sidebarHandler.classList.add('dragging');
            document.body.style.cursor = 'col-resize';
        });

        document.addEventListener('mousemove', function(e) {
            if (!isDraggingSidebar) return;
            let width = e.clientX;
            if (width < 200) width = 200;
            if (width > 600) width = 600;
            document.documentElement.style.setProperty('--sidebar-width', width + 'px');
        });

        document.addEventListener('mouseup', function() {
            if (isDraggingSidebar) {
                isDraggingSidebar = false;
                sidebarHandler.classList.remove('dragging');
                document.body.style.cursor = '';
            }
        });
    }

})();
