# -*- coding: utf-8 -*-
"""
퀸잇 경쟁사 트래킹 — 통합 크롤러 + 대시보드 생성기
------------------------------------------------------
실행: python3 crawler.py
결과: reports/YYYY-MM-DD.html  (전체 대시보드)
      reports/latest.html      (항상 최신본 덮어씀)
      data/YYYY-MM-DD.json     (원본 데이터 백업)
"""

import json, time, datetime, re, traceback
from pathlib import Path
import requests
from bs4 import BeautifulSoup

BASE   = Path(__file__).parent
DATA   = BASE / "data";    DATA.mkdir(exist_ok=True)
REPORT = BASE / "reports"; REPORT.mkdir(exist_ok=True)
TODAY  = datetime.date.today().isoformat()
NOW    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

HDR = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

APPS = {
    "포스티":  {"ios": "1570315038", "android": "com.kakaostyle.posty"},
    "에이블리": {"ios": "1361166884", "android": "com.ablyclothes.app"},
    "지그재그": {"ios": "976185078",  "android": "com.kakaostyle.zigzag"},
}

# ──────────────────────────────────────────────────────────────
# 1. 앱스토어
# ──────────────────────────────────────────────────────────────
def ios_reviews(app_id, name):
    url = f"https://itunes.apple.com/kr/rss/customerreviews/id={app_id}/sortBy=mostRecent/json"
    try:
        r = requests.get(url, headers=HDR, timeout=10); r.raise_for_status()
        feed    = r.json().get("feed", {})
        entries = feed.get("entry", [])
        reviews = []
        for e in entries[1:6]:
            reviews.append({
                "title":   e.get("title",   {}).get("label", ""),
                "content": e.get("content", {}).get("label", ""),
                "rating":  e.get("im:rating", {}).get("label", ""),
                "author":  e.get("author",  {}).get("name", {}).get("label", ""),
                "date":    e.get("updated", {}).get("label", "")[:10],
            })
        avg = (feed.get("entry", [{}])[0].get("im:ratingAverage", {}).get("label"))
        return {"app": name, "platform": "iOS", "reviews": reviews, "rating": avg}
    except Exception as e:
        return {"app": name, "platform": "iOS", "reviews": [], "error": str(e)}

def android_info(pkg, name):
    url = f"https://play.google.com/store/apps/details?id={pkg}&hl=ko"
    try:
        r = requests.get(url, headers=HDR, timeout=12); r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        updated = None
        for tag in soup.find_all(string=re.compile(r"20\d{2}년 \d+월 \d+일")):
            updated = tag.strip(); break
        changes = ""
        for s in soup.find_all("script"):
            if s.string and "recentChangesHtml" in s.string:
                m = re.search(r'"recentChangesHtml","(.*?)"', s.string)
                if m:
                    changes = re.sub(r"\\u003c.*?\\u003e", "",
                                     m.group(1).replace("\\n", " "))[:300]
                break
        return {"app": name, "platform": "Android", "updated": updated, "recent_changes": changes}
    except Exception as e:
        return {"app": name, "platform": "Android", "error": str(e)}

def crawl_appstore():
    print("[1/4] 앱스토어 수집...")
    out = []
    for name, ids in APPS.items():
        print(f"  · {name} iOS");     out.append(ios_reviews(ids["ios"], name));          time.sleep(1.2)
        print(f"  · {name} Android"); out.append(android_info(ids["android"], name)); time.sleep(1.2)
    return out

