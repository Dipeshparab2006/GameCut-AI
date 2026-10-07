<?php
require_once 'php/bootstrap.php';
require_once 'php/config.php';
require_once 'php/session.php';

// Require authentication
requireAuth();

// Get current user data
$currentUser = getCurrentUser();
$userId = (int)($currentUser['id'] ?? 0);
$flash = getFlashMessage();

function checkedAttr($value) {
    return (int)$value === 1 ? 'checked' : '';
}

function selectedAttr($actual, $expected) {
    return (string)$actual === (string)$expected ? 'selected' : '';
}

function settingValue($settings, $key, $default = '') {
    return $settings[$key] ?? $default;
}

function settingResponse($type, $message, $tab = 'appearance') {
    $allowedTabs = ['appearance', 'profile', 'notifications', 'security', 'permissions', 'preferences'];
    if (!in_array($tab, $allowedTabs, true)) {
        $tab = 'appearance';
    }

    setFlashMessage($type, $message);
    header('Location: settings.php?tab=' . urlencode($tab));
    exit();
}

$allowedTabs = ['appearance', 'profile', 'notifications', 'security', 'permissions', 'preferences'];
$activeTab = in_array($_GET['tab'] ?? 'appearance', $allowedTabs, true) ? $_GET['tab'] : 'appearance';

try {
    $stmt = $pdo->prepare("INSERT IGNORE INTO user_settings (user_id) VALUES (?)");
    $stmt->execute([$userId]);

    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        if (!verifyCsrfToken($_POST['csrf_token'] ?? '')) {
            settingResponse('error', 'Your session expired. Please try again.');
        }

        $section = $_POST['settings_section'] ?? '';
        $activeTab = in_array($section, $allowedTabs, true) ? $section : 'appearance';

        if ($section === 'profile') {
            $name = trim($_POST['username'] ?? '');
            $email = trim($_POST['email'] ?? '');
            $bio = trim($_POST['bio'] ?? '');
            $avatarPath = null;

            if ($name === '' || strlen($name) < 2) {
                settingResponse('error', 'Name must be at least 2 characters.', 'profile');
            }

            if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
                settingResponse('error', 'Please enter a valid email address.', 'profile');
            }

            $stmt = $pdo->prepare("SELECT COUNT(*) FROM users WHERE email = ? AND id <> ?");
            $stmt->execute([$email, $userId]);
            if ((int)$stmt->fetchColumn() > 0) {
                settingResponse('error', 'That email is already used by another account.', 'profile');
            }

            if (!empty($_FILES['avatar']['name']) && $_FILES['avatar']['error'] === UPLOAD_ERR_OK) {
                $allowedAvatarTypes = ['image/jpeg' => 'jpg', 'image/png' => 'png', 'image/webp' => 'webp'];
                $avatarMime = mime_content_type($_FILES['avatar']['tmp_name']);

                if (!isset($allowedAvatarTypes[$avatarMime]) || $_FILES['avatar']['size'] > 2 * 1024 * 1024) {
                    settingResponse('error', 'Avatar must be JPG, PNG, or WEBP and under 2MB.', 'profile');
                }

                $avatarDir = __DIR__ . DIRECTORY_SEPARATOR . 'images' . DIRECTORY_SEPARATOR . 'avatars';
                if (!is_dir($avatarDir)) {
                    mkdir($avatarDir, 0775, true);
                }

                $avatarName = 'avatar_user_' . $userId . '_' . date('YmdHis') . '.' . $allowedAvatarTypes[$avatarMime];
                $avatarTarget = $avatarDir . DIRECTORY_SEPARATOR . $avatarName;

                if (!move_uploaded_file($_FILES['avatar']['tmp_name'], $avatarTarget)) {
                    settingResponse('error', 'Avatar upload failed. Please try again.', 'profile');
                }

                $avatarPath = 'images/avatars/' . $avatarName;
            }

            $pdo->beginTransaction();
            $stmt = $pdo->prepare("UPDATE users SET username = ?, email = ? WHERE id = ?");
            $stmt->execute([$name, $email, $userId]);

            $_SESSION['username'] = $name;
            $_SESSION['email'] = $email;

            if ($avatarPath) {
                $stmt = $pdo->prepare("UPDATE user_settings SET bio = ?, avatar_path = ? WHERE user_id = ?");
                $stmt->execute([$bio, $avatarPath, $userId]);
            } else {
                $stmt = $pdo->prepare("UPDATE user_settings SET bio = ? WHERE user_id = ?");
                $stmt->execute([$bio, $userId]);
            }

            $pdo->commit();
            settingResponse('success', 'Profile saved.', 'profile');
        }

        if ($section === 'appearance') {
            $theme = in_array($_POST['theme'] ?? 'system', ['light', 'dark', 'system'], true) ? $_POST['theme'] : 'system';
            $fontSize = in_array($_POST['font_size'] ?? 'comfortable', ['comfortable', 'large', 'compact'], true) ? $_POST['font_size'] : 'comfortable';
            $compactMode = isset($_POST['compact_mode']) ? 1 : 0;
            $accentColor = preg_match('/^#[0-9A-Fa-f]{6}$/', $_POST['accent_color'] ?? '') ? $_POST['accent_color'] : '#7C3AED';

            $stmt = $pdo->prepare("UPDATE user_settings SET theme = ?, font_size = ?, compact_mode = ?, accent_color = ? WHERE user_id = ?");
            $stmt->execute([$theme, $fontSize, $compactMode, $accentColor, $userId]);
            settingResponse('success', 'Appearance saved.', 'appearance');
        }

        if ($section === 'notifications') {
            $stmt = $pdo->prepare("UPDATE user_settings SET email_notifications = ?, push_notifications = ?, marketing_updates = ? WHERE user_id = ?");
            $stmt->execute([
                isset($_POST['email_notifications']) ? 1 : 0,
                isset($_POST['push_notifications']) ? 1 : 0,
                isset($_POST['marketing_updates']) ? 1 : 0,
                $userId
            ]);
            settingResponse('success', 'Notifications saved.', 'notifications');
        }

        if ($section === 'security') {
            $stmt = $pdo->prepare("UPDATE user_settings SET two_factor_enabled = ? WHERE user_id = ?");
            $stmt->execute([isset($_POST['two_factor_enabled']) ? 1 : 0, $userId]);
            settingResponse('success', 'Security settings saved.', 'security');
        }

        if ($section === 'preferences') {
            $stmt = $pdo->prepare("UPDATE user_settings SET language = ?, timezone = ?, currency = ?, default_export = ? WHERE user_id = ?");
            $stmt->execute([
                $_POST['language'] ?? 'English',
                $_POST['timezone'] ?? 'Asia/Kolkata',
                $_POST['currency'] ?? 'INR',
                $_POST['default_export'] ?? 'YouTube Shorts 1080p',
                $userId
            ]);
            settingResponse('success', 'Preferences saved.', 'preferences');
        }
    }

    $stmt = $pdo->prepare("SELECT * FROM user_settings WHERE user_id = ?");
    $stmt->execute([$userId]);
    $settings = $stmt->fetch() ?: [];
} catch (PDOException $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }
    error_log('Settings error: ' . $e->getMessage());
    $settings = [];
    $flash = ['type' => 'error', 'message' => 'Settings could not be loaded.'];
}

