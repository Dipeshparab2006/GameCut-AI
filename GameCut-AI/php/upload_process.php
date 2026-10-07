<?php
// Keep AJAX responses clean and machine-readable.
ob_start();
require_once 'bootstrap.php';
require_once 'config.php';
require_once 'session.php';
require_once 'helpers.php';

requireAuth();

$isAjax = strtolower($_SERVER['HTTP_X_REQUESTED_WITH'] ?? '') === 'xmlhttprequest';

function uploadResponse($type, $message, $redirect = '../upload.php') {
    global $isAjax;

    setFlashMessage($type, $message);

    if ($isAjax) {
        while (ob_get_level() > 0) {
            ob_end_clean();
        }
        $ajaxRedirect = strpos($redirect, '../') === 0 ? substr($redirect, 3) : $redirect;
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode([
            'ok' => $type === 'success',
            'type' => $type,
            'message' => $message,
            'redirect' => $ajaxRedirect
        ]);
        exit();
    }

    header('Location: ' . $redirect);
    exit();
}

function cleanUploadName($value, $fallback) {
    $name = trim($value !== '' ? $value : $fallback);
    $name = preg_replace('/[^\p{L}\p{N}\s._-]+/u', '', $name);
    $name = preg_replace('/\s+/', ' ', $name);
    $name = trim($name, " ._-");

    if ($name === '') {
        $name = 'Gameplay Upload';
    }

    return mb_substr($name, 0, 120);
}

function videoSignatureMatches($path, $extension) {
    $handle = fopen($path, 'rb');
    if (!$handle) {
        return false;
    }

    $header = fread($handle, 64);
    fclose($handle);

    if (in_array($extension, ['mp4', 'mov'], true)) {
        return strlen($header) >= 12 && substr($header, 4, 4) === 'ftyp';
    }

    if ($extension === 'avi') {
        return substr($header, 0, 4) === 'RIFF' && substr($header, 8, 4) === 'AVI ';
    }

    if (in_array($extension, ['mkv', 'webm'], true)) {
        return substr($header, 0, 4) === "\x1A\x45\xDF\xA3";
    }

    return false;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    uploadResponse('error', 'Invalid upload request.');
}

if (!verifyCsrfToken($_POST['csrf_token'] ?? '')) {
    uploadResponse('error', 'Your session expired. Please refresh and upload again.');
}

$user = getCurrentUser();
$userId = (int)($user['id'] ?? 0);
$projectName = trim($_POST['project_name'] ?? '');
$game = trim($_POST['game'] ?? 'Other Game');
$style = trim($_POST['style'] ?? 'Esports');
$outputLength = trim($_POST['output_length'] ?? '30 sec');
$targetDuration = filter_var($_POST['target_duration'] ?? null, FILTER_VALIDATE_FLOAT);
$playbackSpeed = filter_var($_POST['playback_speed'] ?? null, FILTER_VALIDATE_FLOAT);
if ($targetDuration === false || $targetDuration === null) {
    $targetDuration = (float) preg_replace('/[^0-9.]/', '', $outputLength);
}
if ($targetDuration <= 0 || $targetDuration > 14400) {
    uploadResponse('error', 'Choose an output duration between 1 second and 4 hours.');
}
if ($playbackSpeed === false || $playbackSpeed === null) {
    $playbackSpeed = stripos($style, 'slow') !== false ? 0.5 : (stripos($style, 'fast') !== false ? 2.0 : 1.0);
}
if ($playbackSpeed < 0.25 || $playbackSpeed > 8) {
    uploadResponse('error', 'Playback speed must be between 0.25x and 8x.');
}
$file = $_FILES['gameplay_video'] ?? null;
$allowedExtensions = ['mp4', 'mov', 'mkv', 'avi', 'webm'];
$allowedMimeTypes = ['video/mp4', 'video/quicktime', 'video/x-matroska', 'video/x-mkv', 'video/x-msvideo', 'video/webm'];
$maxSize = 1024 * 1024 * 1024;

if (!$file || $file['error'] !== UPLOAD_ERR_OK) {
    appLog('upload', 'Upload rejected: invalid file field', ['user_id' => $userId, 'error_code' => $file['error'] ?? null]);
    uploadResponse('error', 'Please choose a valid gameplay video to upload.');
}

$originalName = $file['name'];
$extension = strtolower(pathinfo($originalName, PATHINFO_EXTENSION));
$mimeType = mime_content_type($file['tmp_name']) ?: ($file['type'] ?? 'application/octet-stream');
$safeOriginalName = mb_substr(basename($originalName), 0, 180);

