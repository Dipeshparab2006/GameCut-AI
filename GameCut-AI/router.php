<?php
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$file = __DIR__ . str_replace('/', DIRECTORY_SEPARATOR, rawurldecode($path));

if ($path === '/' || $path === '') {
    require __DIR__ . DIRECTORY_SEPARATOR . 'index.php';
    return true;
}

if (is_file($file)) {
    return false;
}

return false;
