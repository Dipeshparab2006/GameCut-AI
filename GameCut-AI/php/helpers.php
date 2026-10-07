<?php
function appLog($channel, $message, array $context = []) {
    $allowedChannels = ['upload', 'error', 'ai', 'delete', 'security', 'system'];
    if (!in_array($channel, $allowedChannels, true)) {
        $channel = 'error';
    }

    $logDir = dirname(__DIR__) . DIRECTORY_SEPARATOR . 'logs';
    if (!is_dir($logDir)) {
        mkdir($logDir, 0775, true);
    }

    $line = sprintf(
        "[%s] %s %s%s",
        date('Y-m-d H:i:s'),
        strtoupper($channel),
        $message,
        $context ? ' ' . json_encode($context, JSON_UNESCAPED_SLASHES) : ''
    );

    file_put_contents($logDir . DIRECTORY_SEPARATOR . $channel . '.log', $line . PHP_EOL, FILE_APPEND | LOCK_EX);
}
