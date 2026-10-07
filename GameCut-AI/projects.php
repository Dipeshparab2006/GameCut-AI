<?php
require_once 'php/bootstrap.php';
require_once 'php/config.php';
require_once 'php/session.php';
require_once 'php/helpers.php';

// Require authentication
requireAuth();

// Get current user data
$currentUser = getCurrentUser();
$userId = (int)($currentUser['id'] ?? 0);
$projects = [];

function projectsFormatSize($bytes) {
    if ($bytes >= 1073741824) {
        return round($bytes / 1073741824, 1) . ' GB';
    }
    if ($bytes >= 1048576) {
        return round($bytes / 1048576, 1) . ' MB';
    }
    if ($bytes >= 1024) {
        return round($bytes / 1024, 1) . ' KB';
    }
    return (int)$bytes . ' B';
}

try {
    $stmt = $pdo->prepare(
        "SELECT p.id, p.project_name, p.description, p.status AS project_status, p.created_at,
                v.file_size, v.output_path, latest_job.status AS job_status, latest_job.progress
         FROM projects p
         LEFT JOIN videos v ON v.project_id = p.id
         LEFT JOIN (
             SELECT j1.video_id, j1.status, j1.progress
             FROM ai_jobs j1
             INNER JOIN (
                 SELECT video_id, MAX(id) AS latest_id
                 FROM ai_jobs
                 GROUP BY video_id
             ) newest ON newest.video_id = j1.video_id AND newest.latest_id = j1.id
         ) latest_job ON latest_job.video_id = v.id
         WHERE p.user_id = ? AND p.delete_requested_at IS NULL
         ORDER BY p.created_at DESC"
    );
    $stmt->execute([$userId]);
    $projects = $stmt->fetchAll();
} catch (PDOException $e) {
    error_log('Projects load error: ' . $e->getMessage());
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Shorts Library - GameCut AI</title>
    <script src="js/theme-init.js"></script>
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/dashboard.css">
    <link rel="stylesheet" href="css/responsive.css">
    <style>
        .projects-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
        }

        .projects-filters {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .filter-btn {
            background: var(--card);
            border: 1px solid var(--border);
            color: var(--text-muted);
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            cursor: pointer;
            transition: var(--transition);
        }

        .filter-btn:hover {
            border-color: var(--border-light);
            color: var(--text);
        }

        .filter-btn.active {
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }

        .projects-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 1.5rem;
        }

        .project-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            transition: var(--transition);
            display: flex;
            flex-direction: column;
        }

        .project-card:hover {
            transform: translateY(-5px);
            border-color: var(--border-light);
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }

        .project-thumb {
            width: 100%;
            aspect-ratio: 16/9;
            background-color: #111;
            position: relative;
            background-size: cover;
            background-position: center;
        }

        .project-thumb.draft-thumb {
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--background);
            color: var(--border-light);
        }

        .project-duration {
            position: absolute;
            bottom: 8px;
            right: 8px;
            background: rgba(0,0,0,0.8);
            color: white;
            font-size: 0.75rem;
            padding: 0.1rem 0.4rem;
            border-radius: 4px;
            font-variant-numeric: tabular-nums;
        }

        .project-details {
            padding: 1.25rem;
            flex: 1;
            display: flex;
            flex-direction: column;
        }

        .project-title {
            font-size: 1rem;
            margin-bottom: 0.5rem;
            font-weight: 600;
        }

        .project-meta-info {
            font-size: 0.875rem;
            color: var(--text-muted);
            margin-bottom: 1rem;
            flex: 1;
        }

        .project-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
            gap: 0.75rem;
        }

        @media (max-width: 768px) {
            .projects-header {
                flex-direction: column;
                align-items: stretch;
                gap: 1rem;
            }

            .projects-filters {
                overflow-x: auto;
                padding-bottom: 0.25rem;
                scrollbar-width: thin;
            }

            .filter-btn {
                white-space: nowrap;
            }
        }

        @media (max-width: 400px) {
            .projects-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body class="dashboard-body">
    <!-- Sidebar -->
    <aside class="sidebar">
        <div class="sidebar-header">
            <a href="index.php" class="logo">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="url(#paint0_linear_p)" />
                    <path d="M2 17L12 22L22 17" stroke="url(#paint1_linear_p)" stroke-width="2" stroke-linecap="round"/>
                    <path d="M2 12L12 17L22 12" stroke="url(#paint2_linear_p)" stroke-width="2" stroke-linecap="round"/>
                    <defs>
                        <linearGradient id="paint0_linear_p" x1="12" y1="2" x2="12" y2="12" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                        <linearGradient id="paint1_linear_p" x1="12" y1="17" x2="12" y2="22" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                        <linearGradient id="paint2_linear_p" x1="12" y1="12" x2="12" y2="17" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                    </defs>
                </svg>
                <span>GameCut <span class="text-gradient">AI</span></span>
            </a>
        </div>
        
        <nav class="sidebar-nav">
            <a href="dashboard.php" class="nav-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
                <span>Dashboard</span>
            </a>
            <a href="projects.php" class="nav-item active">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
                <span>Projects</span>
            </a>
            <a href="upload.php" class="nav-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                <span>Upload</span>
            </a>
            <a href="upload.php" class="nav-item"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line></svg><span>AI Styles</span></a>
            <a href="preview.php" class="nav-item"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg><span>Results</span></a>
            <a href="settings.php" class="nav-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
                <span>Settings</span>
            </a>
        </nav>
    </aside>

    <!-- Main Content -->
    <main class="main-content">
        <header class="topbar">
            <div class="search-bar">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                <input type="text" placeholder="Search shorts...">
            </div>
            
            <div class="topbar-actions">
                <div class="profile-dropdown">
                    <div class="avatar">
                        <img src="https://ui-avatars.com/api/?name=<?php echo urlencode($currentUser['username'] ?? 'User'); ?>&background=7C3AED&color=fff" alt="User Avatar">
                    </div>
                </div>
            </div>
        </header>

        <div class="content-wrapper">
            <div class="projects-header">
                <h2>AI Shorts Library</h2>
                <a href="upload.php" class="btn btn-primary">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                    Generate Short
                </a>
            </div>

            <div class="projects-filters">
                <button class="filter-btn active">All Projects</button>
                <button class="filter-btn">Ready</button>
                <button class="filter-btn">Processing</button>
            </div>

            <div class="projects-grid fade-in">
                <?php if (empty($projects)): ?>
                    <div class="empty-state">
                        <h4>No projects yet</h4>
                        <p>Your uploaded gameplay projects will appear here.</p>
                        <a href="upload.php" class="btn btn-primary">Upload Gameplay</a>
                    </div>
                <?php else: ?>
                    <?php foreach ($projects as $project): ?>
                        <?php
                            $jobStatus = $project['job_status'] ?: $project['project_status'];
                            $isReady = $project['project_status'] === 'completed' && !empty($project['output_path']);
                            $statusKey = $isReady ? 'ready' : ($jobStatus === 'failed' ? 'failed' : (($jobStatus === 'processing') ? 'processing' : 'queued'));
                            $statusClass = $isReady ? 'status-done' : ($jobStatus === 'failed' ? 'status-failed' : 'status-processing');
                            $statusLabel = $isReady ? 'Ready' : ($jobStatus === 'failed' ? 'Failed' : ($jobStatus === 'processing' ? 'Processing' : 'Queued'));
                            if ($jobStatus === 'processing') {
                                $statusLabel .= ' (' . (int)$project['progress'] . '%)';
                            }
                        ?>
                        <div class="project-card" data-project-status="<?php echo htmlspecialchars($statusKey); ?>">
                            <div class="project-thumb <?php echo $isReady ? '' : 'draft-thumb'; ?>" <?php echo $isReady ? 'style="background-image:url(\'api/media.php?project_id=' . (int)$project['id'] . '&type=thumbnail\')"' : ''; ?>>
                                <?php if (!$isReady): ?><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg><?php endif; ?>
                            </div>
                            <div class="project-details">
                                <h4 class="project-title"><?php echo htmlspecialchars($project['project_name']); ?></h4>
                                <div class="project-meta-info">
                                    Uploaded <?php echo htmlspecialchars(date('M j, Y', strtotime($project['created_at']))); ?>
                                    <?php if (!empty($project['file_size'])): ?>
                                        • <?php echo htmlspecialchars(projectsFormatSize((int)$project['file_size'])); ?>
                                    <?php endif; ?>
                                </div>
                                <div class="project-footer">
                                    <span class="project-status <?php echo htmlspecialchars($statusClass); ?>" style="padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600;"><?php echo htmlspecialchars($statusLabel); ?></span>
                                    <div style="display:flex; gap:.4rem; align-items:center;">
                                        <a href="<?php echo $isReady ? 'preview.php?project_id=' . (int)$project['id'] : 'processing.php?project_id=' . (int)$project['id']; ?>" class="btn btn-outline btn-sm" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;"><?php echo $isReady ? 'View' : 'Status'; ?></a>
                                        <button type="button" class="btn btn-outline btn-sm delete-project-btn" data-project-id="<?php echo (int)$project['id']; ?>" data-csrf="<?php echo htmlspecialchars(csrfToken(), ENT_QUOTES, 'UTF-8'); ?>" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; color:#ef4444;">Delete</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    <?php endforeach; ?>
                <?php endif; ?>
            </div>
        </div>
    </main>

    <script src="js/app.js"></script>
    <script src="js/projects.js"></script>
    <script>
        document.querySelectorAll('.filter-btn').forEach(btn => btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const label = btn.textContent.trim().toLowerCase();
            const filter = label.startsWith('ready') ? 'ready' : (label.startsWith('processing') ? 'processing' : 'all');
            document.querySelectorAll('.project-card').forEach(card => { card.hidden = filter !== 'all' && card.dataset.projectStatus !== filter; });
        }));
    </script>
</body>
</html>
