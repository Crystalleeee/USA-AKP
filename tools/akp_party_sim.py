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
gbp_usd = 1.30     # ASSUME FX
goodie_gbp = 1.16 + 0.38 + 0.15 + 0.59   # CITED (Merch plugin, qty 1000, incl. print): bag+crayons+stickers+badge
goodie_usd = round(goodie_gbp * gbp_usd, 2)
freight_mult = 1.35  # ASSUME freight/duty/testing allowance (UK->US, CPSIA)
goodie_landed = round(goodie_usd * freight_mult, 2)
consum = 20.0      # ASSUME tableware/decor/cleaning per party
pay_fee = 0.03     # ASSUME card fees
def unit(price, kids, goodie_incl):
    labor = host_wage*burden*host_hours
    g = goodie_landed*kids if goodie_incl else 0
    cost = labor + consum + price*pay_fee + g
    return {"price": price, "labor": round(labor,1), "consumables": consum, "fees": round(price*pay_fee,1),
            "goodie": round(g,1), "cost": round(cost,1), "contrib": round(price-cost,1), "margin": round((price-cost)/price*100)}
out["goodie"] = {"gbp": round(goodie_gbp,2), "usd": goodie_usd, "landed_usd": goodie_landed}
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

# 6) Daily throughput vs dwell (REASONING): capacity 615 (DECK), 10 h, peak factor 0.5 (ASSUME)
out["throughput"] = {f"{d}h": round(615*10/d*0.5) for d in (1.5, 2.0, 2.5)}

# 7) Weekday field-trip model (REASONING; $15/student CITED Meow Wolf Denver; chaperone 1:8 free CITED)
ft = []
for groups, students, price in [(1, 30, 15), (2, 40, 15), (2, 40, 18)]:
    rev = groups*students*price
    staff = 2*3*host_wage*burden*groups**0  # 2 educators x 3h per morning
    ft.append({"groups": groups, "students": students, "price": price, "rev": rev, "staff": round(staff), "contrib": round(rev-staff)})
out["fieldtrip"] = ft
print(json.dumps(out, ensure_ascii=False, indent=1))

# 8) Plaza birthday spotlight — 4 rooms (S1,S2,S3,L), conflict check (REASONING)
#    Party = play 0-50, plaza window 50-55, move 55-60, room 60-120, turnover 120-150 (DECK cycle 2h + 30m)
WAVES = [600, 750, 900, 1050]          # DECK: 10:00, 12:30, 15:00, 17:30 (minutes from 00:00)
CLOSE = 1200                           # DECK: 20:00
def hm(m): return f"{m//60:02d}:{m%60:02d}"
def schedule(offsets):
    rows = []
    for room, off in offsets.items():
        for w in WAVES:
            s = w + off
            rows.append({"room": room, "start": s, "spot": (s + 50, s + 55), "end": s + 120, "clean_end": s + 150})
    return rows
def conflicts(rows):
    spots = sorted(r["spot"] for r in rows)
    return sum(1 for a, b in zip(spots, spots[1:]) if b[0] < a[1])
sync = schedule({"S1": 0, "S2": 0, "S3": 0, "L": 0})
stag = schedule({"S1": 0, "S2": 10, "S3": 20, "L": 30})
out["spotlight"] = {
    "sync_conflicts": conflicts(sync),
    "stagger_conflicts": conflicts(stag),
    "stagger_last_end": hm(max(r["end"] for r in stag)),
    "stagger_last_start": hm(max(r["start"] for r in stag)),
    "stagger_table": {room: [f'{hm(r["start"])} / ★{hm(r["spot"][0])}' for r in stag if r["room"] == room] for room in ("S1", "S2", "S3", "L")},
    "plaza_min_per_day_max": len(stag) * 5,
}
assert conflicts(sync) == 12          # failure control: synchronized starts collide (3 per wave x 4 waves)
assert conflicts(stag) == 0           # staggered starts never overlap
assert max(r["end"] for r in stag) <= CLOSE
assert all(b["start"] >= a["clean_end"] for room in ("S1","S2","S3","L")
           for a, b in zip([r for r in stag if r["room"]==room], [r for r in stag if r["room"]==room][1:]))
# Revenue of solo spotlight add-on (ASSUME price $89 within $79-99 band, attach 30% of base-scenario parties)
spot_price, attach = 89, 0.30
spot_week = sims["base"]["parties_week"] * attach
spot_cost = 20/60*host_wage*burden + 10/60*host_wage*burden + spot_price*pay_fee   # content QA 20m + plaza MC 10m + fees
out["spotlight"].update({"price": spot_price, "attach": attach, "per_week": round(spot_week, 1),
    "rev_year": round(spot_week*spot_price*weeks), "cost_each": round(spot_cost, 1), "contrib_each": round(spot_price-spot_cost, 1)})
print(json.dumps(out["spotlight"], ensure_ascii=False, indent=1))
