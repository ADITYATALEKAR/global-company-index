# -*- coding: utf-8 -*-
"""Wikidata businesses that are dissolved / defunct -> kb_dissolved.json (excluded from matching)."""
import json, urllib.request, urllib.parse
EP = "https://qlever.cs.uni-freiburg.de/api/wikidata"
q = ("PREFIX wdt: <http://www.wikidata.org/prop/direct/> PREFIX wd: <http://www.wikidata.org/entity/> "
     "SELECT DISTINCT ?c WHERE { ?c wdt:P31/wdt:P279* wd:Q4830453 . { ?c wdt:P576 [] } UNION { ?c wdt:P31 wd:Q15911738 } }")
r = urllib.request.Request(EP + "?" + urllib.parse.urlencode({"query": q}), headers={"User-Agent": "global-company-index/1.0 (+https://github.com/ADITYATALEKAR/global-company-index)", "Accept": "application/sparql-results+json"})
dead = sorted({b["c"]["value"].rsplit("/", 1)[-1] for b in json.loads(urllib.request.urlopen(r, timeout=900).read())["results"]["bindings"]})
json.dump(dead, open("kb_dissolved.json", "w")); print("dissolved:", len(dead))
