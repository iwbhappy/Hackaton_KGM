"""Excel-compatible UTF-8 BOM semicolon CSV."""
import csv
import io
from app.exporters.common import COLUMNS, csv_safe, display_value


def export_csv(rows: list[dict]) -> bytes:
    """Export all current result attributes with safe string cells."""
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
    writer.writerow([title for _, title in COLUMNS])
    for row in rows:
        writer.writerow([csv_safe(display_value(row, key)) for key, _ in COLUMNS])
    return output.getvalue().encode("utf-8-sig")
