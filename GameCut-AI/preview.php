<?php
require_once 'php/bootstrap.php';
require_once 'php/config.php';
require_once 'php/session.php';

// Require authentication
requireAuth();

// Get current user data
$currentUser = getCurrentUser();
$userId = (int)($currentUser['id'] ?? 0);
$result = null;
$downloadUrl = '';
$thumbnailUrl = '';
$sourceUrl = '';
$outputWidth = null;
$outputHeight = null;
$hasOutput = false;

try {
    $projectId = (int)($_GET['project_id'] ?? 0);
    $params = [$userId];
    $where = 'p.user_id = ? AND p.delete_requested_at IS NULL';

    if ($projectId > 0) {
        $where .= ' AND p.id = ?';
        $params[] = $projectId;
    }

    $stmt = $pdo->prepare(
        "SELECT p.id AS project_id, p.project_name, p.description, p.status AS project_status,
                v.output_path, v.file_path, v.duration, v.created_at, latest_job.status AS job_status,
                latest_job.progress, latest_job.current_step
         FROM projects p
         JOIN videos v ON v.project_id = p.id
         LEFT JOIN (
             SELECT j1.video_id, j1.status, j1.progress, j1.current_step
             FROM ai_jobs j1
             INNER JOIN (
                 SELECT video_id, MAX(id) AS latest_id
                 FROM ai_jobs
                 GROUP BY video_id
             ) newest ON newest.video_id = j1.video_id AND newest.latest_id = j1.id
         ) latest_job ON latest_job.video_id = v.id
         WHERE $where
         ORDER BY FIELD(p.status, 'completed', 'processing', 'draft', 'failed'), p.created_at DESC
         LIMIT 1"
    );
    $stmt->execute($params);
    $result = $stmt->fetch();

    if ($result && !empty($result['output_path'])) {
        $absoluteOutput = __DIR__ . DIRECTORY_SEPARATOR . str_replace(['/', '\\'], DIRECTORY_SEPARATOR, $result['output_path']);
        $hasOutput = is_file($absoluteOutput);
        if ($hasOutput) {
            $mediaBaseUrl = 'api/media.php?project_id=' . (int)$result['project_id'];
            // Uploads are intentionally denied direct web access. Route every
            // preview/download through the authenticated byte-range endpoint.
            $downloadUrl = appUrl($mediaBaseUrl . '&type=output');
            $thumbnailPath = pathinfo($result['output_path'], PATHINFO_DIRNAME) . '/' . pathinfo($result['output_path'], PATHINFO_FILENAME) . '_thumbnail.jpg';
            $thumbnailAbsolute = __DIR__ . DIRECTORY_SEPARATOR . str_replace(['/', '\\'], DIRECTORY_SEPARATOR, $thumbnailPath);
            if (is_file($thumbnailAbsolute)) $thumbnailUrl = appUrl($mediaBaseUrl . '&type=thumbnail');
            $sourceUrl = appUrl($mediaBaseUrl . '&type=source');
            $probe = @json_decode((string)shell_exec('"C:\\xampp\\htdocs\\AI Video Editor\\GameCut-AI\\bin\\ffprobe.exe" -v quiet -print_format json -show_streams ' . escapeshellarg($absoluteOutput)), true);
            foreach (($probe['streams'] ?? []) as $stream) {
                if (($stream['codec_type'] ?? '') === 'video') { $outputWidth = (int)($stream['width'] ?? 0); $outputHeight = (int)($stream['height'] ?? 0); break; }
            }
        }
    }
} catch (PDOException $e) {
    error_log('Preview load error: ' . $e->getMessage());
}

$title = $result['project_name'] ?? 'No completed short yet';
$statusText = $hasOutput ? 'Ready' : ucfirst($result['job_status'] ?? $result['project_status'] ?? 'Waiting');
$statusClass = $hasOutput ? 'status-done' : (strtolower($statusText) === 'failed' ? 'status-failed' : 'status-processing');
$progress = (int)($result['progress'] ?? 0);
$videoDuration = $result['duration'] ?? 'Unknown';
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo htmlspecialchars($hasOutput ? 'Your AI Short is Ready' : 'AI Short Not Ready'); ?> - GameCut AI</title>
    <script src="js/theme-init.js"></script>
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/preview.css">
    <link rel="stylesheet" href="css/responsive.css">
