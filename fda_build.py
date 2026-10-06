# -*- coding: utf-8 -*-
"""US FDA bulk data (public domain, refreshed weekly) -> gov/fda_kb.json:
drug ingredient -> companies, device type -> manufacturers (+ country)."""
import collections, json, os, urllib.request, zipfile, io
os.makedirs("gov", exist_ok=True)
d = json.loads(urllib.request.urlopen(urllib.request.Request("https://api.fda.gov/download.json", headers={"User-Agent": "x"}), timeout=60).read())
def load(a, b):
    out = []
    for p in d["results"][a][b]["partitions"]:
        z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(p["file"], timeout=600).read()))
        out += json.loads(z.read(z.namelist()[0]))["results"]
    return out
ing = collections.defaultdict(set)
for p in load("drug", "ndc"):
    lab = (p.get("labeler_name") or "").strip()
    if not lab: continue
    for a in p.get("active_ingredients") or []:
        if a.get("name"): ing[a["name"].strip().lower()].add(lab)
    if p.get("generic_name"): ing[p["generic_name"].strip().lower()].add(lab)
cls = {c["product_code"]: c.get("device_name", "") for c in load("device", "classification")}
dev, country = collections.defaultdict(set), {}
for r in load("device", "registrationlisting"):
    reg = r.get("registration") or {}
    firm = (reg.get("name") or "").strip()
    if not firm: continue
    country[firm] = reg.get("iso_country_code", "")
    for pr in r.get("products") or []:
        dn = (pr.get("openfda") or {}).get("device_name") or cls.get(pr.get("product_code"), "")
        if dn: dev[dn.lower()].add(firm)
json.dump({"drug_ingredient_to_companies": {k: sorted(v) for k, v in ing.items()},
           "device_type_to_companies": {k: sorted(v) for k, v in dev.items()},
           "device_firm_country": country,
           "exported": {k: d["results"][k.split('/')[0]][k.split('/')[1]].get("export_date") for k in ("drug/ndc", "device/registrationlisting")}},
          open("gov/fda_kb.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"FDA: {len(ing)} drug ingredients, {len(dev)} device types, {len(country)} device firms")