# ──────────────────────────────────────────────────────────────
# 2. 기획전
# ──────────────────────────────────────────────────────────────
def scrape_events(url, source, base=""):
    try:
        r    = requests.get(url, headers=HDR, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("a[href*='event'], a[href*='exhibition'], a[href*='promo']")
        seen, out = set(), []
        for c in cards[:20]:
            href = c.get("href", "")
            if href in seen or not href: continue
            seen.add(href)
            t = c.get_text(strip=True)
            if len(t) < 3: continue
            out.append({"title": t[:80],
                        "url": (base + href if href.startswith("/") else href),
                        "source": source})
        if not out:
            og = soup.find("meta", property="og:title")
            out.append({"title": og["content"] if og else source + " 기획전",
                        "url": url, "source": source,
                        "note": "앱 전용 — 상세 목록은 앱에서 확인"})
        return out
    except Exception as e:
        return [{"error": str(e), "source": source, "url": url}]

def crawl_events():
    print("[2/4] 기획전 수집...")
    r = {
        "posty":    scrape_events("https://posty.kr/events", "포스티", "https://posty.kr"),
        "ably":     scrape_events("https://m.a-bly.com/exhibitions", "에이블리", "https://m.a-bly.com"),
        "cm29":     scrape_events("https://www.29cm.co.kr/exhibition", "29CM", "https://www.29cm.co.kr"),
        "wconcept": scrape_events("https://www.wconcept.co.kr/Display/eventList", "W컨셉", "https://www.wconcept.co.kr"),
    }
    for k, v in r.items(): print(f"  · {k}: {len(v)}건")
    return r

# ──────────────────────────────────────────────────────────────
# 3. 뉴스 (네이버)
# ──────────────────────────────────────────────────────────────
NEWS_RSS = {
    "포스티":  "https://news.google.com/rss/search?q=포스티+패션&hl=ko&gl=KR&ceid=KR:ko",
    "에이블리": "https://news.google.com/rss/search?q=에이블리+패션&hl=ko&gl=KR&ceid=KR:ko",
    "지그재그": "https://news.google.com/rss/search?q=지그재그+카카오스타일&hl=ko&gl=KR&ceid=KR:ko",
    "29CM":   "https://news.google.com/rss/search?q=29CM+무신사&hl=ko&gl=KR&ceid=KR:ko",
    "W컨셉":  "https://news.google.com/rss/search?q=W컨셉+패션&hl=ko&gl=KR&ceid=KR:ko",
    "무신사":  "https://news.google.com/rss/search?q=무신사+패션플랫폼&hl=ko&gl=KR&ceid=KR:ko",
}

def fetch_news_rss(brand, url):
    items = []
    try:
        r    = requests.get(url, headers=HDR, timeout=10); r.raise_for_status()
        soup = BeautifulSoup(r.text, "xml")
        for item in soup.find_all("item")[:3]:
            title = item.find("title")
            link  = item.find("link")
            desc  = item.find("description")
            pubdt = item.find("pubDate")
            if not title: continue
            raw_title   = title.get_text(strip=True)
            clean_title = re.sub(r"\s*-\s*[^-]+$", "", raw_title)
            date_str = ""
            if pubdt:
                try:
                    dt = datetime.datetime.strptime(pubdt.get_text(strip=True), "%a, %d %b %Y %H:%M:%S %Z")
                    date_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    date_str = pubdt.get_text(strip=True)[:16]
            raw_desc   = desc.get_text(strip=True) if desc else ""
            clean_desc = re.sub(r"<[^>]+>", "", raw_desc)[:120]
            items.append({"title": clean_title, "url": link.get_text(strip=True) if link else "",
                          "desc": clean_desc, "date": date_str, "brand": brand})
    except Exception as e:
        print(f"    RSS 오류({brand}): {e}")
    return items

def crawl_news():
    print("[3/4] 뉴스 수집 (Google News RSS)...")
    out = {}
    for brand, url in NEWS_RSS.items():
        print(f"  · {brand}")
        out[brand] = fetch_news_rss(brand, url)
        import time; time.sleep(0.8)
    return out

# ──────────────────────────────────────────────────────────────
# 4. JSON 저장
# ──────────────────────────────────────────────────────────────
def save_json(data):
    for p in [DATA / f"{TODAY}.json", DATA / "latest.json"]:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("✅ JSON 저장 완료")

# ──────────────────────────────────────────────────────────────
# 5. 대시보드 HTML 빌더
# ──────────────────────────────────────────────────────────────

NEWS_META = {
    "포스티":  ("#6246ea", "#ede9fe"),
    "에이블리": ("#d63b3b", "#fef2f2"),
    "지그재그": ("#b06000", "#fffbeb"),
    "29CM":   ("#1d56d1", "#eff6ff"),
    "W컨셉":  ("#555555", "#f5f5f5"),
    "무신사":  ("#222222", "#f0f0f0"),
}

def _news_rows(items):
    if not items:
        return "<div style='font-size:12px;color:#aaa;padding:10px 0'>수집된 뉴스가 없습니다</div>"
    html = ""
    for it in items:
        html += f"""
        <div style='padding:11px 0;border-bottom:1px solid #f0f0f0'>
          <a href='{it.get("url","#")}' target='_blank'
             style='font-size:13px;font-weight:500;color:#18191f;line-height:1.4;
                    display:block;margin-bottom:3px;text-decoration:none'>
            {it.get("title","")}
          </a>
          <div style='font-size:12px;color:#52546a;line-height:1.5'>{it.get("desc","")}</div>
          <div style='font-size:10px;color:#aaa;margin-top:3px;font-family:monospace'>{it.get("date","")}</div>
        </div>"""
    return html

def news_card(brand, items):
    c, bg = NEWS_META.get(brand, ("#555", "#f5f5f5"))
    return f"""
    <div style='background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:18px 20px;
                box-shadow:0 1px 3px rgba(0,0,0,0.04)'>
      <div style='display:flex;align-items:center;gap:8px;margin-bottom:13px;
                  padding-bottom:11px;border-bottom:1px solid #f0f0f0'>
        <div style='width:8px;height:8px;border-radius:50%;background:{c};flex-shrink:0'></div>
        <span style='font-size:14px;font-weight:700'>{brand}</span>
        <span style='font-size:10px;background:{bg};color:{c};padding:2px 7px;
                     border-radius:999px;font-weight:600;margin-left:auto'>최신 뉴스</span>
      </div>
      {_news_rows(items)}
    </div>"""

def _rev_rows(reviews):
    if not reviews:
        return "<div style='font-size:12px;color:#aaa;padding:8px 0'>리뷰 데이터를 가져오지 못했습니다</div>"
    html = ""
    for rv in reviews[:3]:
        stars = "★" * int(rv.get("rating") or 0)
        html += f"""
        <div style='padding:8px 0;border-bottom:1px solid #f5f5f5'>
          <div style='font-size:11px;color:#f59e0b'>{stars}</div>
          <div style='font-size:13px;font-weight:500;margin:2px 0'>{rv.get("title","")}</div>
          <div style='font-size:12px;color:#666;line-height:1.5'>{rv.get("content","")[:110]}…</div>
          <div style='font-size:10px;color:#aaa;margin-top:2px;font-family:monospace'>
            {rv.get("author","")} · {rv.get("date","")}
          </div>
        </div>"""
    return html

def app_card(name, ios_d, and_d, color):
    rating   = ios_d.get("rating") or "—"
    updated  = and_d.get("updated") or "—"
    changes  = and_d.get("recent_changes", "")
    ch_html  = (f"<div style='font-size:12px;color:#555;background:#f9f9f9;border-radius:6px;"
                f"padding:9px;margin-bottom:9px;line-height:1.5'>{changes[:200]}</div>"
                if changes else "")
    return f"""
    <div style='background:#fff;border:1px solid #e5e7eb;border-radius:14px;
                border-left:4px solid {color};padding:18px 20px;
                box-shadow:0 1px 3px rgba(0,0,0,0.04)'>
      <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:11px'>
        <span style='font-size:15px;font-weight:700'>{name}</span>
        <span style='background:{color}18;color:{color};font-size:11px;
                     padding:3px 10px;border-radius:999px;font-weight:600'>iOS ★ {rating}</span>
      </div>
      {ch_html}
      <div style='font-size:11px;color:#aaa;margin-bottom:9px'>Android 최근 업데이트: {updated}</div>
      <div style='font-size:12px;font-weight:600;color:#444;margin-bottom:3px'>최신 리뷰</div>
      {_rev_rows(ios_d.get("reviews", []))}
    </div>"""

def event_section(events, color):
    if not events:
        return "<p style='font-size:12px;color:#aaa'>수집된 기획전이 없습니다</p>"
    html = ""
    for e in events[:6]:
        if "error" in e:
            html += f"<div style='font-size:12px;color:#ef4444;padding:6px 0'>수집 오류: {e['error'][:60]}</div>"
            continue
        note = (f"<div style='font-size:11px;color:#aaa;margin-top:2px'>{e.get('note','')}</div>"
                if e.get("note") else "")
        html += f"""
        <a href='{e.get("url","#")}' target='_blank'
           style='display:block;padding:10px 13px;border:1px solid #e5e7eb;border-radius:8px;
                  margin-bottom:7px;text-decoration:none;background:#fff'
           onmouseover="this.style.borderColor='{color}'"
           onmouseout="this.style.borderColor='#e5e7eb'">
          <div style='font-size:13px;font-weight:500;color:#111'>{e.get("title","")}</div>
          {note}
        </a>"""
    return html


CSS = """
:root{
  --bg:#f4f5f7;--bg2:#fff;--bg3:#f0f1f4;
  --border:rgba(0,0,0,0.08);--bHv:rgba(0,0,0,0.16);
  --text:#18191f;--text2:#52546a;--text3:#9496aa;
  --purple:#6246ea;--purpleD:rgba(98,70,234,0.08);--purpleB:rgba(98,70,234,0.22);
  --teal:#0b8f63;--tealD:rgba(11,143,99,0.08);
  --coral:#d63b3b;--coralD:rgba(214,59,59,0.08);
  --amber:#b06000;--amberD:rgba(176,96,0,0.08);
  --blue:#1d56d1;--blueD:rgba(29,86,209,0.08);
  --green:#157a3c;--greenD:rgba(21,122,60,0.08);
  --r:10px;--rl:14px;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Noto Sans KR',sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.6}
a{text-decoration:none;color:inherit}
.shell{display:flex;min-height:100vh}
/* sidebar */
.sb{width:228px;flex-shrink:0;background:var(--bg2);border-right:1px solid var(--border);
    padding:22px 0;position:fixed;top:0;left:0;bottom:0;display:flex;
    flex-direction:column;z-index:20;box-shadow:1px 0 0 var(--border)}
.logo{padding:0 18px 20px;border-bottom:1px solid var(--border);margin-bottom:14px}
.logo-badge{display:inline-block;background:var(--purpleD);border:1px solid var(--purpleB);
            color:var(--purple);font-size:10px;font-weight:700;padding:2px 8px;
            border-radius:999px;letter-spacing:.07em;margin-bottom:7px}
.logo h1{font-size:15px;font-weight:700;line-height:1.3}
.logo p{font-size:11px;color:var(--text3);margin-top:2px}
.ng{padding:0 8px;margin-bottom:2px}
.nl{font-size:10px;color:var(--text3);letter-spacing:.09em;font-weight:700;padding:0 8px;margin-bottom:2px}
.ni{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;
    cursor:pointer;color:var(--text2);font-size:13px;transition:all .12s;border:1px solid transparent}
.ni:hover{background:var(--bg3);color:var(--text)}
.ni.on{background:var(--purpleD);border-color:var(--purpleB);color:var(--purple);font-weight:500}
.nd{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.sf{margin-top:auto;padding:12px 18px 0;border-top:1px solid var(--border)}
.lp{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text3)}
.ld{width:7px;height:7px;border-radius:50%;background:var(--teal);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
/* main */
.main{margin-left:228px;flex:1;padding:30px 34px;max-width:1160px}
.page{display:none}
.page.on{display:block;animation:fu .2s ease}
@keyframes fu{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}
.ph{margin-bottom:24px}
.ph h2{font-size:20px;font-weight:700}
.ph p{font-size:13px;color:var(--text2);margin-top:3px}
/* grid */
.g2{display:grid;grid-template-columns:1fr 1fr;gap:13px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:13px}
.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:11px}
.gA{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
.ng2{display:grid;grid-template-columns:1fr 1fr;gap:13px}
/* card */
.card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--rl);
      padding:17px 19px;box-shadow:0 1px 3px rgba(0,0,0,0.04);transition:border-color .12s}
.card:hover{border-color:var(--bHv)}
.sl{font-size:11px;color:var(--text3);font-weight:700;letter-spacing:.07em;margin-bottom:14px;margin-top:22px}
/* kpi */
.kv{font-size:26px;font-weight:700;font-family:'DM Mono',monospace;line-height:1.1}
.kl{font-size:11px;color:var(--text3);font-weight:500;margin-bottom:4px}
.ks{font-size:11px;color:var(--text3);margin-top:3px}
.ku{font-size:11px;color:var(--teal);margin-top:3px}
.kd{font-size:11px;color:var(--coral);margin-top:3px}
/* comp */
.cc{background:var(--bg2);border:1px solid var(--border);border-radius:var(--rl);
    padding:15px 17px;box-shadow:0 1px 3px rgba(0,0,0,0.04);transition:border-color .12s,transform .12s}
.cc:hover{border-color:var(--bHv);transform:translateY(-1px)}
.cc.D{border-left:3px solid var(--purple)}
.cc.I{border-left:3px solid var(--teal)}
.cn{font-size:14px;font-weight:700;margin-bottom:5px}
.ct{display:inline-block;font-size:10px;padding:2px 8px;border-radius:999px;margin-bottom:7px;font-weight:600}
.td{background:var(--purpleD);color:var(--purple);border:1px solid var(--purpleB)}
.ti{background:var(--tealD);color:var(--teal);border:1px solid rgba(11,143,99,.22)}
.cd{font-size:12px;color:var(--text2);line-height:1.6}
.cs{margin-top:9px;font-size:11px;color:var(--text3)}
.cs strong{color:var(--text2);font-family:'DM Mono',monospace}
/* badge */
.badge{display:inline-block;font-size:10px;padding:2px 7px;border-radius:999px;font-weight:600}
.bl{background:var(--coralD);color:var(--coral);border:1px solid rgba(214,59,59,.22)}
.bs{background:var(--blueD);color:var(--blue);border:1px solid rgba(29,86,209,.22)}
.bd{background:var(--bg3);color:var(--text3);border:1px solid var(--border)}
.bh{background:#fff3cd;color:#8a5700;border:1px solid #f5c842}
.bDi{background:var(--purpleD);color:var(--purple);border:1px solid var(--purpleB)}
.bW{background:var(--coralD);color:var(--coral);border:1px solid rgba(214,59,59,.22)}
/* price */
.pr{display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px}
.pr span:first-child{color:var(--text2)}
.pr span:last-child{color:var(--text);font-family:'DM Mono',monospace;font-size:11px}
.bb{height:5px;border-radius:3px;background:var(--bg3);margin-bottom:11px}
.bf{height:100%;border-radius:3px;transition:width .6s cubic-bezier(.4,0,.2,1)}
/* promo */
.pi{display:flex;gap:11px;padding:12px 0;border-bottom:1px solid var(--border)}
.pi:last-child{border-bottom:none;padding-bottom:0}
.pa{width:3px;border-radius:2px;flex-shrink:0;min-height:42px;align-self:stretch}
.pb{flex:1}
.ph2{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:3px}
.pn{font-size:13px;font-weight:700}
.pt{font-size:12px;color:var(--text2);line-height:1.55}
.pd{font-size:11px;color:var(--text3);margin-top:3px;font-family:'DM Mono',monospace}
/* alert */
.ai{display:flex;align-items:flex-start;gap:11px;padding:10px 0;border-bottom:1px solid var(--border)}
.ai:last-child{border-bottom:none}
.ac{font-size:13px;font-weight:700;margin-bottom:2px}
.at{font-size:12px;color:var(--text2);line-height:1.5}
.ad{font-size:10px;color:var(--text3);margin-top:3px;font-family:'DM Mono',monospace}
/* table */
.dt{width:100%;border-collapse:collapse;font-size:12px}
.dt th{text-align:left;padding:7px 11px;color:var(--text3);font-size:10px;font-weight:700;
       letter-spacing:.06em;border-bottom:1px solid var(--border)}
.dt td{padding:10px 11px;border-bottom:1px solid var(--border);color:var(--text2);vertical-align:top}
.dt tr:last-child td{border-bottom:none}
.dt tr:hover td{background:var(--bg3)}
.dn{color:var(--text);font-weight:600}
/* pill */
.pill{display:inline-block;font-size:10px;padding:2px 8px;border-radius:999px;font-weight:600;white-space:nowrap}
.p-ok{background:var(--greenD);color:var(--green);border:1px solid rgba(21,122,60,.2)}
.p-warn{background:var(--amberD);color:var(--amber);border:1px solid rgba(176,96,0,.2)}
.p-block{background:var(--coralD);color:var(--coral);border:1px solid rgba(214,59,59,.2)}
/* misc */
.ibox{background:var(--bg3);border:1px solid var(--border);border-radius:var(--r);
      padding:12px 14px;font-size:12px;color:var(--text2);line-height:1.7;margin-top:13px}
.ibox strong{color:var(--text);font-weight:600}
.ins{background:var(--purpleD);border:1px solid var(--purpleB);border-radius:var(--r);
     padding:12px 14px;font-size:12px;color:var(--text2);line-height:1.7;margin-top:13px}
.ins strong{color:var(--purple);font-weight:700}
.legend{display:flex;gap:14px;margin-bottom:12px;flex-wrap:wrap}
.li{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--text2)}
.ld2{width:8px;height:8px;border-radius:2px;flex-shrink:0}
.ubanner{display:flex;align-items:center;gap:10px;background:var(--purpleD);border:1px solid var(--purpleB);
         border-radius:var(--r);padding:10px 16px;margin-bottom:22px;font-size:12px;color:var(--purple)}
.ubanner strong{font-weight:700}
@media(max-width:960px){
  .sb{width:54px}.logo,.nl,.ni span,.sf{display:none}
  .main{margin-left:54px;padding:18px}
  .g3,.g4{grid-template-columns:repeat(2,1fr)}
  .ng2{grid-template-columns:1fr}
}
@media(max-width:620px){
  .g2,.g3,.g4,.gA,.ng2{grid-template-columns:1fr}
  .main{padding:12px}
}
::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#d0d2df;border-radius:3px}
"""


def generate_dashboard(data):
    ios_map, and_map = {}, {}
    for item in data.get("appstore", []):
        n = item["app"]
        if item.get("platform") == "iOS": ios_map[n] = item
        else: and_map[n] = item

    events = data.get("events", {})
    news   = data.get("news",   {})

    # 수집된 포스티 이벤트 제목 (배너용)
    posty_ev = ""
    for e in events.get("posty", []):
        if "error" not in e and e.get("title"):
            posty_ev = e["title"]; break

    # 앱 카드 (3개)
    app_cards = (
        app_card("포스티",  ios_map.get("포스티",{}),  and_map.get("포스티",{}),  "#6246ea") +
        app_card("에이블리", ios_map.get("에이블리",{}), and_map.get("에이블리",{}), "#d63b3b") +
        app_card("지그재그", ios_map.get("지그재그",{}), and_map.get("지그재그",{}), "#b06000")
    )

    # 뉴스 카드
    news_cards = "".join(
        news_card(b, news.get(b, []))
        for b in ["포스티","에이블리","지그재그","29CM","W컨셉","무신사"]
    )

    # 기획전
    ev_p = event_section(events.get("posty", []),    "#6246ea")
    ev_a = event_section(events.get("ably", []),     "#d63b3b")
    ev_c = event_section(events.get("cm29", []),     "#1d56d1")
    ev_w = event_section(events.get("wconcept", []), "#555555")

    return f"""<!DOCTYPE html>
<html lang='ko'>
<head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>퀸잇 경쟁사 대시보드 — {TODAY}</title>
<link rel='preconnect' href='https://fonts.googleapis.com'>
<link href='https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&family=DM+Mono:wght@400;500&display=swap' rel='stylesheet'>
<style>{CSS}</style>
</head>
<body>
<div class='shell'>

<aside class='sb'>
  <div class='logo'>
    <div class='logo-badge'>QUEENIT MD</div>
    <h1>경쟁사<br>트래킹</h1>
    <p>4050 여성 패션 플랫폼</p>
  </div>
  <div class='ng'>
    <div class='nl'>분석</div>
    <div class='ni on' onclick="go('overview',this)"><div class='nd' style='background:var(--purple)'></div><span>경쟁사 현황</span></div>
    <div class='ni' onclick="go('price',this)"><div class='nd' style='background:var(--amber)'></div><span>가격대 비교</span></div>
    <div class='ni' onclick="go('promo',this)"><div class='nd' style='background:var(--coral)'></div><span>기획전·프로모션</span></div>
    <div class='ni' onclick="go('flash',this)"><div class='nd' style='background:#e67e00'></div><span>타임특가</span></div>
  </div>
  <div class='ng'>
    <div class='nl'>실시간 수집</div>
    <div class='ni' onclick="go('appstore',this)"><div class='nd' style='background:var(--teal)'></div><span>앱스토어 현황</span></div>
    <div class='ni' onclick="go('events',this)"><div class='nd' style='background:#0b8f63'></div><span>기획전 수집본</span></div>
    <div class='ni' onclick="go('alerts',this)"><div class='nd' style='background:#d63b3b'></div><span>가격 변동 알림</span></div>
    <div class='ni' onclick="go('news',this)"><div class='nd' style='background:var(--blue)'></div><span>기사·내부 소식</span></div>
    <div class='ni' onclick="go('crawl',this)"><div class='nd' style='background:var(--text3)'></div><span>크롤링 설정</span></div>
  </div>
  <div class='sf'>
    <div class='lp'><div class='ld'></div><span>자동수집 {NOW}</span></div>
  </div>
</aside>

<main class='main'>

<div class='ubanner'>
  <div class='ld' style='flex-shrink:0'></div>
  <span>오늘 <strong>{TODAY}</strong> 자동 수집 완료 &nbsp;|&nbsp; 포스티 최신: <strong>{posty_ev or "수집 중"}</strong></span>
</div>

<!-- 경쟁사 현황 -->
<div id='page-overview' class='page on'>
  <div class='ph'><h2>경쟁사 현황</h2><p>4050 여성 패션 시장 직·간접 경쟁사 전체 현황</p></div>
  <div class='g4'>
    <div class='card'><div class='kl'>퀸잇</div><div class='kv' style='font-size:16px;line-height:1.3'>4050 멋진 어른들의<br>라이프 스타일링샵</div><div class='ku' style='margin-top:8px'>▲ 4050 단독 사용률 1위</div></div>
    <div class='card'><div class='kl'>직접 경쟁사</div><div class='kv'>6</div><div class='ks'>포스티·GS샵·롯데·현대·CJ·SK스토아</div></div>
    <div class='card'><div class='kl'>간접 경쟁사</div><div class='kv'>6</div><div class='ks'>에이블리·지그재그·29CM·W컨셉·무신사·패션플러스</div></div>
    <div class='card'><div class='kl'>최대 가격 위협</div><div class='kv' style='font-size:17px;color:var(--coral)'>에이블리</div><div class='ks'>40대 유입 확대 중</div><div class='kd'>▼ 가격 하방 압박 최강</div></div>
  </div>
  <div class='sl'>직접 경쟁사</div>
  <div class='legend'><div class='li'><div class='ld2' style='background:var(--purple)'></div>직접경쟁</div><div class='li'><div class='ld2' style='background:var(--teal)'></div>간접경쟁</div></div>
  <div class='g3'>
    <div class='cc D'><div class='cn'>포스티</div><span class='ct td'>직접</span><div class='cd'>카카오스타일 운영. AI 개인화·라이브방송 강점. PB '잇파인' 운영. 전 상품 무료배송·무료반품 고정. 누적 회원 220만명 돌파.</div><div class='cs'>거래액 <strong>+20%</strong> (2025)</div></div>
    <div class='cc D'><div class='cn'>GS샵</div><span class='ct td'>직접</span><div class='cd'>GS리테일 계열. TV·모바일 통합 채널. 4050 여성 패션 핵심 구매처. 시즌 기획전·단독 브랜드 운영.</div><div class='cs'>방송특가 최대 60%</div></div><div class='cc D'><div class='cn'>롯데홈쇼핑</div><span class='ct td'>직접</span><div class='cd'>롯데그룹 계열. TV·T커머스·모바일 멀티채널. 4050 여성 패션·뷰티·리빙 기획전 강점. PB·단독 브랜드 다수.</div><div class='cs'>멀티채널 4050 타깃</div></div><div class='cc D'><div class='cn'>현대홈쇼핑</div><span class='ct td'>직접</span><div class='cd'>현대백화점그룹 계열. 프리미엄 여성 패션 포지셔닝. 백화점 브랜드 연계 단독 기획전 강점. 4050 고소득 여성 타깃.</div><div class='cs'>프리미엄 4050 포지셔닝</div></div><div class='cc D'><div class='cn'>CJ온스타일</div><span class='ct td'>직접</span><div class='cd'>CJ그룹 계열. TV·모바일 라이브커머스 강점. 4050 여성 패션·뷰티 기획전 활발. 셀렙샵에디션 PB 운영.</div><div class='cs'>라이브커머스 강점</div></div>
    <div class='cc D'><div class='cn'>SK스토아</div><span class='ct td'>직접</span><div class='cd'>라포랩스 인수 진행 중(약 1100억). T커머스 기반. 통합 시 매출 3,734억 규모 대형 플랫폼 예정.</div><div class='cs'>매출 <strong>3,023억</strong> (2024)</div></div>
  </div>
  <div class='sl' style='margin-top:24px'>간접 경쟁사</div>
  <div class='gA'>
    <div class='cc I'><div class='cn'>에이블리</div><span class='ct ti'>간접</span><div class='cd'>여성 패션 MAU 1위. 40대 유입 확대 중. 초저가·할인코드 전략. 2025 거래액 2.8조, 영업이익 130억.</div><div class='cs'>MAU <strong>938만</strong> · 거래액 <strong>2.8조</strong></div></div>
    <div class='cc I'><div class='cn'>지그재그</div><span class='ct ti'>간접</span><div class='cd'>카카오스타일 운영. 거래액 2조 돌파. 직잭뷰티 +50% 고성장. 30대 공략 확대.</div><div class='cs'>MAU <strong>409만</strong> · 거래액 <strong>2조+</strong></div></div>
    <div class='cc I'><div class='cn'>29CM</div><span class='ct ti'>간접</span><div class='cd'>무신사 계열. GMV 1조 돌파. 2539 여성 디자이너 브랜드 강세. 객단가 타 플랫폼 3~5배.</div><div class='cs'>MAU <strong>199만</strong> · GMV <strong>1조+</strong></div></div>
    <div class='cc I'><div class='cn'>W컨셉</div><span class='ct ti'>간접</span><div class='cd'>신세계 계열. 신임 대표 체질 개선 중. 2025 영업손실 31억 적자 전환.</div><div class='cs' style='color:var(--coral)'>⚠ 2025 적자 · 대표 교체</div></div>
    <div class='cc I'><div class='cn'>무신사</div><span class='ct ti'>간접</span><div class='cd'>MAU 703만. 오프라인 확장(숍인숍 30%가 4050). 2025 매출 1.47조, 영업이익 +37%.</div><div class='cs'>MAU <strong>703만</strong> · 영업이익 <strong>+37%</strong></div></div>
  </div>
</div>

<!-- 가격대 비교 -->
<div id='page-price' class='page'>
  <div class='ph'><h2>가격대 비교</h2><p>주요 경쟁사 카테고리별 가격 포지셔닝 · 퀸잇 기준선 대비</p></div>
  <div class='g2'>
    <div class='card' style='border-color:var(--purpleB)'>
      <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:14px'><span style='font-size:13px;font-weight:700;color:var(--purple)'>퀸잇 (자사)</span><span class='badge bDi'>기준</span></div>
      <div class='pr'><span>아우터</span><span>99,000~299,000원</span></div><div class='bb'><div class='bf' style='width:72%;background:var(--purple)'></div></div>
      <div class='pr'><span>상의</span><span>39,000~99,000원</span></div><div class='bb'><div class='bf' style='width:46%;background:var(--purple)'></div></div>
      <div class='pr'><span>할인율</span><span>15~35%</span></div><div class='bb'><div class='bf' style='width:25%;background:var(--purple)'></div></div>
    </div>
    <div class='card'>
      <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:14px'><span style='font-size:13px;font-weight:700'>포스티</span><span class='badge bDi'>직접</span></div>
      <div class='pr'><span>아우터</span><span>89,000~189,000원</span></div><div class='bb'><div class='bf' style='width:58%;background:var(--teal)'></div></div>
      <div class='pr'><span>상의</span><span>29,000~79,000원</span></div><div class='bb'><div class='bf' style='width:36%;background:var(--teal)'></div></div>
      <div class='pr'><span>할인율</span><span>20~40%</span></div><div class='bb'><div class='bf' style='width:30%;background:var(--teal)'></div></div>
      <div style='font-size:11px;color:var(--coral);margin-top:5px'>⚠ PB 쿠폰 시 블라우스 2만원대</div>
    </div>
    <div class='card'>
      <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:14px'><span style='font-size:13px;font-weight:700'>에이블리</span><span class='badge bW'>가격위협</span></div>
      <div class='pr'><span>아우터</span><span>39,000~89,000원</span></div><div class='bb'><div class='bf' style='width:26%;background:var(--coral)'></div></div>
      <div class='pr'><span>상의</span><span>15,000~39,000원</span></div><div class='bb'><div class='bf' style='width:16%;background:var(--coral)'></div></div>
      <div class='pr'><span>할인율</span><span>40~70%</span></div><div class='bb'><div class='bf' style='width:55%;background:var(--coral)'></div></div>
      <div style='font-size:11px;color:var(--coral);margin-top:5px'>⚠ 할인코드 "benefits" 상시</div>
    </div>
    <div class='card'>
      <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:14px'><span style='font-size:13px;font-weight:700'>지그재그</span><span class='badge bd'>간접</span></div>
      <div class='pr'><span>아우터</span><span>29,000~89,000원</span></div><div class='bb'><div class='bf' style='width:28%;background:var(--amber)'></div></div>
      <div class='pr'><span>상의</span><span>15,000~49,000원</span></div><div class='bb'><div class='bf' style='width:22%;background:var(--amber)'></div></div>
      <div class='pr'><span>할인율</span><span>30~60%</span></div><div class='bb'><div class='bf' style='width:45%;background:var(--amber)'></div></div>
    </div>
    <div class='card'>
      <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:14px'><span style='font-size:13px;font-weight:700'>29CM</span><span class='badge bd'>간접</span></div>
      <div class='pr'><span>아우터</span><span>199,000~590,000원</span></div><div class='bb'><div class='bf' style='width:88%;background:var(--blue)'></div></div>
      <div class='pr'><span>상의</span><span>79,000~199,000원</span></div><div class='bb'><div class='bf' style='width:65%;background:var(--blue)'></div></div>
      <div class='pr'><span>할인율</span><span>10~25%</span></div><div class='bb'><div class='bf' style='width:16%;background:var(--blue)'></div></div>
      <div style='font-size:11px;color:var(--text3);margin-top:5px'>객단가 타 플랫폼 3~5배</div>
    </div>
    <div class='card'>
      <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:14px'><span style='font-size:13px;font-weight:700'>W컨셉</span><span class='badge bd'>간접</span></div>
      <div class='pr'><span>아우터</span><span>150,000~490,000원</span></div><div class='bb'><div class='bf' style='width:80%;background:#888'></div></div>
      <div class='pr'><span>상의</span><span>59,000~169,000원</span></div><div class='bb'><div class='bf' style='width:58%;background:#888'></div></div>
      <div class='pr'><span>할인율</span><span>10~30%</span></div><div class='bb'><div class='bf' style='width:20%;background:#888'></div></div>
      <div style='font-size:11px;color:var(--coral);margin-top:5px'>2025 적자 전환 · 전략 불확실</div>
    </div>
  </div>
  <div class='ins'><strong>MD 인사이트</strong> — 포스티가 PB 쿠폰으로 퀸잇 중저가 영역 진입 압박 중. 에이블리 초저가가 가격 하방 경계선을 끌어내리고 있음. 퀸잇 프리미엄 티어 확장 시 29CM·W컨셉과의 경쟁 본격화 전망.</div>
</div>

<!-- 기획전·프로모션 -->
<div id='page-promo' class='page'>
  <div class='ph'><h2>기획전 · 프로모션</h2><p>경쟁사 현재 진행 중 및 예정 기획전 현황</p></div>
  <div class='sl'>이번 주 진행 현황</div>
  <div class='card' style='margin-bottom:13px'>
    <div class='pi'><div class='pa' style='background:var(--purple)'></div><div class='pb'><div class='ph2'><span class='pn'>포스티</span><span class='badge bl'>진행중</span><span class='badge bDi'>직접경쟁</span></div><div class='pt'>봄 시즌 오피스룩 기획전 — 정장·블라우스 중심, 최대 35% 할인 + 무료배송. PB '잇파인' 여름 신상 15% 쿠폰 병행.</div><div class='pd'>04.18 ~ 04.27</div></div></div>
    <div class='pi'><div class='pa' style='background:var(--coral)'></div><div class='pb'><div class='ph2'><span class='pn'>에이블리</span><span class='badge bl'>진행중</span></div><div class='pt'>봄 신상 대전 20~40% 할인 + 신규 회원 50% 쿠폰. 할인코드 "benefits" 상시. 5월 메가세일(4/30~5/15) 예고.</div><div class='pd'>04.15 ~ 04.30</div></div></div>
    <div class='pi'><div class='pa' style='background:var(--amber)'></div><div class='pb'><div class='ph2'><span class='pn'>지그재그</span><span class='badge bl'>진행중</span></div><div class='pt'>봄 아우터 재고 소진 40% 할인 + 직잭뷰티×패션 콜라보 기획전. 쿠폰 랜덤뽑기 매일 12시.</div><div class='pd'>04.20 ~ 04.25</div></div></div>
    <div class='pi'><div class='pa' style='background:var(--blue)'></div><div class='pb'><div class='ph2'><span class='pn'>무신사·29CM</span><span class='badge bl'>진행중</span></div><div class='pt'>2026 어스 위크 공동 캠페인 — 지속가능 브랜드 특집 + 회원 쿠폰 20%.</div><div class='pd'>04.22 ~ 04.26</div></div></div>
    <div class='pi'><div class='pa' style='background:#888'></div><div class='pb'><div class='ph2'><span class='pn'>W컨셉</span><span class='badge bs'>예정</span></div><div class='pt'>어린이날 시즌 기획전(선물세트 카테고리 확장) 준비 중.</div><div class='pd'>05.01 예정</div></div></div>
  </div>
  <div class='sl'>플랫폼별 패턴 비교</div>
  <div class='g2'>
    <div class='card'><div style='font-size:13px;font-weight:700;margin-bottom:10px;padding-bottom:9px;border-bottom:1px solid var(--border)'>포스티</div><div class='ai' style='padding:7px 0'><div><div class='ac' style='font-size:12px'>주기</div><div class='at'>월 2~3회 정기 + 명절 특집</div></div></div><div class='ai' style='padding:7px 0'><div><div class='ac' style='font-size:12px'>방식</div><div class='at'>카테고리 정률 + PB 쿠폰 이중 전략</div></div></div><div class='ai' style='padding:7px 0;border-bottom:none'><div><div class='ac' style='font-size:12px'>차별점</div><div class='at'>라이브커머스 연동 + 전 상품 무료배송</div></div></div></div>
    <div class='card'><div style='font-size:13px;font-weight:700;margin-bottom:10px;padding-bottom:9px;border-bottom:1px solid var(--border)'>에이블리</div><div class='ai' style='padding:7px 0'><div><div class='ac' style='font-size:12px'>주기</div><div class='at'>상시 할인 + 주 1회 이벤트</div></div></div><div class='ai' style='padding:7px 0'><div><div class='ac' style='font-size:12px'>방식</div><div class='at'>쿠폰 중심(최대 50%), 신규 유입 특화</div></div></div><div class='ai' style='padding:7px 0;border-bottom:none'><div><div class='ac' style='font-size:12px'>차별점</div><div class='at'>상시 할인코드 + 5월 메가세일</div></div></div></div>
    <div class='card'><div style='font-size:13px;font-weight:700;margin-bottom:10px;padding-bottom:9px;border-bottom:1px solid var(--border)'>지그재그</div><div class='ai' style='padding:7px 0'><div><div class='ac' style='font-size:12px'>주기</div><div class='at'>뷰티·패션 콜라보 월 1~2회</div></div></div><div class='ai' style='padding:7px 0'><div><div class='ac' style='font-size:12px'>방식</div><div class='at'>카테고리 크로스 묶음 + 쿠폰 랜덤뽑기</div></div></div><div class='ai' style='padding:7px 0;border-bottom:none'><div><div class='ac' style='font-size:12px'>차별점</div><div class='at'>직잭뷰티 GMV 확장 + 경품 이벤트</div></div></div></div>
    <div class='card'><div style='font-size:13px;font-weight:700;margin-bottom:10px;padding-bottom:9px;border-bottom:1px solid var(--border)'>무신사·29CM</div><div class='ai' style='padding:7px 0'><div><div class='ac' style='font-size:12px'>주기</div><div class='at'>멤버스데이 매월 1~3일 + 시즌 빅세일</div></div></div><div class='ai' style='padding:7px 0'><div><div class='ac' style='font-size:12px'>방식</div><div class='at'>무신사머니 적립 + 카드사 즉시할인</div></div></div><div class='ai' style='padding:7px 0;border-bottom:none'><div><div class='ac' style='font-size:12px'>차별점</div><div class='at'>캠페인 기획 강점 (어스위크 등)</div></div></div></div>
  </div>
</div>

<!-- 타임특가 -->
<div id='page-flash' class='page'>
  <div class='ph'><h2>타임특가 모니터링</h2><p>경쟁사 한정 타임특가·데일리딜 시간대별 현황</p></div>
  <div class='sl'>진행 중 타임특가</div>
  <div class='card' style='margin-bottom:13px'>
    <div class='pi'><div class='pa' style='background:var(--purple)'></div><div class='pb'><div class='ph2'><span class='pn'>포스티</span><span class='badge bh'>🔥 매일특가</span></div><div class='pt'>최대 90% 할인 상품 별도 섹션 매일 갱신. 재고 소진 시 자동 종료.</div><div class='pd'>매일 00:00 갱신</div></div></div>
    <div class='pi'><div class='pa' style='background:var(--coral)'></div><div class='pb'><div class='ph2'><span class='pn'>에이블리</span><span class='badge bh'>🔥 하루특가</span></div><div class='pt'>하루특가·50% 이상·아이코닉 특가 섹션 상시. 오전/오후 2회 오픈.</div><div class='pd'>매일 10:00 / 20:00</div></div></div>
    <div class='pi'><div class='pa' style='background:var(--amber)'></div><div class='pb'><div class='ph2'><span class='pn'>지그재그</span><span class='badge bh'>🔥 선착순쿠폰</span></div><div class='pt'>99% 쿠폰 랜덤뽑기 + 선착순 1,000 포인트. 타임 한정.</div><div class='pd'>매일 12:00</div></div></div>
    <div class='pi'><div class='pa' style='background:var(--blue)'></div><div class='pb'><div class='ph2'><span class='pn'>무신사</span><span class='badge bl'>진행중</span></div><div class='pt'>멤버스데이 매월 1~3일 20% 쿠폰 + 10% 적립. 10만원↑ 8,000원 추가 혜택.</div><div class='pd'>매월 1~3일</div></div></div>
    <div class='pi'><div class='pa' style='background:#555'></div><div class='pb'><div class='ph2'><span class='pn'>29CM</span><span class='badge bs'>시즌별</span></div><div class='pt'>이굿위크 — 브랜드 런칭 특가 + 디자이너 단독 발매.</div><div class='pd'>시즌별</div></div></div>
  </div>
  <div class='sl'>구조 비교</div>
  <div class='card'>
    <table class='dt'><thead><tr><th>플랫폼</th><th>방식</th><th>오픈 시간</th><th>최대 할인</th><th>특이사항</th></tr></thead>
    <tbody>
      <tr><td class='dn'>포스티</td><td>매일 갱신 섹션</td><td>00:00</td><td>최대 90%</td><td>재고 소진 자동 종료</td></tr>
      <tr><td class='dn'>에이블리</td><td>하루특가 2회</td><td>10:00/20:00</td><td>50% 이상</td><td>카테고리별 2회</td></tr>
      <tr><td class='dn'>지그재그</td><td>쿠폰 랜덤뽑기</td><td>12:00</td><td>99% 쿠폰</td><td>선착순 소진</td></tr>
      <tr><td class='dn'>무신사</td><td>멤버스데이</td><td>매월 1~3일</td><td>20%+적립</td><td>무신사머니 연동</td></tr>
      <tr><td class='dn'>29CM</td><td>이굿위크</td><td>시즌별</td><td>20% 쿠폰</td><td>디자이너 단독</td></tr>
    </tbody></table>
  </div>
  <div class='ins'><strong>MD 인사이트</strong> — 포스티(00시)·에이블리(10·20시)·지그재그(12시) 다른 시간대 운영. 퀸잇 타임특가 기획 시 공백 슬롯(오후 7시대) 검토 유효.</div>
</div>

<!-- 앱스토어 현황 (자동수집) -->
<div id='page-appstore' class='page'>
  <div class='ph'><h2>앱스토어 현황</h2><p>자동 수집 — {TODAY}</p></div>
  <div class='g2'>{app_cards}</div>
</div>

<!-- 기획전 수집본 (자동수집) -->
<div id='page-events' class='page'>
  <div class='ph'><h2>기획전 수집본</h2><p>크롤러가 오늘 수집한 경쟁사 기획전 — {TODAY}</p></div>
  <div class='sl'>포스티</div><div class='card'>{ev_p}</div>
  <div class='sl'>에이블리</div><div class='card'>{ev_a}</div>
  <div class='sl'>29CM</div><div class='card'>{ev_c}</div>
  <div class='sl'>W컨셉</div><div class='card'>{ev_w}</div>
  <div class='ibox'><strong>안내</strong> — 포스티·에이블리는 앱 전용 서비스라 공개 웹 기획전 페이지 기반으로 수집합니다. 상세 내역은 앱에서 확인하세요.</div>
</div>

<!-- 가격 변동 알림 -->
<div id='page-alerts' class='page'>
  <div class='ph'><h2>가격 변동 알림</h2><p>경쟁사 가격·할인 변동 감지 내역</p></div>
  <div class='sl'>최근 감지 내역</div>
  <div class='card'>
    <div class='ai'><div style='font-size:15px;flex-shrink:0'>🔻</div><div><div class='ac'>포스티</div><div class='at'>여름 신상 아우터 평균 5% 인하 — PB '잇파인' 런칭 연동. 쿠폰 적용 시 블라우스 2만원대.</div><div class='ad'>2026-04-18 · 보도자료</div></div></div>
    <div class='ai'><div style='font-size:15px;flex-shrink:0'>🔖</div><div><div class='ac'>에이블리</div><div class='at'>세트 묶음 30% 추가 할인 + 봄 신상 대전 중복. 실질 할인율 최대 65%.</div><div class='ad'>2026-04-20 · 앱스토어 수집</div></div></div>
    <div class='ai'><div style='font-size:15px;flex-shrink:0'>🏷</div><div><div class='ac'>지그재그</div><div class='at'>봄 아우터 재고 소진 40% 할인 — 동대문 기반 상품 위주.</div><div class='ad'>2026-04-18 · 수동 수집</div></div></div>
    <div class='ai'><div style='font-size:15px;flex-shrink:0'>✨</div><div><div class='ac'>29CM</div><div class='at'>어스 위크 참여 브랜드 단독 특가 + 회원 쿠폰 20%.</div><div class='ad'>2026-04-20 · 공식 보도자료</div></div></div>
    <div class='ai'><div style='font-size:15px;flex-shrink:0'>📊</div><div><div class='ac'>무신사</div><div class='at'>나이키 메가쇼케이스 12만원↑ 15,000원 혜택. 무신사 현대카드 5% 추가 청구할인.</div><div class='ad'>2026-04-15 · 수동 수집</div></div></div>
    <div class='ai'><div style='font-size:15px;flex-shrink:0'>⚠️</div><div><div class='ac'>W컨셉</div><div class='at'>2025 적자 전환 후 마케팅 축소 기조. 할인 빈도 감소 추세.</div><div class='ad'>2026-04-15 · 업계 기사</div></div></div>
  </div>
</div>

<!-- 기사·내부 소식 (자동수집) -->
<div id='page-news' class='page'>
  <div class='ph'><h2>주요 기사 · 내부 소식</h2><p>경쟁사별 최신 뉴스 — 자동 수집 {TODAY}</p></div>
  <div class='ng2'>{news_cards}</div>
</div>

<!-- 크롤링 설정 -->
<div id='page-crawl' class='page'>
  <div class='ph'><h2>크롤링 설정</h2><p>자동 수집 현황 및 로드맵</p></div>
  <div class='sl'>수집 대상 현황</div>
  <div class='card'>
    <table class='dt'><thead><tr><th>경쟁사</th><th>수집 항목</th><th>방법</th><th>상태</th></tr></thead>
    <tbody>
      <tr><td class='dn'>포스티</td><td>iOS 리뷰 5건, Android 업데이트, 기획전</td><td>앱스토어 RSS + 웹</td><td><span class='pill p-ok'>자동</span></td></tr>
      <tr><td class='dn'>에이블리</td><td>iOS 리뷰 5건, 기획전 목록</td><td>앱스토어 RSS + 웹</td><td><span class='pill p-ok'>자동</span></td></tr>
      <tr><td class='dn'>지그재그</td><td>iOS 리뷰 5건, Android 업데이트</td><td>앱스토어 RSS + 웹</td><td><span class='pill p-ok'>자동</span></td></tr>
      <tr><td class='dn'>29CM</td><td>기획전 목록 + 링크</td><td>공개 웹페이지</td><td><span class='pill p-warn'>간헐 차단</span></td></tr>
      <tr><td class='dn'>W컨셉</td><td>기획전, 신규 입점</td><td>공개 웹페이지</td><td><span class='pill p-ok'>자동</span></td></tr>
      <tr><td class='dn'>뉴스 (전체)</td><td>네이버 뉴스 검색 3건</td><td>네이버 검색</td><td><span class='pill p-ok'>자동</span></td></tr>
    </tbody></table>
  </div>
  <div class='sl'>자동화 로드맵</div>
  <div class='card'>
    <table class='dt'><thead><tr><th>단계</th><th>내용</th><th>상태</th></tr></thead>
    <tbody>
      <tr><td class='dn'>1단계 ✅</td><td>앱스토어 리뷰 자동 수집 + 대시보드 HTML 생성</td><td><span class='pill p-ok'>완료</span></td></tr>
      <tr><td class='dn'>2단계 ✅</td><td>29CM·W컨셉 기획전 웹 크롤링</td><td><span class='pill p-ok'>완료</span></td></tr>
      <tr><td class='dn'>3단계 ✅</td><td>네이버 뉴스 자동 수집 (경쟁사별 3건)</td><td><span class='pill p-ok'>완료</span></td></tr>
      <tr><td class='dn'>4단계</td><td>공식 인스타그램 피드 자동 수집</td><td><span class='pill p-warn'>개발 예정</span></td></tr>
      <tr><td class='dn'>5단계</td><td>앱 내 상품 가격 직접 크롤링</td><td><span class='pill p-block'>정책 검토</span></td></tr>
    </tbody></table>
  </div>
  <div class='ibox'><strong>자동 실행</strong> — Mac cron에 등록되어 <strong>매일 오전 9:00</strong> 자동 실행됩니다.<br>
  결과 파일: <code>reports/{TODAY}.html</code> + <code>reports/latest.html</code> (항상 최신본)<br>
  수동 실행: <code>python3 crawler.py</code> &nbsp;|&nbsp; 최신 열기: <code>open reports/latest.html</code></div>
</div>

</main>
</div>
<script>
function go(id, el) {{
  document.querySelectorAll('.page').forEach(p => p.classList.remove('on'));
  document.getElementById('page-' + id).classList.add('on');
  document.querySelectorAll('.ni').forEach(n => n.classList.remove('on'));
  el.classList.add('on');
  window.scrollTo({{top:0, behavior:'smooth'}});
}}
</script>
</body>
</html>"""


def save_dashboard(html):
    dated  = REPORT / f"{TODAY}.html"
    latest = REPORT / "latest.html"
    dated.write_text(html,  encoding="utf-8")
    latest.write_text(html, encoding="utf-8")
    print(f"✅ 대시보드: {dated}")
    print(f"✅ 최신본:   {latest}")
    return latest


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────
def main():
    print("=" * 54)
    print(f"  퀸잇 경쟁사 크롤러 + 대시보드  {TODAY}")
    print("=" * 54)

    data = {"collected_at": TODAY}

    try:    data["appstore"] = crawl_appstore()
    except: data["appstore"] = []; print("⚠ 앱스토어 수집 실패")

    try:    data["events"] = crawl_events()
    except: data["events"] = {}; print("⚠ 기획전 수집 실패")

    try:    data["news"] = crawl_news()
    except: data["news"] = {}; print("⚠ 뉴스 수집 실패")

    print("[4/4] 대시보드 생성...")
    save_json(data)
    html   = generate_dashboard(data)
    latest = save_dashboard(html)

    print()
    print("=" * 54)
    print(f"  완료!  open {latest}")
    print("=" * 54)


if __name__ == "__main__":
    main()
