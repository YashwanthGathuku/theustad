param(
    [string]$InputVideo = "docs/video/theustad-build-week-demo-raw.mp4",
    [string]$OutputVideo = "docs/video/theustad-build-week-demo.mp4",
    [string]$OutputCaptions = "docs/video/theustad-build-week-demo.en.srt",
    [string]$EvidenceDirectory = "docs/evidence/theustad-1.0/video"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$inputPath = Join-Path $root $InputVideo
$outputPath = Join-Path $root $OutputVideo
$captionPath = Join-Path $root $OutputCaptions
$evidencePath = Join-Path $root $EvidenceDirectory
$buildDir = Join-Path $PSScriptRoot "build\theustad-narrated"
$markerPath = Join-Path $PSScriptRoot "build\theustad-demo-markers.txt"
$selectedVideo = Join-Path $buildDir "selected-source.mp4"
$narrationPath = Join-Path $buildDir "narration.wav"

foreach ($command in @("ffmpeg", "ffprobe")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "$command is required on PATH." }
}
if (-not (Test-Path -LiteralPath $inputPath)) { throw "Input video not found: $inputPath" }
if (-not (Test-Path -LiteralPath $markerPath)) { throw "Marker file not found: $markerPath" }

New-Item -ItemType Directory -Force -Path $buildDir, $evidencePath | Out-Null

function Format-SrtTime([double]$seconds) {
    $time = [TimeSpan]::FromSeconds($seconds)
    return ("{0:00}:{1:00}:{2:00},{3:000}" -f [int]$time.Hours, [int]$time.Minutes, [int]$time.Seconds, [int]$time.Milliseconds)
}

$cues = @(
    [pscustomobject]@{ Start = 0; End = 6; Text = "I show that TheUstad treats a coding agent's done message as a claim, not proof." }
    [pscustomobject]@{ Start = 6.2; End = 14; Text = "My control run is real Codex work on a pinned open-source project, but it has no protected verdict or audit root." }
    [pscustomobject]@{ Start = 14.2; End = 21; Text = "I install TheUstad as one Codex plugin; its standalone CLI uses the same enforcement core." }
    [pscustomobject]@{ Start = 21.2; End = 33; Text = "The run skill freezes trusted tests and configuration outside the target repository, starts a separate child Codex task, and resumes that exact child with verifier evidence." }
    [pscustomobject]@{ Start = 33.2; End = 43; Text = "FINAL VERIFIED means the explicit completion claim passed the configured protected verifier; it does not mean all software is universally correct." }
    [pscustomobject]@{ Start = 43.2; End = 54; Text = "This conftest-poisoning scene is a deterministic adversarial rehearsal. TheUstad reports TAMPERED and removes the planted protected file." }
    [pscustomobject]@{ Start = 54.2; End = 61.7; Text = "Changing a copied audit record makes validation BROKEN, while the untouched SHA-256 chain remains VALID against its externally anchored root." }
    [pscustomobject]@{ Start = 62; End = 69.9; Text = "I used Codex with GPT-5.6 to build, test, red-team, document, and package TheUstad for OpenAI Build Week." }
)
if (($cues | Where-Object { $_.End -ge 178 }).Count -gt 0) { throw "A narration cue ends at or after 178 seconds." }

$transcriptLines = foreach ($cue in $cues) { "[$(Format-SrtTime $cue.Start) - $(Format-SrtTime $cue.End)] $($cue.Text)" }
[System.IO.File]::WriteAllLines((Join-Path $root "docs\video\theustad-build-week-demo-transcript.txt"), $transcriptLines, [System.Text.UTF8Encoding]::new($false))

$srtLines = New-Object System.Collections.Generic.List[string]
for ($i = 0; $i -lt $cues.Count; $i++) {
    $cue = $cues[$i]
    $srtLines.Add(($i + 1).ToString())
    $srtLines.Add("$(Format-SrtTime $cue.Start) --> $(Format-SrtTime $cue.End)")
    $srtLines.Add($cue.Text)
    $srtLines.Add("")
}
[System.IO.File]::WriteAllLines($captionPath, $srtLines, [System.Text.UTF8Encoding]::new($false))

