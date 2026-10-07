<?php
/**
 * Application configuration.
 *
 * Environment variables are authoritative. A local .env file is supported
 * only for development convenience and is ignored by Git and Apache.
 */
function gamecutLoadEnvironmentFile(string $path): void
{
    if (!is_file($path) || !is_readable($path)) {
        return;
    }

    $lines = file($path, FILE_IGNORE_NEW_LINES);
    if ($lines === false) {
        throw new RuntimeException('The local environment file cannot be read.');
    }

    foreach ($lines as $line) {
        $line = trim($line);
        if ($line === '' || $line[0] === '#') {
            continue;
        }

        $separator = strpos($line, '=');
        if ($separator === false) {
            throw new RuntimeException('The local environment file contains an invalid entry.');
        }

        $key = trim(substr($line, 0, $separator));
        $value = trim(substr($line, $separator + 1));
        if (!preg_match('/\A[A-Z][A-Z0-9_]*\z/', $key)) {
            throw new RuntimeException('The local environment file contains an invalid variable name.');
        }

        if (strlen($value) >= 2) {
            $quote = $value[0];
            if (($quote === '"' || $quote === "'") && substr($value, -1) === $quote) {
                $value = substr($value, 1, -1);
            }
        }

        // Deployment-provided environment variables always win over .env.
        if (getenv($key) === false) {
            putenv($key . '=' . $value);
            $_ENV[$key] = $value;
        }
    }
}

function configValue(string $key, $default = null)
{
    $value = getenv($key);
    return $value === false || $value === '' ? $default : $value;
}

function configRequired(string $key, bool $allowEmpty = false): string
{
    $value = getenv($key);
    if ($value === false || (!$allowEmpty && trim($value) === '')) {
        throw new RuntimeException('Missing required configuration: ' . $key . '.');
    }

    return $value;
}

function configEmailList(string $key): array
{
    $value = configValue($key, '');
    if ($value === '') {
        return [];
    }

    $emails = [];
    foreach (explode(',', $value) as $email) {
        $email = strtolower(trim($email));
        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
            throw new RuntimeException('Invalid email configured in ' . $key . '.');
        }
        $emails[$email] = true;
    }

    return array_keys($emails);
}

function gamecutValidHost(string $host): bool
{
    return (bool) preg_match('/\A(?:[A-Za-z0-9.-]+|\[[A-Fa-f0-9:]+\])(?::[0-9]{1,5})?\z/', $host);
}

function gamecutNormalizeSiteUrl(string $url, bool $requireHttps): string
{
    if (filter_var($url, FILTER_VALIDATE_URL) === false) {
        throw new RuntimeException('GAMECUT_SITE_URL must be a valid absolute URL.');
    }

    $parts = parse_url($url);
    $scheme = strtolower($parts['scheme'] ?? '');
    if (!isset($parts['host']) || isset($parts['user']) || isset($parts['pass']) || isset($parts['query']) || isset($parts['fragment'])) {
        throw new RuntimeException('GAMECUT_SITE_URL must not contain credentials, a query string, or a fragment.');
    }
    if (!in_array($scheme, ['http', 'https'], true) || ($requireHttps && $scheme !== 'https')) {
        throw new RuntimeException('GAMECUT_SITE_URL must use HTTPS in production.');
    }

    return rtrim($url, '/');
}

function gamecutDevelopmentSiteUrl(): string
{
    $scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
    $configuredHost = configValue('GAMECUT_SITE_HOST', '');
    $requestHost = $_SERVER['HTTP_HOST'] ?? 'localhost';
    $host = $configuredHost !== '' ? $configuredHost : $requestHost;
    if (!gamecutValidHost($host)) {
        $host = 'localhost';
    }

    // Web requests use SCRIPT_NAME. CLI checks need the XAMPP project path.
    $defaultBasePath = configValue('GAMECUT_BASE_PATH', '/AI Video Editor/GameCut-AI');
    $scriptName = PHP_SAPI === 'cli'
        ? $defaultBasePath . '/index.php'
        : ($_SERVER['SCRIPT_NAME'] ?? $defaultBasePath . '/index.php');
    $scriptDir = str_replace('\\', '/', dirname($scriptName));
    $sitePath = rtrim($scriptDir, '/');

    if (preg_match('#/(php|api)$#', $sitePath)) {
        $sitePath = dirname($sitePath);
    }

    $encodedPath = implode('/', array_map('rawurlencode', array_filter(explode('/', $sitePath), 'strlen')));
    return $scheme . '://' . $host . ($encodedPath === '' ? '' : '/' . $encodedPath);
}

