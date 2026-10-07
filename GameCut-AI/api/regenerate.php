<?php
require_once dirname(__DIR__) . '/php/bootstrap.php';
require_once dirname(__DIR__) . '/php/config.php';
require_once dirname(__DIR__) . '/php/session.php';
require_once dirname(__DIR__) . '/php/helpers.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

function regenerationResponse(int $status, bool $ok, string $message, array $extra = []): void {
    http_response_code($status);
    echo json_encode(array_merge(['ok' => $ok, 'message' => $message], $extra));
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    regenerationResponse(405, false, 'Method not allowed.');
}

if (!isLoggedIn()) {
    regenerationResponse(401, false, 'Unauthorized.');
}

if (!verifyCsrfToken($_POST['csrf_token'] ?? '')) {
    regenerationResponse(403, false, 'Invalid request. Refresh the page and try again.');
}

$projectId = filter_var($_POST['project_id'] ?? null, FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]);
$outputLength = (string)($_POST['output_length'] ?? '45');
$paddingBefore = filter_var($_POST['padding_before'] ?? 2, FILTER_VALIDATE_FLOAT);
$paddingAfter = filter_var($_POST['padding_after'] ?? 3, FILTER_VALIDATE_FLOAT);

if (!$projectId) {
    regenerationResponse(400, false, 'A valid project is required.');
}

if (!in_array($outputLength, ['30', '45', '60'], true)) {
    $outputLength = '45';
}

$paddingBefore = $paddingBefore === false ? 2.0 : max(0.0, min(10.0, (float)$paddingBefore));
$paddingAfter = $paddingAfter === false ? 3.0 : max(0.0, min(10.0, (float)$paddingAfter));
$user = getCurrentUser();
$userId = (int)($user['id'] ?? 0);

try {
    $pdo->beginTransaction();

    // Lock all execution rows before their project/video parents. The worker
    // claims in that same job -> project/video order, avoiding a regeneration
    // deadlock while an existing job is being claimed.
    $jobLockStmt = $pdo->prepare(
        'SELECT id, video_id, payload
         FROM ai_jobs
         WHERE project_id = ? AND user_id = ?
         ORDER BY id DESC
         FOR UPDATE'
    );
    $jobLockStmt->execute([$projectId, $userId]);
    $lockedJobs = $jobLockStmt->fetchAll();

    $projectStmt = $pdo->prepare(
        'SELECT p.id AS project_id, v.id AS video_id
         FROM projects p
         JOIN videos v ON v.project_id = p.id
         WHERE p.id = ? AND p.user_id = ?
         LIMIT 1
         FOR UPDATE'
    );
    $projectStmt->execute([$projectId, $userId]);
    $project = $projectStmt->fetch();

    if (!$project) {
        $pdo->rollBack();
        regenerationResponse(404, false, 'Project not found.');
    }

    $previousJob = null;
    foreach ($lockedJobs as $lockedJob) {
        if ((int)$lockedJob['video_id'] === (int)$project['video_id']) {
            $previousJob = $lockedJob;
            break;
        }
    }

    $previousPayload = [];
    if (!empty($previousJob['payload'])) {
        $decoded = json_decode((string)$previousJob['payload'], true);
        if (is_array($decoded)) {
            $previousPayload = $decoded;
        }
    }

    // A regeneration is a new immutable execution. Never reset an active row:
    // an old worker must not share its artifacts or be able to publish later.
    $cancelStmt = $pdo->prepare(
        "UPDATE ai_jobs
         SET status = 'cancelled',
             current_step = 'superseded_by_regeneration',
             error_message = 'Superseded by a newer regeneration request.',
             completed_at = NOW()
         WHERE video_id = ? AND status IN ('queued', 'processing')"
    );
    $cancelStmt->execute([(int)$project['video_id']]);

    $payload = [
        'game' => is_string($previousPayload['game'] ?? null) ? $previousPayload['game'] : 'Other Game',
        'style' => is_string($previousPayload['style'] ?? null) ? $previousPayload['style'] : 'Esports',
        'output_length' => $outputLength . ' sec',
        'target_duration' => (int)$outputLength,
        'playback_speed' => $previousPayload['playback_speed'] ?? 1.0,
        'padding_before' => $paddingBefore,
        'padding_after' => $paddingAfter,
        'source_path' => $previousPayload['source_path'] ?? null,
        'original_filename' => $previousPayload['original_filename'] ?? null,
        'regenerated' => true,
    ];
    $payload = array_filter($payload, static fn($value) => $value !== null);

    $insertStmt = $pdo->prepare(
        "INSERT INTO ai_jobs
            (project_id, video_id, user_id, job_type, status, priority, payload, available_at, created_at)
         VALUES (?, ?, ?, 'video_processing', 'queued', 5, ?, NOW(), NOW())"
    );
    $insertStmt->execute([
        (int)$project['project_id'],
        (int)$project['video_id'],
        $userId,
        json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES),
    ]);
    $newJobId = (int)$pdo->lastInsertId();

    $pdo->prepare("UPDATE projects SET status = 'processing', completed_at = NULL WHERE id = ?")
        ->execute([(int)$project['project_id']]);
    $pdo->prepare(
        "UPDATE videos
         SET status = 'processing', processing_started_at = NOW(), processing_completed_at = NULL
         WHERE id = ?"
    )->execute([(int)$project['video_id']]);

    $pdo->commit();

    appLog('ai', 'Regeneration queued', [
        'user_id' => $userId,
        'project_id' => (int)$project['project_id'],
        'video_id' => (int)$project['video_id'],
        'job_id' => $newJobId,
    ]);
    regenerationResponse(202, true, 'Regeneration queued.', ['job_id' => $newJobId]);
} catch (Throwable $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }

    error_log('Could not queue regeneration: ' . $e->getMessage());
    appLog('error', 'Regeneration queue failed', [
        'user_id' => $userId,
        'project_id' => (int)$projectId,
        'error' => $e->getMessage(),
    ]);
    regenerationResponse(500, false, 'Could not queue regeneration. Please try again.');
}