# Use scene markers to remove recorder pre-roll and accelerate only the live-run wait.
$markers = @(Get-Content -LiteralPath $markerPath | ForEach-Object {
    $parts = $_ -split '\s+', 2
    if ($parts.Count -ne 2) { throw "Invalid marker: $_" }
    [pscustomobject]@{ Timestamp = [int64]$parts[0]; Scene = $parts[1] }
})
if ($markers.Count -lt 2 -or $markers.Scene[-1] -ne "closing") { throw "Markers do not contain the complete ordered recording." }
$sceneOrder = @("intro", "control", "install", "plugin_start", "plugin_result", "tamper", "audit", "closing")
if (($markers.Scene -join ",") -ne ($sceneOrder -join ",")) { throw "Scene markers are missing or out of order." }
$rawDuration = [double](& ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $inputPath)
$selectedDuration = [math]::Min($rawDuration, [double](($markers[-1].Timestamp - $markers[0].Timestamp) + 4))
if ($selectedDuration -le 0) { throw "Could not derive a positive marker-bounded source duration." }
$sourceStart = [math]::Max(0, $rawDuration - $selectedDuration)
$pluginStart = [double](($markers | Where-Object Scene -eq "plugin_start").Timestamp - $markers[0].Timestamp)
$pluginResult = [double](($markers | Where-Object Scene -eq "plugin_result").Timestamp - $markers[0].Timestamp)
$speedStart = $pluginStart + 5
$speedEnd = $pluginResult - 2
if ($speedStart -ge $speedEnd) { throw "Plugin wait markers do not define an editable interval." }
$editedDuration = $speedStart + (($speedEnd - $speedStart) / 2) + ($selectedDuration - $speedEnd)
$presentationDuration = $editedDuration + 10
if (($cues | Measure-Object -Property End -Maximum).Maximum -gt $presentationDuration) { throw "Narration cues exceed the presentation duration." }
$culture = [System.Globalization.CultureInfo]::InvariantCulture
$sourceStartText = $sourceStart.ToString("0.###", $culture)
$middleStartText = ($sourceStart + $speedStart).ToString("0.###", $culture)
$middleEndText = ($sourceStart + $speedEnd).ToString("0.###", $culture)
$sourceEndText = ($sourceStart + $selectedDuration).ToString("0.###", $culture)
$editFilter = "[0:v]trim=start=$sourceStartText`:end=$middleStartText,setpts=PTS-STARTPTS[v0];[0:v]trim=start=$middleStartText`:end=$middleEndText,setpts=(PTS-STARTPTS)/2[v1];[0:v]trim=start=$middleEndText`:end=$sourceEndText,setpts=PTS-STARTPTS[v2];[v0][v1][v2]concat=n=3:v=1:a=0[vout]"
& ffmpeg -y -hide_banner -loglevel error -i $inputPath -filter_complex $editFilter -map "[vout]" -an -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p $selectedVideo
if ($LASTEXITCODE -ne 0) { throw "Could not create the marker-selected source video." }

$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $speaker.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -eq "Microsoft Zira Desktop" } | Select-Object -First 1
if ($voice) { $speaker.SelectVoice($voice.VoiceInfo.Name) }
$speaker.Rate = 2
$speaker.Volume = 100
$segmentPaths = New-Object System.Collections.Generic.List[string]
for ($i = 0; $i -lt $cues.Count; $i++) {
    $segmentPath = Join-Path $buildDir ("narration-{0:D2}.wav" -f $i)
    $speaker.SetOutputToWaveFile($segmentPath)
    $speaker.Speak($cues[$i].Text)
    $speaker.SetOutputToNull()
    $segmentDuration = [double](& ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $segmentPath)
    if ($segmentDuration -gt ($cues[$i].End - $cues[$i].Start)) { throw "Narration segment $i exceeds its caption window." }
    $segmentPaths.Add($segmentPath)
}
$speaker.Dispose()

