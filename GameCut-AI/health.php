<?php
define('APP_ALLOW_DB_FAILURE', true);
require_once __DIR__ . '/php/bootstrap.php';
require_once __DIR__ . '/php/config.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$checks = [
    'app' => [
        'name' => SITE_NAME,
        'site_url' => SITE_URL,
        'php_version' => PHP_VERSION,
        'server' => $_SERVER['SERVER_SOFTWARE'] ?? 'CLI',
    ],
    'urls' => [
        'website' => appUrl('index.php'),
        'local_access' => appUrl('local.php'),
        'phpmyadmin' => rtrim(PHPMYADMIN_URL, '/') . '/index.php?route=/database/structure&db=' . rawurlencode(DB_NAME),
    ],
    'database' => [
        'ok' => false,
        'host' => DB_HOST,
        'port' => DB_PORT,
        'name' => DB_NAME,
        'tables' => null,
        'error' => null,
    ],
    'security' => [
        'display_errors' => ini_get('display_errors') === '1' ? 'on' : 'off',
        'session_cookie_httponly' => (bool) ini_get('session.cookie_httponly'),
        'session_cookie_samesite' => ini_get('session.cookie_samesite') ?: 'not set',
    ],
];

if ($pdo instanceof PDO) {
    try {
        $checks['database']['ok'] = true;
        $checks['database']['server_time'] = $pdo->query('SELECT NOW()')->fetchColumn();
        $checks['database']['tables'] = (int) $pdo
            ->query('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()')
            ->fetchColumn();
    } catch (Throwable $e) {
        $checks['database']['error'] = 'Database query failed.';
        error_log('Health database query failed: ' . $e->getMessage());
    }
} else {
    $checks['database']['error'] = 'Database connection failed.';
}

$checks['ok'] = $checks['database']['ok'];
http_response_code($checks['ok'] ? 200 : 503);

echo json_encode($checks, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
