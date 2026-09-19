from reports.summary import build_report

ALL_LINES = ["east,2,1050", "West, 1, 999", "", "east,1,5", "bad line", "north,-1,100", "south,x,1", ",1,1"]

EXPECTED = "\n".join(
    [
        "REGION      ORDERS       TOTAL",
        "EAST             2      $21.05",
        "WEST             1       $9.99",
        "-" * 30,
        "TOTAL                   $31.04",
        "skipped lines: 4",
    ]
)


def test_report_text_is_stable():
    assert build_report(ALL_LINES) == EXPECTED


def test_no_skipped_line_when_clean():
    assert "skipped" not in build_report(["east,1,100"])