$inputArgs = @("-y", "-hide_banner", "-loglevel", "error")
foreach ($segmentPath in $segmentPaths) { $inputArgs += @("-i", $segmentPath) }
$filters = New-Object System.Collections.Generic.List[string]
$mixInputs = ""
for ($i = 0; $i -lt $cues.Count; $i++) {
    $filters.Add("[$i`:a]adelay=$([int]($cues[$i].Start * 1000)):all=1[a$i]")
    $mixInputs += "[a$i]"
}
$filters.Add("$mixInputs" + "amix=inputs=$($cues.Count):duration=longest:normalize=0,alimiter=limit=0.95[aout]")
& ffmpeg @inputArgs -filter_complex ($filters -join ";") -map "[aout]" -c:a pcm_s16le $narrationPath
if ($LASTEXITCODE -ne 0) { throw "Could not mix SAPI narration." }

$captionFilterPath = $captionPath.Replace("\", "/").Replace(":", "\:")
$videoFilter = "tpad=stop_mode=clone:stop_duration=10,subtitles='$captionFilterPath':force_style='Fontname=Arial,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BackColour=&H80000000,BorderStyle=3,Outline=1,Shadow=0,Alignment=2,MarginV=24'"
$finalLimit = [math]::Min(178.0, $presentationDuration)
& ffmpeg -y -hide_banner -loglevel error -i $selectedVideo -i $narrationPath -vf $videoFilter -map 0:v:0 -map 1:a:0 -c:v libx264 -preset medium -crf 18 -c:a aac -b:a 160k -af "apad=pad_dur=178" -t $finalLimit -movflags +faststart $outputPath
if ($LASTEXITCODE -ne 0) { throw "Could not render the narrated video." }

$probe = & ffprobe -v error -show_entries stream=index,codec_type,codec_name,channels,width,height,duration -show_entries format=duration,size -of json $outputPath
if ($LASTEXITCODE -ne 0) { throw "ffprobe rejected the rendered video." }
[System.IO.File]::WriteAllText((Join-Path $evidencePath "video_probe.json"), ($probe -join [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))

$audioCheck = Join-Path $buildDir "volumedetect.txt"
$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& ffmpeg -v info -i $outputPath -map 0:a:0 -af volumedetect -f null NUL 2> $audioCheck
$audioExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorAction
if ($audioExitCode -ne 0) { throw "Audio audibility probe failed." }
$audioText = Get-Content -Raw -LiteralPath $audioCheck
if ($audioText -notmatch 'mean_volume:\s*(-?\d+(?:\.\d+)?) dB' -or [double]$Matches[1] -le -60) { throw "Narration audio is silent or missing." }

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $outputPath).Hash.ToUpperInvariant()
[System.IO.File]::WriteAllText((Join-Path $evidencePath "video_sha256.txt"), "$hash  theustad-build-week-demo.mp4`r`n", [System.Text.UTF8Encoding]::new($false))
$frameTimes = @(5, 18, 38, 49, 56, 67)
$finalDuration = [double](& ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $outputPath)
foreach ($seconds in $frameTimes) {
    if ($seconds -lt $finalDuration) {
        & ffmpeg -y -hide_banner -loglevel error -ss $seconds -i $outputPath -frames:v 1 (Join-Path $evidencePath ("inspection-{0:D3}s.png" -f $seconds))
        if ($LASTEXITCODE -ne 0) { throw "Could not extract inspection frame at $seconds seconds." }
    }
}

Write-Host "Narrated video: $outputPath"
Write-Host "Captions: $captionPath"
Write-Host "Probe: $(Join-Path $evidencePath 'video_probe.json')"
Write-Host "SHA-256: $hash"