if (!in_array($extension, $allowedExtensions, true) || !in_array($mimeType, $allowedMimeTypes, true)) {
    appLog('upload', 'Upload rejected: MIME or extension not allowed', ['user_id' => $userId, 'extension' => $extension, 'mime' => $mimeType]);
    uploadResponse('error', 'Only MP4, MOV, MKV, AVI, and WEBM videos are allowed.');
}

if (!videoSignatureMatches($file['tmp_name'], $extension)) {
    appLog('upload', 'Upload rejected: file signature mismatch', ['user_id' => $userId, 'filename' => $safeOriginalName, 'extension' => $extension]);
    uploadResponse('error', 'This file does not look like a valid video. Please export and upload a supported video file.');
}

if ((int)$file['size'] > $maxSize) {
    appLog('upload', 'Upload rejected: file too large', ['user_id' => $userId, 'filename' => $safeOriginalName, 'size' => (int)$file['size']]);
    uploadResponse('error', 'Maximum upload size is 1GB.');
}

$projectName = cleanUploadName($projectName, pathinfo($safeOriginalName, PATHINFO_FILENAME));

$stmt = $pdo->prepare(
    "SELECT COUNT(*) FROM videos
     WHERE user_id = ? AND original_filename = ? AND file_size = ? AND deleted_at IS NULL"
);
$stmt->execute([$userId, $safeOriginalName, (int)$file['size']]);
if ((int)$stmt->fetchColumn() > 0) {
    appLog('upload', 'Upload rejected: duplicate detected', ['user_id' => $userId, 'filename' => $safeOriginalName, 'size' => (int)$file['size']]);
    uploadResponse('error', 'This video already exists in your uploads.');
}

$uploadDir = dirname(__DIR__) . DIRECTORY_SEPARATOR . 'uploads' . DIRECTORY_SEPARATOR . 'original';
if (!is_dir($uploadDir)) {
    mkdir($uploadDir, 0775, true);
}

$storedName = 'user_' . $userId . '_' . date('YmdHis') . '_' . bin2hex(random_bytes(4)) . '.' . $extension;
$targetPath = $uploadDir . DIRECTORY_SEPARATOR . $storedName;
$relativePath = 'uploads/original/' . $storedName;
$description = sprintf('Game: %s | Style: %s | Output length: %s', $game, $style, $outputLength);

try {
    $pdo->beginTransaction();

    $stmt = $pdo->prepare("INSERT INTO projects (user_id, project_name, description, status, created_at) VALUES (?, ?, ?, 'draft', NOW())");
    $stmt->execute([$userId, $projectName, $description]);
    $projectId = (int)$pdo->lastInsertId();

    if (!move_uploaded_file($file['tmp_name'], $targetPath)) {
        throw new RuntimeException('Could not save uploaded file.');
    }

    $stmt = $pdo->prepare(
        "INSERT INTO videos (project_id, user_id, original_filename, stored_filename, file_path, file_size, mime_type, status, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, 'uploaded', NOW())"
    );
    $stmt->execute([
        $projectId,
        $userId,
        $safeOriginalName,
        $storedName,
        $relativePath,
        (int)$file['size'],
        $mimeType
    ]);
    $videoId = (int)$pdo->lastInsertId();

    $jobPayload = json_encode([
        'game' => $game,
        'style' => $style,
        'output_length' => $outputLength,
        'target_duration' => $targetDuration,
        'playback_speed' => $playbackSpeed,
        'source_path' => $relativePath,
        'original_filename' => $safeOriginalName
    ], JSON_THROW_ON_ERROR);

    $stmt = $pdo->prepare(
        "INSERT INTO ai_jobs (project_id, video_id, user_id, job_type, status, priority, payload, available_at, created_at)
         VALUES (?, ?, ?, 'video_processing', 'queued', 5, ?, NOW(), NOW())"
    );
    $stmt->execute([$projectId, $videoId, $userId, $jobPayload]);
    $jobId = (int)$pdo->lastInsertId();

    $pdo->commit();
    appLog('upload', 'Upload saved', ['user_id' => $userId, 'project_id' => $projectId, 'video_id' => $videoId, 'filename' => $safeOriginalName]);
    appLog('ai', 'AI job queued', ['user_id' => $userId, 'project_id' => $projectId, 'video_id' => $videoId, 'job_id' => $jobId]);
    uploadResponse('success', 'Gameplay uploaded. AI job queued for processing.', '../processing.php?project_id=' . $projectId);
} catch (Throwable $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }

    if (is_file($targetPath)) {
        unlink($targetPath);
    }

    error_log('Upload failed: ' . $e->getMessage());
    appLog('error', 'Upload failed', ['user_id' => $userId, 'message' => $e->getMessage()]);
    uploadResponse('error', 'Upload failed. Please try again.');
}
