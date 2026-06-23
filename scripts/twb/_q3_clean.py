"""One-off: clean the Q3 Launch CSV (drop trailing-space duplicate columns) and
report value formats so IR column dataTypes can be set correctly."""
import csv, json, os

SRC = r"Data/Q3 Buyer/Q3LaunchData 1.csv"
DST = r"Data/Q3 Buyer/Q3LaunchData_clean.csv"
DROP = {"Delivery Month ", "Delivery Season ", "Region ", "Sales Area ",
        "Style Code ", "Style Description "}

with open(SRC, encoding="utf-8", newline="") as f:
    r = csv.reader(f)
    headers = next(r)
    rows = list(r)

keep_idx = [i for i, h in enumerate(headers) if h not in DROP]
keep_headers = [headers[i] for i in keep_idx]

with open(DST, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(keep_headers)
    for row in rows:
        w.writerow([row[i] for i in keep_idx])

idx = {h: i for i, h in enumerate(headers)}
sample = rows[0]
print("CLEAN COLS:", len(keep_headers))
print("Date:", sample[idx["Date"]], "| Delivery Date:", sample[idx["Delivery Date"]])
print("Order $ (USD):", sample[idx["Order $ (USD)"]], "| Margin $:", sample[idx["Margin $"]])
print("Year:", sample[idx["Year"]], "| Month:", sample[idx["Month"]])
print("Measure for Rank:", sample[idx["Measure for Rank"]])
print("HEADERS:", json.dumps(keep_headers))
