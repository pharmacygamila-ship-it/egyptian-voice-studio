# نشر المشروع على GitHub (سطر واحد)
#
# الاستخدام:
#   .\publish.ps1 -RepoUrl "https://github.com/USERNAME/REPO.git"
#
# قبل التشغيل لازم تكون أنشأت ريبو فاضي على GitHub (من غير README).

param(
    [Parameter(Mandatory = $true)]
    [string]$RepoUrl
)

git branch -M main

$existing = git remote 2>$null
if ($existing -contains "origin") {
    git remote set-url origin $RepoUrl
} else {
    git remote add origin $RepoUrl
}

Write-Host "→ الفرع: main | الريموت: $RepoUrl" -ForegroundColor Cyan
git push -u origin main

Write-Host "`n✅ تم الرفع. افتح الريبو على GitHub." -ForegroundColor Green
