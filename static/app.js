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
    const batchQueue = document.getElementById('batch-queue');
    const uploadFolderHint = document.getElementById('upload-folder-hint');
    
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
    let activeEventSources = [];
    let selectedProjectId = null;
    let selectedProjectName = '';
    let historyRequestId = 0;
    let toastTimer = null;

    // ---- Helpers ----
    window.showToast = function(msg) {
        let toast = document.getElementById('toast-notif');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'toast-notif';
            toast.className = 'toast-notification';
            toast.setAttribute('role', 'status');
            toast.setAttribute('aria-live', 'polite');
            toast.innerHTML = '<span id="toast-message"></span>';
            document.body.appendChild(toast);
        }
        toast.querySelector('#toast-message').textContent = msg;
        toast.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
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

    function escapeHtml(value) {
        return String(value || '').replace(/[&<>"']/g, (ch) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
        }[ch]));
    }

    function formatDate(value) {
        const date = value ? new Date(value.replace(' ', 'T')) : new Date();
        if (Number.isNaN(date.getTime())) return '';
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }

    function updateUploadFolderHint() {
        if (!uploadFolderHint) return;
        uploadFolderHint.textContent = selectedProjectId
            ? `Files will be saved in "${selectedProjectName}".`
            : 'Choose a folder on the left, or upload to a new folder automatically.';
    }

    function removeProjectFromExplorer(projectId) {
        document.querySelectorAll('.project-group').forEach((projectEl) => {
            if (String(projectEl.dataset.projectId) === String(projectId)) {
                projectEl.remove();
            }
        });
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
        activeEventSources.forEach(source => source.close());
        activeEventSources = [];

        splitScreen.style.display = 'none';
        processingScreen.style.display = 'none';
        uploadScreen.style.display = 'flex';
        headerDocName.textContent = 'No Document Loaded';
        downloadBtn.style.display = 'none';
        if (reloadBtn) reloadBtn.style.display = 'none';
        if (batchQueue) {
            batchQueue.style.display = 'none';
            batchQueue.innerHTML = '';
        }
        updateUploadFolderHint();
        
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
        if (files.length > 0) handleFileSelect(files);
    });

    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    // The explorer toolbar uses the same multi-file picker as the drop zone.
    window.openFilePicker = function() {
        fileInput.click();
    };

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) handleFileSelect(fileInput.files);
    });

    // ---- Parsing Mode UI ----
    document.querySelectorAll('.parsing-mode-option').forEach(option => {
        option.addEventListener('click', function() {
            document.querySelectorAll('.parsing-mode-option').forEach(opt => opt.classList.remove('active'));
            this.classList.add('active');
            const radio = this.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
        });
    });

    function handleFileSelect(fileList) {
        const files = Array.from(fileList).filter(file => file.name);
        if (files.length === 0) return;

        const invalidFile = files.find(file => !file.name.toLowerCase().endsWith('.pdf'));
        if (invalidFile) {
            showToast('Please choose PDF files only');
            return;
        }

        const oversizedFile = files.find(file => file.size > 100 * 1024 * 1024);
        if (oversizedFile) {
            showToast('File is too large (100 MB max)');
            return;
        }

        uploadAndTranslate(files);
    }

    // ---- Translation Flow ----
    async function uploadAndTranslate(files) {
        uploadScreen.style.display = 'none';
        splitScreen.style.display = 'none';
        processingScreen.style.display = 'flex';
        downloadBtn.style.display = 'none';
        headerDocName.textContent = files.length === 1 ? files[0].name : `${files.length} PDFs queued`;

        progressFill.style.width = '5%';
        progressStage.textContent = 'Uploading...';
        progressDetail.textContent = files.length === 1 ? 'Sending file to the server' : `Sending ${files.length} files to the server`;
        
        setStep(1, 'active');
        setStep(2, '');
        setStep(3, '');

        const fallbackProjectName = files.length > 1
            ? `Uploads ${new Date().toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })}`
            : files[0].name.replace(/\.pdf$/i, '');
        const batchState = files.map((file, index) => ({
            index,
            file,
            jobId: null,
            filename: file.name,
            dlFilename: null,
            percent: 0,
            status: 'queued',
            pages: 0,
        }));

        renderBatchQueue(batchState);

        const selectedMode = document.querySelector('input[name="parsing_mode"]:checked')?.value || 'auto';

        try {
            const completed = [];
            let projectId = selectedProjectId;
            let projectName = selectedProjectName || fallbackProjectName;

            if (!projectId) {
                const project = await createProject(fallbackProjectName, { select: true, silent: true });
                projectId = project.id;
                projectName = project.name;
            }

            async function processItem(item) {
                item.status = 'uploading';
                renderBatchQueue(batchState);

                const formData = new FormData();
                formData.append('file', item.file);
                formData.append('parsing_mode', selectedMode);
                formData.append('project_name', projectName);
                if (projectId) formData.append('project_id', projectId);

                const response = await fetch('/upload', { method: 'POST', body: formData });
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || `Could not upload ${item.file.name}`);
                }

                item.jobId = data.job_id;
                item.pages = data.pages || 0;
                item.status = 'processing';
                renderBatchQueue(batchState);

                const result = await connectProgress(data.job_id, item.file.name, item, batchState);
                completed.push(result);
            }

            const queue = batchState.slice();
            const workers = Array.from({ length: Math.min(2, queue.length) }, async () => {
                while (queue.length > 0) {
                    const item = queue.shift();
                    await processItem(item);
                }
            });
            await Promise.all(workers);

            const firstDone = completed[0];
            if (firstDone) {
                setTimeout(() => {
                    showWorkspace(firstDone.jobId, firstDone.filename, firstDone.dlFilename || 'translated.pdf');
                    loadHistory();
                }, 600);
            }

        } catch (err) {
            showToast(err.message || 'Cannot connect to the server');
            resetToUpload();
        }
    }

    function renderBatchQueue(batchState) {
        if (!batchQueue) return;
        batchQueue.style.display = batchState.length > 1 ? 'flex' : 'none';
        batchQueue.innerHTML = batchState.map(item => {
            const statusText = {
                queued: 'Queued',
                uploading: 'Uploading',
                processing: 'Translating',
                complete: 'Done',
                error: 'Error',
            }[item.status] || item.status;
            return `
                <div class="batch-item ${item.status}">
                    <div class="batch-item-main">
                        <span class="batch-item-name">${escapeHtml(item.filename)}</span>
                        <span class="batch-item-status">${statusText}</span>
                    </div>
                    <div class="batch-item-bar"><span style="width: ${item.percent || 0}%"></span></div>
                </div>
            `;
        }).join('');
    }

    function updateOverallProgress(batchState) {
        if (!batchState || batchState.length === 0) return;
        const total = batchState.reduce((sum, item) => sum + (item.percent || 0), 0);
        const overall = Math.round(total / batchState.length);
        progressFill.style.width = overall + '%';
        const done = batchState.filter(item => item.status === 'complete').length;
        progressDetail.textContent = batchState.length > 1
            ? `Completed ${done}/${batchState.length} files`
            : progressDetail.textContent;
    }

    function connectProgress(jobId, filename, batchItem = null, batchState = null) {
        if (!batchItem && eventSource) eventSource.close();

        const source = new EventSource('/progress/' + jobId);
        if (batchItem) {
            activeEventSources.push(source);
        } else {
            eventSource = source;
        }

        return new Promise((resolve, reject) => {
        source.addEventListener('stage', (e) => {
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

        source.addEventListener('info', (e) => {
            const data = JSON.parse(e.data);
            if (data.pages) totalPages = data.pages;
        });

        source.addEventListener('progress', (e) => {
            const data = JSON.parse(e.data);
            let pct = data.percent || 0;

            // Map backend percent (0-100% total)
            if (batchItem) {
                batchItem.percent = pct;
                batchItem.status = 'processing';
                renderBatchQueue(batchState);
                updateOverallProgress(batchState);
            } else {
                progressFill.style.width = pct + '%';
            }

            if (data.step === 'translate') {
                progressDetail.textContent = `Translated ${data.current}/${data.total} batches`;
            } else if (data.step === 'build_redact') {
                progressDetail.textContent = `Cleaning original text ${data.current}/${data.total}`;
            } else if (data.step === 'build_insert') {
                progressDetail.textContent = `Placing Thai text ${data.current}/${data.total}`;
            }
        });

        source.addEventListener('complete', (e) => {
            const data = JSON.parse(e.data);
            source.close();
            if (!batchItem) eventSource = null;

            totalPages = data.pages || totalPages;
            setStep(3, 'completed');
            if (batchItem) {
                batchItem.percent = 100;
                batchItem.status = 'complete';
                batchItem.dlFilename = data.filename || 'translated.pdf';
                renderBatchQueue(batchState);
                updateOverallProgress(batchState);
            } else {
                progressFill.style.width = '100%';
            }
            progressStage.textContent = 'Translation complete';
            progressDetail.textContent = `Translated ${totalPages} pages`;

            if (!batchItem) {
                setTimeout(() => {
                    showWorkspace(jobId, filename, data.filename || 'translated.pdf');
                    loadHistory(); // refresh history
                }, 800);
            }
            resolve({ jobId, filename, dlFilename: data.filename || 'translated.pdf', pages: totalPages });
        });

        source.addEventListener('error', (e) => {
            let msg = 'Translation failed';
            try {
                const data = JSON.parse(e.data);
                msg = data.message || msg;
            } catch (_) {}
            source.close();
            if (batchItem) {
                batchItem.status = 'error';
                renderBatchQueue(batchState);
            } else {
                eventSource = null;
                showToast(msg);
                resetToUpload();
            }
            reject(new Error(msg));
        });
        });
    }

    // ---- Workspace View (PDF.js Rendering for text selection) ----
    let currentRenderSession = 0;
    let reloadDebounceTimer = null;

    function debouncedReloadWorkspace(delay = 250) {
        if (reloadDebounceTimer) clearTimeout(reloadDebounceTimer);
        reloadDebounceTimer = setTimeout(() => {
            if (currentJobId && currentOrigFilename && currentDlFilename) {
                showWorkspace(currentJobId, currentOrigFilename, currentDlFilename);
            }
        }, delay);
    }

    async function renderPDF(url, container, sessionId) {
        try {
            const loadingTask = pdfjsLib.getDocument(url);
            const pdf = await loadingTask.promise;
            
            if (currentRenderSession !== sessionId) return;
            
            // Setup responsive scaling observer to re-render when container resizes
            if (!container._resizeObserver) {
                let lastWidth = container.clientWidth;
                container._resizeObserver = new ResizeObserver(entries => {
                    for (let entry of entries) {
                        const newWidth = entry.contentRect.width;
                        if (Math.abs(newWidth - lastWidth) > 20) {
                            lastWidth = newWidth;
                            debouncedReloadWorkspace(300);
                        }
                    }
                });
                container._resizeObserver.observe(container);
            }
            
            // Calculate scale based on container width and user zoom
            const userZoom = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--pdf-zoom').trim()) || 1.0;
            let availableWidth = container.clientWidth - 40; // 20px padding left/right
            if (availableWidth <= 0) {
                const rect = container.getBoundingClientRect();
                availableWidth = (rect.width || 600) - 40;
                if (availableWidth <= 0) availableWidth = 600;
            }
            const targetWidth = availableWidth * userZoom;

            for (let i = 1; i <= pdf.numPages; i++) {
                if (currentRenderSession !== sessionId) {
                    loadingTask.destroy();
                    return;
                }
                const page = await pdf.getPage(i);
                
                // Get unscaled viewport to calculate ratio
                const unscaledViewport = page.getViewport({ scale: 1.0 });
                const scale = targetWidth / unscaledViewport.width;
                const viewport = page.getViewport({ scale: scale });
                
                const pageDiv = document.createElement('div');
                pageDiv.className = 'pdf-page-container';
                pageDiv.style.position = 'relative';
                pageDiv.style.margin = '0 auto 20px auto';
                pageDiv.style.width = viewport.width + 'px';
                pageDiv.style.height = viewport.height + 'px';
                pageDiv.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
                pageDiv.style.backgroundColor = 'white'; // Ensure PDF background is white
                
                const outputScale = (window.devicePixelRatio || 1) * 1.5; // Render at 1.5x resolution for sharper scaling

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
                textLayerDiv.style.setProperty('--scale-factor', viewport.scale);
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
        
        const container = document.querySelector('.split-pane-container');
        if (container && !container.className.includes('view-')) {
            container.classList.add('view-both');
        }
        
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
    function selectProject(project) {
        selectedProjectId = project?.id || null;
        selectedProjectName = project?.name || '';
        document.querySelectorAll('.project-group').forEach(el => {
            el.classList.toggle('selected', selectedProjectId !== null && String(el.dataset.projectId) === String(selectedProjectId));
        });
        updateUploadFolderHint();
    }

    async function createProject(name = '', options = {}) {
        const response = await fetch('/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Could not create folder');
        }
        if (options.select) {
            selectProject(data.project);
        }
        if (!options.silent) {
            showToast('Folder created');
            await loadHistory();
            selectProject(data.project);
        }
        return data.project;
    }

    function openFolderComposer() {
        const existingComposer = historyContainer.querySelector('.folder-composer');
        if (existingComposer) {
            existingComposer.querySelector('input').focus();
            return;
        }

        const composer = document.createElement('form');
        composer.className = 'folder-composer';
        composer.innerHTML = `
            <svg class="project-folder-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3"><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
            <input type="text" aria-label="Folder name" placeholder="Folder name" maxlength="120" autocomplete="off">
            <button class="folder-composer-action" type="submit" title="Create folder" aria-label="Create folder">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="m5 12 4 4L19 6"/></svg>
            </button>
            <button class="folder-composer-action cancel-folder-composer" type="button" title="Cancel" aria-label="Cancel">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="m6 6 12 12M18 6 6 18"/></svg>
            </button>
        `;
        historyContainer.prepend(composer);

        const input = composer.querySelector('input');
        const submitButton = composer.querySelector('[type="submit"]');
        const cancelButton = composer.querySelector('.cancel-folder-composer');

        cancelButton.addEventListener('click', () => composer.remove());
        input.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') composer.remove();
        });
        composer.addEventListener('submit', async (event) => {
            event.preventDefault();
            const name = input.value.trim();
            if (!name) {
                input.focus();
                return;
            }

            submitButton.disabled = true;
            try {
                await createProject(name, { select: true });
            } catch (err) {
                submitButton.disabled = false;
                showToast(err.message || 'Could not create folder');
                input.focus();
            }
        });
        input.focus();
    }

    window.createFolder = openFolderComposer;

    async function renameProject(project) {
        const name = prompt('Rename folder', project.name);
        if (name === null) return;
        const trimmed = name.trim();
        if (!trimmed) {
            showToast('Folder name is required');
            return;
        }

        try {
            const response = await fetch(`/projects/${project.id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: trimmed }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Could not rename folder');
            if (Number(selectedProjectId) === Number(project.id)) {
                selectedProjectName = data.project.name;
                updateUploadFolderHint();
            }
            showToast('Folder renamed');
            await loadHistory();
        } catch (err) {
            showToast(err.message || 'Could not rename folder');
        }
    }

    async function deleteProject(project) {
        if (!project?.id) return;

        let mode = 'keep_files';
        if (project.files.length > 0) {
            const deleteFolder = confirm(
                `Delete folder "${project.name}"? Its ${project.files.length} file${project.files.length === 1 ? '' : 's'} will be kept in Unfiled unless you choose to delete them next.`
            );
            if (!deleteFolder) return;
            if (confirm('Also permanently delete the files in this folder?')) {
                mode = 'delete_files';
            }
        } else if (!confirm(`Delete the empty folder "${project.name}"?`)) {
            return;
        }

        try {
            const response = await fetch(`/projects/${project.id}?mode=${mode}`, { method: 'DELETE' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Could not delete folder');
            if (Number(selectedProjectId) === Number(project.id)) {
                selectProject(null);
            }
            removeProjectFromExplorer(project.id);
            showToast(mode === 'delete_files' ? 'Folder and files deleted' : 'Folder deleted; files moved to Unfiled');
            await loadHistory();
        } catch (err) {
            showToast(err.message || 'Could not delete folder');
        }
    }

    async function moveFileToProject(jobId, project) {
        if (!jobId || !project?.id) return;
        try {
            const response = await fetch(`/files/${jobId}/move`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_id: project.id }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Could not move file');
            showToast(`Moved to ${project.name}`);
            await loadHistory();
        } catch (err) {
            showToast(err.message || 'Could not move file');
        }
    }

    async function loadHistory() {
        const requestId = ++historyRequestId;
        try {
            const response = await fetch('/history', { cache: 'no-store' });
            const data = await response.json();
            if (requestId !== historyRequestId) return;
            
            const projects = data.projects || [];
            if (projects.length === 0) {
                historyContainer.innerHTML = '<div class="history-loading" style="font-size: 12px; padding: 10px; color: var(--fg-muted);">No folders yet</div>';
                updateUploadFolderHint();
                return;
            }
            
            historyContainer.innerHTML = '';
            projects.forEach((project) => {
                const projectDiv = document.createElement('div');
                projectDiv.className = 'project-group';
                projectDiv.dataset.projectId = project.id || '';
                const renameControl = project.id ? `
                    <button class="project-action-btn rename-project-btn" type="button" title="Rename folder" aria-label="Rename folder">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                    </button>
                    <button class="project-action-btn delete-project-btn" type="button" title="Delete folder" aria-label="Delete folder">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    </button>
                ` : '';
                projectDiv.innerHTML = `
                    <div class="project-row" role="button" tabindex="0">
                        <span class="project-row-left">
                            <svg class="project-chevron" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
                            <svg class="project-folder-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3"><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
                            <span class="project-name">${escapeHtml(project.name)}</span>
                        </span>
                        <span class="project-row-actions">
                            ${renameControl}
                            <span class="project-count">${project.files.length}</span>
                        </span>
                    </div>
                    <div class="project-files"></div>
                `;

                const filesContainer = projectDiv.querySelector('.project-files');
                const projectRow = projectDiv.querySelector('.project-row');
                const isOpen = project.files.some(item => item.job_id === currentJobId) || historyContainer.children.length === 0;
                projectDiv.classList.toggle('open', isOpen);
                projectDiv.classList.toggle('selected', selectedProjectId !== null && String(project.id) === String(selectedProjectId));

                projectRow.addEventListener('click', () => {
                    selectProject(project);
                    projectDiv.classList.toggle('open');
                });
                if (project.id) {
                    projectRow.addEventListener('dragover', (e) => {
                        e.preventDefault();
                        projectDiv.classList.add('drop-target');
                    });
                    projectRow.addEventListener('dragleave', () => {
                        projectDiv.classList.remove('drop-target');
                    });
                    projectRow.addEventListener('drop', async (e) => {
                        e.preventDefault();
                        projectDiv.classList.remove('drop-target');
                        const jobId = e.dataTransfer.getData('text/job-id');
                        await moveFileToProject(jobId, project);
                    });
                }

                const renameBtn = projectDiv.querySelector('.rename-project-btn');
                if (renameBtn) {
                    renameBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        renameProject(project);
                    });
                }

                const deleteProjectBtn = projectDiv.querySelector('.delete-project-btn');
                if (deleteProjectBtn) {
                    deleteProjectBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        deleteProject(project);
                    });
                }

                if (project.files.length === 0) {
                    filesContainer.innerHTML = '<div class="empty-folder-note">Empty folder</div>';
                }

                project.files.forEach((item) => {
                    const dateStr = formatDate(item.created_at);
                    const isActive = (item.job_id === currentJobId) ? 'active' : '';
                    const div = document.createElement('div');
                    div.className = `history-item ${isActive}`;
                    div.draggable = true;
                    div.dataset.jobId = item.job_id;
                    div.innerHTML = `
                        <div class="history-item-info">
                            <svg class="history-item-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                            <span class="history-item-title">${escapeHtml(item.filename)}</span>
                        </div>
                        <div class="history-item-actions">
                            <span class="history-item-meta">${dateStr}</span>
                            <button class="delete-history-btn" title="Delete file" aria-label="Delete">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                            </button>
                        </div>
                    `;

                    div.addEventListener('dragstart', (e) => {
                        e.dataTransfer.setData('text/job-id', item.job_id);
                        e.dataTransfer.effectAllowed = 'move';
                        div.classList.add('dragging');
                    });
                    div.addEventListener('dragend', () => {
                        div.classList.remove('dragging');
                    });

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
                        if (confirm('Delete this translated file?')) {
                            try {
                                const res = await fetch('/delete/' + item.job_id, { method: 'DELETE' });
                                const result = await res.json();
                                if (result.success) {
                                    if (currentJobId === item.job_id) {
                                        resetToUpload();
                                    }
                                    div.remove();
                                    await loadHistory();
                                } else {
                                    showToast(result.error || 'Could not delete file');
                                }
                            } catch (err) {
                                showToast('Delete failed');
                            }
                        }
                    });

                    filesContainer.appendChild(div);
                });

                historyContainer.appendChild(projectDiv);
            });
            
        } catch (err) {
            console.error(err);
        }
    }

    function fetchHistory() {
        return loadHistory();
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
        debouncedReloadWorkspace(150);
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
            debouncedReloadWorkspace(100);
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

    // =========================================================================
    // AUTHENTICATION LOGIC (LOGIN & REGISTER)
    // =========================================================================
    let currentUser = null;

    async function checkAuthStatus() {
        try {
            const res = await fetch('/api/me');
            const data = await res.json();
            if (data.logged_in) {
                currentUser = data.user;
                updateAuthUI(true, currentUser.email);
            } else {
                currentUser = null;
                updateAuthUI(false);
            }
            fetchHistory();
        } catch (e) {
            console.error('Error checking auth status:', e);
        }
    }

    function updateAuthUI(isLoggedIn, email = '') {
        const userDisplayName = document.getElementById('user-display-name');
        const authBtn = document.getElementById('auth-modal-btn');
        if (isLoggedIn) {
            userDisplayName.textContent = email;
            authBtn.title = "Click to log out";
            authBtn.onclick = handleLogout;
        } else {
            userDisplayName.textContent = 'Sign in';
            authBtn.title = "Sign in / Create account";
            authBtn.onclick = openAuthModal;
        }
    }

    window.openAuthModal = function() {
        document.getElementById('auth-modal').style.display = 'flex';
        document.getElementById('auth-error-box').style.display = 'none';
    };

    window.closeAuthModal = function() {
        document.getElementById('auth-modal').style.display = 'none';
    };

    window.switchAuthTab = function(tab) {
        const loginForm = document.getElementById('form-login');
        const regForm = document.getElementById('form-register');
        const tabLogin = document.getElementById('tab-login');
        const tabReg = document.getElementById('tab-register');
        const errorBox = document.getElementById('auth-error-box');

        errorBox.style.display = 'none';

        if (tab === 'login') {
            loginForm.style.display = 'block';
            regForm.style.display = 'none';
            tabLogin.classList.add('active');
            tabReg.classList.remove('active');
        } else {
            loginForm.style.display = 'none';
            regForm.style.display = 'block';
            tabReg.classList.add('active');
            tabLogin.classList.remove('active');
        }
    };

    window.handleLoginSubmit = async function(e) {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        const errorBox = document.getElementById('auth-error-box');

        try {
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();
            if (!res.ok || data.error) {
                errorBox.textContent = data.error || 'Sign in failed';
                errorBox.style.display = 'block';
            } else {
                currentUser = data.user;
                updateAuthUI(true, currentUser.email);
                closeAuthModal();
                showToast(`Welcome ${currentUser.email}`);
                fetchHistory();
            }
        } catch (err) {
            errorBox.textContent = 'Connection error';
            errorBox.style.display = 'block';
        }
    };

    window.handleRegisterSubmit = async function(e) {
        e.preventDefault();
        const email = document.getElementById('reg-email').value;
        const password = document.getElementById('reg-password').value;
        const errorBox = document.getElementById('auth-error-box');

        try {
            const res = await fetch('/api/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();
            if (!res.ok || data.error) {
                errorBox.textContent = data.error || 'Registration failed';
                errorBox.style.display = 'block';
            } else {
                currentUser = data.user;
                updateAuthUI(true, currentUser.email);
                closeAuthModal();
                showToast(`Account created. Welcome ${currentUser.email}`);
                fetchHistory();
            }
        } catch (err) {
            errorBox.textContent = 'Connection error';
            errorBox.style.display = 'block';
        }
    };

    window.handleGoogleCredentialResponse = async function(response) {
        const errorBox = document.getElementById('auth-error-box');
        try {
            const res = await fetch('/api/google-login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ credential: response.credential })
            });
            const data = await res.json();
            if (!res.ok || data.error) {
                errorBox.textContent = data.error || 'Google sign in failed';
                errorBox.style.display = 'block';
            } else {
                currentUser = data.user;
                updateAuthUI(true, currentUser.email);
                closeAuthModal();
                showToast(`Welcome ${currentUser.email} (Google)`);
                fetchHistory();
            }
        } catch (err) {
            errorBox.textContent = 'Google sign in connection error';
            errorBox.style.display = 'block';
        }
    };

    async function handleLogout() {
        if (!confirm('Log out?')) return;
        try {
            await fetch('/api/logout', { method: 'POST' });
            currentUser = null;
            updateAuthUI(false);
            showToast('Logged out');
            fetchHistory();
        } catch (err) {
            console.error('Error logging out:', err);
        }
    }


    // Call checkAuthStatus on startup
    checkAuthStatus();

    // Mobile View Mode Switcher
    window.setMobileView = function(mode) {
        const container = document.querySelector('.split-pane-container');
        if (!container) return;
        container.classList.remove('view-en', 'view-th', 'view-both');
        container.classList.add('view-' + mode);
        
        document.querySelectorAll('.mobile-tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === mode);
        });
        
        debouncedReloadWorkspace(150);
    };

})();
