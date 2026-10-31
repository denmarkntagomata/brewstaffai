"""
generate_dataset.py - creates the BrewStaffAI training data (Objective 1)
Runs the simulator under many random café conditions, averages 3 runs per
condition, and labels each row Okay / Congested / Overloaded.

Run:  python generate_dataset.py          (about 15 seconds)
Out:  data/dataset.csv
"""
import csv
import os
import random
import time

from sim_engine import simulate_avg
from labels import label, add_load_features, FEATURES

N_ROWS = 4000
REPS = 3
SEED = 2026

# Ranges based on the COMP 014 field observations at Jungle Brew
RANGES = dict(
    arr_rate=(0.10, 1.20),      # 6 to 72 customers per hour
    p_simple=(0.20, 0.80),
    cashier_mean=(0.7, 1.3),
    simple_prep=(1.5, 2.5),
    complex_prep=(3.5, 5.5),
)


def sample(rng):
    row = {k: round(rng.uniform(*v), 3) for k, v in RANGES.items()}
    row["num_cashier"] = rng.choice([1, 2])
    row["num_barista"] = rng.choice([1, 2, 3, 4])
    return row


def main():
    rng = random.Random(SEED)
    os.makedirs("data", exist_ok=True)
    cols = FEATURES + ["avg_wait", "balk_rate", "util_cashier", "util_barista", "label"]
    start = time.time()
    with open("data/dataset.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for i in range(N_ROWS):
            row = sample(rng)
            res = simulate_avg({**row, "duration": 60}, reps=REPS, base_seed=i * 10)
            row = add_load_features(row)
            row.update(avg_wait=round(res["avg_wait"], 3), balk_rate=round(res["balk_rate"], 4),
                       util_cashier=round(res["util_cashier"], 4), util_barista=round(res["util_barista"], 4))
            row["label"] = label(res["avg_wait"])
            w.writerow({k: (round(row[k], 4) if isinstance(row[k], float) else row[k]) for k in cols})
    print(f"Saved data/dataset.csv: {N_ROWS} rows in {time.time() - start:.1f} s")


if __name__ == "__main__":
    main()
