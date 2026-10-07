<?php
require_once dirname(__DIR__) . '/php/bootstrap.php';
require_once dirname(__DIR__) . '/php/config.php';
require_once dirname(__DIR__) . '/php/session.php';
require_once dirname(__DIR__) . '/php/helpers.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

function deleteProjectResponse(int $status, bool $ok, string $message): void {
    http_response_code($status);
    echo json_encode(['ok' => $ok, 'message' => $message]);
    exit;
}

function removeProjectFile(string $projectRoot, ?string $relativePath): void {
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

function removeProjectTempDirectory(string $directory): void {
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

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    deleteProjectResponse(405, false, 'Method not allowed.');
}
if (!isLoggedIn()) {
    deleteProjectResponse(401, false, 'Unauthorized.');
}
if (!verifyCsrfToken($_POST['csrf_token'] ?? '')) {
    deleteProjectResponse(403, false, 'Invalid CSRF token.');
}

$projectId = filter_var($_POST['project_id'] ?? null, FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]);
$user = getCurrentUser();
$userId = (int)($user['id'] ?? 0);
if (!$projectId) {
    deleteProjectResponse(400, false, 'Invalid project ID.');
}

try {
    $pdo->beginTransaction();

    // Match worker locking order: jobs first, then the project/video records.
    // This turns a delete into a durable cancellation request instead of
    // removing files while FFmpeg may still be writing them.
    $jobLock = $pdo->prepare(
        'SELECT id FROM ai_jobs WHERE project_id = ? AND user_id = ? FOR UPDATE'
    );
    $jobLock->execute([$projectId, $userId]);

    $projectLock = $pdo->prepare(
        'SELECT id FROM projects WHERE id = ? AND user_id = ? FOR UPDATE'
    );
    $projectLock->execute([$projectId, $userId]);
    if (!$projectLock->fetch()) {
        $pdo->rollBack();
        deleteProjectResponse(404, false, 'Project not found.');
    }

    $processingStmt = $pdo->prepare(
        "SELECT COUNT(*) FROM ai_jobs WHERE project_id = ? AND user_id = ? AND status = 'processing'"
    );
    $processingStmt->execute([$projectId, $userId]);
    $hasProcessingJob = (int)$processingStmt->fetchColumn() > 0;

    $pdo->prepare(
        "UPDATE ai_jobs
         SET status = 'cancelled',
             current_step = 'cancelled_for_project_deletion',
             cancel_requested_at = COALESCE(cancel_requested_at, NOW()),
             error_message = 'Cancelled because the project was deleted.',
             completed_at = NOW()
         WHERE project_id = ? AND user_id = ? AND status = 'queued'"
    )->execute([$projectId, $userId]);

    $pdo->prepare(
        "UPDATE ai_jobs
         SET cancel_requested_at = COALESCE(cancel_requested_at, NOW()),
             delete_requested_at = NOW(),
             current_step = 'cancellation_requested',
             error_message = 'Cancelled because the project was deleted.'
         WHERE project_id = ? AND user_id = ? AND status = 'processing'"
    )->execute([$projectId, $userId]);

    // Queued jobs have not started writing media and can be removed now.
    // Processing jobs stay deferred until the worker has released ownership.
    if (!$hasProcessingJob) {
        $videosStmt = $pdo->prepare('SELECT file_path, output_path FROM videos WHERE project_id = ? FOR UPDATE');
        $videosStmt->execute([$projectId]);
        $videoRows = $videosStmt->fetchAll();
        $jobsStmt = $pdo->prepare('SELECT id FROM ai_jobs WHERE project_id = ? FOR UPDATE');
        $jobsStmt->execute([$projectId]);
        $jobRows = $jobsStmt->fetchAll();
        $pdo->prepare('DELETE FROM projects WHERE id = ? AND user_id = ?')->execute([$projectId, $userId]);
        $pdo->commit();

        $projectRoot = dirname(__DIR__);
        foreach ($videoRows as $video) {
            removeProjectFile($projectRoot, $video['file_path']);
            removeProjectFile($projectRoot, $video['output_path']);
        }
        foreach ($jobRows as $job) {
            removeProjectTempDirectory($projectRoot . DIRECTORY_SEPARATOR . 'uploads' . DIRECTORY_SEPARATOR . 'temp' . DIRECTORY_SEPARATOR . (int)$job['id']);
        }

        appLog('delete', 'Project deletion finalized immediately', ['user_id' => $userId, 'project_id' => $projectId]);
        deleteProjectResponse(200, true, 'Project and generated files deleted.');
    }

    $pdo->prepare('UPDATE projects SET delete_requested_at = NOW() WHERE id = ? AND user_id = ?')
        ->execute([$projectId, $userId]);
    $pdo->commit();

    appLog('delete', 'Project deletion requested', ['user_id' => $userId, 'project_id' => $projectId]);
    deleteProjectResponse(202, true, 'Project deletion is scheduled. Active processing will stop safely.');
} catch (Throwable $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }
    error_log('Project deletion request failed: ' . $e->getMessage());
    appLog('error', 'Project deletion request failed', [
        'user_id' => $userId,
        'project_id' => (int)$projectId,
        'error' => $e->getMessage(),
    ]);
    deleteProjectResponse(500, false, 'Could not schedule project deletion.');
}
