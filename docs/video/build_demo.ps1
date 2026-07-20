$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $here "build"
$output = Join-Path $here "gate-v2-demo.mp4"

python (Join-Path $here "render_demo.py")

Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice.SelectVoice("Microsoft David Desktop")
$voice.Rate = 3
$voice.Volume = 100

$segments = @()
for ($index = 1; $index -le 8; $index++) {
    $number = "{0:D2}" -f $index
    $textPath = Join-Path $build "narration-$number.txt"
    $wavePath = Join-Path $build "narration-$number.wav"
    $imagePath = Join-Path $build "slide-$number.png"
    $segmentPath = Join-Path $build "segment-$number.mp4"

    $voice.SetOutputToWaveFile($wavePath)
    $voice.Speak((Get-Content -Raw -LiteralPath $textPath))
    $voice.SetOutputToNull()

    $audioDuration = [double](& ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $wavePath)
    $segmentDuration = $audioDuration + 1.0

    & ffmpeg -y -loglevel error -loop 1 -framerate 30 -i $imagePath -i $wavePath `
        -vf "scale=1920:1080,format=yuv420p" -af "apad=pad_dur=1" `
        -t $segmentDuration -c:v libx264 -preset medium -crf 20 -tune stillimage `
        -c:a aac -b:a 160k -movflags +faststart $segmentPath
    if ($LASTEXITCODE -ne 0) {
        throw "ffmpeg failed while rendering segment $number"
    }
    $segments += "file '$($segmentPath.Replace('\', '/'))'"
}
$voice.Dispose()

$concatPath = Join-Path $build "segments.txt"
[IO.File]::WriteAllLines(
    $concatPath,
    $segments,
    (New-Object System.Text.UTF8Encoding($false))
)

& ffmpeg -y -loglevel error -f concat -safe 0 -i $concatPath -c copy -movflags +faststart $output
if ($LASTEXITCODE -ne 0) {
    throw "ffmpeg failed while joining the demo"
}

& ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 $output
Write-Output "VIDEO $output"
