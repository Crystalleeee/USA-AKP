"""AKP party room simulation. All inputs are labelled: DECK (internal deck), CITED (public source), ASSUME (assumption)."""
import json, math
SF_PER_M2 = 10.7639
IBC_TABLES = 15.0   # CITED: IBC Table 1004.5 unconcentrated (tables and chairs), 15 net sf/person
rooms = {"small": {"m2": 10.0, "n": 3, "kids": 10, "price": 300},   # DECK
         "large": {"m2": 14.4, "n": 1, "kids": 15, "price": 450}}   # DECK
out = {}

# 1) Occupant-load check
def max_occ(m2): return math.floor(m2 * SF_PER_M2 / IBC_TABLES)
def need_m2(p): return p * IBC_TABLES / SF_PER_M2
occ = {}
for k, r in rooms.items():
    occ[k] = {"m2": r["m2"], "sf": round(r["m2"]*SF_PER_M2, 1), "ibc_max": max_occ(r["m2"]),
              "scen": {}}
    for label, extra in [("kids+host", 1), ("kids+host+2parents", 3), ("kids+host+parents_all", 1 + r["kids"])]:
        p = r["kids"] + extra
        occ[k]["scen"][label] = {"persons": p, "need_m2": round(need_m2(p), 1)}
out["occupancy"] = occ
# 1b) ACTUAL design dimensions (user, 2026-11-05): small 4.9x6.0 m x2, 5.0x6.0 m x1, large 6.0x7.0 m x1
COMFORT_M2 = 2.0   # ASSUME comfortable party layout, m2 per person (not a code value)
actual = {"small_ab": 4.9*6.0, "small_c": 5.0*6.0, "large": 6.0*7.0}
out["occupancy_actual"] = {k: {"m2": round(v, 1), "sf": round(v*SF_PER_M2, 1), "ibc_max": max_occ(v),
                               "comfort_max": math.floor(v / COMFORT_M2)} for k, v in actual.items()}
out["occupancy_actual"]["total_m2"] = round(sum([actual["small_ab"]*2, actual["small_c"], actual["large"]]), 1)
assert max_occ(29.4) == 21 and max_occ(30.0) == 21 and max_occ(42.0) == 30
assert need_m2(13) <= 29.4 and need_m2(18) <= 42.0      # plan + 2 parents fits in every room
assert need_m2(31) > 42.0                                 # control: large room with every invited parent does not fit
assert max_occ(10.0) == 7 and max_occ(14.4) == 10          # failure control: values the text will quote
assert max_occ(20.0) != 7                                   # a larger room must not give the same answer

# 2) Weekly slots by operating calendar (DECK: school term Mon/Fri/Sat/Sun 10-20 -> 4 slots; Tue-Thu 12-20 -> 3 slots)
slot_days = {"weekend": (2, 4), "fri": (1, 4), "mon": (1, 4), "tue_thu": (3, 3)}
# ASSUME utilisation per slot by day type (conservative / base / optimistic)
util = {"conservative": {"weekend": .70, "fri": .30, "mon": .10, "tue_thu": .10},
        "base":         {"weekend": .85, "fri": .45, "mon": .20, "tue_thu": .20},
        "optimistic":   {"weekend": .95, "fri": .60, "mon": .30, "tue_thu": .30}}
uplift = {"small": 60, "large": 80}   # ASSUME avg add-on/extra-kid uplift per party, within xlsx scenario band (+$30~150)
weeks = 52
sims = {}
for s, u in util.items():
    parties = {"small": 0.0, "large": 0.0}
    for d, (days, slots) in slot_days.items():
        for k, r in rooms.items():
            parties[k] += days * slots * r["n"] * u[d]
    wk_parties = parties["small"] + parties["large"]
    wk_rev = sum(parties[k] * (rooms[k]["price"] + uplift[k]) for k in rooms)
    sims[s] = {"parties_week": round(wk_parties, 1), "rev_week": round(wk_rev),
               "rev_year": round(wk_rev * weeks), "kids_week": round(sum(parties[k]*rooms[k]["kids"] for k in rooms))}
total_slots = sum(days*slots*sum(r["n"] for r in rooms.values()) for days, slots in slot_days.values())
out["slots_week"] = total_slots
out["scenarios"] = sims
deck_max_day = sum(r["price"]*r["n"]*4 for r in rooms.values())
assert deck_max_day == 5400                                 # reproduces deck's $5,400/day ceiling
out["deck_max_day"] = deck_max_day
out["deck_max_year_if_full"] = deck_max_day*7*weeks

