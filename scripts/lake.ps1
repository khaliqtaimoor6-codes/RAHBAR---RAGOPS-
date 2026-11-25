# PowerShell front for scripts/lake.sh (Windows). Runs it with Git Bash, not WSL's bash
# (which is what plain `bash` means in PowerShell, and has no kubectl config).
#   .\scripts\lake.ps1 upload data\batch_b
#   .\scripts\lake.ps1 ingest | delete <doc_id> | restore <doc_id> | ls [path] | pull
$git = (Get-Command git -ErrorAction Stop).Source            # ...\Git\cmd\git.exe
$bash = Join-Path (Split-Path (Split-Path $git)) "bin\bash.exe"
if (-not (Test-Path $bash)) { throw "Git Bash not found next to $git" }
$argsFixed = @($args | ForEach-Object { $_ -replace '\\', '/' })   # @() keeps one arg an array
& $bash "$PSScriptRoot/lake.sh" @argsFixed
exit $LASTEXITCODE
