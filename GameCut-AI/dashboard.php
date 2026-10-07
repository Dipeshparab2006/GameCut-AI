<?php
require_once 'php/bootstrap.php';
require_once 'php/config.php';
require_once 'php/session.php';

// Require authentication
requireAuth();

// Get current user data
$currentUser = getCurrentUser();
$flash = getFlashMessage();
$userId = (int)($currentUser['id'] ?? 0);
$displayName = trim($currentUser['username'] ?? 'Creator');
$firstName = preg_split('/\s+/', $displayName)[0] ?? 'Creator';
$adminEmails = configEmailList('GAMECUT_ADMIN_EMAILS');
$isAdminUser = in_array($currentUser['email'] ?? '', $adminEmails, true);
$dashboardStats = [
    'completedVideos' => 0,
    'storageBytes' => 0,
    'storageLabel' => '0 MB',
    'storagePercent' => 0,
    'lastLogin' => 'First login',
    'lastUpload' => 'No uploads yet',
    'processingStatus' => 'Idle',
    'queuePosition' => 'Not queued',
];
$recentProjects = [];

function formatStorageSize($bytes) {
    if ($bytes >= 1073741824) {
        return round($bytes / 1073741824, 1) . ' GB';
    }

    if ($bytes >= 1048576) {
        return round($bytes / 1048576, 1) . ' MB';
    }

    if ($bytes >= 1024) {
        return round($bytes / 1024, 1) . ' KB';
    }

    return $bytes . ' B';
}

function formatRelativeDate($dateValue) {
    if (!$dateValue) {
        return 'Recently';
    }

    $timestamp = strtotime($dateValue);
    $diff = time() - $timestamp;

    if ($diff < 60) {
        return 'Just now';
    }

    if ($diff < 3600) {
        return floor($diff / 60) . ' min ago';
    }

    if ($diff < 86400) {
        return floor($diff / 3600) . ' hours ago';
    }

    return date('M j, Y', $timestamp);
}

