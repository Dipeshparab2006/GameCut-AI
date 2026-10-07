<?php
define('APP_ALLOW_DB_FAILURE', true);
require_once __DIR__ . '/../php/bootstrap.php';
require_once __DIR__ . '/../php/config.php';

$root = dirname(__DIR__);
$failures = 0;

function resultLine($ok, $label, $detail = '') {
    global $failures;

    if (!$ok) {
        $failures++;
    }

    echo ($ok ? '[PASS] ' : '[FAIL] ') . $label . ($detail !== '' ? ' - ' . $detail : '') . PHP_EOL;
}

function httpStatus($url) {
    $context = stream_context_create([
        'http' => [
            'method' => 'GET',
            'timeout' => 8,
            'ignore_errors' => true,
        ],
    ]);

    $body = @file_get_contents($url, false, $context);
    $headers = $http_response_header ?? [];

    foreach ($headers as $header) {
        if (preg_match('#^HTTP/\S+\s+(\d{3})#', $header, $matches)) {
            return [(int) $matches[1], $body ?: ''];
        }
    }

    return [0, ''];
}

echo 'GameCut AI smoke checks' . PHP_EOL;
echo 'Site URL: ' . SITE_URL . PHP_EOL . PHP_EOL;

$phpFiles = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS));
foreach ($phpFiles as $file) {
    if ($file->getExtension() !== 'php') {
        continue;
    }

    $path = $file->getPathname();
    $command = escapeshellarg(PHP_BINARY) . ' -l ' . escapeshellarg($path);
    exec($command, $output, $code);
    resultLine($code === 0, 'PHP syntax: ' . str_replace($root . DIRECTORY_SEPARATOR, '', $path));
}

echo PHP_EOL;

$urls = [
    'Website' => appUrl('index.php'),
    'Local access' => appUrl('local.php'),
    'Health endpoint' => appUrl('health.php'),
    'Connection test' => appUrl('test_connection.php'),
];

foreach ($urls as $label => $url) {
    [$status, $body] = httpStatus($url);
    resultLine($status >= 200 && $status < 400, $label . ' URL', $url . ' returned HTTP ' . $status);

    if ($label === 'Website') {
        resultLine(strpos($body, 'Upload Gameplay') !== false, 'Website content', 'new homepage headline found');
    }
}

echo PHP_EOL;

if ($pdo instanceof PDO) {
    try {
        $tableCount = (int) $pdo
            ->query('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()')
            ->fetchColumn();
        resultLine($tableCount > 0, 'Database connection', DB_NAME . ' has ' . $tableCount . ' tables');
    } catch (Throwable $e) {
        resultLine(false, 'Database query', 'query failed');
    }
} else {
    resultLine(false, 'Database connection', 'could not connect to ' . DB_HOST . ':' . DB_PORT . '/' . DB_NAME);
}

echo PHP_EOL . ($failures === 0 ? 'All smoke checks passed.' : $failures . ' smoke check(s) failed.') . PHP_EOL;
exit($failures === 0 ? 0 : 1);
