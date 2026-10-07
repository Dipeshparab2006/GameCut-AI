<?php
require_once dirname(__DIR__) . '/php/bootstrap.php';
require_once dirname(__DIR__) . '/php/config.php';
require_once dirname(__DIR__) . '/php/session.php';

header('Content-Type: application/json');

if (!isLoggedIn()) {
    http_response_code(401);
    echo json_encode(['ok' => false, 'message' => 'Unauthorized']);
    exit();
}

$user = getCurrentUser();
$userId = (int)($user['id'] ?? 0);
$projectId = (int)($_GET['project_id'] ?? 0);

if ($projectId <= 0) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'message' => 'Invalid project ID']);
    exit();
}

try {
    $stmt = $pdo->prepare(
        "SELECT p.id AS project_id, p.status AS project_status,
                v.output_path, latest_job.id AS job_id, latest_job.status AS job_status,
                latest_job.progress, latest_job.current_step, latest_job.error_message
         FROM projects p
         LEFT JOIN videos v ON v.project_id = p.id
         LEFT JOIN (
             SELECT j1.id, j1.video_id, j1.status, j1.progress, j1.current_step, j1.error_message
             FROM ai_jobs j1
             INNER JOIN (
                 SELECT video_id, MAX(id) AS latest_id
                 FROM ai_jobs
                 GROUP BY video_id
             ) newest ON newest.video_id = j1.video_id AND newest.latest_id = j1.id
         ) latest_job ON latest_job.video_id = v.id
         WHERE p.id = ? AND p.user_id = ? AND p.delete_requested_at IS NULL
         LIMIT 1"
    );
    $stmt->execute([$projectId, $userId]);
    $job = $stmt->fetch();

    if (!$job) {
        http_response_code(404);
        echo json_encode(['ok' => false, 'message' => 'Project not found']);
        exit();
    }

    echo json_encode([
        'ok' => true,
        'project_id' => (int)$job['project_id'],
        'project_status' => $job['project_status'],
        'job_id' => $job['job_id'] ? (int)$job['job_id'] : null,
        'job_status' => $job['job_status'] ?: $job['project_status'],
        'progress' => (int)($job['progress'] ?? 0),
        'current_step' => $job['current_step'] ?: ucfirst((string)($job['job_status'] ?: $job['project_status'])),
        'error_message' => $job['error_message'],
        'completed' => $job['job_status'] === 'completed' || $job['project_status'] === 'completed',
        'ready' => $job['project_status'] === 'completed' && !empty($job['output_path']),
        'preview_url' => appUrl('preview.php?project_id=' . (int)$job['project_id']),
    ]);
} catch (PDOException $e) {
    error_log('Job status error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['ok' => false, 'message' => 'Could not load job status']);
}
