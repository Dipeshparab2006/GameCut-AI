<?php
require_once __DIR__ . '/php/bootstrap.php';
require_once __DIR__ . '/php/config.php';
require_once __DIR__ . '/php/session.php';

if (isLoggedIn()) {
    header('Location: dashboard.php');
    exit();
}

$html = file_get_contents(__DIR__ . '/index.html');

if ($html === false) {
    http_response_code(500);
    include __DIR__ . '/500.php';
    exit();
}

$html = str_replace('href="index.html"', 'href="index.php"', $html);

echo $html;
