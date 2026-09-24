import datetime as dt
import html
import json
import re
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path
from .classify import classify_job
from .google_careers import fetch_google_careers
from .microsoft_careers import fetch_microsoft_careers, is_named_msr

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "companies.json"
DB = ROOT / "state" / "radar.sqlite3"
OUT = ROOT / "site" / "data.json"
SNAPSHOT = ROOT / "state" / "snapshot.json"
USER_AGENT = "ResearchLabRadar/0.1 (public research dashboard)"

PAPER_RELEVANT = re.compile(r"artificial intelligence|machine learning|deep learning|language model|\bllm\b|robot|multimodal|computer vision|agentic|\bagent\b|reinforcement learning|neural network|generative ai|transformer|speech recognition|ai safety|alignment|interpretability|foundation model|diffusion model", re.I)


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def post_json(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"User-Agent": "Mozilla/5.0 (ResearchLabRadar/0.1)", "Accept": "application/json", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def companies():
    return json.loads(CONFIG.read_text())


def normalize_job(company, raw):
    provider = company["jobs"]["type"]
    if provider == "workday":
        source = company["jobs"]
        path = raw["externalPath"]
        title = raw.get("title") or ""
        result = {"id": (raw.get("bulletFields") or [path])[-1], "title": title, "location": raw.get("locationsText") or "", "url": f"https://{source['host']}/en-US/{source['site']}{path}", "published_at": None, "description": ""}
    elif provider == "ashby":
        title = raw.get("title") or ""
        description = raw.get("descriptionPlain") or ""
        result = {"id": str(raw["id"]), "title": title, "location": raw.get("location") or "", "url": raw.get("jobUrl") or "", "published_at": raw.get("publishedAt"), "description": description}
    elif provider == "google_careers":
        title = raw["title"]
        result = {"id": str(raw["id"]), "title": title, "location": raw.get("location") or "", "url": raw["url"], "published_at": None, "description": "", "unit_hint": raw.get("organization") or ""}
    elif provider == "microsoft_careers":
        title = raw["title"]
        result = {"id": str(raw["id"]), "title": title, "location": raw.get("location") or "", "url": raw["url"], "published_at": raw.get("published_at"), "description": "", "unit_hint": raw.get("department") or ""}
    else:
        title = raw.get("title") or ""
        description = html.unescape(re.sub(r"<[^>]*>", " ", raw.get("content") or ""))
        result = {"id": str(raw["id"]), "title": title, "location": (raw.get("location") or {}).get("name") or "", "url": raw.get("absolute_url") or "", "published_at": raw.get("first_published"), "description": description}
    result["company_id"] = company["id"]
    labels = classify_job(title)
    result.update(labels)
    result["relevant"] = labels["role_family"] != "other"
    result.setdefault("unit_hint", "")
    return result


def fetch_jobs(company):
    source = company["jobs"]
    if source["type"] == "google_careers":
        raw, url = fetch_google_careers(source["query"])
        return [normalize_job(company, item) for item in raw], url
    if source["type"] == "microsoft_careers":
        raw, url = fetch_microsoft_careers(source["query"])
        subset = source["subset"]
        raw = [item for item in raw if is_named_msr(item) == (subset == "msr")]
        if not raw:
            raise ValueError("Microsoft Careers returned no positions for this named subset")
        return [normalize_job(company, item) for item in raw], url
    if source["type"] == "workday":
        endpoint = f"https://{source['host']}/wday/cxs/{source['tenant']}/{source['site']}/jobs"
        found = {}
        for term in source["terms"]:
            offset = 0
            while True:
                page = post_json(endpoint, {"appliedFacets":{},"limit":20,"offset":offset,"searchText":term})
                postings = page.get("jobPostings") or []
                if not postings and offset == 0:
                    raise ValueError(f"Empty Workday response for {term}; keeping prior snapshot")
                for item in postings:
                    normalized = normalize_job(company,item)
                    found[normalized["id"]] = normalized
                offset += len(postings)
                if offset >= page.get("total",0) or len(postings) < 20:
                    break
        jobs = list(found.values())
        if not jobs:
            raise ValueError("Empty job response; keeping previous snapshot")
        return jobs, f"https://{source['host']}/en-US/{source['site']}"
    if source["type"] == "ashby":
        url = "https://api.ashbyhq.com/posting-api/job-board/" + urllib.parse.quote(source["token"])
    else:
        url = "https://boards-api.greenhouse.io/v1/boards/" + urllib.parse.quote(source["token"]) + "/jobs?content=true"
    data = get_json(url)
    jobs = [normalize_job(company, item) for item in data["jobs"]]
    if not jobs:
        raise ValueError("Empty job response; keeping previous snapshot")
    return jobs, url


def connect(path=DB):
    fresh = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS jobs (
      company_id TEXT NOT NULL, id TEXT NOT NULL, title TEXT NOT NULL,
      location TEXT NOT NULL, url TEXT NOT NULL, published_at TEXT,
      topics TEXT NOT NULL, relevant INTEGER NOT NULL, active INTEGER NOT NULL,
      first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
      role_family TEXT NOT NULL DEFAULT 'other',
      topic_evidence TEXT NOT NULL DEFAULT '{}',
      unit_hint TEXT NOT NULL DEFAULT '',
      missing_runs INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(company_id,id)
    );
    CREATE TABLE IF NOT EXISTS events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, company_id TEXT NOT NULL,
      job_id TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
      occurred_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sources (
      company_id TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL,
      last_attempt TEXT, last_success TEXT, item_count INTEGER NOT NULL DEFAULT 0,
      error TEXT, url TEXT,
      PRIMARY KEY(company_id,kind)
    );
    CREATE TABLE IF NOT EXISTS papers (
      id TEXT PRIMARY KEY, company_id TEXT NOT NULL, title TEXT NOT NULL,
      publication_date TEXT, url TEXT NOT NULL, citations INTEGER NOT NULL,
      first_seen TEXT NOT NULL
    );
    """)
    columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
    for name, definition in (
        ("role_family", "TEXT NOT NULL DEFAULT 'other'"),
        ("topic_evidence", "TEXT NOT NULL DEFAULT '{}'"),
        ("unit_hint", "TEXT NOT NULL DEFAULT ''"),
        ("missing_runs", "INTEGER NOT NULL DEFAULT 0"),
    ):
        if name not in columns:
            db.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")
    if fresh and path == DB and SNAPSHOT.exists():
        restore_state(db, SNAPSHOT)
    return db


def save_state(db, path=SNAPSHOT):
    tables = ("jobs", "events", "sources", "papers")
    state = {name:[dict(row) for row in db.execute(f"SELECT * FROM {name}")] for name in tables}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")))


def restore_state(db, path=SNAPSHOT):
    state = json.loads(path.read_text())
    with db:
        for table in ("jobs", "events", "sources", "papers"):
            rows = state.get(table, [])
            if not rows:
                continue
            columns = list(rows[0])
            placeholders = ",".join("?" for _ in columns)
            query = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
            db.executemany(query, ([row.get(col) for col in columns] for row in rows))


def apply_jobs(db, company, jobs, source_url, now=None):
    now = now or utc_now()
    cid = company["id"]
    prev = db.execute("SELECT last_success FROM sources WHERE company_id=? AND kind='jobs'", (cid,)).fetchone()
    baseline = prev is None or prev["last_success"] is None
    seen = set()
    with db:
        for job in jobs:
            jid = job["id"]
            seen.add(jid)
            old = db.execute("SELECT title,location,active FROM jobs WHERE company_id=? AND id=?", (cid,jid)).fetchone()
            if old is None:
                db.execute("""INSERT INTO jobs
                  (company_id,id,title,location,url,published_at,topics,relevant,active,first_seen,last_seen,role_family,topic_evidence,unit_hint,missing_runs)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                  (cid,jid,job["title"],job["location"],job["url"],job["published_at"],
                   json.dumps(job["topics"]),int(job["relevant"]),1,now,now,
                   job.get("role_family","other"),json.dumps(job.get("topic_evidence",{})),job.get("unit_hint","")))
                if not baseline:
                    db.execute("INSERT INTO events(company_id,job_id,kind,title,occurred_at) VALUES (?,?,?,?,?)", (cid,jid,"new",job["title"],now))
            else:
                changed = old["title"] != job["title"] or old["location"] != job["location"]
                kind = "reopened" if not old["active"] else ("changed" if changed else None)
                db.execute("""UPDATE jobs SET title=?,location=?,url=?,published_at=?,topics=?,relevant=?,
                  role_family=?,topic_evidence=?,unit_hint=?,active=1,last_seen=?,missing_runs=0
                  WHERE company_id=? AND id=?""",
                  (job["title"],job["location"],job["url"],job["published_at"],json.dumps(job["topics"]),
                   int(job["relevant"]),job.get("role_family","other"),json.dumps(job.get("topic_evidence",{})),
                   job.get("unit_hint",""),now,cid,jid))
                if kind and not baseline:
                    db.execute("INSERT INTO events(company_id,job_id,kind,title,occurred_at) VALUES (?,?,?,?,?)", (cid,jid,kind,job["title"],now))
        active = db.execute("SELECT id,title,missing_runs FROM jobs WHERE company_id=? AND active=1", (cid,)).fetchall()
        for old in active:
            if old["id"] not in seen:
                missing_runs = old["missing_runs"] + 1
                db.execute("UPDATE jobs SET missing_runs=? WHERE company_id=? AND id=?", (missing_runs,cid,old["id"]))
                if missing_runs >= 2:
                    db.execute("UPDATE jobs SET active=0 WHERE company_id=? AND id=?", (cid,old["id"]))
                    if not baseline:
                        db.execute("INSERT INTO events(company_id,job_id,kind,title,occurred_at) VALUES (?,?,?,?,?)", (cid,old["id"],"removed",old["title"],now))
        db.execute("INSERT INTO sources(company_id,kind,status,last_attempt,last_success,item_count,error,url) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(company_id,kind) DO UPDATE SET status=excluded.status,last_attempt=excluded.last_attempt,last_success=excluded.last_success,item_count=excluded.item_count,error=NULL,url=excluded.url", (cid,"jobs","ok",now,now,len(jobs),None,source_url))
    return {"count":len(jobs),"baseline":baseline}


