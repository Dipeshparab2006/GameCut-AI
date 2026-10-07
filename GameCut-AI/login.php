<?php
require_once 'php/bootstrap.php';
require_once 'php/config.php';
require_once 'php/session.php';

if (isLoggedIn()) {
    header('Location: dashboard.php');
    exit();
}

$error = '';
$email = '';
$flash = getFlashMessage();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!verifyCsrfToken($_POST['csrf_token'] ?? '')) {
        $error = 'Your session expired. Please try again.';
    } else {
    $email = trim($_POST['email'] ?? '');
    $password = $_POST['password'] ?? '';

    if ($email === '' || $password === '') {
        $error = 'Please fill in all fields';
    } else {
        try {
            $stmt = $pdo->prepare("SELECT id, username, email, password FROM users WHERE email = ?");
            $stmt->execute([$email]);
            $user = $stmt->fetch();

            if ($user && password_verify($password, $user['password'])) {
                $updateLogin = $pdo->prepare("UPDATE users SET last_login = NOW() WHERE id = ?");
                $updateLogin->execute([$user['id']]);

                // Prevent session fixation and discard any previous account's
                // session identifier before establishing the new identity.
                regenerateSession();
                $_SESSION['user_id'] = $user['id'];
                $_SESSION['username'] = $user['username'];
                $_SESSION['email'] = $user['email'];
                $_SESSION['logged_in'] = true;

                header('Location: dashboard.php');
                exit();
            }

            $error = 'Invalid email or password';
        } catch (PDOException $e) {
            $error = 'Login failed. Please try again.';
        }
    }
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - GameCut AI</title>
    <script src="js/theme-init.js"></script>
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/auth.css">
    <link rel="stylesheet" href="css/responsive.css">
</head>
<body class="auth-body">
    <div class="auth-card fade-in">
        <div class="auth-header">
            <a href="index.php" class="logo">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="url(#paint0)" />
                    <path d="M2 17L12 22L22 17" stroke="url(#paint1)" stroke-width="2" stroke-linecap="round"/>
                    <path d="M2 12L12 17L22 12" stroke="url(#paint2)" stroke-width="2" stroke-linecap="round"/>
                    <defs>
                        <linearGradient id="paint0" x1="12" y1="2" x2="12" y2="12" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                        <linearGradient id="paint1" x1="12" y1="17" x2="12" y2="22" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                        <linearGradient id="paint2" x1="12" y1="12" x2="12" y2="17" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                    </defs>
                </svg>
                <span>GameCut <span class="text-gradient">AI</span></span>
            </a>
            <h2>Welcome back</h2>
            <p>Log in to your account to continue</p>
        </div>

        <?php if ($flash): ?>
            <div class="auth-alert auth-alert-<?php echo htmlspecialchars($flash['type']); ?>">
                <?php echo htmlspecialchars($flash['message']); ?>
            </div>
        <?php endif; ?>

        <?php if ($error): ?>
            <div class="auth-alert auth-alert-error"><?php echo htmlspecialchars($error); ?></div>
        <?php endif; ?>

        <form class="auth-form" action="login.php" method="POST">
            <?php echo csrfField(); ?>
            <div class="form-group">
                <label for="email">Email Address</label>
                <input type="email" id="email" name="email" placeholder="you@example.com" value="<?php echo htmlspecialchars($email); ?>" required>
            </div>

            <div class="form-group">
                <a href="mailto:support@gamecut.ai?subject=Password%20reset%20request" class="forgot-password">Forgot password?</a>
                <label for="password">Password</label>
                <input type="password" id="password" name="password" placeholder="Password" required>
            </div>

            <button type="submit" class="btn btn-primary w-100">Log In</button>
        </form>

        <div class="social-login">
            <button type="button" class="btn-social">Google</button>
            <button type="button" class="btn-social">Discord</button>
        </div>

        <div class="auth-footer">
            Don't have an account? <a href="register.php">Sign Up</a>
        </div>
    </div>
    <script src="js/app.js"></script>
</body>
</html>
