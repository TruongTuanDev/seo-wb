param(
    [string]$AppDomain = "app.your-domain.com",
    [string]$ApiDomain = "api.your-domain.com",
    [string]$CookieDomain = ".your-domain.com",
    [string]$PostgresPassword = "",
    [string]$RabbitmqPassword = "",
    [switch]$KeepExistingSecrets
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Read-EnvFile {
    param([string]$Path)

    $data = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $data
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $idx = $trimmed.IndexOf("=")
        if ($idx -lt 1) {
            continue
        }

        $key = $trimmed.Substring(0, $idx).Trim()
        $value = $trimmed.Substring($idx + 1)

        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        $data[$key] = $value
    }

    return $data
}

function Write-EnvFile {
    param(
        [string]$Path,
        [hashtable]$Data,
        [string[]]$Order
    )

    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($key in $Order) {
        if ($Data.ContainsKey($key)) {
            $lines.Add(("{0}={1}" -f $key, $Data[$key]))
        }
    }

    $dir = Split-Path -Parent $Path
    if ($dir) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }

    Set-Content -LiteralPath $Path -Value $lines
}

function New-RandomHex {
    param([int]$Bytes = 24)

    $buffer = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buffer)
    return ([System.BitConverter]::ToString($buffer)).Replace("-", "").ToLowerInvariant()
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$localEnvPath = Join-Path $repoRoot "seo-wb-backend/.env"
$backendEnvPath = Join-Path $repoRoot "deploy/env/backend.env"
$composeEnvPath = Join-Path $repoRoot "deploy/env/compose.env"

$localEnv = Read-EnvFile -Path $localEnvPath
$existingBackendEnv = Read-EnvFile -Path $backendEnvPath
$existingComposeEnv = Read-EnvFile -Path $composeEnvPath

if (-not $KeepExistingSecrets) {
    $existingBackendEnv = @{}
    $existingComposeEnv = @{}
}

$backendOrder = @(
    "APP_NAME",
    "APP_ENV",
    "APP_SECRET_KEY",
    "JWT_EXPIRE_MINUTES",
    "JWT_BIND_USER_AGENT",
    "CORS_ALLOW_ORIGINS",
    "COOKIE_DOMAIN",
    "COOKIE_SECURE",
    "COOKIE_SAMESITE",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_CARD_MODEL",
    "OPENAI_IMAGE_MODEL",
    "OPENAI_IMAGE_CONCURRENCY",
    "OPENAI_IMAGE_RETRY_ATTEMPTS",
    "ENCRYPTION_KEY",
    "WB_CONTENT_BASE_URL",
    "WB_FINANCE_API_BASE_URL",
    "WB_COMMON_API_BASE_URL",
    "ENABLE_WB_RAW_PROXY",
    "AUTH_COOKIE_NAME",
    "CSRF_COOKIE_NAME",
    "ADMIN_AUTH_COOKIE_NAME",
    "ADMIN_CSRF_COOKIE_NAME",
    "AUTH_RATE_LIMIT_REQUESTS",
    "AUTH_RATE_LIMIT_WINDOW_SECONDS",
    "GLOBAL_RATE_LIMIT_REQUESTS",
    "GLOBAL_RATE_LIMIT_WINDOW_SECONDS",
    "DB_POOL_SIZE",
    "DB_MAX_OVERFLOW",
    "DB_POOL_RECYCLE_SECONDS",
    "MAX_GENERATE_IMAGES",
    "MAX_AI_PRODUCT_IMAGES",
    "MAX_UPLOAD_IMAGE_BYTES",
    "MAX_JOB_FILES",
    "MAX_MEDIA_UPLOAD_BYTES",
    "MAX_CARD_PAYLOAD_BYTES",
    "MAX_AI_CONCURRENCY",
    "MAX_BACKGROUND_JOBS",
    "ENABLE_IMAGE_VALIDATION_RETRY",
    "GENERATED_IMAGE_JPEG_QUALITY",
    "WB_TIMEOUT_SECONDS",
    "WB_MEDIA_TIMEOUT_SECONDS",
    "WB_MAX_CONNECTIONS",
    "WB_MAX_KEEPALIVE_CONNECTIONS",
    "WB_RETRY_ATTEMPTS",
    "WB_RETRY_BACKOFF_SECONDS",
    "WB_CATALOG_CACHE_TTL_SECONDS",
    "FINANCE_AUTO_SYNC_TIMEZONE",
    "FINANCE_BOOTSTRAP_LOOKBACK_DAYS",
    "FINANCE_SCHEDULER_POLL_SECONDS",
    "FINANCE_SCHEDULER_LEADER_LOCK_SECONDS",
    "FINANCE_AUTO_JOB_LOCK_SECONDS",
    "USAGE_RESET_SCHEDULER_POLL_SECONDS",
    "CLOUDINARY_CLOUD_NAME",
    "CLOUDINARY_API_KEY",
    "CLOUDINARY_API_SECRET"
)

