document.addEventListener('DOMContentLoaded', () => {
    const uploadBox = document.getElementById('uploadBox');
    const fileInput = document.getElementById('fileInput');
    
    const filePreview = document.getElementById('filePreview');
    const removeFileBtn = document.getElementById('removeFileBtn');
    const fileNameDisplay = document.getElementById('fileName');
    const fileSizeDisplay = document.getElementById('fileSize');
    const uploadForm = document.getElementById('uploadForm');
    const projectNameInput = document.getElementById('projectName');
    const styleInput = document.getElementById('styleInput');
    const lengthInput = document.getElementById('lengthInput');
    const targetDuration = document.getElementById('targetDuration');
    const motionSpeedSettings = document.getElementById('motionSpeedSettings');
    const playbackSpeed = document.getElementById('playbackSpeed');
    const motionSpeedLabel = document.getElementById('motionSpeedLabel');
    const motionSpeedHint = document.getElementById('motionSpeedHint');
    const submitBtn = document.getElementById('startProcessingBtn');
    const uploadProgress = document.getElementById('uploadProgress');
    const uploadProgressFill = document.getElementById('uploadProgressFill');
    const uploadProgressText = document.getElementById('uploadProgressText');
    const cancelUploadBtn = document.getElementById('cancelUploadBtn');
    let activeUpload = null;

    // Trigger file input when clicking the box or "browse files"
    uploadBox.addEventListener('click', async () => {
        fileInput.click();
    });

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadBox.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Highlight drop area when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadBox.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadBox.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        uploadBox.classList.add('dragover');
    }

    function unhighlight(e) {
        uploadBox.classList.remove('dragover');
    }

    // Handle dropped files
    uploadBox.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        let dt = e.dataTransfer;
        let files = dt.files;
        if (files.length > 0) {
            fileInput.files = files;
        }
        handleFiles(files);
    }

    // Handle file input change
    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });

    async function handleFiles(files) {
        if (files.length > 0) {
            const file = files[0];
            
            // Validate file type
            const validTypes = ['video/mp4', 'video/quicktime', 'video/x-matroska', 'video/x-mkv', 'video/x-msvideo', 'video/webm'];
            if (!validTypes.includes(file.type) && !file.name.match(/\.(mp4|mov|mkv|avi|webm)$/i)) {
                showToast('Invalid file type', 'Please upload a valid video file (MP4, MOV, MKV, AVI, WEBM)');
                return;
            }

            // Validate file size (max 1GB)
            const maxSize = 1024 * 1024 * 1024;
            if (file.size > maxSize) {
                showToast('File too large', 'Maximum file size is 1GB');
                return;
            }

            // Update UI
            fileNameDisplay.textContent = file.name;
            if (projectNameInput && !projectNameInput.value.trim()) {
                projectNameInput.value = file.name.replace(/\.[^/.]+$/, '');
            }
            
            // Format size
            const sizeInMB = (file.size / (1024 * 1024)).toFixed(2);
            const sizeInGB = (file.size / (1024 * 1024 * 1024)).toFixed(2);
            const displaySize = file.size > 1024 * 1024 * 1024 ? `${sizeInGB} GB` : `${sizeInMB} MB`;
            fileSizeDisplay.textContent = `${displaySize} • Ready to upload`;

            // Switch view
            uploadBox.classList.add('hidden');
            filePreview.classList.remove('hidden');
            
            showToast('Video selected', 'Review the details, then upload to queue it.');
        }
    }

    // Handle removing file
    removeFileBtn.addEventListener('click', async () => {
        fileInput.value = ''; // clear input
        if (projectNameInput) {
            projectNameInput.value = '';
        }
        filePreview.classList.add('hidden');
        uploadBox.classList.remove('hidden');
        
    });

    // Option buttons behave like simple single-choice pills inside each group.
    const platformBtns = document.querySelectorAll('.platform-btn');
    const outputLengthGroup = document.getElementById('outputLengthSettings') || document.getElementById('targetDuration')?.closest('.setting-group');
    function updateMotionControls(style) {
        if (!motionSpeedSettings || !playbackSpeed) return;
        const normalizedStyle = String(style || '').toLowerCase();
        const isSlow = normalizedStyle.includes('slow motion');
        const isFast = normalizedStyle.includes('fast motion');
        const isMotionMode = isSlow || isFast;

        motionSpeedSettings.classList.toggle('hidden', !isMotionMode);
        if (outputLengthGroup) {
            outputLengthGroup.classList.toggle('hidden', isMotionMode);
        }

        if (!isMotionMode) return;
        motionSpeedLabel.textContent = isSlow ? 'Slow motion amount' : 'Fast motion speed';
        motionSpeedHint.textContent = isSlow
            ? 'The selected speed applies to the entire uploaded video.'
            : 'The selected speed applies to the entire uploaded video.';
        Array.from(playbackSpeed.options).forEach(option => {
            const value = Number(option.value);
            option.hidden = isSlow ? value > 1 : value < 1;
        });
        playbackSpeed.value = isSlow ? '0.5' : '2';
    }
    platformBtns.forEach(btn => {
        btn.addEventListener('click', event => {
            event.stopPropagation();
            const group = btn.closest('[data-choice-group]');
            if (group) {
                group.querySelectorAll('.platform-btn').forEach(item => item.classList.remove('active'));
                if (group.dataset.choiceGroup === 'style' && styleInput) {
                    styleInput.value = btn.textContent.trim();
                    updateMotionControls(styleInput.value);
                }
                if (group.dataset.choiceGroup === 'length' && lengthInput) {
                    lengthInput.value = btn.textContent.trim();
                    if (targetDuration) targetDuration.value = btn.textContent.trim().replace(/[^0-9.]/g, '');
                }
            }
            btn.classList.add('active');
        });
    });
    if (targetDuration) {
        targetDuration.addEventListener('input', () => {
            const customValue = Number(targetDuration.value);
            if (!Number.isFinite(customValue) || customValue <= 0) return;
            document.querySelectorAll('[data-choice-group="length"] .platform-btn').forEach(item => item.classList.remove('active'));
            if (lengthInput) lengthInput.value = `${customValue} sec`;
        });
    }

    if (uploadForm) {
        uploadForm.addEventListener('submit', event => {
            event.preventDefault();

            if (!fileInput.files.length) {
                showToast('Choose a video', 'Select gameplay before uploading.');
                uploadBox.classList.remove('hidden');
                filePreview.classList.add('hidden');
                return;
            }

            const formData = new FormData(uploadForm);
            const xhr = new XMLHttpRequest();
            activeUpload = xhr;

            uploadProgress.classList.remove('hidden');
            uploadProgressFill.style.width = '0%';
            uploadProgressText.textContent = 'Uploading 0%';
            submitBtn.disabled = true;

            xhr.upload.addEventListener('progress', event => {
                if (!event.lengthComputable) {
                    uploadProgressText.textContent = 'Uploading...';
                    return;
                }

                const percent = Math.round((event.loaded / event.total) * 100);
                uploadProgressFill.style.width = `${percent}%`;
                uploadProgressText.textContent = `Uploading ${percent}%`;
            });

            xhr.addEventListener('load', () => {
                activeUpload = null;

                try {
                    // PHP can prepend a UTF-8 BOM or whitespace before JSON.
                    // Normalize it so a successful upload is not reported as a
                    // failed upload after the file has already been saved.
                    const rawResponse = (xhr.responseText || '').replace(/^\uFEFF/, '').trim();
                    const response = JSON.parse(rawResponse);
                    if (response.ok && xhr.status >= 200 && xhr.status < 300 && response.redirect) {
                        uploadProgressFill.style.width = '100%';
                        uploadProgressText.textContent = 'Upload complete. Starting render…';
                        submitBtn.disabled = true;
                        if (cancelUploadBtn) cancelUploadBtn.disabled = true;
                        showToast('Upload complete', 'Opening the render status page…');
                        window.location.assign(response.redirect);
                        return;
                    }

                    submitBtn.disabled = false;
                    if (cancelUploadBtn) cancelUploadBtn.disabled = false;
                    showToast('Upload failed', response.message || 'The upload could not be queued.');
                } catch (error) {
                    submitBtn.disabled = false;
                    if (cancelUploadBtn) cancelUploadBtn.disabled = false;
                    const status = xhr.status ? ` (HTTP ${xhr.status})` : '';
                    showToast('Upload failed', `The server returned an invalid response${status}. Please check the PHP error log.`);
                    console.error('Upload response parsing failed:', error, xhr.responseText);
                }
            });

            xhr.addEventListener('error', () => {
                activeUpload = null;
                submitBtn.disabled = false;
                if (cancelUploadBtn) cancelUploadBtn.disabled = false;
                uploadProgress.classList.add('hidden');
                showToast('Upload failed', 'Network error while uploading.');
            });

            xhr.addEventListener('abort', () => {
                activeUpload = null;
                submitBtn.disabled = false;
                uploadProgress.classList.add('hidden');
                showToast('Upload cancelled', 'No project was created.');
            });

            xhr.open('POST', uploadForm.action);
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
            xhr.send(formData);
        });
    }

    if (cancelUploadBtn) {
        cancelUploadBtn.addEventListener('click', () => {
            if (activeUpload) {
                activeUpload.abort();
            }
        });
    }
});
