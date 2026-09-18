$sourceDir = Join-Path $PSScriptRoot 'review-loop'
$sourceSkillPath = Join-Path $sourceDir 'SKILL.md'
$requiredFiles = @($sourceSkillPath, (Join-Path $sourceDir 'agents\openai.yaml'))

foreach ($requiredFile in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf -ErrorAction Stop)) {
        throw "Missing skill file: $requiredFile"
    }
}

$skillContent = Get-Content -LiteralPath $sourceSkillPath -Raw -Encoding UTF8 -ErrorAction Stop
$pathComparison = [System.StringComparison]::Ordinal
if ([System.IO.Path]::DirectorySeparatorChar -eq '\') {
    $pathComparison = [System.StringComparison]::OrdinalIgnoreCase
}

# Resolve each existing ancestor, including junctions and symbolic links.
# Resolve-Path alone does not resolve all filesystem links.
function Get-CanonicalDirectory([string]$Path, [int]$LinkDepth = 0) {
    if ($LinkDepth -gt 40) { throw "Too many directory links: $Path" }
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $rootPath = [System.IO.Path]::GetPathRoot($fullPath)
    if ($fullPath.Equals($rootPath, $pathComparison)) { return $rootPath }
    $parentPath = Get-CanonicalDirectory ([System.IO.Path]::GetDirectoryName($fullPath)) $LinkDepth
    $candidate = Join-Path $parentPath ([System.IO.Path]::GetFileName($fullPath))
    try {
        $item = Get-Item -LiteralPath $candidate -Force -ErrorAction Stop
    } catch [System.Management.Automation.ItemNotFoundException] {
        return $candidate
    }
    # Cloud-backed directories can be reparse points without redirecting paths.
    # Only symbolic links and junctions need a target to be canonicalized.
    if ($item.LinkType -eq 'SymbolicLink' -or $item.LinkType -eq 'Junction') {
        $linkTarget = @($item.Target)[0]
        if (-not $linkTarget) { throw "Cannot resolve directory link: $candidate" }
        if (-not [System.IO.Path]::IsPathRooted($linkTarget)) {
            $linkTarget = Join-Path $parentPath $linkTarget
        }
        return Get-CanonicalDirectory $linkTarget ($LinkDepth + 1)
    }
    if (-not $item.PSIsContainer) { throw "Not a directory: $candidate" }
    return $candidate
}

function Test-PathOverlap([string]$First, [string]$Second) {
    $separator = [System.IO.Path]::DirectorySeparatorChar
    return $First.Equals($Second, $pathComparison) -or
        $First.StartsWith($Second.TrimEnd($separator) + $separator, $pathComparison) -or
        $Second.StartsWith($First.TrimEnd($separator) + $separator, $pathComparison)
}

$sourceDir = Get-CanonicalDirectory $sourceDir
$targets = @(
    (Join-Path $HOME '.agents\skills\review-loop'),
    (Join-Path $HOME '.claude\skills\review-loop')
)
$resolvedTargets = @()
foreach ($targetDir in $targets) {
    $resolved = Get-CanonicalDirectory $targetDir
    if (Test-PathOverlap $sourceDir $resolved) {
        throw "Source and destination overlap: $targetDir"
    }
    $resolvedTargets += $resolved
}
if (Test-PathOverlap $resolvedTargets[0] $resolvedTargets[1]) {
    throw 'Installation destinations overlap.'
}

$stages = @()
$locks = @()
$installing = $false
$completed = $false
try {
    # CreateNew is exclusive and shares the Bash installer's lock-file protocol.
    # Hold both locks until all cleanup and rollback operations have finished.
    foreach ($targetDir in $targets) {
        $skillsDir = Split-Path -Parent $targetDir
        New-Item -ItemType Directory -Path $skillsDir -Force -ErrorAction Stop | Out-Null
        $lockPath = Join-Path $skillsDir '.review-loop-install.lock'
        try {
            $lockStream = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        } catch {
            throw "Cannot acquire installation lock: $lockPath. Another installer may be running. $_"
        }
        $locks += $lockPath
        $lockStream.Dispose()
    }

    # Prepare both copies before replacing either installed skill.
    for ($i = 0; $i -lt $targets.Count; $i++) {
        $skillsDir = Split-Path -Parent $targets[$i]
        New-Item -ItemType Directory -Path $skillsDir -Force -ErrorAction Stop | Out-Null
        $stage = Join-Path $skillsDir ('.review-loop-install.' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $stage -ErrorAction Stop | Out-Null
        $stages += $stage
        $newDir = Join-Path $stage 'new'
        Copy-Item -LiteralPath $sourceDir -Destination $newDir -Recurse -Force -ErrorAction Stop
        if ($i -eq 1) {
            $claudeSkillContent = $skillContent -replace '\A---\r?\n', "---`ndisable-model-invocation: true`n"
            $preparedSkillPath = Join-Path $stage 'claude-skill.md'
            [System.IO.File]::WriteAllText($preparedSkillPath, $claudeSkillContent, [System.Text.UTF8Encoding]::new($false))
            Move-Item -LiteralPath $preparedSkillPath -Destination (Join-Path $newDir 'SKILL.md') -Force -ErrorAction Stop
        }
        foreach ($relativePath in @('SKILL.md', 'agents\openai.yaml')) {
            Get-Content -LiteralPath (Join-Path $newDir $relativePath) -Raw -ErrorAction Stop | Out-Null
        }
    }

    $installing = $true
    for ($i = 0; $i -lt $targets.Count; $i++) {
        if (Test-Path -LiteralPath $targets[$i] -ErrorAction Stop) {
            Move-Item -LiteralPath $targets[$i] -Destination (Join-Path $stages[$i] 'previous') -ErrorAction Stop
        }
        Move-Item -LiteralPath (Join-Path $stages[$i] 'new') -Destination $targets[$i] -ErrorAction Stop
    }
    $completed = $true
} finally {
    for ($i = $stages.Count - 1; $i -ge 0; $i--) {
        $stage = $stages[$i]
        try {
            if ($installing -and -not $completed) {
                if (-not (Test-Path -LiteralPath (Join-Path $stage 'new') -ErrorAction Stop)) {
                    Remove-Item -LiteralPath $targets[$i] -Recurse -Force -ErrorAction Stop
                }
                $previousDir = Join-Path $stage 'previous'
                if (Test-Path -LiteralPath $previousDir -ErrorAction Stop) {
                    Move-Item -LiteralPath $previousDir -Destination $targets[$i] -ErrorAction Stop
                }
            }
            Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction Stop
        } catch {
            Write-Warning "Cleanup or rollback failed; recovery files retained at ${stage}: $_"
        }
    }
    foreach ($lockPath in $locks) {
        try {
            Remove-Item -LiteralPath $lockPath -Force -ErrorAction Stop
        } catch {
            Write-Warning "Could not remove installation lock: ${lockPath}: $_"
        }
    }
}
