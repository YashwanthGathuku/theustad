from iniconfig import IniConfig


def test_lengths_report_sections_and_section_entries() -> None:
    config = IniConfig(
        "gate-demo.ini",
        """\
[alpha]
first = 1
second = 2

[beta]
third = 3
""",
    )

    assert len(config) == 2
    assert len(config["alpha"]) == 2
    assert len(config["beta"]) == 1
