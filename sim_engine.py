"""
sim_engine.py — BrewStaffAI headless queueing simulator
=========================================================
Reused from the group's COMP 014 project (jungle_brew_gui_v5.py, class SimEngine).
Same model: customers arrive (Poisson), order at the cashier, then wait for the
barista (simple or complex drink). The Tkinter window, sleeps, and animation are
removed so the simulation can run thousands of times in seconds.

Three fixes from the COMP 014 version:
  FIX 1  Balking checks the TOTAL number of people waiting (cashier + barista line),
         not just the cashier line. Before, customers never balked.
  FIX 2  Customers still waiting when the time slot ends are counted in the
         average wait. Before, busy runs looked better than they really were.
  FIX 3  The simulation uses its own random generator (random.Random(seed)), so
         the same seed always gives the same result. Before, the coffee-smoke
         animation used the same random numbers and changed the results.
"""
import random
import simpy

DEFAULTS = dict(
    arr_rate=0.40,      # customers per minute (0.40 = 24 per hour; observed peak)
    p_simple=0.40,      # share of simple drinks
    num_cashier=1,
    cashier_mean=1.0,   # minutes per order at the cashier
    num_barista=1,
    simple_prep=2.0,    # minutes per simple drink
    complex_prep=4.5,   # minutes per complex drink
    duration=60,        # one time slot = 60 minutes
    balk_thresh=8,      # people waiting before a new customer walks out
    seed=42,
)


def simulate(params=None, **overrides):
    """Run one simulation and return a dictionary of results."""
    p = {**DEFAULTS, **(params or {}), **overrides}
    rng = random.Random(p["seed"])                       # FIX 3
    env = simpy.Environment()
    cashier = simpy.Resource(env, capacity=int(p["num_cashier"]))
    barista = simpy.Resource(env, capacity=int(p["num_barista"]))
    dur = p["duration"]

    waits, system_times = [], []
    in_system = {}                                       # customers not finished yet
    stats = {"arrived": 0, "balked": 0, "busy_c": 0.0, "busy_b": 0.0}

    def customer(cid, otype):
        stats["arrived"] += 1
        arrive = env.now
        if len(cashier.queue) + len(barista.queue) >= p["balk_thresh"]:   # FIX 1
            stats["balked"] += 1
            return
        rec = {"arrive": arrive, "service": 0.0, "since": None}
        in_system[cid] = rec

        with cashier.request() as req:
            yield req
            svc = rng.expovariate(1 / p["cashier_mean"])
            rec["since"] = env.now
            stats["busy_c"] += min(svc, max(0.0, dur - env.now))
            yield env.timeout(svc)
            rec["service"] += svc
            rec["since"] = None

        with barista.request() as req:
            yield req
            mean = p["simple_prep"] if otype == "simple" else p["complex_prep"]
            prep = rng.expovariate(1 / mean)
            rec["since"] = env.now
            stats["busy_b"] += min(prep, max(0.0, dur - env.now))
            yield env.timeout(prep)
            rec["service"] += prep
            rec["since"] = None

        waits.append(max(0.0, env.now - arrive - rec["service"]))
        system_times.append(env.now - arrive)
        del in_system[cid]

    def arrivals():
        cid = 0
        while True:
            yield env.timeout(rng.expovariate(p["arr_rate"]))
            if env.now >= dur:
                break
            cid += 1
            otype = "simple" if rng.random() < p["p_simple"] else "complex"
            env.process(customer(cid, otype))

    env.process(arrivals())
    env.run(until=dur)

    # FIX 2: count the waiting time so far of customers who are not finished yet
    unfinished = []
    for rec in in_system.values():
        done = rec["service"] + ((dur - rec["since"]) if rec["since"] is not None else 0.0)
        unfinished.append(max(0.0, (dur - rec["arrive"]) - done))
    all_waits = waits + unfinished

    arrived = stats["arrived"]
    return {
        "avg_wait": sum(all_waits) / len(all_waits) if all_waits else 0.0,
        "avg_system": sum(system_times) / len(system_times) if system_times else 0.0,
        "served": len(waits),
        "still_waiting": len(unfinished),
        "balked": stats["balked"],
        "arrived": arrived,
        "balk_rate": stats["balked"] / arrived if arrived else 0.0,
        "util_cashier": min(1.0, stats["busy_c"] / (p["num_cashier"] * dur)),
        "util_barista": min(1.0, stats["busy_b"] / (p["num_barista"] * dur)),
    }


def simulate_avg(params, reps=5, base_seed=1):
    """Run the same setup several times with different seeds and average the results."""
    runs = [simulate(params, seed=base_seed + i) for i in range(reps)]
    return {k: sum(r[k] for r in runs) / reps for k in runs[0]}


if __name__ == "__main__":
    # Quick check with the COMP 014 scenarios (60-minute slot)
    for name, ch in [("A Baseline", {}), ("B +1 Barista", {"num_barista": 2}),
                     ("D1 Promo surge", {"arr_rate": 0.60}),
                     ("D2 Surge + 3 baristas", {"arr_rate": 0.60, "num_barista": 3})]:
        r = simulate_avg({**DEFAULTS, **ch}, reps=20)
        print(f"{name:24s} wait={r['avg_wait']:5.2f} min  balk={r['balk_rate']*100:4.1f}%  "
              f"barista util={r['util_barista']*100:4.1f}%")
