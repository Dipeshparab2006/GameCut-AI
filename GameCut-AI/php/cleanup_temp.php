<?php
/**
 * Cleanup Temporary Files Script
 * Designed to be run via cron (e.g., daily)
 * 
 * Usage: php cleanup_temp.php
 */

// This script recursively deletes temp files. It is intentionally unavailable
// through the web server; schedule it with the CLI only.
if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    header('Content-Type: text/plain; charset=utf-8');
    exit('This maintenance script must be run from the command line.');
}

require_once __DIR__ . '/bootstrap.php';
require_once __DIR__ . '/config.php';

$maxAgeSeconds = 24 * 3600; // 24 hours

$directoriesToClean = [
    dirname(__DIR__) . DIRECTORY_SEPARATOR . 'uploads' . DIRECTORY_SEPARATOR . 'temp',
    dirname(__DIR__) . DIRECTORY_SEPARATOR . 'tmp'
];

$deletedCount = 0;
$failedCount = 0;
$bytesFreed = 0;

$now = time();

echo "Starting temporary file cleanup...\n";

foreach ($directoriesToClean as $dir) {
    if (!is_dir($dir)) {
        continue;
    }

    echo "Scanning directory: $dir\n";

    $iterator = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($dir, RecursiveDirectoryIterator::SKIP_DOTS),
        RecursiveIteratorIterator::CHILD_FIRST
    );

    foreach ($iterator as $file) {
        if ($file->isFile()) {
            $lastModified = $file->getMTime();
            $age = $now - $lastModified;

            if ($age > $maxAgeSeconds) {
                $size = $file->getSize();
                $path = $file->getRealPath();
                
                if (@unlink($path)) {
                    $deletedCount++;
                    $bytesFreed += $size;
                    echo "Deleted: $path\n";
                } else {
                    $failedCount++;
                    echo "Failed to delete: $path\n";
                }
            }
        } elseif ($file->isDir()) {
            // Remove empty directories if they are older than maxAge too
            $path = $file->getRealPath();
            $files = array_diff(scandir($path), ['.', '..']);
            if (empty($files)) {
                $lastModified = filemtime($path);
                if (($now - $lastModified) > $maxAgeSeconds) {
                    @rmdir($path);
                    echo "Removed empty dir: $path\n";
                }
            }
        }
    }
}

$mbFreed = round($bytesFreed / (1024 * 1024), 2);
echo "Cleanup finished.\n";
echo "Files deleted: $deletedCount\n";
echo "Space freed: {$mbFreed} MB\n";
echo "Failed deletions: $failedCount\n";

appLog('system', 'Temporary file cleanup completed', [
    'deleted_count' => $deletedCount,
    'freed_bytes' => $bytesFreed,
    'failed_count' => $failedCount
]);