# 3) Unit economics per small party (base price, base tier)
wage = 15.71       # CITED: Colorado state minimum 2027 (opening year per deck calendar 2027.11)
host_wage = 20.0   # ASSUME market host wage above minimum
burden = 1.20      # ASSUME payroll burden
host_hours = 2.5   # ASSUME: 60 room + 30 setup/cleanup + 60 play supervision partial
# Goodie Bag, US-sourced (CITED: 4imprint product pages read 2026-11-05; unit price at 1,000 pcs, USD)
goodie_items = {"bag 113971-SB (CPSIA)": 2.89, "crayon 4-pack 1556 (CPSIA)": 0.49,
                "sticker sheet 122247-GG (CPSIA)": 0.52, "button 1.5in 157188-RD-112": 0.49}
goodie_setup = 35 + 35          # set-up: bag $35/color + crayons $35; stickers and buttons have none
ship_mult = 1.10                # ASSUME domestic shipping/tax allowance
goodie_unit = sum(goodie_items.values()) + goodie_setup / 1000
goodie_landed = round(goodie_unit * ship_mult, 2)
premium_unit = 2.89 + 1.19 + 0.52 + 0.49 + (35 + 30) / 1000   # coloring book & crayon set 157900-SET replaces crayons
premium_landed = round(premium_unit * ship_mult, 2)
assert round(sum(goodie_items.values()), 2) == 4.39 and goodie_landed == 4.91 and premium_landed == 5.67
consum = 20.0      # ASSUME tableware/decor/cleaning per party
pay_fee = 0.03     # ASSUME card fees
def unit(price, kids, goodie_incl):
    labor = host_wage*burden*host_hours
    g = goodie_landed*kids if goodie_incl else 0
    cost = labor + consum + price*pay_fee + g
    return {"price": price, "labor": round(labor,1), "consumables": consum, "fees": round(price*pay_fee,1),
            "goodie": round(g,1), "cost": round(cost,1), "contrib": round(price-cost,1), "margin": round((price-cost)/price*100)}
out["goodie"] = {"items_sum": round(sum(goodie_items.values()), 2), "unit_with_setup": round(goodie_unit, 3), "landed": goodie_landed, "premium_landed": premium_landed}
out["unit_small_deck"] = unit(300, 10, False)
out["unit_small_deck_goodie"] = unit(300, 10, True)

# 4) Price-gap check: party per-kid vs ticket (DECK: Child $30 regular, effective $24-27)
gap = {"party_per_kid": 300/10, "ticket_regular": 30, "ticket_eff_low": 24, "ticket_eff_high": 27}
gap["premium_low"] = gap["party_per_kid"] - gap["ticket_eff_high"]
gap["premium_high"] = gap["party_per_kid"] - gap["ticket_eff_low"]
out["gap"] = gap
# MoPA (CITED, AUD): Casual 39/child, Fully hosted 59/child, min 10; ASSUME AUD->USD 0.65
aud = 0.65
out["mopa_usd"] = {"casual": round(39*aud,1), "hosted": round(59*aud,1), "casual_min": round(390*aud), "hosted_min": round(590*aud)}

# 5) Proposed per-child tiers (REASONING) and their unit economics
tiers = {"casual": {"per_kid": 36, "min": 10, "goodie": False},
         "hosted": {"per_kid": 48, "min": 10, "goodie": True}}
out["tiers"] = {k: {**v, "min_price": v["per_kid"]*v["min"], "econ": unit(v["per_kid"]*v["min"], v["min"], v["goodie"])} for k, v in tiers.items()}

# 6) Daily throughput vs dwell (REASONING): capacity 615 (DECK), 9 h open 10:00-19:00 (decision 2026-11-05), peak factor 0.5 (ASSUME)
out["throughput"] = {f"{d}h": round(615*9/d*0.5) for d in (1.5, 2.0, 2.5)}
assert out["throughput"] == {"1.5h": 1845, "2.0h": 1384, "2.5h": 1107}

# 7) Weekday field-trip model (REASONING; $15/student CITED Meow Wolf Denver; chaperone 1:8 free CITED)
ft = []
for groups, students, price in [(1, 30, 15), (2, 40, 15), (2, 40, 18)]:
    rev = groups*students*price
    staff = 2*3*host_wage*burden*groups**0  # 2 educators x 3h per morning
    ft.append({"groups": groups, "students": students, "price": price, "rev": rev, "staff": round(staff), "contrib": round(rev-staff)})
out["fieldtrip"] = ft
print(json.dumps(out, ensure_ascii=False, indent=1))

