# -*- coding: utf-8 -*-
"""
No-AI web search for reports left with fewer than 5 verified companies.

Per report: 2 DuckDuckGo queries ("<market> market key players", "<market> manufacturers").
A company is ADDED only if its name resolves to a real company in our index (1.4M Wikidata/FDA +
our 54k) -- nothing can be invented -- AND at least one of:
  listed    named in a result that is about players/companies/manufacturers of this market
  own_site  a result is the company's own site (domain = company name) and that page is about
            this market's product words
  repeated  named in 2+ different results
Market-research publishers, directories, marketplaces, encyclopedias and media are never companies
here. Max 20 added, never padded.

  python websearch.py IDS_JSON OUT.jsonl [CANDS...]   (IDS = report ids; subjects read from reports2.tsv.gz)
"""
import gzip, html, json, os, random, re, sys, time, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "gh_repo")); sys.path.insert(0, HERE)
from common import norm

SOURCES = os.environ.get("SOURCES", "ddg,news").split(",")
DELAY = float(os.environ.get("DELAY", "0"))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
NOT_COMPANIES = re.compile(
    r"(marketresearch|marketsandmarkets|grandview|fortunebusiness|futuremarket|gminsights|researchandmarkets|precedence|"
    r"mordor|alliedmarket|imarc|technavio|businessresearch|verifiedmarket|persistence|insightpartners|transparency|"
    r"databridge|polaris|spherical|straits|marketreport|cognitive|coherent|factmr|globenewswire|prnewswire|einpresswire|"
    r"openpr|linkedin|wikipedia|youtube|amazon|alibaba|indiamart|made-in-china|ebay|reddit|quora|medium|forbes|reuters|"
    r"bloomberg|statista|ibisworld|zionmarket|exactitude|thebrainy|maximize|skyquest|emergen|astute|vantage|reportlinker|"
    r"sciencedirect|researchgate|ncbi|mdpi|springer|dictionary|merriam|cambridge|facebook|instagram|twitter|x\.com)", re.I)
LIST_CTX = re.compile(r"\b(key|major|leading|prominent|top|dominant|notable)\s+(players?|companies|manufacturers|vendors|suppliers|participants)"
                      r"|\bplayers?\s*(include|such as|are|:)|companies\s+(such as|like|include)|\bmanufacturers?\b|\bdominate", re.I)
STOP = set("the and of for in on with by from to a an market global inc ltd llc co corp equipment system systems products".split())


def ddg(q):
    data = urllib.parse.urlencode({"q": q}).encode()
    for attempt in range(4):
        try:
            t = urllib.request.urlopen(urllib.request.Request("https://html.duckduckgo.com/html/", data=data, headers=UA), timeout=25).read().decode("utf-8", "replace")
            if "result__a" in t or "No results" in t:
                out = []
                for u, ti, sn in re.findall(r'class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>', t, re.S):
                    u = urllib.parse.unquote(re.sub(r".*uddg=([^&]+).*", r"\1", u))
                    out.append((u, html.unescape(re.sub(r"<[^>]+>", "", ti)), html.unescape(re.sub(r"<[^>]+>", "", sn))))
                return out
        except Exception:
            pass
        time.sleep(20 * (attempt + 1))                   # rate-limited: back off
    return None


NEWS_ACT = re.compile(r"\b(launch|launches|launched|introduc|unveil|announc|expand|acquir|supplier|supplies|manufactur|"
                      r"opens|plant|facility|partner|debuts|releases|new line|range of)", re.I)


def gnews(q):
    """Google News RSS: lenient (our server already polls it daily). Returns (publisher_url, headline, '')."""
    u = "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q=" + urllib.parse.quote(q)
    for attempt in range(3):
        try:
            t = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25).read().decode("utf-8", "replace")
            out = []
            for item in re.findall(r"<item>(.*?)</item>", t, re.S)[:30]:
                ti = html.unescape((re.search(r"<title>(.*?)</title>", item, re.S) or [None, ""])[1])
                src = re.search(r'<source url="([^"]+)">(.*?)</source>', item)
                if src: ti = re.sub(r"\s+-\s+" + re.escape(html.unescape(src.group(2))) + r"\s*$", "", ti)
                out.append(("news:" + (src.group(1) if src else ""), ti, ""))
            return out
        except Exception:
            time.sleep(10 * (attempt + 1))
    return []


def spans(text):
    """every 1-5 word capitalised span (and every comma/semicolon-separated list item) -> normalised key"""
    keys = {}
    for m in re.finditer(r"\b([A-Z0-9][\w&.\-']*(?:\s+(?:&\s+|and\s+|de\s+|of\s+)?[A-Z0-9][\w&.\-']*){0,5})", text):
        w = m.group(1).split()
        for a in range(len(w)):
            for b in range(len(w), a, -1):
                k = norm(" ".join(w[a:b]))
                if len(k) >= 4: keys.setdefault(k, " ".join(w[a:b]))
    for item in re.split(r"[,;:]|\band\b", text):
        k = norm(item.strip())
        if 4 <= len(k) <= 40: keys.setdefault(k, item.strip())
    return keys


