/**
 * GameCut AI — Processing Page
 * Polls /api/job_status.php for real job progress from the Python worker.
 * Never fakes 100% until the job is actually completed and the file is ready.
 */
document.addEventListener('DOMContentLoaded', () => {
    const progressCircle   = document.getElementById('progressCircle');
    const progressPercent  = document.getElementById('progressPercent');
    const currentStepText  = document.getElementById('currentStepText');
    const estimatedTimeSpan = document.querySelector('#estimatedTime span');
    const processingMain   = document.querySelector('.processing-main');
    const pipelineStatus   = document.getElementById('pipelineStatus');
    const projectId        = processingMain ? parseInt(processingMain.dataset.projectId, 10) : 0;

    const CIRCUMFERENCE = 565; // 2 * π * 90

    // Map every worker current_step → { uiIndex (1-based), label }
    // uiIndex maps to step-1 … step-8 in processing.php
    const STEP_MAP = {
        'queued':                    { uiIndex: 1, label: 'Queued — Waiting for Worker' },
        'analyzing':                 { uiIndex: 2, label: 'Analyzing Gameplay...' },
        'scene_detection':           { uiIndex: 2, label: 'Scene Detection...' },
        'scene_detection_completed': { uiIndex: 3, label: 'Scene Detection Complete' },
        'speech_analysis':           { uiIndex: 3, label: 'Speech Analysis...' },
        'speech_analysis_completed': { uiIndex: 3, label: 'Speech Analysis Complete' },
        'audio_analysis':            { uiIndex: 3, label: 'Audio Analysis...' },
        'visual_analysis':           { uiIndex: 3, label: 'Visual Analysis...' },
        'highlight_scoring':         { uiIndex: 4, label: 'Finding Highlights...' },
        'advanced_analysis_completed':{ uiIndex: 4, label: 'Highlights Scored' },
        'no_highlight_candidates':   { uiIndex: 4, label: 'No Strong Highlights Found' },
        'agent_planning':            { uiIndex: 5, label: 'AI Editing Plan...' },
        'plan_validation':           { uiIndex: 5, label: 'Validating Plan...' },
        'rendering':                 { uiIndex: 6, label: 'Rendering 9:16 Video...' },
        'output_validation':         { uiIndex: 7, label: 'Validating Output...' },
        'completed':                 { uiIndex: 8, label: 'Done!' },
    };

    // Steps in the UI — must match ids in processing.php
    const UI_STEPS = ['step-1','step-2','step-3','step-4','step-5','step-6','step-7','step-8'];

    let lastRenderedProgress = -1;
    let pollingInterval      = null;
    let startTime            = Date.now();
    let lastStepSeen         = null;

    // ---------- DOM helpers ----------

    function setCircleProgress(pct) {
        pct = Math.max(0, Math.min(100, pct));
        if (pct === lastRenderedProgress) return;
        lastRenderedProgress = pct;
        progressPercent.textContent = Math.round(pct) + '%';
        const offset = CIRCUMFERENCE - (pct / 100) * CIRCUMFERENCE;
        progressCircle.style.strokeDashoffset = offset;
    }

    function markStepDone(index /* 1-based */) {
        const el = document.getElementById('step-' + index);
        if (!el) return;
        el.classList.remove('active', 'pending');
        el.classList.add('completed');
        const spinner = el.querySelector('.spinner');
        const check   = el.querySelector('.check-icon');
        if (spinner) spinner.classList.add('hidden');
        if (check)   check.classList.remove('hidden');
    }

    function markStepActive(index) {
        const el = document.getElementById('step-' + index);
        if (!el) return;
        el.classList.remove('pending', 'completed');
        el.classList.add('active');
        const spinner = el.querySelector('.spinner');
        if (spinner) spinner.classList.remove('hidden');
    }

    function syncUiToStep(uiIndex) {
        for (let i = 1; i <= UI_STEPS.length; i++) {
            if (i < uiIndex) {
                markStepDone(i);
            } else if (i === uiIndex) {
                markStepActive(i);
            }
            // steps after uiIndex stay pending (no change)
        }
    }

    function markAllDone() {
        for (let i = 1; i <= UI_STEPS.length; i++) markStepDone(i);
    }

    function showError(message) {
        if (currentStepText) {
            currentStepText.textContent = 'Processing Failed';
            currentStepText.style.color = 'var(--danger, #ef4444)';
        }
        if (estimatedTimeSpan) estimatedTimeSpan.textContent = 'Please try again.';
        // Add error detail below the circle if possible
        const statusContainer = document.querySelector('.status-container');
        if (statusContainer && message) {
            const existing = document.getElementById('error-detail');
            if (!existing) {
                const p = document.createElement('p');
                p.id = 'error-detail';
                p.style.cssText = 'color:var(--danger,#ef4444);font-size:0.8rem;margin-top:0.5rem;word-break:break-word;';
                p.textContent = message.length > 200 ? message.slice(0, 200) + '…' : message;
                statusContainer.appendChild(p);
            }
        }
    }

    function updateEstimatedTime(progress) {
        if (progress <= 0) {
            estimatedTimeSpan.textContent = 'Calculating…';
            return;
        }
        const elapsed = (Date.now() - startTime) / 1000;
        const rate = progress / elapsed; // percent per second
        if (rate > 0 && progress < 100) {
            const remaining = Math.round((100 - progress) / rate);
            const mins = Math.floor(remaining / 60);
            const secs = remaining % 60;
            estimatedTimeSpan.textContent = mins > 0
                ? `~${mins}m ${secs}s remaining`
                : `~${secs}s remaining`;
        } else if (progress >= 100) {
            estimatedTimeSpan.textContent = 'Redirecting…';
        } else {
            estimatedTimeSpan.textContent = 'Calculating…';
        }
    }

    // ---------- Polling ----------

    async function pollStatus() {
        if (!projectId) {
            if (currentStepText) currentStepText.textContent = 'No project ID — check the URL.';
            return;
        }

        let data;
        try {
            const resp = await fetch('api/job_status.php?project_id=' + projectId, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                cache: 'no-store',
            });
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            data = await resp.json();
        } catch (err) {
            console.warn('[GameCut] Poll error:', err.message);
            if (estimatedTimeSpan) estimatedTimeSpan.textContent = 'Reconnecting…';
            return; // retry on next interval
        }

        if (!data.ok) {
            console.error('[GameCut] Job status error:', data.message);
            return;
        }

        const jobStatus   = data.job_status   || data.project_status || 'queued';
        const progress    = parseInt(data.progress, 10) || 0;
        const currentStep = data.current_step  || jobStatus;
        const stepKey     = (currentStep || '').toLowerCase();

        if (pipelineStatus) {
            const queued = jobStatus === 'queued';
            pipelineStatus.textContent = queued ? 'Queued — waiting for worker' :
                (jobStatus === 'processing' ? 'Running' : jobStatus);
            pipelineStatus.classList.toggle('status-processing', queued || jobStatus === 'processing');
            pipelineStatus.classList.toggle('status-done', jobStatus === 'completed');
            pipelineStatus.classList.toggle('status-failed', jobStatus === 'failed');
        }
        if (queued && estimatedTimeSpan) {
            const position = Number(data.queue_position || 0);
            const running = Number(data.other_projects_running || 0);
            estimatedTimeSpan.textContent = position > 0
                ? `Queue position ${position}${running ? ` · ${running} other project${running === 1 ? '' : 's'} running` : ''}`
                : 'Waiting for worker…';
        }

        // --- Update circle & estimated time ---
        setCircleProgress(progress);
        updateEstimatedTime(progress);

        // --- Update step text ---
        const stepInfo = STEP_MAP[stepKey];
        if (stepInfo && currentStepText) {
            currentStepText.textContent = stepInfo.label;
            if (stepKey !== lastStepSeen) {
                lastStepSeen = stepKey;
                syncUiToStep(stepInfo.uiIndex);
            }
        } else if (currentStep && currentStepText) {
            // Unknown step — show it verbatim
            currentStepText.textContent = currentStep.replace(/_/g, ' ');
        }

        // --- Terminal states ---
        if (jobStatus === 'failed') {
            clearInterval(pollingInterval);
            setCircleProgress(progress || 0);
            markAllDone(); // mark done up to where it got
            showError(data.error_message || 'An unknown error occurred.');
            return;
        }

        if (data.completed && data.ready) {
            clearInterval(pollingInterval);
            setCircleProgress(100);
            markAllDone();
            if (currentStepText) {
                currentStepText.textContent = 'Done!';
                currentStepText.style.color = 'var(--success, #22c55e)';
            }
            if (estimatedTimeSpan) estimatedTimeSpan.textContent = 'Redirecting…';
            setTimeout(() => {
                window.location.href = 'preview.php?project_id=' + projectId;
            }, 1200);
            return;
        }

        // Completed DB state but output not yet on disk — keep polling
        if (data.completed && !data.ready) {
            if (currentStepText) currentStepText.textContent = 'Finalizing…';
        }
    }

    // ---------- Init ----------

    // Show initial server-side progress immediately
    const initialProgress = parseInt(progressPercent ? progressPercent.textContent : '0', 10) || 0;
    setCircleProgress(initialProgress);

    if (!projectId) {
        if (currentStepText) currentStepText.textContent = 'No project found — please upload a video first.';
        if (estimatedTimeSpan) estimatedTimeSpan.textContent = '';
        return;
    }

    // Poll immediately then every 3 seconds
    pollStatus();
    pollingInterval = setInterval(pollStatus, 3000);
});
