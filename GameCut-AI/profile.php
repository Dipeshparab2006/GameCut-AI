<?php
require_once 'php/bootstrap.php';
require_once 'php/config.php';
require_once 'php/session.php';

requireAuth();

$currentUser = getCurrentUser();
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Profile - GameCut AI</title>
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/dashboard.css">
    <link rel="stylesheet" href="css/responsive.css">
</head>
<body class="dashboard-body">
    <main class="main-content">
        <div class="content-wrapper">
            <h1>Profile</h1>
            <p>Name: <?php echo htmlspecialchars($currentUser['username'] ?? 'User'); ?></p>
            <p>Email: <?php echo htmlspecialchars($currentUser['email'] ?? ''); ?></p>
            <p><a href="dashboard.php">Back to dashboard</a></p>
        </div>
    </main>
</body>
</html>
