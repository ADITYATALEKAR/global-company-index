# -*- coding: utf-8 -*-
"""
Match company names to the GLEIF golden copy (official global LEI register, CC0): headquarters country + city per
EXACT legal name (case / punctuation / legal-suffix insensitive). Only ACTIVE entities; a name that maps to entities in
different countries is reported as ambiguous (left out). Streams the zip, any size.
  python gleif_match.py NAMES.txt GLEIF.csv.zip OUT.tsv
"""
import csv, io, re, sys, zipfile, collections
csv.field_size_limit(10 ** 7)
LEGAL = re.compile(r"\b(inc|incorporated|ltd|limited|llc|corp|corporation|co|company|sa|se|ag|gmbh|plc|oy|uab|spa|bv|nv|pvt|private|"
                   r"sas|srl|kk|pte|pty|lp|llp|sarl|ab|asa|as|kgaa|holdings?|group)\b", re.I)
key = lambda s: re.sub(r"[^a-z0-9]", "", LEGAL.sub(" ", re.sub(r"\(.*?\)", " ", (s or "").lower().replace("&", " and "))))
names = {}
for l in open(sys.argv[1], encoding="utf-8"):
    k = key(l.strip())
    if len(k) >= 3: names.setdefault(k, l.strip())
print("our names", len(names), flush=True)
hit = collections.defaultdict(set); n = 0
z = zipfile.ZipFile(sys.argv[2])
with z.open(z.namelist()[0]) as f:
    r = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
    for row in r:
        n += 1
        if n % 500000 == 0: print(f"  {n:,} entities", flush=True)
        if row.get("Entity.EntityStatus") != "ACTIVE": continue
        k = key(row.get("Entity.LegalName"))
        if k in names:
            hit[k].add((row.get("Entity.HeadquartersAddress.Country") or row.get("Entity.LegalAddress.Country") or "",
                        (row.get("Entity.HeadquartersAddress.City") or row.get("Entity.LegalAddress.City") or "").title()))
with open(sys.argv[3], "w", encoding="utf-8") as fo:
    ok = amb = 0
    for k, s in hit.items():
        countries = {c for c, _ in s if c}
        if len(countries) != 1: amb += 1; continue
        cities = {ci for c, ci in s if ci}
        fo.write(f"{names[k]}\t{countries.pop()}\t{cities.pop() if len(cities) == 1 else ''}\n"); ok += 1
print(f"GLEIF entities {n:,} | our names matched {ok} (one country) | ambiguous {amb}", flush=True)
