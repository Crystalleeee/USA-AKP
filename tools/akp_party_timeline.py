"""Party room timeline options for Arte kids park USA (minimal staffing, facade event).

Each party lasts 120 min: party room 0-60, facade event 60-65 (5 min), play 65-120.
A room needs at least 20 min after its 60 min of use before the next party starts.
Open 10:00-20:00, so the last party must start by 18:00.

Two party staff roles (ASSUME, minutes relative to party start):
  host   (진행): cake and media show 35..50, facade escort and event 55..65      -> 25 min
  runner (준비): welcome at the room -10..0, cleanup and reset 60..80           -> 30 min
Weekday solo (one person, check-in done by the ticket counter): cake/show 35..50, facade 55..65,
  cleanup 65..85 -> 50 min per party.
Food is pre-plated in the party pantry and set by the runner during reset; parents serve.

Run: python3 tools/akp_party_timeline.py
"""
import json

OPEN, LAST_START, CLOSE = 600, 1080, 1200
ROOMS = ["S1", "S2", "S3", "L"]
TASKS = {"host": [(35, 50), (55, 65)], "runner": [(-10, 0), (60, 80)]}
FACADE = (60, 65)


def hm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def wave(step, cycle):
    """Rooms start `step` min apart inside a wave; each room repeats every `cycle` min."""
    out = []
    for i, r in enumerate(ROOMS):
        t = OPEN + i * step
        while t <= LAST_START:
            out.append((t, r)); t += cycle
    return sorted(out)


def rotation(interval):
    """A new party every `interval` min, rooms in turn S1 -> S2 -> S3 -> L."""
    out, t, i = [], OPEN, 0
    while t <= LAST_START:
        out.append((t, ROOMS[i % 4])); t += interval; i += 1
    return out


def check(parties):
    last = {}
    for t, r in parties:                       # 60 min use + 20 min reset before the next party
        if r in last:
            assert t - last[r] >= 80, (r, hm(last[r]), hm(t))
        last[r] = t
    ev = sorted(t + FACADE[0] for t, _ in parties)
    gaps = [b - a for a, b in zip(ev, ev[1:])]
    peak = {}
    for role, spans in TASKS.items():
        load = [0] * (CLOSE + 200)
        for t, _ in parties:
            for a, b in spans:
                for m in range(t + a, t + b):
                    load[m] += 1
        peak[role] = max(load)
    busy_min = sum(b - a for spans in TASKS.values() for a, b in spans) * len(parties)
    return {"parties": len(parties), "per_room": {r: sum(1 for _, x in parties if x == r) for r in ROOMS},
            "facade_min_gap": min(gaps), "facade_overlap": sum(1 for g in gaps if g < FACADE[1] - FACADE[0]),
            "peak_host": peak["host"], "peak_runner": peak["runner"], "staff_needed": peak["host"] + peak["runner"],
            "staff_hours": round(busy_min / 60, 1)}


OPTS = {
    "15min_wave": wave(15, 90),        # 4 rooms 15 min apart, 90-min room cycle
    "20min_rotation": rotation(20),    # 80-min room cycle (60 use + 20 reset)
    "30min_rotation": rotation(30),    # 120-min room cycle
    "60min_weekday": rotation(60),     # weekday: one party an hour
}
RES = {k: check(v) for k, v in OPTS.items()}

if __name__ == "__main__":
    print(json.dumps(RES, indent=1))
    print("30min:", [(hm(t), r) for t, r in OPTS["30min_rotation"]])

assert RES["15min_wave"]["parties"] == 23 and RES["15min_wave"]["facade_min_gap"] == 15
assert RES["20min_rotation"]["parties"] == 25 and RES["20min_rotation"]["facade_min_gap"] == 20
assert RES["30min_rotation"]["parties"] == 17 and RES["30min_rotation"]["facade_min_gap"] == 30
assert RES["30min_rotation"]["per_room"] == {"S1": 5, "S2": 4, "S3": 4, "L": 4}
assert RES["60min_weekday"]["parties"] == 9
assert all(r["facade_overlap"] == 0 for r in RES.values())       # no facade clashes in any option
assert RES["30min_rotation"]["staff_needed"] == 2                # host 1 + runner 1
assert RES["60min_weekday"]["staff_needed"] == 2                 # same pair; one person can cover with gaps
SOLO = [(35, 50), (55, 65), (65, 85)]
def solo_peak(parties):
    load = [0] * (CLOSE + 200)
    for t, _ in parties:
        for a, b in SOLO:
            for m in range(t + a, t + b):
                load[m] += 1
    return max(load)
assert solo_peak(OPTS["60min_weekday"]) == 1                    # one person can run weekday parties hourly
assert solo_peak(OPTS["30min_rotation"]) == 2                   # but not every 30 min
assert RES["15min_wave"]["staff_needed"] >= 3 and RES["20min_rotation"]["staff_needed"] >= 3