def mark_error(db, company_id, kind, error, now=None):
    now = now or utc_now()
    with db:
        db.execute("INSERT INTO sources(company_id,kind,status,last_attempt,error) VALUES (?,?,?,?,?) ON CONFLICT(company_id,kind) DO UPDATE SET status='error',last_attempt=excluded.last_attempt,error=excluded.error", (company_id,kind,"error",now,str(error)[:300]))


def relabel_jobs(db):
    """Apply current title rules to old snapshots as well as newly fetched jobs."""
    with db:
        for row in db.execute("SELECT company_id,id,title FROM jobs").fetchall():
            labels = classify_job(row["title"])
            db.execute("""UPDATE jobs SET topics=?,relevant=?,role_family=?,topic_evidence=?
              WHERE company_id=? AND id=?""",
              (json.dumps(labels["topics"]),int(labels["role_family"] != "other"),
               labels["role_family"],json.dumps(labels["topic_evidence"]),row["company_id"],row["id"]))


def fetch_papers(company, since_days=30):
    ids = company["openalex_ids"]
    if not ids:
        return [], None
    since = (dt.date.today() - dt.timedelta(days=since_days)).isoformat()
    papers = []
    for institution_id in ids:
        params = {"filter":f"institutions.id:{institution_id},from_publication_date:{since},has_doi:true", "sort":"publication_date:desc", "per-page":"50", "select":"id,title,publication_date,doi,cited_by_count,type"}
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
        for raw in get_json(url).get("results", []):
            title = raw.get("title") or ""
            doi = raw.get("doi") or ""
            if (len(title) < 20 or len(title) > 250 or not doi or
                raw.get("type") not in ("article","preprint","proceedings-article") or
                "10.5281/zenodo" in doi.lower() or
                not PAPER_RELEVANT.search(title) or
                (raw.get("publication_date") or "9999") > dt.date.today().isoformat()):
                continue
            papers.append({"id":raw["id"], "company_id":company["id"], "title":title, "publication_date":raw.get("publication_date"), "url":doi, "citations":raw.get("cited_by_count") or 0})
    return list({p["url"].lower():p for p in papers}.values()), "https://openalex.org/"


