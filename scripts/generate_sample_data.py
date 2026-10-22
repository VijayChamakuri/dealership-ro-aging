"""Generate the synthetic repair order export in data/sample/.

The output is deterministic (fixed seed) and includes data quality issues
commonly found in DMS exports: inconsistent status casing and spacing, a
missing open date, and a repair order exported twice.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(21)
AS_OF = date(2026, 10, 21)
BRANCHES = ["Indianapolis", "Fort Wayne", "Columbus", "Nashville"]
STATUSES = [
    "Open",
    "Open",
    "Waiting on Parts",
    "In Progress",
    "Sublet Out",
    "Closed",
    "Invoiced",
    "Void",
]
PAYERS = ["Customer", "Warranty", "Internal"]
UNITS = [
    "Ford E-450 Shuttle Bus",
    "Ford Transit 350",
    "Chevy 4500 Cutaway",
    "Ram ProMaster",
    "Freightliner S2C School Bus",
]
COMPLAINTS = [
    "A/C not cooling",
    "Wheelchair lift inoperative",
    "Brake noise",
    "Check engine light",
    "PM service",
    "Door actuator fault",
    "Coolant leak",
    "Electrical short at rear heater",
]

rows = []
for i in range(1, 121):
    opened = AS_OF - timedelta(
        days=random.choice(
            [
                random.randint(0, 7),
                random.randint(8, 30),
                random.randint(31, 90),
                random.randint(91, 160),
            ]
        )
    )
    status = random.choice(STATUSES)
    rows.append(
        {
            "ro_number": f"RO{240000 + i}",
            "branch": random.choice(BRANCHES),
            "open_date": opened.isoformat(),
            "status": status,
            "payer_type": random.choice(PAYERS),
            "unit": random.choice(UNITS),
            "complaint": random.choice(COMPLAINTS),
            "technician": random.choice(
                ["T. Alvarez", "J. Brooks", "M. Chen", "R. Davis", "K. Evans", ""]
            ),
            "labor_hours": round(random.uniform(0.5, 14), 1),
            "labor_amount": 0,
            "parts_amount": round(random.uniform(0, 3200), 2),
        }
    )
    rows[-1]["labor_amount"] = round(rows[-1]["labor_hours"] * 165, 2)

# Data quality issues
rows[3]["status"] = "Closed "
rows[8]["status"] = "closed"
rows[15]["status"] = "INVOICED"
rows[22]["open_date"] = ""
rows.append(dict(rows[30]))

out = Path(__file__).resolve().parents[1] / "data" / "sample" / "repair_orders.csv"
with out.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"wrote {len(rows)} rows to {out}")
