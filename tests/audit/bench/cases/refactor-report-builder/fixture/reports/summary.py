def build_report(all_lines: list[str]) -> str:
    totals: dict[str, int] = {}
    counts: dict[str, int] = {}
    skipped = 0
    for line in all_lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) != 3:
            skipped += 1
            continue
        region = parts[0].strip().lower()
        if not region:
            skipped += 1
            continue
        try:
            quantity = int(parts[1])
            unit_cents = int(parts[2])
        except ValueError:
            skipped += 1
            continue
        if quantity < 0 or unit_cents < 0:
            skipped += 1
            continue
        if region not in totals:
            totals[region] = 0
            counts[region] = 0
        totals[region] += quantity * unit_cents
        counts[region] += 1
    output = []
    output.append("REGION      ORDERS       TOTAL")
    grand_total = 0
    for region in sorted(totals):
        dollars = totals[region] // 100
        cents = totals[region] % 100
        output.append(
            region.upper().ljust(10) + str(counts[region]).rjust(8) + ("$" + str(dollars) + "." + str(cents).rjust(2, "0")).rjust(12)
        )
        grand_total += totals[region]
    dollars = grand_total // 100
    cents = grand_total % 100
    output.append("-" * 30)
    output.append("TOTAL".ljust(18) + ("$" + str(dollars) + "." + str(cents).rjust(2, "0")).rjust(12))
    if skipped:
        output.append("skipped lines: " + str(skipped))
    return "\n".join(output)
