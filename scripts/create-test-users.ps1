# KAKEHASHI Phase 1 テストユーザー作成スクリプト (PowerShell)
#
# 使用方法:
#   .\scripts\create-test-users.ps1 `
#     -TenantId "xxxxx-xxxxx-xxxxx-xxxxx" `
#     -AppId "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" `
#     -AppSecret "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" `
#     -TenantDomain "company.onmicrosoft.com" `
#     -UserCount 12
#
# 前提条件:
#   - PowerShell 7+ / Windows PowerShell 5.1+
#   - Microsoft.Graph PowerShell SDK インストール
#   - Entra ID テナント管理者権限
#
# インストール:
#   Install-Module Microsoft.Graph -Force

param(
    [Parameter(Mandatory=$true)]
    [string]$TenantId,

    [Parameter(Mandatory=$true)]
    [string]$AppId,

    [Parameter(Mandatory=$true)]
    [string]$AppSecret,

    [Parameter(Mandatory=$true)]
    [string]$TenantDomain,

    [Parameter(Mandatory=$false)]
    [int]$UserCount = 12
)

# ========================================
# ログ関数
# ========================================
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# ========================================
# ステップ 1: Entra ID 認証
# ========================================
Write-Info "================================"
Write-Info "KAKEHASHI テストユーザー作成開始"
Write-Info "================================"
Write-Info "ステップ 1/3: Entra ID 認証中..."

try {
    $SecureAppSecret = ConvertTo-SecureString -String $AppSecret -AsPlainText -Force
    $Credential = New-Object System.Management.Automation.PSCredential($AppId, $SecureAppSecret)

    Connect-MgGraph -TenantId $TenantId -ClientSecretCredential $Credential -ErrorAction Stop > $null
    Write-Success "Entra ID 認証成功"
} catch {
    Write-Error "Entra ID 認証失敗: $_"
    exit 1
}

# ========================================
# ステップ 2: テストユーザー作成
# ========================================
Write-Info "ステップ 2/3: テストユーザー作成中..."

$CreatedUsers = @()
$FailedUsers = @()

for ($i = 1; $i -le $UserCount; $i++) {
    $UserNum = "{0:D3}" -f $i
    $UserPrincipalName = "rep-$UserNum@$TenantDomain"
    $DisplayName = "営業マン$UserNum"
    $TempPassword = "TempPassword@$(Get-Random -Minimum 100000 -Maximum 999999)"

    try {
        $PasswordProfile = @{
            ForceChangePasswordNextSignIn = $true
            Password = $TempPassword
        }

        $User = New-MgUser `
            -UserPrincipalName $UserPrincipalName `
            -DisplayName $DisplayName `
            -MailNickname "rep$UserNum" `
            -PasswordProfile $PasswordProfile `
            -AccountEnabled $true `
            -ErrorAction Stop

        $CreatedUsers += @{
            UserPrincipalName = $UserPrincipalName
            DisplayName = $DisplayName
            TempPassword = $TempPassword
            ObjectId = $User.Id
        }

        Write-Info "  ✓ $DisplayName ($UserPrincipalName) 作成完了"
    } catch {
        $FailedUsers += @{
            UserPrincipalName = $UserPrincipalName
            Error = $_.Exception.Message
        }
        Write-Warning "  ✗ $DisplayName 作成失敗: $($_.Exception.Message)"
    }
}

# ========================================
# ステップ 3: 結果レポート
# ========================================
Write-Info "ステップ 3/3: レポート生成中..."

$ReportFile = "test-users-report-$(Get-Date -Format 'yyyyMMdd-HHmmss').csv"

$CreatedUsers | Export-Csv -Path $ReportFile -NoTypeInformation -Encoding UTF8
Write-Success "レポート保存完了: $ReportFile"

# ========================================
# 完了サマリー
# ========================================
Write-Success "================================"
Write-Success "テストユーザー作成完了"
Write-Success "================================"
Write-Host ""
Write-Host "作成成功: $($CreatedUsers.Count) 名"
Write-Host "作成失敗: $($FailedUsers.Count) 名"
Write-Host ""

if ($CreatedUsers.Count -gt 0) {
    Write-Host "作成されたユーザー一覧:" -ForegroundColor Green
    $CreatedUsers | ForEach-Object {
        Write-Host "  $($_.DisplayName): $($_.UserPrincipalName)"
    }
}

if ($FailedUsers.Count -gt 0) {
    Write-Host "失敗したユーザー:" -ForegroundColor Yellow
    $FailedUsers | ForEach-Object {
        Write-Host "  $($_.UserPrincipalName): $($_.Error)"
    }
}

Write-Host ""
Write-Host "詳細レポート: $ReportFile" -ForegroundColor Cyan

# 接続を切断
Disconnect-MgGraph
