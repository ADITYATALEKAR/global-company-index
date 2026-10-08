# -*- coding: utf-8 -*-
"""
Published market figures straight from research firms' own public pages (no search engine -> no search blocking).
  python firm_pages.py sitemaps OUT.tsv            every report URL listed in each firm's public sitemap
  python firm_pages.py fetch URLS.txt OUT.jsonl     for each URL: page title + meta description + sentences that
                                                    state a market size / CAGR / regional share (polite: 1 request
                                                    every ~2 s per firm, resumable)
Output lines for "fetch" match the web-search format: {"url", "results": [[url, title, summary]]}
"""
import gzip, json, os, re, sys, time, html, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
FIRMS = ["precedenceresearch.com", "straitsresearch.com", "thebusinessresearchcompany.com", "grandviewresearch.com", "marketsandmarkets.com",
         "mordorintelligence.com", "gminsights.com", "imarcgroup.com", "futuremarketinsights.com", "coherentmarketinsights.com",
         "marketresearchfuture.com", "expertmarketresearch.com", "emergenresearch.com", "factmr.com", "persistencemarketresearch.com",
         "transparencymarketresearch.com", "skyquestt.com", "polarismarketresearch.com", "databridgemarketresearch.com",
         "towardshealthcare.com", "novaoneadvisor.com", "sphericalinsights.com", "researchandmarkets.com"]
SKIP = re.compile(r"/(ja|ko|zh|de|fr|es|it|pt|ru|ar|cn|jp|kr|vi|tr|nl|pl|id|th)/|blog|news|career|about|contact|author|tag/|category|"
                  r"press-?release|faq|privacy|terms|webinar|infographic|whitepaper", re.I)


def get(u, n=800_000, tries=3):
    for a in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30)
            b = r.read(n)
            if u.endswith(".gz") or b[:2] == b"\x1f\x8b": b = gzip.decompress(b)
            return b.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410): return ""
            time.sleep(5 * (a + 1))
        except Exception:
            time.sleep(5 * (a + 1))
    return ""


def sitemaps(out):
    with open(out, "w", encoding="utf-8") as fo:
        for firm in FIRMS:
            robots = get(f"https://www.{firm}/robots.txt", 50_000)
            todo = re.findall(r"(?im)^sitemap:\s*(\S+)", robots) or [f"https://www.{firm}/sitemap.xml"]
            seen, n = set(), 0
            while todo and len(seen) < 400:
                sm = todo.pop(0)
                if sm in seen or SKIP.search(sm): continue
                seen.add(sm)
                body = get(sm, 30_000_000)
                for loc in re.findall(r"<loc>\s*([^<\s]+)", body):
                    loc = html.unescape(loc)
                    if re.search(r"\.xml(\.gz)?$", loc, re.I): todo.append(loc); continue
                    if SKIP.search(loc) or not re.search(r"market|industry|report", loc, re.I): continue
                    fo.write(f"{firm}\t{loc}\n"); n += 1
                time.sleep(1)
            print(f"{firm}: {n} report pages from {len(seen)} sitemaps", flush=True)


SENT = re.compile(r"[^.]{0,220}?(?:(?:USD|US\$|\$)\s?\d[\d,.]*\s?(?:trillion|billion|million|bn|mn|B|M)\b|CAGR|compound annual|"
                  r"(?:North America|Europe|Asia[- ]Pacific)[^.]{0,60}\d{1,2}(?:\.\d+)?\s?%)[^.]{0,220}\.", re.I)


def fetch(urls_file, out):
    urls = [l.strip() for l in open(urls_file, encoding="utf-8") if l.strip()]
    done = set()
    if os.path.exists(out):
        for l in open(out, encoding="utf-8"):
            try: done.add(json.loads(l)["url"])
            except ValueError: pass
    fails = 0
    with open(out, "a", encoding="utf-8") as fo:
        for i, u in enumerate(urls):
            if u in done: continue
            page = get(u)
            if not page:
                fails += 1
                if fails >= 25 and fails > i // 2: print("too many failures - stopping, rerun later", flush=True); return
                continue
            title = html.unescape(re.search(r"(?is)<title[^>]*>(.*?)</title>", page).group(1).strip()) if re.search(r"(?is)<title", page) else ""
            meta = re.search(r'(?is)<meta[^>]+(?:name|property)=["\'](?:og:)?description["\'][^>]+content=["\']([^"\']+)', page)
            body = re.sub(r"(?s)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", page)
            text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body)))
            sents = [m.group(0).strip() for m in SENT.finditer(text[:60_000])][:12]
            summary = " ".join(([html.unescape(meta.group(1))] if meta else []) + sents)[:3000]
            fo.write(json.dumps({"url": u, "results": [[u, title, summary]]}, ensure_ascii=False) + "\n"); fo.flush()
            if i % 50 == 0: print(f"  {i}/{len(urls)}", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    {"sitemaps": lambda: sitemaps(sys.argv[2]), "fetch": lambda: fetch(sys.argv[2], sys.argv[3])}[sys.argv[1]]()
