import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "docs" / "video"


def read_script(name):
    return (VIDEO / name).read_text(encoding="utf-8")


def test_wsl_demo_contains_the_eight_scene_proof_contract():
    wsl_script = read_script("run_theustad_demo_wsl.sh")

    assert "THEUSTAD 1.0 - CODING CLAIMS NEED PROOF" in wsl_script
    assert "WITHOUT THEUSTAD" in wsl_script
    assert "$theustad:run" in wsl_script
    assert "TAMPERED" in wsl_script
    assert "BROKEN" in wsl_script and "VALID" in wsl_script

    scenes = (
        "intro",
        "control",
        "install",
        "plugin_start",
        "plugin_result",
        "tamper",
        "audit",
        "closing",
    )
    for scene in scenes:
        assert re.search(rf"mark\s+{scene}\b", wsl_script)


def test_windows_recorder_is_fail_closed_and_uses_the_required_capture():
    powershell_script = read_script("record_theustad_demo.ps1")

    assert "ffmpeg" in powershell_script.lower()
    assert "gdigrab" in powershell_script
    assert "-draw_mouse 0" in powershell_script
    assert "1920" in powershell_script and "1080" in powershell_script
    assert "-framerate 12" in powershell_script
    assert "ffprobe" in powershell_script
    assert "theustad-build-week-demo-raw.mp4" in powershell_script

    configured_duration = re.search(
        r"\$timeoutSeconds\s*=\s*(\d+)", powershell_script
    ).group(1)
    assert int(configured_duration) < 720
    assert "180" not in configured_duration


def test_windows_recorder_requires_markers_in_order_and_clean_stop():
    powershell_script = read_script("record_theustad_demo.ps1")

    assert "intro" in powershell_script
    assert "closing" in powershell_script
    assert 'WriteLine("q")' in powershell_script
    assert "recording.status" in powershell_script
    assert "$recordedStatus" in powershell_script
    assert "-ne 0" in powershell_script
