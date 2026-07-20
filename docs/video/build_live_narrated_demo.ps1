param(
    [string]$InputVideo = "docs/video/gate-real-project-live.mp4",
    [string]$OutputVideo = "docs/video/gate-real-project-live-narrated.mp4",
    [string]$OutputCaptions = "docs/video/gate-real-project-live-narrated.en.srt"
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Speech

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$inputPath = Join-Path $root $InputVideo
$outputPath = Join-Path $root $OutputVideo
$captionPath = Join-Path $root $OutputCaptions
$buildDir = Join-Path $PSScriptRoot "build\live-narrated"

if (-not (Test-Path $inputPath)) {
    throw "Input video not found: $inputPath"
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "ffmpeg is required on PATH."
}

New-Item -ItemType Directory -Force $buildDir | Out-Null

# Keep each spoken claim synchronized with the real recording's milestones.
$cues = @(
    @{ Start = 0;   End = 11;  Text = "Gate v2 verifies coding agent completion claims. This is a real task in a pinned clone of the iniconfig project, recorded from Codex Desktop." },
    @{ Start = 12;  End = 27;  Text = "I used Codex with GPT-5.6 to make the requested change. First, this is the ordinary workflow without Gate." },
    @{ Start = 28;  End = 43;  Text = "Codex starts on the same task, changes the real project, and runs its tests. The task may look complete, but only the agent's final message explains the result." },
    @{ Start = 44;  End = 59;  Text = "There is no protected task binding, independent verdict, or audit root. A developer must trust the claim, inspect the work manually, or try to reconstruct the evidence later." },
    @{ Start = 60;  End = 75;  Text = "That is the gap Gate addresses. Passing a narrow test or saying done is not the same as a completion claim that can be checked by someone else." },
    @{ Start = 76;  End = 88;  Text = "Now Gate is installed from the public master branch and discovered in Codex as gate at personal." },
    @{ Start = 89;  End = 104; Text = "The gate run skill starts a fresh protected child task. The agent still performs the implementation work, while Gate enforces what has to be true before completion is accepted." },
    @{ Start = 105; End = 120; Text = "Gate binds the task, protects the verifier and test configuration, records the evidence, and independently checks the finished state." },
    @{ Start = 121; End = 137; Text = "Here, the child run changes the real project and runs the prescribed verification. Gate records manifest checks, timeout handling, the final claim, and the SHA-256 audit chain." },
    @{ Start = 138; End = 151; Text = "An agent cannot make a passing narrow test become a verified completion merely by writing a confident final message." },
    @{ Start = 152; End = 164; Text = "The result is FINAL VERIFIED. Gate reports the exact child thread ID, the audit root, and an independent verifier validates that chain." },
    @{ Start = 165; End = 174; Text = "Without Gate, Codex says the project is complete. With Gate, that completion claim is independently auditable." }
)

function Format-SrtTime([int]$seconds) {
    $time = [TimeSpan]::FromSeconds($seconds)
    return ("{0:00}:{1:00}:{2:00},000" -f $time.Hours, $time.Minutes, $time.Seconds)
}

$srtLines = New-Object System.Collections.Generic.List[string]
for ($i = 0; $i -lt $cues.Count; $i++) {
    $cue = $cues[$i]
    $srtLines.Add(($i + 1).ToString())
    $srtLines.Add("$(Format-SrtTime $cue.Start) --> $(Format-SrtTime $cue.End)")
    $srtLines.Add($cue.Text)
    $srtLines.Add("")
}
[System.IO.File]::WriteAllLines($captionPath, $srtLines, [System.Text.UTF8Encoding]::new($false))

$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.SelectVoice("Microsoft Zira Desktop")
$speaker.Rate = -1
$speaker.Volume = 100

$segmentPaths = New-Object System.Collections.Generic.List[string]
for ($i = 0; $i -lt $cues.Count; $i++) {
    $segmentPath = Join-Path $buildDir ("narration-{0:D2}.wav" -f $i)
    $speaker.SetOutputToWaveFile($segmentPath)
    $speaker.Speak($cues[$i].Text)
    $speaker.SetOutputToNull()
    $segmentPaths.Add($segmentPath)
}
$speaker.Dispose()

$inputArgs = @("-y", "-hide_banner", "-loglevel", "error")
foreach ($segmentPath in $segmentPaths) {
    $inputArgs += @("-i", $segmentPath)
}

$filters = New-Object System.Collections.Generic.List[string]
$mixInputs = ""
for ($i = 0; $i -lt $cues.Count; $i++) {
    $delay = [int]($cues[$i].Start * 1000)
    $filters.Add("[$($i):a]adelay=$($delay):all=1[a$i]")
    $mixInputs += "[a$i]"
}
$filters.Add("$mixInputs" + "amix=inputs=$($cues.Count):duration=longest:normalize=0,alimiter=limit=0.95[aout]")
$narrationPath = Join-Path $buildDir "narration.wav"
& ffmpeg @inputArgs -filter_complex ($filters -join ";") -map "[aout]" -c:a pcm_s16le $narrationPath
if ($LASTEXITCODE -ne 0) {
    throw "ffmpeg could not mix narration."
}

$captionFilterPath = $captionPath.Replace("\", "/").Replace(":", "\:")
$videoFilter = "subtitles='$captionFilterPath':force_style='Fontname=Arial,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BackColour=&H80000000,BorderStyle=3,Outline=1,Shadow=0,Alignment=2,MarginV=24'"
& ffmpeg -y -hide_banner -loglevel error -i $inputPath -i $narrationPath -vf $videoFilter -map 0:v:0 -map 1:a:0 -c:v libx264 -preset medium -crf 18 -c:a aac -b:a 160k -af "apad=pad_dur=175" -t 175 -movflags +faststart $outputPath
if ($LASTEXITCODE -ne 0) {
    throw "ffmpeg could not render narrated video."
}

Write-Host "Narrated video: $outputPath"
Write-Host "Caption file: $captionPath"
