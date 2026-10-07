<?php
require_once 'php/bootstrap.php';
require_once 'php/config.php';
require_once 'php/session.php';

requireAuth();

$currentUser = getCurrentUser();
$adminEmails = configEmailList('GAMECUT_ADMIN_EMAILS');
if (!in_array($currentUser['email'] ?? '', $adminEmails, true)) {
    http_response_code(403);
    echo 'Forbidden';
    exit();
}

$stats = [
    'users' => 0,
    'uploads' => 0,
    'videos' => 0,
    'storage' => '0 MB',
];
$recentJobs = [];

function adminFormatStorage($bytes) {
    if ($bytes >= 1073741824) {
        return round($bytes / 1073741824, 2) . ' GB';
    }

    if ($bytes >= 1048576) {
        return round($bytes / 1048576, 2) . ' MB';
    }

    if ($bytes >= 1024) {
        return round($bytes / 1024, 2) . ' KB';
    }

    return (int)$bytes . ' B';
}

try {
    $stats['users'] = (int)$pdo->query("SELECT COUNT(*) FROM users")->fetchColumn();
    $stats['uploads'] = (int)$pdo->query("SELECT COUNT(*) FROM projects")->fetchColumn();
    $stats['videos'] = (int)$pdo->query("SELECT COUNT(*) FROM videos WHERE deleted_at IS NULL")->fetchColumn();
    $stats['storage'] = adminFormatStorage((int)$pdo->query("SELECT COALESCE(SUM(file_size), 0) FROM videos WHERE deleted_at IS NULL")->fetchColumn());

    $stmt = $pdo->query(
        "SELECT j.id, j.status, j.job_type, j.created_at, p.project_name, u.username
         FROM ai_jobs j
         JOIN projects p ON p.id = j.project_id
         JOIN users u ON u.id = j.user_id
         ORDER BY j.created_at DESC
         LIMIT 8"
    );
    $recentJobs = $stmt->fetchAll();
} catch (PDOException $e) {
    error_log('Admin dashboard error: ' . $e->getMessage());
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - GameCut AI</title>
    <script src="js/theme-init.js"></script>
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/dashboard.css">
    <link rel="stylesheet" href="css/responsive.css">
</head>
<body class="dashboard-body">
    <aside class="sidebar">
        <div class="sidebar-header">
            <a href="dashboard.php" class="logo">
                <span>GameCut <span class="text-gradient">AI</span></span>
            </a>
        </div>
        <nav class="sidebar-nav">
            <a href="dashboard.php" class="nav-item"><span>Dashboard</span></a>
            <a href="projects.php" class="nav-item"><span>Projects</span></a>
            <a href="upload.php" class="nav-item"><span>Upload</span></a>
            <a href="admin.php" class="nav-item active"><span>Admin</span></a>
            <a href="php/logout.php" class="nav-item"><span>Logout</span></a>
        </nav>
    </aside>

    <main class="main-content">
        <header class="topbar">
            <div class="page-title">
                <h2>Admin Overview</h2>
            </div>
        </header>

        <div class="content-wrapper">
            <div class="stats-grid fade-in">
                <div class="stat-card">
                    <div class="stat-details">
                        <span class="stat-label">Total Users</span>
                        <h3 class="stat-value"><?php echo (int)$stats['users']; ?></h3>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-details">
                        <span class="stat-label">Total Uploads</span>
                        <h3 class="stat-value"><?php echo (int)$stats['uploads']; ?></h3>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-details">
                        <span class="stat-label">Total Videos</span>
                        <h3 class="stat-value"><?php echo (int)$stats['videos']; ?></h3>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-details">
                        <span class="stat-label">Storage Used</span>
                        <h3 class="stat-value"><?php echo htmlspecialchars($stats['storage']); ?></h3>
                    </div>
                </div>
            </div>

            <section class="recent-projects fade-in">
                <div class="section-header-small">
                    <h3>Recent AI Jobs</h3>
                </div>

                <?php if (empty($recentJobs)): ?>
                    <div class="empty-state">
                        <h4>No AI jobs yet</h4>
                        <p>Queued upload jobs will appear here.</p>
                    </div>
                <?php else: ?>
                    <div class="admin-table-wrap">
                        <table class="admin-table">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Project</th>
                                    <th>User</th>
                                    <th>Type</th>
                                    <th>Status</th>
                                    <th>Created</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php foreach ($recentJobs as $job): ?>
                                    <tr>
                                        <td>#<?php echo (int)$job['id']; ?></td>
                                        <td><?php echo htmlspecialchars($job['project_name']); ?></td>
                                        <td><?php echo htmlspecialchars($job['username']); ?></td>
                                        <td><?php echo htmlspecialchars($job['job_type']); ?></td>
                                        <td><span class="project-status status-draft"><?php echo htmlspecialchars(ucfirst($job['status'])); ?></span></td>
                                        <td><?php echo htmlspecialchars(date('M j, g:i A', strtotime($job['created_at']))); ?></td>
                                    </tr>
                                <?php endforeach; ?>
                            </tbody>
                        </table>
                    </div>
                <?php endif; ?>
            </section>
        </div>
    </main>
    <script src="js/app.js"></script>
</body>
</html>
