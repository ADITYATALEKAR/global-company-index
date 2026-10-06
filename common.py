# -*- coding: utf-8 -*-
"""Name cleaning + normalisation, identical to the company name normalisation."""
import re

SPLIT = re.compile(r'\s*,?\s*\d+\.\s+')
SUFFIX_ONLY = re.compile(
    r'^(inc|inc\.|llc|l\.l\.c\.?|ltd|ltd\.?\)?|limited|plc|p\.l\.c\.?|corp|corp\.|'
    r'corporation|co|co\.|company|gmbh|ag|a\.g\.?|sa|s\.a\.?|s\.a\.s\.?|nv|n\.v\.?|'
    r'bv|b\.v\.?|ab|as|a/s|oy|oyj|spa|s\.p\.a\.?|kk|k\.k\.?|pte|pty|srl|s\.r\.l\.?|'
    r'holdings?|group|sro|sro\.?|and|&|the|others?|etc|etc\.|n/a|na|tbd|none)$', re.I)
JUNK = re.compile(r'^[\W\d_]+$')
SUFFIXES = re.compile(
    r'\b(incorporated|inc|llc|ltd|limited|plc|corp|corporation|company|co|gmbh|ag|'
    r'sa|sas|nv|bv|ab|as|oy|oyj|spa|kk|pte|pty|srl|holdings|holding|group|'
    r'international|technologies|technology|solutions|systems|industries|'
    r'laboratories|labs|pharmaceuticals|pharma|healthcare|the)\b', re.I)


def clean(nm):
    nm = re.sub(r'\s+', ' ', nm.strip(" \t\r\n.,;:·—–-"))
    if len(nm) < 2 or len(nm) > 120 or SUFFIX_ONLY.match(nm) or JUNK.match(nm):
        return None
    if re.match(r'^(industry\s+leader|company\s*\d+)\b', nm, re.I):
        return None
    return nm


def norm(nm):
    s = re.sub(r'\(.*?\)', ' ', nm.lower())
    s = SUFFIXES.sub(' ', s)
    return re.sub(r'[^a-z0-9]+', '', s)


