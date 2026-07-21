$ErrorActionPreference = "Stop"

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$videoDir = Join-Path $repo "docs\video"
$build = Join-Path $videoDir "build"
$output = Join-Path $videoDir "theustad-build-week-demo-raw.mp4"
$markers = Join-Path $build "theustad-demo-markers.txt"
$done = Join-Path $build "recording.done"
$status = Join-Path $build "recording.status"
$timeoutSeconds = 660
$sceneOrder = @("intro", "control", "install", "plugin_start", "plugin_result", "tamper", "audit", "closing")

New-Item -ItemType Directory -Force -Path $build | Out-Null
Remove-Item -LiteralPath $output, $markers, $done, $status -Force -ErrorAction SilentlyContinue

$ffmpeg = (Get-Command ffmpeg.exe -ErrorAction Stop).Source
$ffprobe = (Get-Command ffprobe.exe -ErrorAction Stop).Source
$capture = New-Object System.Diagnostics.Process
$capture.StartInfo = New-Object System.Diagnostics.ProcessStartInfo
$capture.StartInfo.FileName = $ffmpeg
$capture.StartInfo.Arguments = @(
    "-y -loglevel warning",
    "-f gdigrab -framerate 12 -draw_mouse 0 -video_size 1920x1080 -i desktop",
    "-an -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p",
    "-movflags +faststart $output"
) -join " "
$capture.StartInfo.UseShellExecute = $false
$capture.StartInfo.RedirectStandardInput = $true
$capture.StartInfo.CreateNoWindow = $true
[void]$capture.Start()

$wslRepo = (& wsl.exe wslpath -a -u $repo).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($wslRepo)) { throw "Could not resolve the repository inside WSL." }
$wslScript = "$wslRepo/docs/video/run_theustad_demo_wsl.sh"
$wslMarkers = (& wsl.exe wslpath -a -u $markers).Trim()
$wslDone = (& wsl.exe wslpath -a -u $done).Trim()
$wslStatus = (& wsl.exe wslpath -a -u $status).Trim()
$command = "wsl.exe -d Ubuntu-24.04 -u gathu -- env THEUSTAD_ROOT='$wslRepo' VIDEO_MARKERS='$wslMarkers' VIDEO_DONE='$wslDone' VIDEO_STATUS='$wslStatus' bash '$wslScript'; exit " + '$LASTEXITCODE'

$terminal = Start-Process powershell.exe -ArgumentList @(
    "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-Command", $command
) -PassThru -WindowStyle Normal

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class TheUstadWindow {
    [DllImport("user32.dll")]
    public static extern bool ShowWindowAsync(IntPtr handle, int command);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr handle);
}
"@

for ($attempt = 0; $attempt -lt 50; $attempt++) {
    $terminal.Refresh()
    if ($terminal.MainWindowHandle -ne 0) {
        [TheUstadWindow]::ShowWindowAsync($terminal.MainWindowHandle, 3) | Out-Null
        [TheUstadWindow]::SetForegroundWindow($terminal.MainWindowHandle) | Out-Null
        break
    }
    Start-Sleep -Milliseconds 200
}

$runError = $null
try {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    while (-not (Test-Path -LiteralPath $done)) {
        if ($terminal.HasExited) { throw "The WSL recording terminal exited before writing the done marker." }
        if ((Get-Date) -gt $deadline) { throw "Timed out waiting for the WSL recording harness." }
        Start-Sleep -Seconds 1
    }
    if (-not (Test-Path -LiteralPath $status)) { throw "The WSL harness did not write a status file." }
    $recordedStatus = [int](Get-Content -Raw -LiteralPath $status)
    if ($recordedStatus -ne 0) { throw "The WSL harness exited with code $recordedStatus." }
} catch {
    $runError = $_
} finally {
    if (-not $capture.HasExited) {
        $capture.StandardInput.WriteLine("q")
        $capture.StandardInput.Flush()
        if (-not $capture.WaitForExit(30000)) { $capture.Kill() }
    }
    if (-not $terminal.HasExited) { $terminal.CloseMainWindow() | Out-Null }
}

if ($runError) { throw $runError }
if ($capture.ExitCode -ne 0) { throw "FFmpeg exited with code $($capture.ExitCode)." }
if (-not (Test-Path -LiteralPath $markers)) { throw "The WSL harness did not write scene markers." }

$actualScenes = @(
    Get-Content -LiteralPath $markers | ForEach-Object {
        $parts = $_ -split '\s+', 2
        if ($parts.Count -ne 2 -or $parts[1] -notin $sceneOrder) { throw "Invalid scene marker: $_" }
        $parts[1]
    }
)
if (($actualScenes -join ",") -ne ($sceneOrder -join ",")) { throw "Scene markers are missing or out of order." }

$probe = & $ffprobe -v error -show_entries stream=codec_name,width,height,duration -show_entries format=duration,size -of json $output
if ($LASTEXITCODE -ne 0) { throw "ffprobe rejected the recorded video." }
$probe
Get-FileHash -Algorithm SHA256 -LiteralPath $output | Format-List
Write-Output "VIDEO $output"
