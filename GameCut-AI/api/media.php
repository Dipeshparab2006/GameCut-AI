<?php
require_once dirname(__DIR__) . '/php/bootstrap.php';
require_once dirname(__DIR__) . '/php/config.php';
require_once dirname(__DIR__) . '/php/session.php';

requireAuth();
$projectId = (int)($_GET['project_id'] ?? 0);
$type = $_GET['type'] ?? 'output';
if ($projectId <= 0 || !in_array($type, ['source', 'output', 'thumbnail'], true)) { http_response_code(400); exit('Invalid media request'); }

$user = getCurrentUser();
$stmt = $pdo->prepare('SELECT v.file_path, v.output_path FROM videos v JOIN projects p ON p.id = v.project_id WHERE v.project_id = ? AND p.user_id = ? LIMIT 1');
$stmt->execute([$projectId, (int)$user['id']]);
$video = $stmt->fetch();
if (!$video) { http_response_code(404); exit('Media not found'); }

$relative = $type === 'source' ? $video['file_path'] : $video['output_path'];
if ($type === 'thumbnail' && $relative) $relative = pathinfo($relative, PATHINFO_DIRNAME) . '/' . pathinfo($relative, PATHINFO_FILENAME) . '_thumbnail.jpg';
$base = realpath(dirname(__DIR__) . '/uploads');
$path = $relative ? realpath(dirname(__DIR__) . '/' . ltrim($relative, '/\\')) : false;
if (!$base || !$path || !str_starts_with($path, $base . DIRECTORY_SEPARATOR) || !is_file($path)) { http_response_code(404); exit('Media file not found'); }

$mime = $type === 'thumbnail' ? 'image/jpeg' : 'video/mp4';
$size = filesize($path); $start = 0; $end = $size - 1;
header('Content-Type: ' . $mime); header('Accept-Ranges: bytes'); header('Cache-Control: private, max-age=3600');
if (isset($_SERVER['HTTP_RANGE']) && preg_match('/bytes=(\d*)-(\d*)/', $_SERVER['HTTP_RANGE'], $m)) {
    $start = $m[1] === '' ? max(0, $size - (int)$m[2]) : (int)$m[1];
    $end = $m[2] === '' ? $end : min($end, (int)$m[2]);
    if ($start > $end || $start >= $size) { http_response_code(416); header("Content-Range: bytes */$size"); exit; }
    http_response_code(206); header("Content-Range: bytes $start-$end/$size");
}
$length = $end - $start + 1; header('Content-Length: ' . $length);
$handle = fopen($path, 'rb'); fseek($handle, $start); $remaining = $length;
while ($remaining > 0 && !feof($handle)) { $chunk = fread($handle, min(1024 * 1024, $remaining)); echo $chunk; $remaining -= strlen($chunk); flush(); }
fclose($handle);
