# Codex and Claude Code
$skillsDirs = @(
    (Join-Path $HOME '.agents\skills'),
    (Join-Path $HOME '.claude\skills')
)

foreach ($skillsDir in $skillsDirs) {
    $targetDir = Join-Path $skillsDir 'review-loop'

    if (Test-Path -LiteralPath $targetDir) {
        Remove-Item -LiteralPath $targetDir -Recurse -Force -ErrorAction Stop
    }

    New-Item -ItemType Directory -Path $skillsDir -Force -ErrorAction Stop | Out-Null
    Copy-Item -LiteralPath '.\review-loop' -Destination $skillsDir -Recurse -Force -ErrorAction Stop
}