$avatarSrc = settingValue($settings, 'avatar_path') ?: 'https://ui-avatars.com/api/?name=' . urlencode($currentUser['username'] ?? 'User') . '&background=7C3AED&color=fff';
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Settings - GameCut AI</title>
    <script>
        try {
            localStorage.setItem('gamecut-theme', '<?php echo htmlspecialchars(settingValue($settings, 'theme', 'system'), ENT_QUOTES, 'UTF-8'); ?>');
            localStorage.setItem('gamecut-accent', '<?php echo htmlspecialchars(settingValue($settings, 'accent_color', '#7C3AED'), ENT_QUOTES, 'UTF-8'); ?>');
            localStorage.setItem('gamecut-font', '<?php echo htmlspecialchars(settingValue($settings, 'font_size', 'comfortable'), ENT_QUOTES, 'UTF-8'); ?>');
            localStorage.setItem('gamecut-compact', '<?php echo htmlspecialchars(settingValue($settings, 'compact_mode', 0), ENT_QUOTES, 'UTF-8'); ?>');
        } catch (e) {
            // localStorage unavailable
        }
    </script>
    <script src="js/theme-init.js"></script>
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/dashboard.css">
    <link rel="stylesheet" href="css/responsive.css">
    <style>
        .settings-shell {
            display: grid;
            grid-template-columns: 280px minmax(0, 1fr);
            gap: 1.5rem;
        }

        .settings-sidebar,
        .settings-panel {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            box-shadow: var(--shadow-sm);
        }

        .settings-sidebar {
            padding: 1rem;
            align-self: start;
            position: sticky;
            top: 1rem;
        }

        .settings-content {
            min-width: 0;
        }

        .settings-nav-item {
            width: 100%;
            border: none;
            background: transparent;
            color: var(--text-muted);
            padding: 0.85rem 1rem;
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            cursor: pointer;
            text-align: left;
            font-weight: 600;
        }

        .settings-nav-item:hover,
        .settings-nav-item.active {
            background: color-mix(in srgb, var(--primary) 12%, transparent);
            color: var(--primary);
        }

        .settings-panel {
            display: none;
            padding: 1.5rem;
        }

        .settings-panel.active {
            display: block;
            animation: fadeIn 0.35s ease both;
        }

        .panel-heading {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 1.5rem;
            padding-bottom: 1.25rem;
            border-bottom: 1px solid var(--border);
        }

        .panel-heading p {
            margin-top: 0.35rem;
        }

        .settings-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1rem;
        }

        .setting-card {
            border: 1px solid var(--border);
            background: var(--background);
            border-radius: 10px;
            padding: 1rem;
        }

        .theme-choice-grid,
        .accent-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.75rem;
        }

        .choice-card {
            border: 1px solid var(--border);
            background: var(--card);
            color: var(--text);
            border-radius: 10px;
            padding: 1rem;
            cursor: pointer;
            text-align: left;
            min-height: 92px;
        }

        .choice-card.active {
            border-color: var(--primary);
            background: color-mix(in srgb, var(--primary) 8%, var(--card));
            box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 18%, transparent);
        }

        .choice-preview {
            height: 28px;
            border-radius: 8px;
            margin-bottom: 0.75rem;
            border: 1px solid var(--border);
        }

        .preview-light { background: linear-gradient(90deg, #ffffff 50%, #e2e8f0 50%); }
        .preview-dark { background: linear-gradient(90deg, #09090b 50%, #27272a 50%); }
        .preview-system { background: linear-gradient(90deg, var(--card) 0 50%, var(--background) 50%); }

        .accent-swatch {
            height: 44px;
            border-radius: 10px;
            border: 2px solid var(--border);
            cursor: pointer;
            box-shadow: var(--shadow-sm);
        }

        .avatar-row {
            display: flex;
            align-items: center;
            gap: 1.25rem;
            margin-bottom: 1.5rem;
        }

        .avatar-large img {
            width: 88px;
            height: 88px;
            border-radius: 50%;
            border: 3px solid var(--border);
        }

        .form-row {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1rem;
        }

        .form-group {
            margin-bottom: 1rem;
        }

        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.9rem;
        }

        .toggle-row,
        .session-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 1rem 0;
            border-bottom: 1px solid var(--border);
        }

        .toggle-row:last-child,
        .session-row:last-child {
            border-bottom: none;
        }

        .toggle-row p,
        .session-row p {
            margin-top: 0.2rem;
            font-size: 0.875rem;
        }

        .switch {
            position: relative;
            display: inline-block;
            width: 50px;
            height: 28px;
            flex-shrink: 0;
        }

        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }

        .slider {
            position: absolute;
            inset: 0;
            cursor: pointer;
            background: var(--border-light);
            border-radius: 999px;
            border: 1px solid var(--border);
        }

        .slider::before {
            content: "";
            position: absolute;
            width: 22px;
            height: 22px;
            left: 3px;
            top: 3px;
            border-radius: 50%;
            background: var(--card);
            box-shadow: var(--shadow-sm);
        }

        input:checked + .slider {
            background: var(--primary);
        }

        input:checked + .slider::before {
            transform: translateX(22px);
        }

        .danger-zone {
            border-color: color-mix(in srgb, var(--error) 45%, var(--border));
            background: color-mix(in srgb, var(--error) 8%, var(--background));
        }

        .settings-actions {
            display: flex;
            justify-content: flex-end;
            gap: 1rem;
            margin-top: 1.5rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border);
        }

        .permission-grid {
            display: grid;
            gap: 1rem;
        }

        .permission-card {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: center;
            border: 1px solid var(--border);
            background: var(--background);
            border-radius: 12px;
            padding: 1rem;
        }

        .permission-card p {
            margin-top: 0.25rem;
            font-size: 0.9rem;
        }

        .permission-status {
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.65rem;
            border-radius: 999px;
            background: color-mix(in srgb, var(--primary) 14%, transparent);
            color: var(--primary);
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: capitalize;
            white-space: nowrap;
        }

        html[data-theme="light"] .settings-sidebar,
        html[data-theme="light"] .settings-panel {
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.07);
        }

        html[data-theme="light"] .setting-card,
        html[data-theme="light"] .permission-card {
            background: color-mix(in srgb, var(--card) 82%, var(--background));
        }

        html[data-theme="light"] .slider::before {
            background: #ffffff;
        }

        .storage-meter {
            margin-top: 1rem;
        }

        .storage-meter-row {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            color: var(--text-muted);
            font-size: 0.875rem;
            margin-bottom: 0.5rem;
        }

        @media (max-width: 992px) {
            .settings-shell {
                grid-template-columns: 1fr;
            }
            .settings-sidebar {
                position: static;
                display: flex;
                overflow-x: auto;
            }
            .settings-nav-item {
                white-space: nowrap;
            }
        }

        @media (max-width: 640px) {
            .settings-grid,
            .form-row,
            .theme-choice-grid {
                grid-template-columns: 1fr;
            }
            .panel-heading,
            .toggle-row,
            .session-row,
            .settings-actions {
                align-items: stretch;
                flex-direction: column;
            }
        }
    </style>
