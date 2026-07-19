import io

import gate


def test_console_output_escapes_characters_unsupported_by_stream_encoding():
    raw = io.BytesIO()
    stream = io.TextIOWrapper(
        raw,
        encoding="cp1252",
        errors="strict",
        newline="",
    )

    gate._console_output("before \x9d after", stream=stream)
    stream.flush()

    assert raw.getvalue().decode("cp1252") == "before \\x9d after\n"
