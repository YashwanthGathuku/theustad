$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $here "build"
$output = Join-Path $here "gate-real-project-live.mp4"
$done = Join-Path $build "live-recording.done"
$status = Join-Path $build "live-recording.status"
$markers = Join-Path $build "live-recording-markers.txt"
$wslScript = "/mnt/c/Users/Gathu/Projects/gate/.worktrees/gate-codex-plugin/docs/video/run_live_comparison_wsl.sh"
$wslDone = "/mnt/c/Users/Gathu/Projects/gate/.worktrees/gate-codex-plugin/docs/video/build/live-recording.done"
$wslStatus = "/mnt/c/Users/Gathu/Projects/gate/.worktrees/gate-codex-plugin/docs/video/build/live-recording.status"
$wslMarkers = "/mnt/c/Users/Gathu/Projects/gate/.worktrees/gate-codex-plugin/docs/video/build/live-recording-markers.txt"

New-Item -ItemType Directory -Force -Path $build | Out-Null
Remove-Item -LiteralPath $done, $status, $markers -Force -ErrorAction SilentlyContinue

$ffmpeg = (Get-Command ffmpeg.exe -ErrorAction Stop).Source
$capture = New-Object System.Diagnostics.Process
$capture.StartInfo = New-Object System.Diagnostics.ProcessStartInfo
$capture.StartInfo.FileName = $ffmpeg
$capture.StartInfo.Arguments = @(
    "-y -loglevel warning",
    "-f gdigrab -framerate 12 -draw_mouse 0 -i desktop",
    "-c:v libx264 -preset veryfast -crf 24 -pix_fmt yuv420p",
    "-movflags +faststart `"$output`""
) -join " "
$capture.StartInfo.UseShellExecute = $false
$capture.StartInfo.RedirectStandardInput = $true
$capture.StartInfo.CreateNoWindow = $true
[void]$capture.Start()

$command = @"
`$Host.UI.RawUI.WindowTitle = 'Gate Live Proof'
wsl.exe -d Ubuntu-24.04 -u gathu -- env GATE_ROOT=/home/gathu/code/gate HARNESS_ROOT=/mnt/c/Users/Gathu/Projects/gate/.worktrees/gate-codex-plugin DEMO_HOME=/home/gathu/gate-video-code DEMO_VENV_HOME=/home/gathu/.local/share/gate-video-demo DEMO_EVIDENCE=/home/gathu/gate-video-recording-evidence VIDEO_DONE=$wslDone VIDEO_STATUS=$wslStatus VIDEO_MARKERS=$wslMarkers PATH=/home/gathu/.local/bin:/usr/local/bin:/usr/bin:/bin bash $wslScript
exit `$LASTEXITCODE
"@

$terminal = Start-Process powershell.exe -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-NoExit",
    "-Command", $command
) -PassThru

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class GateWindow {
    [DllImport("user32.dll")]
    public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@

for ($attempt = 0; $attempt -lt 50; $attempt++) {
    $terminal.Refresh()
    if ($terminal.MainWindowHandle -ne 0) {
        [GateWindow]::ShowWindowAsync($terminal.MainWindowHandle, 3) | Out-Null
        [GateWindow]::SetForegroundWindow($terminal.MainWindowHandle) | Out-Null
        break
    }
    Start-Sleep -Milliseconds 200
}

$runError = $null
try {
    $deadline = (Get-Date).AddMinutes(15)
    while (-not (Test-Path -LiteralPath $done)) {
        if ($terminal.HasExited) {
            throw "Live comparison terminal exited before writing the completion marker."
        }
        if ((Get-Date) -gt $deadline) {
            throw "Timed out waiting for the live comparison recording."
        }
        Start-Sleep -Seconds 1
    }
    if (-not (Test-Path -LiteralPath $status)) {
        throw "Live comparison did not write a status file."
    }
    $recordedStatus = [int](Get-Content -Raw -LiteralPath $status)
    if ($recordedStatus -ne 0) {
        throw "Live comparison exited with code $recordedStatus."
    }
} catch {
    $runError = $_
} finally {
    Start-Sleep -Seconds 1
    if (-not $capture.HasExited) {
        $capture.StandardInput.WriteLine("q")
        $capture.StandardInput.Flush()
        if (-not $capture.WaitForExit(30000)) {
            $capture.Kill()
        }
    }
    if (-not $terminal.HasExited) {
        $terminal.CloseMainWindow() | Out-Null
    }
}

if ($runError) {
    throw $runError
}
if ($capture.ExitCode -ne 0) {
    throw "FFmpeg exited with code $($capture.ExitCode)."
}

$probe = & ffprobe -v error -show_entries stream=width,height,duration,codec_name `
    -show_entries format=duration,size -of json $output
if ($LASTEXITCODE -ne 0) {
    throw "ffprobe rejected the recorded video."
}
$probe
Get-FileHash -Algorithm SHA256 -LiteralPath $output | Format-List
Write-Output "VIDEO $output"