function appUrl(string $path = ''): string
{
    $base = rtrim(SITE_URL, '/');
    return $base . '/' . ltrim($path, '/');
}

$pdo = null;
$dbConnectionError = null;

try {
    gamecutLoadEnvironmentFile(dirname(__DIR__) . DIRECTORY_SEPARATOR . '.env');

    $appEnvironment = strtolower(trim((string) configValue('GAMECUT_APP_ENV', 'production')));
    if (!in_array($appEnvironment, ['development', 'testing', 'production'], true)) {
        throw new RuntimeException('GAMECUT_APP_ENV must be development, testing, or production.');
    }

    $dbHost = trim(configRequired('GAMECUT_DB_HOST'));
    $dbPort = filter_var(configRequired('GAMECUT_DB_PORT'), FILTER_VALIDATE_INT, [
        'options' => ['min_range' => 1, 'max_range' => 65535],
    ]);
    $dbName = trim(configRequired('GAMECUT_DB_NAME'));
    $dbUser = configRequired('GAMECUT_DB_USER');
    $dbPass = configRequired('GAMECUT_DB_PASS', $appEnvironment !== 'production');

    if (!gamecutValidHost($dbHost)) {
        throw new RuntimeException('GAMECUT_DB_HOST is invalid.');
    }
    if ($dbPort === false) {
        throw new RuntimeException('GAMECUT_DB_PORT must be between 1 and 65535.');
    }
    if (!preg_match('/\A[A-Za-z0-9$_-]{1,64}\z/', $dbName)) {
        throw new RuntimeException('GAMECUT_DB_NAME contains unsupported characters.');
    }
    if (strlen($dbUser) > 128 || preg_match('/[\x00-\x1F\x7F]/', $dbUser)) {
        throw new RuntimeException('GAMECUT_DB_USER is invalid.');
    }
    if ($appEnvironment === 'production' && strtolower($dbUser) === 'root') {
        throw new RuntimeException('The MySQL root account cannot be used in production.');
    }

    $configuredSiteUrl = defined('SITE_URL') ? SITE_URL : configValue('GAMECUT_SITE_URL', '');
    if ($configuredSiteUrl === '') {
        if ($appEnvironment === 'production') {
            throw new RuntimeException('GAMECUT_SITE_URL is required in production.');
        }
        $siteUrl = gamecutDevelopmentSiteUrl();
    } else {
        $siteUrl = gamecutNormalizeSiteUrl($configuredSiteUrl, $appEnvironment === 'production');
    }

    $phpMyAdminUrl = configValue('GAMECUT_PHPMYADMIN_URL', '');
    if ($appEnvironment === 'production' && $phpMyAdminUrl !== '') {
        throw new RuntimeException('GAMECUT_PHPMYADMIN_URL must not be configured in production.');
    }
    if ($phpMyAdminUrl !== '') {
        $phpMyAdminUrl = gamecutNormalizeSiteUrl($phpMyAdminUrl, false);
    }

    define('APP_ENV', $appEnvironment);
    define('DB_HOST', $dbHost);
    define('DB_PORT', (string) $dbPort);
    define('DB_NAME', $dbName);
    define('DB_USER', $dbUser);
    define('DB_PASS', $dbPass);
    if (!defined('SITE_URL')) {
        define('SITE_URL', $siteUrl);
    }
    define('SITE_NAME', 'GameCut AI');
    define('PHPMYADMIN_URL', $phpMyAdminUrl);

    $pdo = new PDO(
        'mysql:host=' . DB_HOST . ';port=' . DB_PORT . ';dbname=' . DB_NAME . ';charset=utf8mb4',
        DB_USER,
        DB_PASS,
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false,
            PDO::ATTR_TIMEOUT => 5,
        ]
    );
} catch (Throwable $e) {
    $dbConnectionError = 'Application configuration or database connection failed.';
    error_log('GameCut configuration/database failure: ' . $e->getMessage());

    if (defined('APP_ALLOW_DB_FAILURE') && APP_ALLOW_DB_FAILURE === true && defined('SITE_URL')) {
        return;
    }

    http_response_code(500);
    include __DIR__ . '/../500.php';
    exit();
}
