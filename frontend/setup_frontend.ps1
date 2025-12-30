# PowerShell script to set up the new frontend

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  AI Invoice Summarizer - Frontend Setup" -ForegroundColor Cyan
Write-Host "  Glassmorphism UI Installation" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$frontendPath = "c:\project\ai invoice summerizer\frontend"

# Navigate to frontend directory
Set-Location $frontendPath

Write-Host "Step 1: Installing dependencies..." -ForegroundColor Yellow
npm install

Write-Host "`nStep 2: Backing up old files..." -ForegroundColor Yellow

# Create backup directory
$backupDir = "src\backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

# Backup old files if they exist
if (Test-Path "src\App.jsx") {
    Move-Item "src\App.jsx" "$backupDir\App.jsx.old" -Force
    Write-Host "  ✓ Backed up App.jsx" -ForegroundColor Green
}

if (Test-Path "src\components\Layout.jsx") {
    Move-Item "src\components\Layout.jsx" "$backupDir\Layout.jsx.old" -Force
    Write-Host "  ✓ Backed up Layout.jsx" -ForegroundColor Green
}

# Backup old pages
$pagesToBackup = @("Dashboard.jsx", "ApprovalQueue.jsx", "InvoiceViewer.jsx")
foreach ($page in $pagesToBackup) {
    if (Test-Path "src\pages\$page") {
        Move-Item "src\pages\$page" "$backupDir\$page.old" -Force
        Write-Host "  ✓ Backed up $page" -ForegroundColor Green
    }
}

Write-Host "`nStep 3: Activating new files..." -ForegroundColor Yellow

# Rename new files to active names
if (Test-Path "src\AppNew.jsx") {
    Move-Item "src\AppNew.jsx" "src\App.jsx" -Force
    Write-Host "  ✓ Activated App.jsx" -ForegroundColor Green
}

if (Test-Path "src\components\LayoutNew.jsx") {
    Move-Item "src\components\LayoutNew.jsx" "src\components\Layout.jsx" -Force
    Write-Host "  ✓ Activated Layout.jsx" -ForegroundColor Green
}

# Activate new pages
$pagesToActivate = @(
    @{Old="DashboardNew.jsx"; New="Dashboard.jsx"},
    @{Old="ApprovalQueueNew.jsx"; New="ApprovalQueue.jsx"},
    @{Old="InvoiceViewerNew.jsx"; New="InvoiceViewer.jsx"}
)

foreach ($page in $pagesToActivate) {
    if (Test-Path "src\pages\$($page.Old)") {
        Move-Item "src\pages\$($page.Old)" "src\pages\$($page.New)" -Force
        Write-Host "  ✓ Activated $($page.New)" -ForegroundColor Green
    }
}

Write-Host "`nStep 4: Checking environment configuration..." -ForegroundColor Yellow

if (-not (Test-Path ".env")) {
    Write-Host "  Creating .env file..." -ForegroundColor Yellow
    @"
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=your_google_client_id_here
"@ | Out-File -FilePath ".env" -Encoding UTF8
    Write-Host "  ✓ Created .env file" -ForegroundColor Green
    Write-Host "  ⚠ Please update VITE_GOOGLE_CLIENT_ID in .env file" -ForegroundColor Yellow
} else {
    Write-Host "  ✓ .env file already exists" -ForegroundColor Green
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete! ✅" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "New Features:" -ForegroundColor Yellow
Write-Host "  ✨ Glassmorphism design system" -ForegroundColor White
Write-Host "  ✨ Google OAuth authentication" -ForegroundColor White
Write-Host "  ✨ Drag & drop file upload" -ForegroundColor White
Write-Host "  ✨ Invoice viewer with field editing" -ForegroundColor White
Write-Host "  ✨ Approval queue with actions" -ForegroundColor White
Write-Host "  ✨ Admin dashboard with charts" -ForegroundColor White
Write-Host "  ✨ Smooth animations & transitions" -ForegroundColor White
Write-Host "  ✨ Fully responsive design" -ForegroundColor White

Write-Host "`nTo start the development server:" -ForegroundColor Cyan
Write-Host "  npm run dev" -ForegroundColor White

Write-Host "`nThe application will be available at:" -ForegroundColor Cyan
Write-Host "  http://localhost:3000" -ForegroundColor White

Write-Host "`nBackup files saved in:" -ForegroundColor Cyan
Write-Host "  $frontendPath\$backupDir" -ForegroundColor White

Write-Host "`n✅ All done! Happy coding! 🚀`n" -ForegroundColor Green