$composeOrder = @(
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "RABBITMQ_USERNAME",
    "RABBITMQ_PASSWORD",
    "RABBITMQ_VHOST",
    "BACKEND_BIND_ADDRESS",
    "BACKEND_HTTP_PORT",
    "FRONTEND_BIND_ADDRESS",
    "FRONTEND_HTTP_PORT",
    "NEXT_PUBLIC_API_URL",
    "NEXT_PUBLIC_CSRF_COOKIE_NAME",
    "NEXT_PUBLIC_ENABLE_FINANCE"
)

$backendEnv = @{}
foreach ($key in $backendOrder) {
    if ($existingBackendEnv.ContainsKey($key)) {
        $backendEnv[$key] = $existingBackendEnv[$key]
    } elseif ($localEnv.ContainsKey($key)) {
        $backendEnv[$key] = $localEnv[$key]
    }
}

if (-not $backendEnv.ContainsKey("APP_NAME")) { $backendEnv["APP_NAME"] = "Seller WB AI Backend" }
if (-not $backendEnv.ContainsKey("APP_SECRET_KEY") -or [string]::IsNullOrWhiteSpace($backendEnv["APP_SECRET_KEY"])) {
    $backendEnv["APP_SECRET_KEY"] = New-RandomHex -Bytes 32
}
if (-not $backendEnv.ContainsKey("ENCRYPTION_KEY") -or [string]::IsNullOrWhiteSpace($backendEnv["ENCRYPTION_KEY"])) {
    $backendEnv["ENCRYPTION_KEY"] = New-RandomHex -Bytes 32
}
if (-not $backendEnv.ContainsKey("WB_FINANCE_API_BASE_URL")) { $backendEnv["WB_FINANCE_API_BASE_URL"] = "https://finance-api.wildberries.ru" }
if (-not $backendEnv.ContainsKey("WB_COMMON_API_BASE_URL")) { $backendEnv["WB_COMMON_API_BASE_URL"] = "https://common-api.wildberries.ru" }
if (-not $backendEnv.ContainsKey("MAX_AI_PRODUCT_IMAGES")) { $backendEnv["MAX_AI_PRODUCT_IMAGES"] = "10" }
if (-not $backendEnv.ContainsKey("ADMIN_AUTH_COOKIE_NAME")) { $backendEnv["ADMIN_AUTH_COOKIE_NAME"] = "seller_wb_admin_access" }
if (-not $backendEnv.ContainsKey("ADMIN_CSRF_COOKIE_NAME")) { $backendEnv["ADMIN_CSRF_COOKIE_NAME"] = "seller_wb_admin_csrf" }
if (-not $backendEnv.ContainsKey("FINANCE_AUTO_SYNC_TIMEZONE")) { $backendEnv["FINANCE_AUTO_SYNC_TIMEZONE"] = "Europe/Moscow" }
if (-not $backendEnv.ContainsKey("FINANCE_BOOTSTRAP_LOOKBACK_DAYS")) { $backendEnv["FINANCE_BOOTSTRAP_LOOKBACK_DAYS"] = "30" }
if (-not $backendEnv.ContainsKey("FINANCE_SCHEDULER_POLL_SECONDS")) { $backendEnv["FINANCE_SCHEDULER_POLL_SECONDS"] = "60" }
if (-not $backendEnv.ContainsKey("FINANCE_SCHEDULER_LEADER_LOCK_SECONDS")) { $backendEnv["FINANCE_SCHEDULER_LEADER_LOCK_SECONDS"] = "90" }
if (-not $backendEnv.ContainsKey("FINANCE_AUTO_JOB_LOCK_SECONDS")) { $backendEnv["FINANCE_AUTO_JOB_LOCK_SECONDS"] = "1800" }
if (-not $backendEnv.ContainsKey("USAGE_RESET_SCHEDULER_POLL_SECONDS")) { $backendEnv["USAGE_RESET_SCHEDULER_POLL_SECONDS"] = "86400" }

