import sys

import local_report_cli as report_cli
import local_report_core as report_core

main = report_cli.main
PublicationOutcome = report_core.PublicationOutcome
publish_local_report = report_core.publish_local_report


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
