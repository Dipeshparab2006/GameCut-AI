<?php
define('APP_ALLOW_DB_FAILURE', true);
require_once __DIR__ . '/php/bootstrap.php';
require_once __DIR__ . '/php/config.php';

$databaseOk = false;
$tableCount = null;
$databaseMessage = '';

try {
    if (!$pdo instanceof PDO) {
        throw new RuntimeException($dbConnectionError ?: 'No database connection is available.');
    }

    $stmt = $pdo->query('SELECT COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema = DATABASE()');
    $tableCount = (int) $stmt->fetchColumn();
    $databaseOk = true;
    $databaseMessage = 'Connected to ' . DB_NAME . ' on ' . DB_HOST . ':' . DB_PORT;
} catch (Throwable $e) {
    $databaseMessage = 'Database connection failed. Check that MySQL is running in XAMPP.';
    error_log('Local access database check failed: ' . $e->getMessage());
}

$websiteUrl = appUrl('index.php');
$phpMyAdminUrl = rtrim(PHPMYADMIN_URL, '/') . '/index.php?route=/database/structure&db=' . rawurlencode(DB_NAME);
$testUrl = appUrl('test_connection.php');
$healthUrl = appUrl('health.php');
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Local Access - GameCut AI</title>
    <style>
        :root {
            color-scheme: light;
            --bg: #f6f8fb;
            --panel: #ffffff;
            --text: #172033;
            --muted: #5d697c;
            --line: #dce3ee;
            --primary: #1f6feb;
            --primary-dark: #164fa8;
            --ok: #188038;
            --bad: #b42318;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            min-height: 100vh;
            font-family: Arial, Helvetica, sans-serif;
            color: var(--text);
            background: var(--bg);
        }

        main {
            width: min(960px, calc(100% - 32px));
            margin: 0 auto;
            padding: 48px 0;
        }

        header {
            margin-bottom: 24px;
        }

        h1 {
            margin: 0 0 8px;
            font-size: clamp(2rem, 4vw, 3rem);
        }

        p {
            margin: 0;
            color: var(--muted);
            line-height: 1.6;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-top: 24px;
        }

        .card {
            display: flex;
            min-height: 190px;
            flex-direction: column;
            justify-content: space-between;
            padding: 22px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            box-shadow: 0 8px 24px rgba(23, 32, 51, 0.08);
        }

        h2 {
            margin: 0 0 8px;
            font-size: 1.2rem;
        }

        .url {
            margin: 14px 0;
            padding: 10px 12px;
            overflow-wrap: anywhere;
            border: 1px solid var(--line);
            border-radius: 6px;
            background: #f9fbfe;
            color: #334155;
            font-family: Consolas, "Courier New", monospace;
            font-size: 0.92rem;
        }

        .button {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 42px;
            padding: 10px 16px;
            border-radius: 6px;
            background: var(--primary);
            color: #ffffff;
            font-weight: 700;
            text-decoration: none;
        }

        .button:hover {
            background: var(--primary-dark);
        }

        .status {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 24px;
            padding: 16px 18px;
            border: 1px solid var(--line);
            border-left: 5px solid <?php echo $databaseOk ? 'var(--ok)' : 'var(--bad)'; ?>;
            border-radius: 8px;
            background: var(--panel);
        }

        .dot {
            width: 12px;
            height: 12px;
            flex: 0 0 12px;
            border-radius: 50%;
            background: <?php echo $databaseOk ? 'var(--ok)' : 'var(--bad)'; ?>;
        }

        .status strong {
            display: block;
            margin-bottom: 2px;
        }
    </style>
</head>
<body>
    <main>
        <header>
            <h1>GameCut AI Local Access</h1>
            <p>Use these separate local URLs for the website and the phpMyAdmin database.</p>
        </header>

        <section class="grid" aria-label="Local links">
            <article class="card">
                <div>
                    <h2>Website</h2>
                    <p>Open the main GameCut AI website through XAMPP Apache.</p>
                    <div class="url"><?php echo htmlspecialchars($websiteUrl, ENT_QUOTES, 'UTF-8'); ?></div>
                </div>
                <a class="button" href="<?php echo htmlspecialchars($websiteUrl, ENT_QUOTES, 'UTF-8'); ?>">Open Website</a>
            </article>

            <article class="card">
                <div>
                    <h2>Database</h2>
                    <p>Open the connected phpMyAdmin database named <strong><?php echo htmlspecialchars(DB_NAME, ENT_QUOTES, 'UTF-8'); ?></strong>.</p>
                    <div class="url"><?php echo htmlspecialchars($phpMyAdminUrl, ENT_QUOTES, 'UTF-8'); ?></div>
                </div>
                <a class="button" href="<?php echo htmlspecialchars($phpMyAdminUrl, ENT_QUOTES, 'UTF-8'); ?>">Open Database</a>
            </article>

            <article class="card">
                <div>
                    <h2>Connection Test</h2>
                    <p>Check whether PHP can connect to your XAMPP MySQL database.</p>
                    <div class="url"><?php echo htmlspecialchars($testUrl, ENT_QUOTES, 'UTF-8'); ?></div>
                </div>
                <a class="button" href="<?php echo htmlspecialchars($testUrl, ENT_QUOTES, 'UTF-8'); ?>">Test Connection</a>
            </article>

            <article class="card">
                <div>
                    <h2>System Health</h2>
                    <p>View a JSON health report for URLs, PHP, and database status.</p>
                    <div class="url"><?php echo htmlspecialchars($healthUrl, ENT_QUOTES, 'UTF-8'); ?></div>
                </div>
                <a class="button" href="<?php echo htmlspecialchars($healthUrl, ENT_QUOTES, 'UTF-8'); ?>">Open Health</a>
            </article>
        </section>

        <section class="status" aria-label="Database status">
            <span class="dot" aria-hidden="true"></span>
            <div>
                <strong><?php echo $databaseOk ? 'Database is connected' : 'Database is not connected'; ?></strong>
                <p>
                    <?php echo htmlspecialchars($databaseMessage, ENT_QUOTES, 'UTF-8'); ?>
                    <?php if ($databaseOk): ?>
                        <?php echo ' Tables found: ' . $tableCount . '.'; ?>
                    <?php endif; ?>
                </p>
            </div>
        </section>
    </main>
</body>
</html>
