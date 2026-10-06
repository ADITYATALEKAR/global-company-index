# -*- coding: utf-8 -*-
"""
Global company knowledge base from Wikidata (free, no key) via the QLever
SPARQL endpoint. One row per company that has an industry (P452) or a product
it makes (P1056): name, aliases, description, countries, industries, products,
website, founded, stock ticker. Written to kb_wikidata.jsonl.

These rows form the candidate pool: a company is never
added unless it exists in a source index.
"""
import json, os, time, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "kb_wikidata.jsonl")
EP = "https://qlever.cs.uni-freiburg.de/api/wikidata"
UA = {"User-Agent": "global-company-index/1.0 (+https://github.com/ADITYATALEKAR/global-company-index)",
      "Accept": "application/sparql-results+json"}
PFX = ("PREFIX wdt: <http://www.wikidata.org/prop/direct/> PREFIX wd: <http://www.wikidata.org/entity/> "
       "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> PREFIX schema: <http://schema.org/> "
       "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> ")


def q(sparql, timeout=900):
    for attempt in range(4):
        try:
            # GET: the endpoint answers POST with a 308 redirect that urllib won't follow
            req = urllib.request.Request(EP + "?" + urllib.parse.urlencode({"query": PFX + sparql}), headers=UA)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read())["results"]["bindings"]
        except Exception as e:
            print("  retry", attempt + 1, str(e)[:120], flush=True); time.sleep(20 * (attempt + 1))
    raise RuntimeError("QLever failed")


def v(b, k):
    return b[k]["value"] if k in b else ""


# companies = instances of (a subclass of) business, with an industry or a product
BASE = "?c wdt:P31/wdt:P279* wd:Q4830453 . { ?c wdt:P452 [] } UNION { ?c wdt:P1056 [] }"

FIELDS = {
    "name":  "?c rdfs:label ?x . FILTER(LANG(?x)='en')",
    "desc":  "?c schema:description ?x . FILTER(LANG(?x)='en')",
    "alias": "?c skos:altLabel ?x . FILTER(LANG(?x)='en')",
    "country": "?c wdt:P17 ?o . ?o rdfs:label ?x . FILTER(LANG(?x)='en')",
    "industry": "?c wdt:P452 ?o . ?o rdfs:label ?x . FILTER(LANG(?x)='en')",
    "product": "?c wdt:P1056 ?o . ?o rdfs:label ?x . FILTER(LANG(?x)='en')",
    "website": "?c wdt:P856 ?x .",
    "founded": "?c wdt:P571 ?x .",
    "ticker": "?c wdt:P249 ?x .",
}

kb = {}
for field, pattern in FIELDS.items():
    t = time.time()
    rows = q(f"SELECT DISTINCT ?c ?x WHERE {{ {BASE} {pattern} }}")
    for b in rows:
        cid = v(b, "c").rsplit("/", 1)[-1]
        rec = kb.setdefault(cid, {"qid": cid})
        val = v(b, "x")
        if field in ("name", "desc", "website", "founded"):
            rec.setdefault(field, val[:10] if field == "founded" else val)
        else:
            rec.setdefault(field + "s", [])
            if val not in rec[field + "s"] and len(rec[field + "s"]) < 25:
                rec[field + "s"].append(val)
    print(f"{field:9} {len(rows):>8} rows  companies so far {len(kb):>7}  ({time.time()-t:.0f}s)", flush=True)

n = 0
with open(OUT, "w", encoding="utf-8") as f:
    for rec in kb.values():
        if rec.get("name"):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n"); n += 1
print(f"DONE: {n} companies with an English name -> {OUT}")
