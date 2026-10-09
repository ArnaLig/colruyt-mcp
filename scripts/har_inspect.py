"""Inspect a HAR file and print anonymised request/response shapes.

Usage: uv run python scripts/har_inspect.py <file.har> <url-substring> [--max N]

Values are replaced by type/length placeholders, except for an allow-list of
non-personal technical keys. Never prints cookies, tokens or API keys.
"""
import base64
import json
import re
import sys
import urllib.parse as up

SAFE_KEYS = re.compile(
    r"^(lang|langId|storeId|catalogId|placeId|branchId|placeType|size|page|pageSize|skip|sort|"
    r"orderBy|searchTerm|query|unit\w*|currency|status|type|\w*Type|\w*Code|quantity|count|total\w*|"
    r"recipeId\w*|technical\w*|commercial\w*|productId|partNumber|catentryId|\w*Id|name|title|"
    r"description|shortName|brand|price\w*|basicPrice|weight\w*|content|isAvailable|available|"
    r"seoName|language|persons|servings|preparationTime|cookingTime|difficulty|amount|\w*Date\w*|"
    r"\w*Time\w*|\w*Url|\w*URL|image\w*|ingredients?|label|value|from|to|start|end)$",
    re.I,
)
PERSONAL = re.compile(r"(token|key|secret|mail|phone|firstName|lastName|nickName|address|street|zip|"
                      r"logon|ecoid|userId|personId|customer|member|card|iban|birth|hashed)", re.I)


def shape(v, key="", depth=0, max_list=2):
    if isinstance(v, dict):
        return {k: shape(x, k, depth + 1) for k, x in v.items()}
    if isinstance(v, list):
        out = [shape(x, key, depth + 1) for x in v[:max_list]]
        if len(v) > max_list:
            out.append(f"…(+{len(v) - max_list})")
        return out
    if PERSONAL.search(key):
        return f"<{type(v).__name__}:redacted>"
    if isinstance(v, str) and not SAFE_KEYS.match(key):
        return f"<str:{len(v)}>"
    if isinstance(v, str) and len(v) > 80:
        return v[:77] + "…"
    return v


def body(content):
    t = content.get("text") or ""
    if content.get("encoding") == "base64":
        t = base64.b64decode(t).decode("utf-8", "ignore")
    return t


def main():
    path, needle = sys.argv[1], sys.argv[2]
    mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 1
    entries = json.load(open(path, encoding="utf-8"))["log"]["entries"]
    n = 0
    for i, e in enumerate(entries):
        r = e["request"]
        if needle not in r["url"] or r["method"] == "OPTIONS":
            continue
        n += 1
        if n > mx:
            continue
        s = up.urlsplit(r["url"])
        q = {k: (v if SAFE_KEYS.match(k) and not PERSONAL.search(k) else f"<{len(v)}>")
             for k, v in up.parse_qsl(s.query, keep_blank_values=True)}
        print(f"\n### [{i}] {r['method']} {s.netloc}{s.path} -> {e['response']['status']}")
        print("query:", json.dumps(q, ensure_ascii=False))
        pd = (r.get("postData") or {}).get("text")
        if pd:
            try:
                print("request body:", json.dumps(shape(json.loads(pd)), ensure_ascii=False, indent=1))
            except ValueError:
                print("request body (non-JSON):", f"<{len(pd)} chars>")
        rb = body(e["response"]["content"])
        try:
            print("response:", json.dumps(shape(json.loads(rb)), ensure_ascii=False, indent=1)[:4000])
        except ValueError:
            print("response (non-JSON):", f"<{len(rb)} chars>")
    print(f"\n({n} matching non-OPTIONS entries)")


if __name__ == "__main__":
    main()
