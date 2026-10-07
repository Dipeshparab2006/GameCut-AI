<?php
ini_set('display_errors', '0');
ini_set('log_errors', '1');

$logDir = dirname(__DIR__) . DIRECTORY_SEPARATOR . 'logs';
if (!is_dir($logDir)) {
    mkdir($logDir, 0775, true);
}
ini_set('error_log', $logDir . DIRECTORY_SEPARATOR . 'error.log');

$sessionDir = dirname(__DIR__) . DIRECTORY_SEPARATOR . 'tmp' . DIRECTORY_SEPARATOR . 'sessions';
if (!is_dir($sessionDir)) {
    mkdir($sessionDir, 0775, true);
}
if (is_writable($sessionDir)) {
    session_save_path($sessionDir);
}

$isHttps = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off');
session_set_cookie_params([
    'lifetime' => 0,
    'path' => '/',
    'domain' => '',
    'secure' => $isHttps,
    'httponly' => true,
    'samesite' => 'Lax',
]);

if (!headers_sent()) {
    header("Content-Security-Policy: default-src 'self'; img-src 'self' data: https://ui-avatars.com https://images.unsplash.com; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'");
    header('X-Content-Type-Options: nosniff');
    header('Referrer-Policy: strict-origin-when-cross-origin');
}

if (session_status() === PHP_SESSION_NONE) {
    try {
        @session_start();
    } catch (Throwable $e) {
        // Session unavailable - page still renders without it
        error_log('Session start failed: ' . $e->getMessage());
    }
}
