<?php
require_once 'php/bootstrap.php';
require_once 'php/config.php';
require_once 'php/session.php';

// Get current user data (if logged in)
$currentUser = getCurrentUser();
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>404 - Page Not Found | GameCut AI</title>
    <script src="js/theme-init.js"></script>
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/responsive.css">
    <style>
        .error-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 2rem;
            text-align: center;
        }

        .error-content {
            max-width: 600px;
        }

        .error-code {
            font-size: 8rem;
            font-weight: 900;
            background: linear-gradient(135deg, #7C3AED, #3B82F6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            line-height: 1;
            margin-bottom: 1rem;
        }

        .error-title {
            font-size: 2rem;
            margin-bottom: 1rem;
            color: var(--text);
        }

        .error-message {
            color: var(--text-muted);
            font-size: 1.125rem;
            margin-bottom: 2rem;
        }

        .error-actions {
            display: flex;
            gap: 1rem;
            justify-content: center;
            flex-wrap: wrap;
        }

        @media (max-width: 640px) {
            .error-code {
                font-size: 5rem;
            }
            
            .error-title {
                font-size: 1.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="error-container">
        <div class="error-content fade-in">
            <div class="error-code">404</div>
            <h1 class="error-title">Oops! Page Not Found</h1>
            <p class="error-message">
                The page you're looking for seems to have been deleted, moved, or doesn't exist.
            </p>
            <div class="error-actions">
                <a href="index.php" class="btn btn-primary btn-lg">
                    Go Home
                </a>
                <?php if (isLoggedIn()): ?>
                    <a href="dashboard.php" class="btn btn-secondary btn-lg">
                        Dashboard
                    </a>
                <?php else: ?>
                    <a href="login.php" class="btn btn-secondary btn-lg">
                        Login
                    </a>
                <?php endif; ?>
            </div>
        </div>
    </div>

    <script src="js/app.js"></script>
</body>
</html>
