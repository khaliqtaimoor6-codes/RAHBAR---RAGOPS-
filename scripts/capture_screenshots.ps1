# Report appendix screenshots (Windows). For each item: open a real PowerShell console
# window, type out the prompt and the command, run the command against the cluster, then
# capture that window to docs/screenshots/<label>.png. Nothing is mocked: what is in the
# picture is what the command printed.
#
#   .\scripts\capture_screenshots.ps1                 # every shot below
#   .\scripts\capture_screenshots.ps1 -Only A1,F1     # some of them
#
# Do not type or click while it runs: each window must stay in front to be captured.
param([string[]]$Only = @(), [string]$TraceId = "")

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path "$PSScriptRoot\..").Path
$out = Join-Path $repo "docs\screenshots"
New-Item -ItemType Directory -Force $out | Out-Null

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class Win {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] public static extern IntPtr FindWindow(string c, string t);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool r);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int a, out RECT r, int s);
}
"@
[Win]::SetProcessDPIAware() | Out-Null

# label, command (as shown and run), console columns, rows, font height (px)
# Tall outputs get a smaller font so the whole window fits above the taskbar.
$shots = @(
  @("A1",   ".\scripts\lake.ps1 report 20261125T1846", 130, 28, 20),
  @("A1b",  ".\scripts\lake.ps1 report 20261125T184827", 130, 19, 20),
  @("A2",   ".\scripts\lake.ps1 ingest 2>&1 | Select-String -NotMatch '""logger""'", 120, 46, 16),
  @("D1",   "kubectl -n rahbar logs -l app=api --tail=-1 | Select-String '""trace_id"": ""__TRACE__""'", 210, 50, 14),
  @("D2-1", "kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_show __TRACE__ | Select-Object -First 44", 230, 56, 13),
  @("D2-2", "kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_show __TRACE__ | Select-Object -Skip 44 -First 27", 230, 40, 13),
  @("D2-3", "kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_show __TRACE__ | Select-Object -Skip 71", 230, 62, 13),
  @("D3",   "kubectl -n rahbar exec deploy/api -- python -m app.tools.trace_summary --since 6h", 110, 30, 20),
  @("F1",   "kubectl -n rahbar get all,pvc,configmap,cronjob,job", 165, 66, 13),
  @("F2",   "kubectl -n rahbar logs job/ingest -c ingest | Select-Object -Last 30", 210, 44, 14),
  @("F5",   "kubectl top pods -n rahbar --containers", 90, 14, 20)
)

function Get-FreshTrace {
  # Ask one question through a port-forward; its trace is the D1/D2 subject.
  $pf = Start-Process kubectl -ArgumentList "-n rahbar port-forward svc/api 18555:8000" -PassThru -WindowStyle Hidden
  Start-Sleep 4
  try {
    $body = '{"question": "How many guests can a graduate bring to the convocation?"}'
    $r = Invoke-RestMethod -Method Post -Uri http://localhost:18555/api/ask -ContentType 'application/json' -Body $body -TimeoutSec 90
    Write-Host "asked: trace $($r.trace_id) answered=$($r.answered_from_context): $($r.answer)"
    return $r.trace_id
  } finally { Stop-Process -Id $pf.Id -ErrorAction SilentlyContinue }
}

if (($Only.Count -eq 0 -or ($Only | Where-Object { $_ -like "D*" })) -and -not $TraceId) {
  $TraceId = Get-FreshTrace
}

foreach ($s in $shots) {
  $label, $cmd, $cols, $rows, $font = $s
  if ($Only.Count -and $Only -notcontains $label) { continue }
  $cmd = $cmd.Replace("__TRACE__", $TraceId)
  $title = "RAHBAR-SHOT-$label"
  $done = Join-Path $env:TEMP "$title.done"
  Remove-Item $done -ErrorAction SilentlyContinue
  $inner = @"
`$host.UI.RawUI.WindowTitle = '$title'
Add-Type -TypeDefinition '
using System; using System.Runtime.InteropServices;
public static class ConFont {
  [StructLayout(LayoutKind.Sequential)] public struct COORD { public short X; public short Y; }
  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] public struct INFO {
    public uint cbSize; public uint nFont; public COORD size; public int family; public int weight;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string face; }
  [DllImport("kernel32.dll")] public static extern IntPtr GetStdHandle(int n);
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] public static extern bool SetCurrentConsoleFontEx(IntPtr h, bool max, ref INFO f);
  public static bool Set(short height) { var f = new INFO(); f.cbSize = (uint)Marshal.SizeOf(f);
    f.size = new COORD { X = 0, Y = height }; f.family = 54; f.weight = 400; f.face = "Consolas";
    return SetCurrentConsoleFontEx(GetStdHandle(-11), false, ref f); } }
'
[ConFont]::Set($font) | Out-Null                    # this window only; console defaults untouched
[Console]::OutputEncoding = [Text.Encoding]::UTF8   # kubectl prints UTF-8
`$ui = `$host.UI.RawUI
# Shrink the window first: the buffer can never be narrower than the window.
`$ui.WindowSize = New-Object Management.Automation.Host.Size([Math]::Min($cols, `$ui.WindowSize.Width), [Math]::Min($rows, `$ui.WindowSize.Height))
`$ui.BufferSize = New-Object Management.Automation.Host.Size($cols, 3000)
`$ui.WindowSize = New-Object Management.Automation.Host.Size($cols, [Math]::Min($rows, `$ui.MaxPhysicalWindowSize.Height))
Set-Location '$repo'
Clear-Host
Write-Host -NoNewline ('PS ' + (Get-Location).Path + '> ')
Write-Host '$($cmd.Replace("'", "''"))'
$cmd
New-Item -ItemType File '$done' | Out-Null
"@
  $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($inner))
  $proc = Start-Process conhost.exe -ArgumentList "powershell.exe -NoExit -NoProfile -EncodedCommand $enc" -PassThru
  $deadline = (Get-Date).AddMinutes(10)
  while (-not (Test-Path $done) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
  Start-Sleep -Milliseconds 800
  # [NullString]::Value, not $null: PowerShell 5.1 turns $null into "" for a string argument
  $h = [Win]::FindWindow([NullString]::Value, $title)
  if ($h -eq [IntPtr]::Zero) { Write-Warning "$label : window not found"; continue }
  [Win]::ShowWindow($h, 9) | Out-Null
  $r0 = New-Object Win+RECT
  [Win]::GetWindowRect($h, [ref]$r0) | Out-Null
  [Win]::MoveWindow($h, 0, 0, $r0.R - $r0.L, $r0.B - $r0.T, $true) | Out-Null   # top-left, clear of the taskbar
  [Win]::SetForegroundWindow($h) | Out-Null
  Start-Sleep -Milliseconds 600
  $r = New-Object Win+RECT
  # DWMWA_EXTENDED_FRAME_BOUNDS (9): the visible window, without the invisible resize border
  [Win]::DwmGetWindowAttribute($h, 9, [ref]$r, 16) | Out-Null
  $w = $r.R - $r.L; $hh = $r.B - $r.T
  $bmp = New-Object Drawing.Bitmap $w, $hh
  $g = [Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
  $file = Join-Path $out "$label.png"
  $bmp.Save($file, [Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
  Write-Host "$label -> $file ($w x $hh)"
  Get-Process -Id $proc.Id -ErrorAction SilentlyContinue | Stop-Process -Force
  Get-Process powershell -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq $title } | Stop-Process -Force
}
"trace used for D1/D2: $TraceId"