$backendEnv["APP_ENV"] = "production"
$backendEnv["CORS_ALLOW_ORIGINS"] = "https://$AppDomain"
$backendEnv["COOKIE_DOMAIN"] = $CookieDomain
$backendEnv["COOKIE_SECURE"] = "true"
if (-not $backendEnv.ContainsKey("COOKIE_SAMESITE")) { $backendEnv["COOKIE_SAMESITE"] = "lax" }

$composeEnv = @{}
foreach ($key in $composeOrder) {
    if ($existingComposeEnv.ContainsKey($key)) {
        $composeEnv[$key] = $existingComposeEnv[$key]
    }
}

$composeEnv["POSTGRES_DB"] = if ($composeEnv.ContainsKey("POSTGRES_DB")) { $composeEnv["POSTGRES_DB"] } else { "seo_wb_db" }
$composeEnv["POSTGRES_USER"] = if ($composeEnv.ContainsKey("POSTGRES_USER")) { $composeEnv["POSTGRES_USER"] } else { "postgres" }
$composeEnv["POSTGRES_PASSWORD"] = if ($PostgresPassword) { $PostgresPassword } elseif ($composeEnv.ContainsKey("POSTGRES_PASSWORD")) { $composeEnv["POSTGRES_PASSWORD"] } else { New-RandomHex }
$composeEnv["RABBITMQ_USERNAME"] = if ($composeEnv.ContainsKey("RABBITMQ_USERNAME")) { $composeEnv["RABBITMQ_USERNAME"] } else { "sellerwb" }
$composeEnv["RABBITMQ_PASSWORD"] = if ($RabbitmqPassword) { $RabbitmqPassword } elseif ($composeEnv.ContainsKey("RABBITMQ_PASSWORD")) { $composeEnv["RABBITMQ_PASSWORD"] } else { New-RandomHex }
$composeEnv["RABBITMQ_VHOST"] = if ($composeEnv.ContainsKey("RABBITMQ_VHOST")) { $composeEnv["RABBITMQ_VHOST"] } else { "sellerwb" }
$composeEnv["BACKEND_BIND_ADDRESS"] = "127.0.0.1"
$composeEnv["BACKEND_HTTP_PORT"] = if ($composeEnv.ContainsKey("BACKEND_HTTP_PORT")) { $composeEnv["BACKEND_HTTP_PORT"] } else { "8000" }
$composeEnv["FRONTEND_BIND_ADDRESS"] = "127.0.0.1"
$composeEnv["FRONTEND_HTTP_PORT"] = if ($composeEnv.ContainsKey("FRONTEND_HTTP_PORT")) { $composeEnv["FRONTEND_HTTP_PORT"] } else { "3000" }
$composeEnv["NEXT_PUBLIC_API_URL"] = "https://$ApiDomain/api/v1"
$composeEnv["NEXT_PUBLIC_CSRF_COOKIE_NAME"] = if ($backendEnv.ContainsKey("CSRF_COOKIE_NAME")) { $backendEnv["CSRF_COOKIE_NAME"] } else { "seller_wb_csrf" }
$composeEnv["NEXT_PUBLIC_ENABLE_FINANCE"] = if ($existingComposeEnv.ContainsKey("NEXT_PUBLIC_ENABLE_FINANCE")) { $existingComposeEnv["NEXT_PUBLIC_ENABLE_FINANCE"] } else { "false" }

Write-EnvFile -Path $backendEnvPath -Data $backendEnv -Order $backendOrder
Write-EnvFile -Path $composeEnvPath -Data $composeEnv -Order $composeOrder

Write-Host "Generated:"
Write-Host " - $backendEnvPath"
Write-Host " - $composeEnvPath"
Write-Host ""
Write-Host "Current production targets:"
Write-Host " - APP domain: https://$AppDomain"
Write-Host " - API domain: https://$ApiDomain"
Write-Host " - COOKIE_DOMAIN: $CookieDomain"
Write-Host ""
Write-Host "Review these values before deploy:"
Write-Host " - APP_SECRET_KEY"
Write-Host " - ENCRYPTION_KEY"
Write-Host " - POSTGRES_PASSWORD"
Write-Host " - RABBITMQ_PASSWORD"