# 8) Confirmed operating model A (2026-11-05): ROOM FIRST, then play; open 10:00-19:00; 10-min staggered starts
#    Party = room 0-60 -> plaza window 60-65 -> play 65-120. Room is free after 60 min, cleanup 30 -> room cycle 90 min.
OPEN, CLOSE = 600, 1140                # 10:00, 19:00 (decision 2026-11-05)
def hm(m): return f"{m//60:02d}:{m%60:02d}"
OFFSETS = {"S1": 0, "S2": 10, "S3": 20, "L": 30}
def plan(order, offsets, room_cycle, party_len=120):
    """Fit as many parties per room as possible so every party ends by CLOSE."""
    rows = []
    for room, off in offsets.items():
        t = OPEN + off
        while t + party_len <= CLOSE:
            spot = (t + 60, t + 65) if order == "room_first" else (t + 50, t + 55)
            rows.append({"room": room, "start": t, "spot": spot, "end": t + party_len})
            t += room_cycle
    return rows
def conflicts(rows):
    sp = sorted(r["spot"] for r in rows)
    return sum(1 for a, b in zip(sp, sp[1:]) if b[0] < a[1])
deck_style = plan("play_first", OFFSETS, 150)                       # deck order: room blocked 2h + 30m
model_a    = plan("room_first", OFFSETS, 90)                        # room 60 + cleanup 30
model_sync = plan("room_first", {k: 0 for k in OFFSETS}, 90)        # same order, no stagger (control)
per_room = {r: sum(1 for x in model_a if x["room"] == r) for r in OFFSETS}
def day_rev(rows): return sum(rooms["large" if x["room"] == "L" else "small"]["price"] for x in rows)
def day_kids(rows): return sum(rooms["large" if x["room"] == "L" else "small"]["kids"] for x in rows)
out["model_a"] = {
    "per_room": per_room, "parties_day": len(model_a), "kids_day": day_kids(model_a), "rev_day": day_rev(model_a),
    "deck_order_10_19": {"parties_day": len(deck_style), "rev_day": day_rev(deck_style), "kids_day": day_kids(deck_style)},
    "conflicts_stagger": conflicts(model_a), "conflicts_sync": conflicts(model_sync),
    "last_end": hm(max(x["end"] for x in model_a)),
    "table": {r: [f'{hm(x["start"])} / ★{hm(x["spot"][0])} / {hm(x["end"])}' for x in model_a if x["room"] == r] for r in OFFSETS},
    "plaza_min_day": len(model_a) * 5, "plaza_share": round(len(model_a) * 5 / (CLOSE - OPEN) * 100, 1),
    "week_capacity": len(model_a) * 7, "rev_week_max": day_rev(model_a) * 7, "rev_year_max": day_rev(model_a) * 7 * weeks,
}
assert per_room == {"S1": 5, "S2": 5, "S3": 5, "L": 5}             # 5 rotations per room in 10:00-19:00
assert len(deck_style) == 12                                         # deck order fits only 3 per room
assert conflicts(model_a) == 0 and conflicts(model_sync) == 15       # control: no stagger -> 3 clashes x 5 waves
assert max(x["end"] for x in model_a) <= CLOSE
assert all(b["start"] - a["start"] >= 90 for r in OFFSETS
           for a, b in zip([x for x in model_a if x["room"] == r], [x for x in model_a if x["room"] == r][1:]))
assert day_rev(model_a) == 6750 and day_kids(model_a) == 225
# Cleanup sensitivity: how long may room cleanup take before the 10-min stagger loses a rotation?
def per_room_with_cleanup(c):
    rows = plan("room_first", OFFSETS, 60 + c)
    return {r: sum(1 for x in rows if x["room"] == r) for r in OFFSETS}
assert all(v == 5 for v in per_room_with_cleanup(37).values())     # 37-min cleanup still gives 20/day
assert per_room_with_cleanup(38)["L"] == 4                          # 38 min: large room L drops to 4
out["model_a"]["max_cleanup_min_for_20"] = 37
# Spotlight add-on economics (ASSUME $89, attach 30% of base-scenario parties)
spot_price, attach = 89, 0.30
spot_week = sims["base"]["parties_week"] * attach
spot_cost = 20/60*host_wage*burden + 10/60*host_wage*burden + spot_price*pay_fee
out["model_a"].update({"spot_per_week": round(spot_week, 1), "spot_rev_year": round(spot_week*spot_price*weeks),
                       "spot_cost": round(spot_cost, 1), "spot_contrib": round(spot_price-spot_cost, 1)})
out["model_a"]["base_util_vs_capacity"] = {k: round(v["parties_week"] / (len(model_a)*7) * 100) for k, v in sims.items()}
print(json.dumps(out["model_a"], ensure_ascii=False, indent=1))