</head>
<body class="dashboard-body">
    <aside class="sidebar">
        <div class="sidebar-header">
            <a href="index.php" class="logo">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7L12 12L22 7L12 2Z" fill="url(#settingsLogoA)" /><path d="M2 17L12 22L22 17" stroke="url(#settingsLogoB)" stroke-width="2" stroke-linecap="round"/><path d="M2 12L12 17L22 12" stroke="url(#settingsLogoC)" stroke-width="2" stroke-linecap="round"/><defs><linearGradient id="settingsLogoA" x1="12" y1="2" x2="12" y2="12"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient><linearGradient id="settingsLogoB" x1="12" y1="17" x2="12" y2="22"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient><linearGradient id="settingsLogoC" x1="12" y1="12" x2="12" y2="17"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient></defs></svg>
                <span>GameCut <span class="text-gradient">AI</span></span>
            </a>
        </div>
        <nav class="sidebar-nav">
            <a href="dashboard.php" class="nav-item"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg><span>Dashboard</span></a>
            <a href="projects.php" class="nav-item"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg><span>Projects</span></a>
            <a href="upload.php" class="nav-item"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg><span>Upload</span></a>
            <a href="settings.php" class="nav-item active"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg><span>Settings</span></a>
        </nav>
    </aside>

    <main class="main-content">
        <header class="topbar">
            <div>
                <div class="breadcrumbs"><a href="dashboard.php">Dashboard</a><span>/</span><span>Settings</span></div>
                <h2>Settings</h2>
            </div>
            <div class="topbar-actions">
                <button class="icon-btn" aria-label="Notifications"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg><span class="notification-badge">3</span></button>
                <div class="profile-dropdown"><div class="avatar"><img src="https://ui-avatars.com/api/?name=<?php echo urlencode($currentUser['username'] ?? 'User'); ?>&background=7C3AED&color=fff" alt="<?php echo htmlspecialchars($currentUser['username'] ?? 'User'); ?>"></div><span><?php echo htmlspecialchars($currentUser['username'] ?? 'User'); ?></span></div>
            </div>
        </header>

        <div class="content-wrapper">
            <div class="settings-shell">
                <nav class="settings-sidebar" aria-label="Settings sections">
                    <button type="button" class="settings-nav-item <?php echo $activeTab === 'appearance' ? 'active' : ''; ?>" data-settings-tab="appearance">Appearance</button>
                    <button type="button" class="settings-nav-item <?php echo $activeTab === 'profile' ? 'active' : ''; ?>" data-settings-tab="profile">Account/Profile</button>
                    <button type="button" class="settings-nav-item <?php echo $activeTab === 'notifications' ? 'active' : ''; ?>" data-settings-tab="notifications">Notifications</button>
                    <button type="button" class="settings-nav-item <?php echo $activeTab === 'security' ? 'active' : ''; ?>" data-settings-tab="security">Privacy & Security</button>
                    <button type="button" class="settings-nav-item <?php echo $activeTab === 'permissions' ? 'active' : ''; ?>" data-settings-tab="permissions">Device Access</button>
                    <button type="button" class="settings-nav-item <?php echo $activeTab === 'preferences' ? 'active' : ''; ?>" data-settings-tab="preferences">Preferences</button>
                </nav>

                <div class="settings-content">
                <?php if ($flash): ?>
                    <div class="dashboard-alert dashboard-alert-<?php echo htmlspecialchars($flash['type']); ?>">
                        <?php echo htmlspecialchars($flash['message']); ?>
                    </div>
                <?php endif; ?>

                <section class="settings-panel <?php echo $activeTab === 'appearance' ? 'active' : ''; ?>" data-settings-panel="appearance">
                    <form method="POST" action="settings.php">
                    <?php echo csrfField(); ?>
                    <input type="hidden" name="settings_section" value="appearance">
                    <input type="hidden" name="theme" id="themeInput" value="<?php echo htmlspecialchars(settingValue($settings, 'theme', 'system')); ?>">
                    <input type="hidden" name="accent_color" id="accentInput" value="<?php echo htmlspecialchars(settingValue($settings, 'accent_color', '#7C3AED')); ?>">
                    <div class="panel-heading"><div><h3>Appearance</h3><p>Personalize how GameCut looks and feels across your devices.</p></div></div>
                    <div class="setting-card">
                        <label>Theme</label>
                        <div class="theme-choice-grid">
                            <button type="button" class="choice-card <?php echo settingValue($settings, 'theme', 'system') === 'light' ? 'active' : ''; ?>" data-theme-value="light"><div class="choice-preview preview-light"></div><strong>Light</strong><p>Bright, clean workspace.</p></button>
                            <button type="button" class="choice-card <?php echo settingValue($settings, 'theme', 'system') === 'dark' ? 'active' : ''; ?>" data-theme-value="dark"><div class="choice-preview preview-dark"></div><strong>Dark</strong><p>Low-glare creator mode.</p></button>
                            <button type="button" class="choice-card <?php echo settingValue($settings, 'theme', 'system') === 'system' ? 'active' : ''; ?>" data-theme-value="system"><div class="choice-preview preview-system"></div><strong>System</strong><p>Follow your device.</p></button>
                        </div>
                    </div>
                    <div class="settings-grid" style="margin-top: 1rem;">
                        <div class="setting-card"><label for="fontSize">Font size</label><select id="fontSize" name="font_size"><option value="comfortable" <?php echo selectedAttr(settingValue($settings, 'font_size', 'comfortable'), 'comfortable'); ?>>Comfortable</option><option value="large" <?php echo selectedAttr(settingValue($settings, 'font_size'), 'large'); ?>>Large</option><option value="compact" <?php echo selectedAttr(settingValue($settings, 'font_size'), 'compact'); ?>>Compact</option></select></div>
                        <div class="setting-card"><label>Compact mode</label><div class="toggle-row"><div><strong>Dense dashboard</strong><p>Show more projects and stats per screen.</p></div><label class="switch"><input type="checkbox" name="compact_mode" <?php echo checkedAttr(settingValue($settings, 'compact_mode', 0)); ?>><span class="slider"></span></label></div></div>
                        <div class="setting-card" style="grid-column: 1 / -1;"><label>Accent color</label><div class="accent-grid"><button type="button" class="accent-swatch" style="background:#7C3AED" data-accent-value="#7C3AED"></button><button type="button" class="accent-swatch" style="background:#2563EB" data-accent-value="#2563EB"></button><button type="button" class="accent-swatch" style="background:#059669" data-accent-value="#059669"></button></div></div>
                    </div>
                    <div class="settings-actions"><button type="reset" class="btn btn-outline" data-settings-cancel>Cancel</button><button type="submit" class="btn btn-primary">Save Changes</button></div>
                    </form>
                </section>

                <section class="settings-panel <?php echo $activeTab === 'profile' ? 'active' : ''; ?>" data-settings-panel="profile">
                    <form method="POST" action="settings.php" enctype="multipart/form-data">
                    <?php echo csrfField(); ?>
                    <input type="hidden" name="settings_section" value="profile">
                    <div class="panel-heading"><div><h3>Account/Profile</h3><p>Update your public creator identity and account details.</p></div></div>
                    <div class="avatar-row"><div class="avatar-large"><img src="<?php echo htmlspecialchars($avatarSrc); ?>" alt="<?php echo htmlspecialchars($currentUser['username'] ?? 'User'); ?>"></div><div><label class="btn btn-secondary" for="avatarInput">Upload Avatar</label><input type="file" id="avatarInput" name="avatar" accept="image/jpeg,image/png,image/webp" hidden><p>JPG, PNG, or WEBP. Recommended 512x512.</p></div></div>
                    <div class="form-row"><div class="form-group"><label>Name</label><input type="text" name="username" value="<?php echo htmlspecialchars($currentUser['username'] ?? ''); ?>" required></div><div class="form-group"><label>Email</label><input type="email" name="email" value="<?php echo htmlspecialchars($currentUser['email'] ?? ''); ?>" required></div></div>
                    <div class="form-group"><label>Bio</label><textarea name="bio" rows="5"><?php echo htmlspecialchars(settingValue($settings, 'bio', 'Gaming content creator using AI to make viral shorts.')); ?></textarea></div>
                    <div class="settings-actions"><button type="reset" class="btn btn-outline" data-settings-cancel>Cancel</button><button type="submit" class="btn btn-primary">Save Profile</button></div>
                    </form>
                </section>

                <section class="settings-panel <?php echo $activeTab === 'notifications' ? 'active' : ''; ?>" data-settings-panel="notifications">
                    <form method="POST" action="settings.php">
                    <?php echo csrfField(); ?>
                    <input type="hidden" name="settings_section" value="notifications">
                    <div class="panel-heading"><div><h3>Notifications</h3><p>Choose when GameCut should reach you.</p></div></div>
                    <div class="setting-card">
                        <div class="toggle-row"><div><strong>Email notifications</strong><p>Get an email when an AI short is ready.</p></div><label class="switch"><input type="checkbox" name="email_notifications" <?php echo checkedAttr(settingValue($settings, 'email_notifications', 1)); ?>><span class="slider"></span></label></div>
                        <div class="toggle-row"><div><strong>Push notifications</strong><p>Receive browser alerts for finished renders.</p></div><label class="switch"><input type="checkbox" name="push_notifications" <?php echo checkedAttr(settingValue($settings, 'push_notifications', 1)); ?>><span class="slider"></span></label></div>
                        <div class="toggle-row"><div><strong>Marketing updates</strong><p>Occasional product launches and creator tips.</p></div><label class="switch"><input type="checkbox" name="marketing_updates" <?php echo checkedAttr(settingValue($settings, 'marketing_updates', 0)); ?>><span class="slider"></span></label></div>
                    </div>
                    <div class="settings-actions"><button type="reset" class="btn btn-outline" data-settings-cancel>Cancel</button><button type="submit" class="btn btn-primary">Save Notifications</button></div>
                    </form>
                </section>

                <section class="settings-panel <?php echo $activeTab === 'security' ? 'active' : ''; ?>" data-settings-panel="security">
                    <form method="POST" action="settings.php">
                    <?php echo csrfField(); ?>
                    <input type="hidden" name="settings_section" value="security">
                    <div class="panel-heading"><div><h3>Privacy & Security</h3><p>Protect your account and manage active devices.</p></div></div>
                    <div class="settings-grid">
                        <div class="setting-card"><h4>Change password</h4><div class="form-group"><label>Current password</label><input type="password" placeholder="Coming soon" disabled></div><div class="form-group"><label>New password</label><input type="password" placeholder="Coming soon" disabled></div><button type="button" class="btn btn-secondary" data-toast="Password changes coming soon">Update Password</button></div>
                        <div class="setting-card"><div class="toggle-row"><div><strong>Two-factor authentication</strong><p>Add an authenticator app before sensitive changes.</p></div><label class="switch"><input type="checkbox" name="two_factor_enabled" <?php echo checkedAttr(settingValue($settings, 'two_factor_enabled', 0)); ?>><span class="slider"></span></label></div></div>
                        <div class="setting-card" style="grid-column: 1 / -1;"><h4>Active sessions</h4><div class="session-row"><div><strong>Windows Chrome</strong><p>Delhi, India • Current session</p></div><button type="button" class="btn btn-outline" data-toast="Current session kept">Current</button></div><div class="session-row"><div><strong>iPhone Safari</strong><p>Last active 2 hours ago</p></div><button type="button" class="btn btn-outline" data-toast="Session revoked">Revoke</button></div></div>
                        <div class="setting-card danger-zone" style="grid-column: 1 / -1;"><h4>Delete account</h4><p>Permanently remove your videos, settings, and account data.</p><button type="button" class="btn btn-outline" data-toast="Delete request requires confirmation">Delete Account</button></div>
                    </div>
                    <div class="settings-actions"><button type="reset" class="btn btn-outline" data-settings-cancel>Cancel</button><button type="submit" class="btn btn-primary">Save Security</button></div>
                    </form>
                </section>

                <section class="settings-panel <?php echo $activeTab === 'permissions' ? 'active' : ''; ?>" data-settings-panel="permissions">
                    <div class="panel-heading">
                        <div>
                            <h3>Device Access</h3>
                            <p>Control the browser permissions GameCut needs for a smooth upload and render experience.</p>
                        </div>
                    </div>

                    <div class="permission-grid">
                        <div class="permission-card">
                            <div>
                                <h4>Video file access</h4>
                                <p>GameCut only reads the video you manually choose in the upload picker. It cannot scan your folders.</p>
                            </div>
                            <span class="permission-status" data-permission-status="files">granted when you choose a video</span>
                        </div>

                        <div class="permission-card">
                            <div>
                                <h4>Render notifications</h4>
                                <p>Allow browser notifications so you can leave the tab and return when your AI short is ready.</p>
                            </div>
                            <div style="display: grid; gap: 0.5rem; justify-items: end;">
                                <span class="permission-status" data-permission-status="notifications">checking</span>
                                <button type="button" class="btn btn-secondary" data-request-notifications>Allow Notifications</button>
                            </div>
                        </div>

                        <div class="permission-card">
                            <div>
                                <h4>Persistent browser storage</h4>
                                <p>Protect temporary render metadata, preferences, and cached settings from automatic browser cleanup.</p>
                            </div>
                            <div style="display: grid; gap: 0.5rem; justify-items: end;">
                                <span class="permission-status" data-permission-status="persistentStorage">checking</span>
                                <button type="button" class="btn btn-secondary" data-request-storage>Protect Storage</button>
                            </div>
                        </div>

                        <div class="setting-card">
                            <h4>Browser storage estimate</h4>
                            <div class="storage-meter">
                                <div class="storage-meter-row">
                                    <span><span data-storage-used>Checking</span> used</span>
                                    <span><span data-storage-quota>Checking</span> available</span>
                                </div>
                                <div class="progress-bar">
                                    <div class="progress-fill" data-storage-bar style="width: 8%"></div>
                                </div>
                                <p data-storage-status style="margin-top: 0.75rem;">Checking browser storage...</p>
                            </div>
                            <button type="button" class="btn btn-outline" style="margin-top: 1rem;" data-refresh-storage>Refresh Storage</button>
                        </div>
                    </div>

                    <div class="settings-actions"><button type="button" class="btn btn-outline" data-settings-cancel>Cancel</button><button type="button" class="btn btn-primary" data-toast="Device access is browser-managed">Save Access Settings</button></div>
                </section>

                <section class="settings-panel <?php echo $activeTab === 'preferences' ? 'active' : ''; ?>" data-settings-panel="preferences">
                    <form method="POST" action="settings.php">
                    <?php echo csrfField(); ?>
                    <input type="hidden" name="settings_section" value="preferences">
                    <div class="panel-heading"><div><h3>Preferences</h3><p>Localize exports, billing views, and creator defaults.</p></div></div>
                    <div class="settings-grid">
                        <div class="setting-card"><label>Language</label><select name="language"><option value="English" <?php echo selectedAttr(settingValue($settings, 'language', 'English'), 'English'); ?>>English</option><option value="Hindi" <?php echo selectedAttr(settingValue($settings, 'language', 'English'), 'Hindi'); ?>>Hindi</option><option value="Spanish" <?php echo selectedAttr(settingValue($settings, 'language', 'English'), 'Spanish'); ?>>Spanish</option></select></div>
                        <div class="setting-card"><label>Timezone</label><select name="timezone"><option value="Asia/Kolkata" <?php echo selectedAttr(settingValue($settings, 'timezone', 'Asia/Kolkata'), 'Asia/Kolkata'); ?>>Asia/Kolkata</option><option value="UTC" <?php echo selectedAttr(settingValue($settings, 'timezone', 'Asia/Kolkata'), 'UTC'); ?>>UTC</option><option value="America/New_York" <?php echo selectedAttr(settingValue($settings, 'timezone', 'Asia/Kolkata'), 'America/New_York'); ?>>America/New_York</option></select></div>
                        <div class="setting-card"><label>Currency</label><select name="currency"><option value="USD" <?php echo selectedAttr(settingValue($settings, 'currency', 'INR'), 'USD'); ?>>USD</option><option value="INR" <?php echo selectedAttr(settingValue($settings, 'currency', 'INR'), 'INR'); ?>>INR</option><option value="EUR" <?php echo selectedAttr(settingValue($settings, 'currency', 'INR'), 'EUR'); ?>>EUR</option></select></div>
                        <div class="setting-card"><label>Default export</label><select name="default_export"><option value="YouTube Shorts 1080p" <?php echo selectedAttr(settingValue($settings, 'default_export', 'YouTube Shorts 1080p'), 'YouTube Shorts 1080p'); ?>>YouTube Shorts 1080p</option><option value="TikTok 1080p" <?php echo selectedAttr(settingValue($settings, 'default_export', 'YouTube Shorts 1080p'), 'TikTok 1080p'); ?>>TikTok 1080p</option><option value="Instagram Reels 1080p" <?php echo selectedAttr(settingValue($settings, 'default_export', 'YouTube Shorts 1080p'), 'Instagram Reels 1080p'); ?>>Instagram Reels 1080p</option></select></div>
                    </div>
                    <div class="settings-actions"><button type="reset" class="btn btn-outline" data-settings-cancel>Cancel</button><button type="submit" class="btn btn-primary">Save Preferences</button></div>
                    </form>
                </section>
                </div>
            </div>
        </div>
    </main>

    <script src="js/app.js"></script>
    <script src="js/storage-manager.js"></script>
    <script>
        (function() {
            try {
                // Tab switching with URL query param sync
                function getActiveSettingsTab() {
                    var params = new URLSearchParams(window.location.search);
                    var tab = params.get('tab') || 'appearance';
                    var validTabs = ['appearance', 'profile', 'notifications', 'security', 'permissions', 'preferences'];
                    if (validTabs.indexOf(tab) !== -1) return tab;
                    return 'appearance';
                }

                function activateSettingsTab(tabId) {
                    try {
                        document.querySelectorAll('[data-settings-tab]').forEach(function(item) { item.classList.remove('active'); });
                        document.querySelectorAll('[data-settings-panel]').forEach(function(panel) { panel.classList.remove('active'); });
                        var tabBtn = document.querySelector('[data-settings-tab="' + tabId + '"]');
                        var tabPanel = document.querySelector('[data-settings-panel="' + tabId + '"]');
                        if (tabBtn) tabBtn.classList.add('active');
                        if (tabPanel) tabPanel.classList.add('active');
                    } catch (e) {
                        // Non-critical UI error
                    }
                }

                // Set initial tab from URL
                activateSettingsTab(getActiveSettingsTab());

                document.querySelectorAll('[data-settings-tab]').forEach(function(button) {
                    button.addEventListener('click', function() {
                        var tabId = button.dataset.settingsTab;
                        if (tabId) {
                            activateSettingsTab(tabId);
                            // Update URL without page reload
                            try {
                                var url = new URL(window.location.href);
                                url.searchParams.set('tab', tabId);
                                window.history.replaceState({}, '', url.toString());
                            } catch (e) {
                                // URL update is non-critical
                            }
                        }
                    });
                });

                // Theme choice cards - update hidden input
                document.querySelectorAll('[data-theme-value]').forEach(function(button) {
                    button.addEventListener('click', function() {
                        try {
                            document.querySelectorAll('[data-theme-value]').forEach(function(item) { item.classList.remove('active'); });
                            button.classList.add('active');
                            var themeInput = document.getElementById('themeInput');
                            if (themeInput) {
                                themeInput.value = button.dataset.themeValue;
                            }
                        } catch (e) {
                            // Non-critical
                        }
                    });
                });

                // Accent color swatches - update hidden input
                document.querySelectorAll('[data-accent-value]').forEach(function(button) {
                    button.addEventListener('click', function() {
                        try {
                            var accentInput = document.getElementById('accentInput');
                            if (accentInput) {
                                accentInput.value = button.dataset.accentValue;
                            }
                            if (window.showToast) {
                                window.showToast('Accent selected', 'Save changes to keep this color.');
                            }
                        } catch (e) {
                            // Non-critical
                        }
                    });
                });

                // Cancel buttons
                document.querySelectorAll('[data-settings-cancel]').forEach(function(button) {
                    button.addEventListener('click', function() {
                        if (window.showToast) {
                            window.showToast('Changes discarded', 'No settings were changed.');
                        }
                    });
                });
            } catch (e) {
                // Fallback: settings still render
            }
        })();
    </script>
</body>
</html>