def domain_key(u):
    h = urllib.parse.urlparse(u).netloc.lower().removeprefix("www.")
    return norm(h.split(".")[0].replace("-", " ")), h


def main():
    ids = json.load(open(os.path.join(HERE, sys.argv[1])))
    out_path = os.path.join(HERE, sys.argv[2])
    sub = {}
    for line in gzip.open(os.path.join(HERE, "reports2.tsv.gz"), "rt", encoding="utf-8"):
        a = line.rstrip("\n").split("\t")
        if int(a[0]) in ids: sub[int(a[0])] = re.sub(r"\s+market\b.*$", "", bytes.fromhex(a[1]).decode("utf-8", "replace"), flags=re.I).strip()
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)["id"] for l in open(out_path, encoding="utf-8")}
    # 1) search (resumable): raw results kept so the matching rules can be re-tuned without searching again
    raw_path = out_path.replace(".jsonl", "_raw.jsonl")
    have = {}
    if os.path.exists(raw_path):
        for l in open(raw_path, encoding="utf-8"): x = json.loads(l); have[x["id"]] = x["results"]
    with open(raw_path, "a", encoding="utf-8") as fr:
        for rid in ([] if os.environ.get("NO_SEARCH") else ids):          # NO_SEARCH: match GitHub results only
            if rid in have or rid in done or rid not in sub: continue
            res = []
            if "ddg" in SOURCES:
                for q in (f"{sub[rid]} market key players", f"{sub[rid]} manufacturers"):
                    r = ddg(q)
                    if r is None: print("search blocked - stopping, rerun later", flush=True); return
                    res += r
                    time.sleep(random.uniform(2.5, 4.5) + DELAY)
            if "news" in SOURCES:
                res += gnews(f'"{sub[rid]}"') + gnews(f"{sub[rid]} manufacturer")
                time.sleep(random.uniform(1, 2))
            have[rid] = res
            fr.write(json.dumps({"id": rid, "results": res}, ensure_ascii=False) + "\n"); fr.flush()
            print(f"  searched {len(have)}/{len(ids)}", flush=True) if len(have) % 25 == 0 else None
    if os.environ.get("SEARCH_ONLY"): return                     # GitHub: search only, matching runs locally
    # 2) every name-like span -> look up in the company index in ONE streaming pass (8 GB laptop)
    want = {}
    for rid, res in have.items():
        for u, ti, sn in res:
            for k in spans(ti + " . " + sn): want.setdefault(k, set()).add(rid)
            dk, _ = domain_key(u)
            if len(dk) >= 4: want.setdefault(dk, set()).add(rid)
    kb = {}
    for line in gzip.open(os.path.join(HERE, "kb_names.tsv.gz"), "rt", encoding="utf-8"):
        k = line[:line.index("\t")]
        if k in want and k not in kb:
            a = line.rstrip("\n").split("\t")
            if len(a) >= 9: kb[k] = {"idx": int(a[1]), "name": a[2], "country": a[3], "sources": a[4].split(","), "cid": a[5] or None,
                                     "qid": a[6] or None, "tier": int(a[7]), "desc": a[8]}
    # 3) evidence rules
    with open(out_path, "a", encoding="utf-8") as fo:
        for rid, res in have.items():
            if rid in done: continue
            subj = {w.rstrip("s") for w in re.findall(r"[a-z0-9]{3,}", sub[rid].lower()) if w not in STOP}
            ev = {}
            for u, ti, sn in res:
                news = u.startswith("news:")
                dk, host = domain_key(u[5:] if news else u)
                publisher = news or bool(NOT_COMPANIES.search(host))
                text = ti + " . " + sn
                listed = bool(LIST_CTX.search(text)) or (news and bool(NEWS_ACT.search(text)))
                on_topic = bool(subj & {w.rstrip("s") for w in re.findall(r"[a-z0-9]{3,}", text.lower())})
                for k in spans(text):
                    if k in kb and not NOT_COMPANIES.search(k) and not (news and k == dk):
                        e = ev.setdefault(k, {"hits": set(), "tags": set()})
                        e["hits"].add(host)
                        if listed and on_topic: e["tags"].add("listed")
                if not publisher and dk in kb and on_topic:
                    e = ev.setdefault(dk, {"hits": set(), "tags": set()}); e["hits"].add(host); e["tags"].add("own_site")
            found = []
            for k, e in ev.items():
                if len(e["hits"]) >= 2: e["tags"].add("repeated")
                if not e["tags"]: continue
                name_words = {w.rstrip("s") for w in re.findall(r"[a-z0-9]{3,}", kb[k]["name"].lower())}
                if name_words and name_words <= subj | STOP: continue        # the market's own words, not a company
                found.append({**kb[k], "evidence": sorted(e["tags"]), "n_sources": len(e["hits"])})
            found.sort(key=lambda c: (-len(c["evidence"]), -c["n_sources"], c["tier"]))
            fo.write(json.dumps({"id": rid, "subject": sub[rid], "found": found[:20]}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
