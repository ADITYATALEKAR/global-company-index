# -*- coding: utf-8 -*-
"""
Match our companies (pdl_ours.tsv.gz: id, norm_key, name, domain, country, which fields are blank) to the People
Data Labs free company dataset (CC BY 4.0) and propose values for BLANK fields only.

Match rules (strict -- a wrong match would put another company's size on a page):
  1. same website domain                                  (best)
  2. else exact normalised name AND same country, and that name+country is unique in PDL
Fields: employee_band <- size, founded <- founded, website <- website, segments <- industry, hq_city <- locality

  python pdl_match.py PDL_FILE [PDL_FILE ...]   (.csv / .csv.gz / .json(l)(.gz); streamed, any size)
Output: pdl_fill.tsv.gz (id, field, value, match_type)
"""
import csv, gzip, io, json, os, re, sys, collections, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "gh_repo")); sys.path.insert(0, HERE)
from common import norm
csv.field_size_limit(10 ** 7)

dom = lambda w: (urllib.parse.urlparse(w if "//" in w else "http://" + w).netloc.lower().removeprefix("www.").split(":")[0] if w else "")
cnorm = lambda c: re.sub(r"[^a-z]", "", (c or "").lower())

ours, by_dom, by_name = {}, {}, collections.defaultdict(list)
for i, l in enumerate(gzip.open(os.path.join(HERE, "pdl_ours.tsv.gz"), "rt", encoding="utf-8")):
    if i == 0: continue
    a = l.rstrip("\n").split("\t")
    r = {"id": int(a[0]), "key": a[1], "name": a[2], "domain": a[3], "country": cnorm(a[4]),
         "need": dict(zip(["employee_band", "founded", "website", "segments", "hq_city"], [x == "1" for x in a[5:10]]))}
    ours[r["id"]] = r
    if r["domain"]: by_dom.setdefault(r["domain"], r["id"])
    by_name[r["key"]].append(r["id"])
print(f"our companies needing data: {len(ours)} | with a domain: {len(by_dom)}", flush=True)


def rows(path):
    if path == "-":                                   # streamed from `unzip -p` (2.4 GB zip on a GitHub runner)
        yield from csv.DictReader(io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace"))
        return
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt", encoding="utf-8", errors="replace") as f:
        first = f.readline(); f.seek(0)
        if first.lstrip().startswith("{"):
            for l in f:
                try: yield json.loads(l)
                except ValueError: pass
        else:
            yield from csv.DictReader(f)


g = lambda r, *ks: next((str(r[k]).strip() for k in ks if r.get(k) not in (None, "", "null")), "")
hits = {}                                    # our id -> (match type, pdl row)
name_seen = collections.Counter()           # (norm name, country) -> how many PDL rows (ambiguity guard)
name_cand = {}
n = 0
for path in sys.argv[1:]:
    for r in rows(path):
        n += 1
        if n % 1_000_000 == 0: print(f"  {n:,} PDL rows read, {len(hits)} matched by domain", flush=True)
        d = dom(g(r, "website", "domain"))
        if d and d in by_dom and by_dom[d] not in hits:
            hits[by_dom[d]] = ("domain", r); continue
        k = norm(g(r, "name"))
        if k in by_name:
            ck = (k, cnorm(g(r, "country")))
            name_seen[ck] += 1
            name_cand[ck] = r
for ck, cnt in name_seen.items():
    if cnt != 1: continue                    # several PDL companies share this name+country: skip
    for oid in by_name[ck[0]]:
        if oid not in hits and ours[oid]["country"] and ours[oid]["country"] == ck[1]:
            hits[oid] = ("name+country", name_cand[ck])
print(f"PDL rows {n:,} | matched {len(hits)} ({sum(1 for t, _ in hits.values() if t == 'domain')} by domain)", flush=True)

out = collections.Counter()
with gzip.open(os.path.join(HERE, "pdl_fill.tsv.gz"), "wt", encoding="utf-8") as fo:
    for oid, (mt, r) in hits.items():
        need = ours[oid]["need"]
        vals = {"employee_band": g(r, "size", "employee_count_range"), "founded": (re.findall(r"\b(1[6-9]\d\d|20[0-2]\d)\b", g(r, "founded")) or [""])[0],
                "website": ("https://" + dom(g(r, "website", "domain"))) if dom(g(r, "website", "domain")) else "",
                "segments": g(r, "industry"), "hq_city": g(r, "locality").title()[:80]}
        for f, v in vals.items():
            if need.get(f) and v:
                fo.write(f"{oid}\t{f}\t{v.replace(chr(9), ' ')[:400]}\t{mt}\n"); out[f] += 1
print("values to fill:", dict(out))
