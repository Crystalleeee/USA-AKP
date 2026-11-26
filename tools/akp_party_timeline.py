"""Party room timeline for Arte kids park USA — minimal staffing with a facade event (v2, 2026-11-26).

Team defaults:
  * each team keeps its room for the whole 120-min party: party room 60 -> play 60
  * cleanup 30 min after the team leaves -> a room is rebooked 150 min after its last start
  * facade event at +60 (5 min), when the group leaves the room for play
  * open 10:00-20:00; a party must end by 20:00, so the last start is 18:00

Who does what (ASSUME):
  * check-in and the on-site birthday photo for the facade queue: ticket counter
  * guests wait at F&B and are called to the room by the call screen; the room is already set
  * party staff, fixed times: cake and media show 35..50, facade escort 55..65
  * party staff, flexible: cleanup and reset 30 min, any time between +120 and the room's next start

Run: python3 tools/akp_party_timeline.py
"""
import json

OPEN, LAST_START, CLOSE = 600, 1080, 1200
ROOMS = ["S1", "S2", "S3", "L"]
SHOW, FACADE_ESCORT = (35, 50), (55, 65)
CLEAN, HOLD, CYCLE = 30, 120, 150

# Staff shifts (minutes from midnight) and meal breaks (30 min, Colorado: shifts over 5 h)
WEEKEND_STAFF = {"A": {"on": (600, 1140), "meal": (840, 870)},     # 10:00-19:00, meal 14:00
                 "B": {"on": (690, 1230), "meal": (905, 935)}}     # 11:30-20:30, meal 15:05
WEEKDAY_STAFF = {"B": {"on": (660, 1230), "meal": (840, 870)}}     # 11:00-20:30, meal 14:00


def hm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def wave(step, first=OPEN):
    """Rooms start `step` min apart; each room is rebooked every 150 min."""
    out = []
    for i, r in enumerate(ROOMS):
        t = first + i * step
        while t <= LAST_START:
            out.append((t, r)); t += CYCLE
    return sorted(out)


def rotation(interval, first=OPEN):
    """One party every `interval` min, each in the room free the longest."""
    out, free, t = [], {r: 0 for r in ROOMS}, first
    while t <= LAST_START:
        cand = [x for x in ROOMS if free[x] <= t]
        if cand:
            r = min(cand, key=lambda x: free[x]); out.append((t, r)); free[r] = t + CYCLE
        t += interval
    return out


def assign(parties, staff):
    """1) place cleanups with a headcount model (people on shift and not on a meal break),
    2) hand each task, in time order, to a person who is free for its whole span."""
    def avail(m):
        return sum(1 for s in staff.values() if s["on"][0] <= m < s["on"][1] and not s["meal"][0] <= m < s["meal"][1])
    load = [0] * (CLOSE + 400)
    tasks = []
    for t, r in parties:
        for kind, (a, b) in (("show", SHOW), ("facade", FACADE_ESCORT)):
            tasks.append((t + a, t + b, kind, r))
            for m in range(t + a, t + b):
                load[m] += 1
    if any(load[m] > avail(m) for m in range(OPEN - 60, CLOSE + 60)):
        return None
    by = {}
    for t, r in parties:
        by.setdefault(r, []).append(t)
    nxt = {(a, r): b for r, ts in by.items() for a, b in zip(ts, ts[1:])}
    for t, r in sorted(parties):
        deadline, s = nxt.get((t, r), CLOSE + 30), t + HOLD
        while s + CLEAN <= deadline and any(load[m] >= avail(m) for m in range(s, s + CLEAN)):
            s += 1
        if s + CLEAN > deadline:
            return None
        for m in range(s, s + CLEAN):
            load[m] += 1
        tasks.append((s, s + CLEAN, "clean", r))
    busy = {p: set() for p in staff}

    def free(p, a, b):
        st = staff[p]
        return (st["on"][0] <= a and b <= st["on"][1] and not (a < st["meal"][1] and b > st["meal"][0])
                and not any(m in busy[p] for m in range(a, b)))
    out = []
    for a, b, kind, r in sorted(tasks):
        cand = [p for p in staff if free(p, a, b)]
        if not cand:
            return None
        # prefer the person whose shift ends first, so the later shift stays free for the evening
        who = min(cand, key=lambda p: staff[p]["on"][1])
        busy[who].update(range(a, b)); out.append((who, kind, r, a, b))
    return out


def summary(parties, staff):
    ev = sorted(t + 60 for t, _ in parties)
    gaps = [b - a for a, b in zip(ev, ev[1:])]
    tasks = assign(parties, staff)
    return {"parties": len(parties), "per_room": {r: sum(1 for _, x in parties if x == r) for r in ROOMS},
            "facade_min_gap": min(gaps), "facade_overlap": sum(1 for g in gaps if g < 5),
            "feasible": tasks is not None,
            "work_min": {p: sum(b - a for w, _, _, a, b in tasks if w == p) for p in staff} if tasks else None}


WEEKEND = wave(30)                 # recommended: rooms 30 min apart
WEEKEND_15 = wave(15)              # alternative: rooms 15 min apart
WEEKDAY = rotation(90, first=660)  # weekday: one party every 90 min from 11:00

RES = {"weekend_30": summary(WEEKEND, WEEKEND_STAFF),
       "weekend_15": summary(WEEKEND_15, WEEKEND_STAFF),
       "weekday_90": summary(WEEKDAY, WEEKDAY_STAFF),
       "weekday_60": summary(rotation(60, first=660), WEEKDAY_STAFF)}

if __name__ == "__main__":
    print(json.dumps(RES, ensure_ascii=False, indent=1))
    for name, (ps, st) in {"weekend_30": (WEEKEND, WEEKEND_STAFF), "weekday_90": (WEEKDAY, WEEKDAY_STAFF)}.items():
        print(name, [f"{hm(t)} {r}" for t, r in ps])
        for w, k, r, a, b in assign(ps, st):
            print("   ", w, k, r, hm(a), hm(b))

assert RES["weekend_30"]["parties"] == 14 and RES["weekend_30"]["feasible"]
assert RES["weekend_30"]["per_room"] == {"S1": 4, "S2": 4, "S3": 3, "L": 3}
assert RES["weekend_30"]["facade_min_gap"] == 30
assert RES["weekend_15"]["parties"] == 15 and RES["weekend_15"]["facade_min_gap"] == 15
assert not RES["weekend_15"]["feasible"]                             # 15-min spacing does not fit two people
assert all(v["facade_overlap"] == 0 for v in RES.values())
assert RES["weekday_90"]["parties"] == 5 and RES["weekday_90"]["feasible"]
assert assign(WEEKEND, {"A": WEEKEND_STAFF["A"]}) is None          # one person cannot run the weekend