def apply_papers(db, company, papers, source_url, now=None):
    now = now or utc_now()
    with db:
        for p in papers:
            db.execute("INSERT INTO papers(id,company_id,title,publication_date,url,citations,first_seen) VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET citations=excluded.citations", (p["id"],p["company_id"],p["title"],p["publication_date"],p["url"],p["citations"],now))
        db.execute("INSERT INTO sources(company_id,kind,status,last_attempt,last_success,item_count,error,url) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(company_id,kind) DO UPDATE SET status=excluded.status,last_attempt=excluded.last_attempt,last_success=excluded.last_success,item_count=excluded.item_count,error=NULL,url=excluded.url", (company["id"],"papers","ok",now,now,len(papers),None,source_url))


def export(db, out=OUT):
    now = utc_now()
    cfg = companies()
    source_rows = db.execute("SELECT * FROM sources").fetchall()
    sources = {(r["company_id"],r["kind"]):dict(r) for r in source_rows}
    jobs = [dict(r) for r in db.execute("SELECT company_id,id,title,location,url,published_at,topics,role_family,topic_evidence,unit_hint,first_seen FROM jobs WHERE active=1 AND relevant=1 ORDER BY published_at DESC,title LIMIT 1000")]
    for j in jobs:
        j["topics"] = json.loads(j["topics"])
        j["topic_evidence"] = json.loads(j["topic_evidence"])
    events = [dict(r) for r in db.execute("SELECT e.company_id,e.job_id,e.kind,e.title,e.occurred_at FROM events e JOIN jobs j ON j.company_id=e.company_id AND j.id=e.job_id WHERE j.relevant=1 ORDER BY e.occurred_at DESC,e.id DESC LIMIT 250")]
    papers = [dict(r) for r in db.execute("SELECT company_id,title,publication_date,url,citations,first_seen FROM papers ORDER BY publication_date DESC LIMIT 250")]
    payload = {"generated_at":now,"method":"Public ATS APIs and OpenAlex; titles use rule-based topic tags. OpenAlex papers are candidates pending affiliation review.","companies":[],"jobs":jobs,"events":events,"papers":papers,"coverage":{"linkedin":"manual_search_only","x":"manual_search_only","llm":"not_configured"}}
    for c in cfg:
        cid = c["id"]
        job_count = db.execute("SELECT COUNT(*) FROM jobs WHERE company_id=? AND active=1 AND relevant=1",(cid,)).fetchone()[0]
        c = {k:v for k,v in c.items() if k not in ("openalex_ids",)}
        c["relevant_jobs"] = job_count
        c["sources"] = {kind:sources.get((cid,kind),{"status":"not_configured"}) for kind in ("jobs","papers")}
        payload["companies"].append(c)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    return payload
