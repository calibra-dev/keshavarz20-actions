param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('GET','POST','PUT','DELETE')]
    [string]$Method,

    [Parameter(Mandatory = $true)]
    [string]$Path,

    [string]$BodyJson = '',

    [int]$TimeoutSec = 120
)

$ErrorActionPreference = 'Stop'

$base = $env:WP_BASE_URL
$user = $env:WP_USERNAME
$pass = $env:WP_APP_PASSWORD

if ([string]::IsNullOrWhiteSpace($base) -or
    [string]::IsNullOrWhiteSpace($user) -or
    [string]::IsNullOrWhiteSpace($pass)) {
    throw 'Required WordPress repository secrets are missing.'
}

$base = $base.TrimEnd('/')
$pathPart = '/' + $Path.TrimStart('/')
$uri = $base + $pathPart

$authText = "$user`:$pass"
$authValue = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($authText))

$headers = @{
    Authorization = "Basic $authValue"
    Accept = 'application/json'
}

$params = @{
    Uri = $uri
    Method = $Method
    Headers = $headers
    TimeoutSec = $TimeoutSec
}

if (-not [string]::IsNullOrWhiteSpace($BodyJson)) {
    $params.ContentType = 'application/json; charset=utf-8'
    $params.Body = [Text.Encoding]::UTF8.GetBytes($BodyJson)
}

Invoke-RestMethod @params
