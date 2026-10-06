# -*- coding: utf-8 -*-
"""
Company index from public data (Wikidata + US FDA), with embeddings.

Sources
  * Wikidata (125,243, minus dissolved)     -- global, with products / industry / description
  * FDA drug ingredients + device types     -- kept as TYPE -> companies lookups (fda_kb.json)

Output
  kb_profiles.jsonl   one row per company: key, name, country, website, sources, text
  kb_vectors.npy      bge-small-en-v1.5 embedding of each profile text (normalised)
  kb_types.jsonl/.npy embeddings of FDA ingredient + device-type names
"""
import gzip, json, os, re, sys, time
import numpy as np
from fastembed import TextEmbedding

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import norm

h = lambda x: bytes.fromhex(x).decode("utf-8", "replace") if x and x != "NULL" else ""
dead = set(json.load(open(os.path.join(HERE, "kb_dissolved.json"))))

profiles, by_norm = [], {}


def add(rec):
    k = norm(rec["name"])
    if len(k) < 2:
        return
    if k in by_norm:                       # same company from another source: merge
        p = profiles[by_norm[k]]
        for f in ("country", "website", "desc"):
            if not p.get(f) and rec.get(f): p[f] = rec[f]
        for f in ("products", "industries"):
            p[f] = list(dict.fromkeys(p.get(f, []) + rec.get(f, [])))[:25]
        p["sources"] = sorted(set(p["sources"]) | set(rec["sources"]))
        if rec.get("qid"): p["qid"] = rec["qid"]
        return
    by_norm[k] = len(profiles); profiles.append(rec)


# 1. optional extra company list (if provided), merged first
for line in (gzip.open(os.path.join(HERE, "extra_companies.tsv.gz"), "rt", encoding="utf-8")
             if os.path.exists(os.path.join(HERE, "extra_companies.tsv.gz")) else []):
    a = line.rstrip("\n").split("\t")
    if len(a) < 9: continue
    add({"cid": int(a[0]), "name": h(a[1]), "desc": h(a[2]), "products": [x.strip() for x in (h(a[4]) or "").split(",") if x.strip()],
         "industries": [x.strip() for x in (h(a[3]) or "").split(",") if x.strip()], "country": h(a[5]), "website": h(a[6]),
         "web_status": a[7], "sources": ["ours"]})
n_ours = len(profiles)

# 2. Wikidata, minus dissolved companies
skipped = 0
for line in open(os.path.join(HERE, "kb_wikidata.jsonl"), encoding="utf-8"):
    r = json.loads(line)
    if r["qid"] in dead:
        skipped += 1; continue
    add({"qid": r["qid"], "name": r["name"], "desc": r.get("desc", ""), "products": r.get("products", []),
         "industries": r.get("industrys", []), "country": (r.get("countrys") or [""])[0], "website": r.get("website", ""),
         "aliases": r.get("aliass", [])[:10], "founded": r.get("founded", ""), "sources": ["wikidata"]})

# 2b. the wider Wikidata pull (businesses with a website or an informative description)
more = os.path.join(HERE, "kb_wikidata_more.jsonl")
if os.path.exists(more):
    for line in open(more, encoding="utf-8"):
        r = json.loads(line)
        if r["qid"] in dead:
            skipped += 1; continue
        add({"qid": r["qid"], "name": r["name"], "desc": r.get("desc", ""), "country": (r.get("countrys") or [""])[0],
             "website": r.get("website", ""), "sources": ["wikidata"]})

# 3. FDA firms: make sure every registry company is a resolvable profile too
fda = json.load(open(os.path.join(HERE, "gov", "fda_kb.json"), encoding="utf-8"))
REPACK = re.compile(r"packag|prepack|medication solutions|\brx\b|pharmacy|repack|distribut|wholesale", re.I)
for typ, firms in fda["device_type_to_companies"].items():
    for f in firms:
        add({"name": f.title() if f.isupper() else f, "country": fda["device_firm_country"].get(f, ""), "products": [typ], "sources": ["fda_device"]})
for ing, labs in fda["drug_ingredient_to_companies"].items():
    for f in labs:
        if REPACK.search(f): continue
        add({"name": f, "products": [ing], "sources": ["fda_drug"]})

for p in profiles:
    parts = [p["name"]]
    if p.get("desc"): parts.append(p["desc"])
    if p.get("products"): parts.append("Products: " + ", ".join(p["products"][:15]))
    if p.get("industries"): parts.append("Industry: " + ", ".join(p["industries"][:6]))
    p["text"] = ". ".join(parts)[:400]
    p["key"] = norm(p["name"])

print(f"profiles: {len(profiles)}  (ours {n_ours}, wikidata dissolved skipped {skipped})", flush=True)
with open(os.path.join(HERE, "kb_profiles.jsonl"), "w", encoding="utf-8") as f:
    for p in profiles: f.write(json.dumps(p, ensure_ascii=False) + "\n")

# Memory-light (2026-10-07): fill a preallocated float16 array in chunks instead of
# list(...) -> np.array (two full copies), and cap ONNX at 4 of 8 cores so the
# laptop stays usable. An 8 GB machine ran out of RAM and crashed Claude Code.
model = TextEmbedding("BAAI/bge-small-en-v1.5", threads=4)


def embed_all(texts, path):
    out = np.lib.format.open_memmap(path, mode="w+", dtype=np.float16, shape=(len(texts), 384))
    t0, CH = time.time(), 4096
    for i in range(0, len(texts), CH):
        chunk = np.array(list(model.embed(texts[i:i + CH], batch_size=64)), dtype=np.float32)
        chunk /= np.linalg.norm(chunk, axis=1, keepdims=True) + 1e-9
        out[i:i + len(chunk)] = chunk.astype(np.float16)
        if (i // CH) % 10 == 0:
            print(f"  embedded {i + len(chunk)}/{len(texts)}  ({time.time()-t0:.0f}s)", flush=True)
    out.flush(); del out


t = time.time()
embed_all([p["text"] for p in profiles], os.path.join(HERE, "kb_vectors.npy"))
print(f"embedded {len(profiles)} profiles in {time.time()-t:.0f}s", flush=True)

types = [{"kind": "device", "name": k, "n": len(v)} for k, v in fda["device_type_to_companies"].items()] + \
        [{"kind": "drug", "name": k, "n": len(v)} for k, v in fda["drug_ingredient_to_companies"].items()]
embed_all([t_["name"] for t_ in types], os.path.join(HERE, "kb_types.npy"))
with open(os.path.join(HERE, "kb_types.jsonl"), "w", encoding="utf-8") as f:
    for t_ in types: f.write(json.dumps(t_, ensure_ascii=False) + "\n")
print(f"embedded {len(types)} FDA types. DONE", flush=True)