</head>
<body class="theme-dark dashboard-body">
    <aside class="sidebar preview-sidebar">
        <div class="sidebar-header">
            <a href="index.php" class="logo"><svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7L12 12L22 7L12 2Z" fill="#7C3AED"/><path d="M2 17L12 22L22 17M2 12L12 17L22 12" stroke="#3B82F6" stroke-width="2" stroke-linecap="round"/></svg><span>GameCut <span class="text-gradient">AI</span></span></a>
        </div>
        <nav class="sidebar-nav">
            <a href="dashboard.php" class="nav-item"><span>Dashboard</span></a>
            <a href="projects.php" class="nav-item"><span>Projects</span></a>
            <a href="upload.php" class="nav-item"><span>Upload</span></a>
            <a href="preview.php" class="nav-item active"><span>Results</span></a>
            <a href="settings.php" class="nav-item"><span>Settings</span></a>
        </nav>
    </aside>
    <!-- Header Navigation -->
    <nav class="navbar scrolled">
        <div class="container nav-container">
            <a href="index.php" class="logo">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="url(#paint0_linear_preview)" />
                    <path d="M2 17L12 22L22 17" stroke="url(#paint1_linear_preview)" stroke-width="2" stroke-linecap="round"/>
                    <path d="M2 12L12 17L22 12" stroke="url(#paint2_linear_preview)" stroke-width="2" stroke-linecap="round"/>
                    <defs>
                        <linearGradient id="paint0_linear_preview" x1="12" y1="2" x2="12" y2="12" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                        <linearGradient id="paint1_linear_preview" x1="12" y1="17" x2="12" y2="22" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                        <linearGradient id="paint2_linear_preview" x1="12" y1="12" x2="12" y2="17" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                    </defs>
                </svg>
                <span>GameCut <span class="text-gradient">AI</span></span>
            </a>
            <div class="nav-actions">
                <a href="upload.php" class="btn btn-outline">New Upload</a>
                <button class="btn btn-primary" id="downloadBtn" <?php echo $hasOutput ? 'data-download-url="' . htmlspecialchars($downloadUrl) . '"' : 'disabled'; ?>>
                    <svg class="icon-download" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                    Download
                </button>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="results-main">
        <!-- Hero Section -->
        <section class="container results-hero">
            <div class="results-copy fade-in">
                <span class="badge"><?php echo htmlspecialchars($hasOutput ? 'AI short generated' : 'AI short pending'); ?></span>
                <h1><?php echo htmlspecialchars($hasOutput ? 'Your YouTube-ready short is ready.' : 'Your short is not ready yet.'); ?></h1>
                <p><?php echo htmlspecialchars($hasOutput ? 'Review the generated short, then download it when you are happy with the result.' : 'The AI job is still queued, processing, or needs the Python worker to run. Check the dashboard for status.'); ?></p>
                <div class="results-actions">
                    <button class="btn btn-secondary btn-lg" id="downloadBtnHero" <?php echo $hasOutput ? 'data-download-url="' . htmlspecialchars($downloadUrl) . '"' : 'disabled'; ?>>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                        Download
                    </button>
                </div>
            </div>

            <?php if ($hasOutput && $sourceUrl): ?>
            <div class="result-video-card comparison-hero-card fade-in">
                <div class="media-label">Input and output <span>FINAL</span></div>
                <div class="source-preview-card">
                    <article class="compare-video-panel"><div class="compare-label"><strong>Original upload</strong><span>Source</span></div><video class="source-video" src="<?php echo htmlspecialchars($sourceUrl); ?>" preload="metadata" controls playsinline></video></article>
                    <article class="compare-video-panel"><div class="compare-label"><strong>Edited highlight</strong><span class="ready-label">Final output</span></div><video class="source-video" src="<?php echo htmlspecialchars($downloadUrl); ?>" <?php echo $thumbnailUrl ? 'poster="' . htmlspecialchars($thumbnailUrl) . '"' : ''; ?> preload="metadata" controls playsinline></video></article>
                </div>
                <div class="video-meta-row"><span><?php echo $outputWidth && $outputHeight ? htmlspecialchars($outputWidth . '×' . $outputHeight) : 'MP4'; ?></span><span>Ready</span><span>H.264 MP4</span></div>
            </div>
            <?php else: ?>
            <div class="result-video-card fade-in"><div class="media-label">Edited highlight <span><?php echo max(0, $progress); ?>%</span></div><div class="short-frame"><div class="short-art"></div></div><div class="video-meta-row"><span>MP4</span><span>Processing</span><span>Please keep this page open</span></div></div>
            <?php endif; ?>
        </section>

        <!-- Results Grid Section -->
        <section class="container results-grid">
            <!-- AI Summary Panel -->
            <div class="result-panel ai-summary stagger-1">
                <div class="section-header-small">
                    <h3>AI Summary</h3>
                    <span class="<?php echo htmlspecialchars($statusClass); ?> result-status"><?php echo htmlspecialchars($statusText); ?></span>
                </div>
                <div class="summary-grid">
                    <div class="summary-item">
                        <span>Original Video</span>
                        <strong><?php echo htmlspecialchars($videoDuration); ?></strong>
                    </div>
                    <div class="summary-item">
                        <span>Output Video</span>
                        <strong><?php echo $hasOutput ? 'Generated' : 'Pending'; ?></strong>
                    </div>
                    <div class="summary-item">
                        <span>Highlights Found</span>
                        <strong><?php echo $hasOutput ? 'Selected' : 'Waiting'; ?></strong>
                    </div>
                    <div class="summary-item">
                        <span>Style</span>
                        <strong><?php echo htmlspecialchars($result['description'] ?? 'Default'); ?></strong>
                    </div>
                </div>
                <ul class="result-checklist">
                    <li><span>Subtitles</span><strong>Optional</strong></li>
                    <li><span>Audio</span><strong>Source preserved</strong></li>
                    <li><span>Thumbnail</span><strong><?php echo $thumbnailUrl ? 'Generated' : 'Unavailable'; ?></strong></li>
                    <li><span>Format</span><strong>H.264 MP4</strong></li>
                </ul>
            </div>

            <!-- Titles and Hashtags Panel -->
            <div class="result-panel stagger-2">
                <h3>Suggested Title</h3>
                <div class="copy-box" id="copyTitleText">
                    <?php echo htmlspecialchars($title); ?>
                    <button class="btn-copy" onclick="copyToClipboard(<?php echo htmlspecialchars(json_encode($title), ENT_QUOTES, 'UTF-8'); ?>)" aria-label="Copy Title">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    </button>
                </div>
                <h3>Hashtags</h3>
                <div class="copy-box small" id="copyTagsText">
                    #valorant #clutch #gaming #shorts #gamecut
                    <button class="btn-copy" onclick="copyToClipboard('#valorant #clutch #gaming #shorts #gamecut')" aria-label="Copy Hashtags">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    </button>
                </div>
            </div>

            <!-- Thumbnail Panel -->
            <div class="result-panel thumbnail-panel stagger-3">
                <h3>Generated Thumbnail</h3>
                <div class="thumbnail-preview" <?php echo $thumbnailUrl ? 'style="background-image:url(\'' . htmlspecialchars($thumbnailUrl, ENT_QUOTES) . '\')"' : ''; ?>>
                    <?php if (!$thumbnailUrl): ?><span>Thumbnail unavailable</span><?php endif; ?>
                </div>
                <?php if ($thumbnailUrl): ?><a class="btn btn-secondary thumbnail-download" href="<?php echo htmlspecialchars($thumbnailUrl); ?>" download="gamecut-thumbnail.jpg">Download thumbnail</a><?php endif; ?>
            </div>
        </section>
    </main>

    <!-- Notification Toast -->
    <div class="toast" id="exportToast">
        <div class="toast-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>
        </div>
        <div class="toast-content">
            <h4>Download started</h4>
            <p>Your AI-generated short is being prepared.</p>
        </div>
        <button class="icon-btn" onclick="this.parentElement.classList.remove('show')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
    </div>

    <script src="js/app.js"></script>
    <script src="js/preview.js"></script>
</body>
</html>
