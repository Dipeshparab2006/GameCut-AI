<?php
/**
 * Finalize project deletions after active worker executions have stopped.
 * Run from Task Scheduler/cron; never expose this file through the web server.
 */
if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit('This maintenance script must be run from the command line.');
}

require_once __DIR__ . '/bootstrap.php';
require_once __DIR__ . '/config.php';
require_once __DIR__ . '/helpers.php';

function removeProjectArtifact(string $projectRoot, ?string $relativePath): void {
    if (!$relativePath) {
        return;
    }

    $uploadsRoot = realpath($projectRoot . DIRECTORY_SEPARATOR . 'uploads');
    $path = realpath($projectRoot . DIRECTORY_SEPARATOR . ltrim($relativePath, '/\\'));
    if (!$uploadsRoot || !$path || !str_starts_with($path, $uploadsRoot . DIRECTORY_SEPARATOR) || !is_file($path)) {
        return;
    }

    @unlink($path);
    $thumbnail = pathinfo($path, PATHINFO_DIRNAME) . DIRECTORY_SEPARATOR
        . pathinfo($path, PATHINFO_FILENAME) . '_thumbnail.jpg';
    if (is_file($thumbnail)) {
        @unlink($thumbnail);
    }
}

function removeProjectDirectory(string $directory): void {
    if (!is_dir($directory)) {
        return;
    }

    $iterator = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($directory, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::CHILD_FIRST
    );
    foreach ($iterator as $item) {
        $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
    }
    @rmdir($directory);
}

$projectRoot = dirname(__DIR__);
$requested = $pdo->query(
    'SELECT id, user_id FROM projects WHERE delete_requested_at IS NOT NULL ORDER BY delete_requested_at ASC LIMIT 100'
)->fetchAll();
$reaped = 0;

foreach ($requested as $project) {
    $projectId = (int)$project['id'];
    try {
        $pdo->beginTransaction();
        $lock = $pdo->prepare('SELECT id FROM projects WHERE id = ? FOR UPDATE');
        $lock->execute([$projectId]);
        if (!$lock->fetch()) {
            $pdo->rollBack();
            continue;
        }

        $active = $pdo->prepare(
            "SELECT COUNT(*) FROM ai_jobs WHERE project_id = ? AND status IN ('queued', 'processing')"
        );
        $active->execute([$projectId]);
        if ((int)$active->fetchColumn() > 0) {
            $pdo->rollBack();
            continue;
        }

        $videos = $pdo->prepare('SELECT file_path, output_path FROM videos WHERE project_id = ? FOR UPDATE');
        $videos->execute([$projectId]);
        $videoRows = $videos->fetchAll();
        $jobs = $pdo->prepare('SELECT id FROM ai_jobs WHERE project_id = ? FOR UPDATE');
        $jobs->execute([$projectId]);
        $jobRows = $jobs->fetchAll();

        // No active lease remains, so it is now safe to reap physical artifacts.
        foreach ($videoRows as $video) {
            removeProjectArtifact($projectRoot, $video['file_path']);
            removeProjectArtifact($projectRoot, $video['output_path']);
        }
        foreach ($jobRows as $job) {
            removeProjectDirectory($projectRoot . DIRECTORY_SEPARATOR . 'uploads' . DIRECTORY_SEPARATOR . 'temp' . DIRECTORY_SEPARATOR . (int)$job['id']);
        }

        $delete = $pdo->prepare('DELETE FROM projects WHERE id = ?');
        $delete->execute([$projectId]);
        $pdo->commit();
        $reaped++;
        appLog('delete', 'Project deletion finalized', ['project_id' => $projectId]);
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        error_log('Project deletion reaper failed: ' . $e->getMessage());
        appLog('error', 'Project deletion reaper failed', ['project_id' => $projectId, 'error' => $e->getMessage()]);
    }
}

echo "Reaped {$reaped} project(s)." . PHP_EOL;
