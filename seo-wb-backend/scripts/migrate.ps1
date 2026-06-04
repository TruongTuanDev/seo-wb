Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    python .\scripts\migrate.py
}
finally {
    Pop-Location
}
