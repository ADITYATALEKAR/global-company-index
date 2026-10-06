# -*- coding: utf-8 -*-
"""
Wider Wikidata pull: every business with a website or an informative English
description (not just "company in Japan"). Output: kb_wikidata_more.jsonl.

Memory-light (2026-10-07): an earlier version held all ~2M rows in RAM (1.2 GB
and growing) on an 8 GB laptop and helped crash Claude Code. Now each page is
written to disk as it arrives and only the set of seen ids stays in memory.
Resumable: re-running skips pages already on disk.
"""
import json, os, re, time, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "kb_wikidata_more.jsonl")
STATE = os.path.join(HERE, "kb_wikidata_more.state")
EP = "https://qlever.cs.uni-freiburg.de/api/wikidata"
UA = {"User-Agent": "global-company-index/1.0 (+https://github.com/ADITYATALEKAR/global-company-index)", "Accept": "application/sparql-results+json"}
PFX = ("PREFIX wdt: <http://www.wikidata.org/prop/direct/> PREFIX wd: <http://www.wikidata.org/entity/> "
       "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> PREFIX schema: <http://schema.org/> ")
GENERIC = re.compile(r"^(an? )?(\w+ )?(company|business|enterprise|firm|corporation|organization|organisation|"
                     r"limited company|public company|private company|joint-stock company|subsidiary|brand|holding company)"
                     r"( (in|of|from|based in|located in|headquartered in|registered in)\b.*)?$", re.I)
PAGE = 100000


def q(body):
    for a in range(5):
        try:
            r = urllib.request.Request(EP + "?" + urllib.parse.urlencode({"query": PFX + body}), headers=UA)
            return json.loads(urllib.request.urlopen(r, timeout=900).read())["results"]["bindings"]
        except Exception as e:
            print("  retry", a + 1, repr(e)[:120], flush=True); time.sleep(30 * (a + 1))
    raise RuntimeError("failed")


v = lambda b, k: b[k]["value"] if k in b else ""
off = int(open(STATE).read()) if os.path.exists(STATE) else 0
seen = set()
if off and os.path.exists(OUT):
    for line in open(OUT, encoding="utf-8"):
        seen.add(json.loads(line)["qid"])
kept = len(seen)
with open(OUT, "a" if off else "w", encoding="utf-8") as f:
    while True:
        page = q(f"""SELECT ?c ?name ?desc ?site ?ctry WHERE {{
          ?c wdt:P31/wdt:P279* wd:Q4830453 .
          ?c rdfs:label ?name . FILTER(LANG(?name)='en')
          OPTIONAL {{ ?c schema:description ?desc . FILTER(LANG(?desc)='en') }}
          OPTIONAL {{ ?c wdt:P856 ?site }}
          OPTIONAL {{ ?c wdt:P17 ?co . ?co rdfs:label ?ctry . FILTER(LANG(?ctry)='en') }}
          FILTER(BOUND(?site) || BOUND(?desc)) }} ORDER BY ?c LIMIT {PAGE} OFFSET {off}""")
        for b in page:
            cid = v(b, "c").rsplit("/", 1)[-1]
            if cid in seen: continue
            d = v(b, "desc").strip()
            informative = bool(d) and not GENERIC.match(d) and len(d) > 12
            if not informative and not v(b, "site"):
                continue
            seen.add(cid)
            f.write(json.dumps({"qid": cid, "name": v(b, "name"), "desc": d if informative else "",
                                "website": v(b, "site"), "countrys": [v(b, "ctry")] if v(b, "ctry") else []},
                               ensure_ascii=False) + "\n")
            kept += 1
        f.flush()
        off += PAGE
        open(STATE, "w").write(str(off))
        print(f"  offset {off}: page {len(page)} rows, companies kept {kept}", flush=True)
        n = len(page); del page
        if n < PAGE: break
print(f"DONE kept {kept} companies", flush=True)