try {
    $stmt = $pdo->prepare("SELECT COUNT(*) FROM videos v JOIN projects p ON p.id = v.project_id WHERE v.user_id = ? AND v.status = 'processed' AND p.delete_requested_at IS NULL");
    $stmt->execute([$userId]);
    $dashboardStats['completedVideos'] = (int)$stmt->fetchColumn();

    $stmt = $pdo->prepare("SELECT COALESCE(SUM(v.file_size), 0) FROM videos v JOIN projects p ON p.id = v.project_id WHERE v.user_id = ? AND v.deleted_at IS NULL AND p.delete_requested_at IS NULL");
    $stmt->execute([$userId]);
    $dashboardStats['storageBytes'] = (int)$stmt->fetchColumn();
    $dashboardStats['storageLabel'] = formatStorageSize($dashboardStats['storageBytes']);
    $dashboardStats['storagePercent'] = min(100, round(($dashboardStats['storageBytes'] / (20 * 1073741824)) * 100));

    $stmt = $pdo->prepare("SELECT last_login FROM users WHERE id = ?");
    $stmt->execute([$userId]);
    $lastLogin = $stmt->fetchColumn();

    if ($lastLogin) {
        $dashboardStats['lastLogin'] = date('M j, g:i A', strtotime($lastLogin));
    }

    $stmt = $pdo->prepare("SELECT v.created_at FROM videos v JOIN projects p ON p.id = v.project_id WHERE v.user_id = ? AND v.deleted_at IS NULL AND p.delete_requested_at IS NULL ORDER BY v.created_at DESC LIMIT 1");
    $stmt->execute([$userId]);
    $lastUpload = $stmt->fetchColumn();
    if ($lastUpload) {
        $dashboardStats['lastUpload'] = formatRelativeDate($lastUpload);
    }

    $stmt = $pdo->prepare(
        "SELECT id, status FROM ai_jobs
         WHERE user_id = ?
         ORDER BY FIELD(status, 'processing', 'queued', 'failed', 'completed', 'cancelled'), created_at DESC
         LIMIT 1"
    );
    $stmt->execute([$userId]);
    $latestJob = $stmt->fetch();
    if ($latestJob) {
        $dashboardStats['processingStatus'] = ucfirst($latestJob['status']);

        if ($latestJob['status'] === 'queued') {
            $stmt = $pdo->prepare("SELECT COUNT(*) FROM ai_jobs WHERE status = 'queued' AND id <= ?");
            $stmt->execute([(int)$latestJob['id']]);
            $dashboardStats['queuePosition'] = '#' . (int)$stmt->fetchColumn();
        } elseif ($latestJob['status'] === 'processing') {
            $dashboardStats['queuePosition'] = 'Now processing';
        }
    }

    $stmt = $pdo->prepare(
        "SELECT p.id, p.project_name, p.status, p.created_at, v.original_filename, v.file_size, v.mime_type
         FROM projects p
         LEFT JOIN videos v ON v.project_id = p.id
         WHERE p.user_id = ? AND p.delete_requested_at IS NULL
         ORDER BY p.created_at DESC
         LIMIT 3"
    );
    $stmt->execute([$userId]);
    $recentProjects = $stmt->fetchAll();
} catch (PDOException $e) {
    error_log("Dashboard stats error: " . $e->getMessage());
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - GameCut AI</title>
    <script src="js/theme-init.js"></script>
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/dashboard.css">
    <link rel="stylesheet" href="css/responsive.css">
</head>
<body class="dashboard-body">
    <!-- Sidebar -->
    <aside class="sidebar">
        <div class="sidebar-header">
            <a href="index.php" class="logo">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="url(#paint0_linear_dash)" />
                    <path d="M2 17L12 22L22 17" stroke="url(#paint1_linear_dash)" stroke-width="2" stroke-linecap="round"/>
                    <path d="M2 12L12 17L22 12" stroke="url(#paint2_linear_dash)" stroke-width="2" stroke-linecap="round"/>
                    <defs>
                        <linearGradient id="paint0_linear_dash" x1="12" y1="2" x2="12" y2="12" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                        <linearGradient id="paint1_linear_dash" x1="12" y1="17" x2="12" y2="22" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                        <linearGradient id="paint2_linear_dash" x1="12" y1="12" x2="12" y2="17" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                    </defs>
                </svg>
                <span>GameCut <span class="text-gradient">AI</span></span>
            </a>
        </div>
        
        <nav class="sidebar-nav">
            <a href="dashboard.php" class="nav-item active">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
                <span>Dashboard</span>
            </a>
            <a href="projects.php" class="nav-item">
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
            <?php if ($isAdminUser): ?>
                <a href="admin.php" class="nav-item">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l7 4v6c0 5-3 9-7 10-4-1-7-5-7-10V6l7-4z"></path></svg>
                    <span>Admin</span>
                </a>
            <?php endif; ?>
        </nav>

        <div class="sidebar-footer">
            <div class="storage-info">
                <div class="storage-header">
                    <span>Storage</span>
                    <span><?php echo htmlspecialchars($dashboardStats['storageLabel']); ?> / 20GB</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: <?php echo (int)$dashboardStats['storagePercent']; ?>%"></div>
                </div>
            </div>
            <a href="settings.php" class="btn btn-outline w-100">Manage Plan</a>
        </div>
    </aside>

    <!-- Main Content -->
    <main class="main-content">
        <!-- Topbar -->
        <header class="topbar">
            <div class="search-bar">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                <input type="text" placeholder="Search shorts, games, styles...">
            </div>
            
            <div class="topbar-actions">
                <button class="icon-btn">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
                    <span class="notification-badge">3</span>
                </button>
                <div class="profile-dropdown">
                    <div class="avatar">
                        <img src="https://ui-avatars.com/api/?name=<?php echo urlencode($currentUser['username'] ?? 'User'); ?>&background=7C3AED&color=fff" alt="User Avatar">
                    </div>
                    <span>Pro Member</span>
                </div>
            </div>
        </header>

        <!-- Dashboard Content -->
        <div class="content-wrapper">
            <?php if ($flash): ?>
                <div class="dashboard-alert dashboard-alert-<?php echo htmlspecialchars($flash['type']); ?>">
                    <?php echo htmlspecialchars($flash['message']); ?>
                </div>
            <?php endif; ?>

            <div class="page-header">
                <h2>Welcome, <?php echo htmlspecialchars($firstName); ?> 👋</h2>
                <a href="upload.php" class="btn btn-primary">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                    Generate Short
                </a>
            </div>

            <!-- Stat Cards -->
            <div class="stats-grid fade-in">
                <div class="stat-card">
                    <div class="stat-icon bg-primary-light">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>
                    </div>
                    <div class="stat-details">
                        <span class="stat-label">Last Upload</span>
                        <h3 class="stat-value stat-value-text"><?php echo htmlspecialchars($dashboardStats['lastUpload']); ?></h3>
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-icon bg-success-light">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                    </div>
                    <div class="stat-details">
                        <span class="stat-label">Processing Status</span>
                        <h3 class="stat-value stat-value-text"><?php echo htmlspecialchars($dashboardStats['processingStatus']); ?></h3>
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-icon bg-warning-light">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                    </div>
                    <div class="stat-details">
                        <span class="stat-label">Queue Position</span>
                        <h3 class="stat-value stat-value-text"><?php echo htmlspecialchars($dashboardStats['queuePosition']); ?></h3>
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-icon bg-secondary-light">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--secondary)" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>
                    </div>
                    <div class="stat-details">
                        <span class="stat-label">Storage Used</span>
                        <h3 class="stat-value"><?php echo htmlspecialchars($dashboardStats['storageLabel']); ?></h3>
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-icon bg-primary-light">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2"><path d="M9 12l2 2 4-4"></path><circle cx="12" cy="12" r="10"></circle></svg>
                    </div>
                    <div class="stat-details">
                        <span class="stat-label">Completed Videos</span>
                        <h3 class="stat-value counter" data-target="<?php echo (int)$dashboardStats['completedVideos']; ?>">0</h3>
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-icon bg-warning-light">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" stroke-width="2"><path d="M12 6v6l4 2"></path><circle cx="12" cy="12" r="10"></circle></svg>
                    </div>
                    <div class="stat-details">
                        <span class="stat-label">Last Login</span>
                        <h3 class="stat-value stat-value-text"><?php echo htmlspecialchars($dashboardStats['lastLogin']); ?></h3>
                    </div>
                </div>
            </div>

            <!-- Main Grid -->
            <div class="dashboard-grid">
                <!-- Recent AI Shorts -->
                <div class="recent-projects fade-in" style="animation-delay: 0.1s;">
                    <div class="section-header-small">
                        <h3>Recent AI Shorts</h3>
                        <a href="projects.php" class="view-all">View All</a>
                    </div>
                    
                    <div class="project-list">
                        <?php if (empty($recentProjects)): ?>
                            <div class="empty-state">
                                <h4>No uploads yet</h4>
                                <p>Your uploaded gameplay projects will appear here.</p>
                                <a href="upload.php" class="btn btn-primary">Upload Gameplay</a>
                            </div>
                        <?php else: ?>
                            <?php foreach ($recentProjects as $project): ?>
                                <div class="project-item">
                                    <div class="project-thumbnail bg-card">
                                        <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="var(--border-light)" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg>
                                    </div>
                                    <div class="project-info">
                                        <h4><?php echo htmlspecialchars($project['project_name']); ?></h4>
                                        <span class="project-meta">
                                            Uploaded <?php echo htmlspecialchars(formatRelativeDate($project['created_at'])); ?>
                                            <?php if (!empty($project['file_size'])): ?>
                                                • <?php echo htmlspecialchars(formatStorageSize((int)$project['file_size'])); ?>
                                            <?php endif; ?>
                                        </span>
                                    </div>
                                    <?php $dashboardStatus = ($project['status'] === 'completed') ? 'Ready' : (($project['status'] === 'processing') ? 'Processing' : (($project['status'] === 'failed') ? 'Failed' : 'Queued')); ?>
                                    <div class="project-status <?php echo $dashboardStatus === 'Ready' ? 'status-done' : ($dashboardStatus === 'Failed' ? 'status-failed' : 'status-processing'); ?>"><?php echo htmlspecialchars($dashboardStatus); ?></div>
                                    <button class="icon-btn" data-toast="Project menu opened" type="button"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"></circle><circle cx="12" cy="5" r="1"></circle><circle cx="12" cy="19" r="1"></circle></svg></button>
                                </div>
                            <?php endforeach; ?>
                        <?php endif; ?>
                    </div>
                </div>

                <!-- Activity Chart (Visual Only) -->
                <div class="activity-chart fade-in" style="animation-delay: 0.2s;">
                    <div class="section-header-small">
                        <h3>Content Output</h3>
                        <select class="custom-select">
                            <option>This Week</option>
                            <option>This Month</option>
                        </select>
                    </div>
                    
                    <div class="fake-chart">
                        <div class="bar" style="height: 40%"><span>Mon</span></div>
                        <div class="bar" style="height: 60%"><span>Tue</span></div>
                        <div class="bar" style="height: 30%"><span>Wed</span></div>
                        <div class="bar" style="height: 80%"><span>Thu</span></div>
                        <div class="bar" style="height: 50%"><span>Fri</span></div>
                        <div class="bar" style="height: 90%"><div class="bar-tooltip">12 Videos</div><span>Sat</span></div>
                        <div class="bar" style="height: 70%"><span>Sun</span></div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <script src="js/app.js"></script>
    <script src="js/dashboard.js"></script>
</body>
</html>
