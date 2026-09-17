$sourceDir = Join-Path $PSScriptRoot 'review-loop'
$sourceSkillPath = Join-Path $sourceDir 'SKILL.md'
$requiredFiles = @(
    $sourceSkillPath,
    (Join-Path $sourceDir 'agents\openai.yaml')
)

foreach ($requiredFile in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf -ErrorAction Stop)) {
        throw "Missing skill file: $requiredFile"
    }
}

$skillContent = Get-Content -LiteralPath $sourceSkillPath -Raw -Encoding UTF8 -ErrorAction Stop

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
    Copy-Item -LiteralPath $sourceDir -Destination $skillsDir -Recurse -Force -ErrorAction Stop
}

# Claude Code uses a frontmatter flag; Codex uses agents/openai.yaml.
$claudeSkillPath = Join-Path $HOME '.claude\skills\review-loop\SKILL.md'
$claudeSkillContent = $skillContent -replace '\A---\r?\n', "---`ndisable-model-invocation: true`n"
[System.IO.File]::WriteAllText($claudeSkillPath, $claudeSkillContent, [System.Text.UTF8Encoding]::new($false))
