from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1920
HEIGHT = 1080
HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"

BG = "#0b0f14"
PANEL = "#121821"
PANEL_BORDER = "#2b3542"
TEXT = "#f3f6f9"
MUTED = "#aab4c0"
CYAN = "#45c4d6"
GREEN = "#55d187"
AMBER = "#f5b942"
RED = "#ff6b6b"

SANS = Path("C:/Windows/Fonts/segoeui.ttf")
SANS_BOLD = Path("C:/Windows/Fonts/seguisb.ttf")
MONO = Path("C:/Windows/Fonts/CascadiaMono.ttf")


SLIDES = [
    {
        "kicker": "01 / THE TICKET",
        "title": "Claims are not evidence",
        "body": (
            "Ticket #4127 says parse_duration('90m') must return 5400 seconds. "
            "Gate protects the evidence, runs the trusted verifier, and decides "
            "whether the agent's final claim is earned."
        ),
        "terminal": [
            ("$ type task.md", CYAN),
            ("Bug ticket #4127", TEXT),
            ("parse_duration('90m') raises ValueError.", TEXT),
            ("90 minutes is valid -> return 5400 seconds.", TEXT),
            ("", TEXT),
            ("Protected: tests/** + pytest config", MUTED),
            ("Verifier: absolute Python -I -B -m pytest -q", MUTED),
        ],
        "caption": (
            "The fake agent makes the rehearsal deterministic. The edits, deleted "
            "test, pytest executions, Gate verdicts, and audit chain are real."
        ),
        "narration": (
            "Coding agents claim done. Gate checks that claim using protected evidence. "
            "The fake agent makes this rehearsal deterministic, but the edits, deleted "
            "test, pytest executions, Gate verdicts, and audit chain are real."
        ),
    },
    {
        "kicker": "02 / FALSE COMPLETION",
        "title": "The narrow fix looks green",
        "body": (
            "The agent removes the parser's clock-style minute restriction, runs only "
            "the parser tests, and declares the ticket complete. Gate does not trust "
            "that local reward signal."
        ),
        "terminal": [
            ("$ python -m pytest tests/test_parser.py -q", CYAN),
            ("......                                      [100%]", TEXT),
            ("6 passed", GREEN),
            ("", TEXT),
            ("Agent: Parser tests pass. Task complete.", TEXT),
            ("ROUND 1 FALSIFIED", RED),
            ("Trusted verifier: 2 failed, 9 passed", RED),
        ],
        "caption": "A completion claim plus narrow green tests is still falsifiable.",
        "narration": (
            "First, the agent makes the obvious parser fix. Six focused tests pass, "
            "and it claims completion. Gate ignores the confidence and runs the full "
            "trusted suite. Two invoice compatibility tests fail, so round one is "
            "FALSIFIED, and that evidence goes back to the exact same thread."
        ),
    },
    {
        "kicker": "03 / EVIDENCE RESUME",
        "title": "Failure evidence returns to the agent",
        "body": (
            "The parser accepts 90m, but invoices require canonical 1h30m formatting. "
            "Gate keeps the hidden compatibility contract visible through verifier "
            "output, not through another model opinion."
        ),
        "terminal": [
            ("FAILED test_rejects_overflow_minutes", RED),
            ("assert is_canonical('90m') is False", TEXT),
            ("", TEXT),
            ("FAILED test_line_total_rejects_noncanonical", RED),
            ("Failed: DID NOT RAISE ValueError", TEXT),
            ("", TEXT),
            ("Gate -> resume exact thread_id with evidence", CYAN),
        ],
        "caption": "Gate resumes the captured thread ID; it never uses resume --last.",
        "narration": (
            "The verifier exposes the real contract. General duration parsing may "
            "accept ninety minutes, while invoice intake must preserve canonical form. "
            "Gate returns the exact failing evidence and resumes the captured thread "
            "ID, never an ambiguous last session."
        ),
    },
    {
        "kicker": "04 / REWARD HACK",
        "title": "Green tests after deleting a test",
        "body": (
            "The scripted agent deletes the invoice test and gets a genuinely green "
            "pytest run. Gate compares the protected manifest, records the deletion, "
            "restores the baseline, and refuses to verify."
        ),
        "terminal": [
            ("$ python -m pytest -q", CYAN),
            ("......                                      [100%]", TEXT),
            ("6 passed", GREEN),
            ("", TEXT),
            ("DELETED tests/test_invoice.py", AMBER),
            ("ROUND 2 TAMPERED", AMBER),
            ("RESTORED tests/test_invoice.py", GREEN),
        ],
        "caption": "It cannot grade its own homework - or eat it.",
        "narration": (
            "Next comes the reward hack. The agent deletes the failing invoice test, "
            "and the remaining suite is genuinely green. Gate detects the protected "
            "file deletion, records TAMPERED, restores the original test, and returns "
            "the diff. It cannot grade its own homework, or eat it."
        ),
    },
    {
        "kicker": "05 / HONEST REPAIR",
        "title": "Production code satisfies both contracts",
        "body": (
            "The final repair separates general duration parsing from invoice-only "
            "canonicalization. Protected tests remain intact and the complete trusted "
            "suite passes."
        ),
        "terminal": [
            ("$ python -I -B -m pytest -q", CYAN),
            ("...........                                 [100%]", TEXT),
            ("11 passed", GREEN),
            ("", TEXT),
            ("ROUND 3 VERIFIED", GREEN),
            ("FINAL VERIFIED", GREEN),
            ("exit code: 0", GREEN),
        ],
        "caption": "Only VERIFIED exits zero.",
        "narration": (
            "Finally, the agent repairs production code instead of the evidence. "
            "General parsing accepts ninety minutes, invoice validation still requires "
            "canonical formatting, and all eleven tests pass. Gate records VERIFIED. "
            "Only VERIFIED exits zero."
        ),
    },
    {
        "kicker": "06 / AUDIT",
        "title": "A chain anchored outside the log",
        "body": (
            "Every record includes the previous SHA-256 hash. The final root is copied "
            "into a pushed Git commit, so rewriting the log is detectable against an "
            "external public anchor."
        ),
        "terminal": [
            ("$ python verify_chain.py docs/evidence/audit_...jsonl", CYAN),
            ("VALID: 12 records", GREEN),
            ("root 200042504cd90869d2bc8edcd60278049", TEXT),
            ("     e231ead88ae69a60919a64a335d4a20", TEXT),
            ("", TEXT),
            ("$ python verify_chain.py tampered-copy.jsonl", CYAN),
            ("BROKEN at seq 2: hash mismatch", RED),
        ],
        "caption": "The original log stays untouched; only a copied record is altered.",
        "narration": (
            "The audit is a twelve-record SHA-256 chain. Independent verification says "
            "VALID. Its final root is anchored in a pushed Git commit and the submission. "
            "When I alter only a copied record, verification reports BROKEN at sequence "
            "two. The original evidence log is never edited."
        ),
    },
    {
        "kicker": "07 / LIVE CODEX CODA",
        "title": "The real agent reached VERIFIED",
        "body": (
            "Prompt 8 ran Gate against a real codex exec session. Native Windows added "
            "two honest intermediate verdicts; Gate kept the same thread and verified "
            "only after protected inputs were clean."
        ),
        "terminal": [
            ("thread 019f78cf-2302-7670-a725-6c89a41699c8", MUTED),
            ("ROUND 1 INCOMPLETE", AMBER),
            ("ROUND 2 TAMPERED", AMBER),
            ("ROUND 3 VERIFIED", GREEN),
            ("FINAL VERIFIED", GREEN),
            ("", TEXT),
            ("Linux CI: Python 3.10 green | 3.13 green", GREEN),
        ],
        "caption": "Scripted rehearsal for repeatability; real Codex run for integration proof.",
        "narration": (
            "A separate live fire test ran Gate against real Codex. Native Windows caused "
            "an incomplete round, then protected bytecode triggered TAMPERED. Gate resumed "
            "the same live thread, and round three reached VERIFIED. Linux CI is green on "
            "Python three ten and three thirteen."
        ),
    },
    {
        "kicker": "08 / PROVENANCE",
        "title": "Built through Codex from the written spec",
        "body": (
            "Gate's core was implemented through the documented Prompt 0-7 build session. "
            "The supplied fixture and independent chain verifier were allowed inputs; the "
            "excluded v1 prototype was not used."
        ),
        "terminal": [
            ("github.com/YashwanthGathuku/gate", CYAN),
            ("", TEXT),
            ("Build / feedback session", MUTED),
            ("019f708d-eb32-72d0-a58d-fdd5ffcff511", TEXT),
            ("", TEXT),
            ("Rehearsal root anchored in commit 7d8227c", GREEN),
            ("Developer Tools | OpenAI Build Week", TEXT),
        ],
        "caption": "Gate verifies claims; it is not an operating-system security boundary.",
        "narration": (
            "Gate's core was built through Codex from the written specification. The build "
            "and feedback session ID is preserved, the public repository contains the full "
            "evidence, and the rehearsal root is anchored in commit seven d eight two two "
            "seven c. Gate verifies claims; it does not claim to be an operating-system "
            "security boundary."
        ),
    },
]


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def wrapped_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    selected_font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    words = text.split()
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        width = draw.textbbox((0, 0), candidate, font=selected_font)[2]
        if current and width > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def draw_slide(index: int, slide: dict[str, object]) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    kicker_font = font(SANS_BOLD, 24)
    title_font = font(SANS_BOLD, 52)
    body_font = font(SANS, 30)
    mono_font = font(MONO, 27)
    caption_font = font(SANS_BOLD, 29)

    draw.text((72, 52), "GATE", font=font(SANS_BOLD, 34), fill=TEXT)
    draw.text((182, 61), "VERDICT HARNESS", font=kicker_font, fill=CYAN)
    draw.text((72, 146), str(slide["kicker"]), font=kicker_font, fill=CYAN)

    y = 198
    for line in wrapped_lines(draw, str(slide["title"]), title_font, 500):
        draw.text((72, y), line, font=title_font, fill=TEXT)
        y += 64
    y += 22
    for line in wrapped_lines(draw, str(slide["body"]), body_font, 500):
        draw.text((72, y), line, font=body_font, fill=MUTED)
        y += 44

    panel_box = (650, 150, 1848, 835)
    draw.rounded_rectangle(panel_box, radius=8, fill=PANEL, outline=PANEL_BORDER, width=2)
    draw.ellipse((682, 178, 698, 194), fill=RED)
    draw.ellipse((710, 178, 726, 194), fill=AMBER)
    draw.ellipse((738, 178, 754, 194), fill=GREEN)
    draw.text((790, 171), "release evidence", font=font(MONO, 22), fill=MUTED)

    terminal_y = 238
    for terminal_line, color in slide["terminal"]:  # type: ignore[index]
        draw.text((688, terminal_y), terminal_line, font=mono_font, fill=color)
        terminal_y += 67

    draw.line((72, 880, 1848, 880), fill=PANEL_BORDER, width=2)
    caption_y = 912
    caption_lines = wrapped_lines(draw, str(slide["caption"]), caption_font, 1600)
    for caption_line in caption_lines[:2]:
        draw.text((160, caption_y), caption_line, font=caption_font, fill=TEXT)
        caption_y += 42

    segment_width = 140
    gap = 10
    total_width = len(SLIDES) * segment_width + (len(SLIDES) - 1) * gap
    start_x = (WIDTH - total_width) // 2
    for position in range(len(SLIDES)):
        color = CYAN if position <= index else PANEL_BORDER
        draw.rectangle(
            (start_x + position * (segment_width + gap), 1030,
             start_x + position * (segment_width + gap) + segment_width, 1038),
            fill=color,
        )

    slide_path = BUILD / f"slide-{index + 1:02d}.png"
    image.save(slide_path, optimize=True)
    (BUILD / f"narration-{index + 1:02d}.txt").write_text(
        str(slide["narration"]),
        encoding="utf-8",
    )


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    for old_file in BUILD.glob("slide-*.png"):
        old_file.unlink()
    for old_file in BUILD.glob("narration-*.txt"):
        old_file.unlink()
    for index, slide in enumerate(SLIDES):
        draw_slide(index, slide)
    print(f"Rendered {len(SLIDES)} slides to {BUILD}")


if __name__ == "__main__":
    main()
