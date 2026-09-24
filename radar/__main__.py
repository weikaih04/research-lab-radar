import argparse
import json
from .core import apply_jobs, apply_papers, companies, connect, export, fetch_jobs, fetch_papers, mark_error, relabel_jobs, save_state
from .microsoft_careers import fetch_microsoft_careers


def main():
    parser = argparse.ArgumentParser(description="Collect public research lab signals")
    parser.add_argument("command", choices=["collect", "export"])
    parser.add_argument("--jobs-only", action="store_true", help="Skip OpenAlex paper candidates")
    parser.add_argument("--company", action="append", help="Collect only this company ID; repeat to select several")
    args = parser.parse_args()
    db = connect()
    if args.command == "collect":
        selected = set(args.company or [])
        registry = companies()
        unknown = selected - {company["id"] for company in registry}
        if unknown:
            parser.error("Unknown company IDs: " + ", ".join(sorted(unknown)))
        retry = []
        for company in registry:
            if selected and company["id"] not in selected:
                continue
            if company["jobs"]:
                try:
                    jobs, url = fetch_jobs(company)
                    outcome = apply_jobs(db, company, jobs, url)
                    print(json.dumps({"company": company["id"], "source": "jobs", **outcome}))
                except Exception as exc:
                    mark_error(db, company["id"], "jobs", exc)
                    print(json.dumps({"company": company["id"], "source": "jobs", "error": str(exc)}))
                    if company["jobs"]["type"] == "microsoft_careers":
                        retry.append(company)
            if not args.jobs_only and company["openalex_ids"]:
                try:
                    papers, url = fetch_papers(company)
                    apply_papers(db, company, papers, url)
                    print(json.dumps({"company": company["id"], "source": "papers", "count": len(papers)}))
                except Exception as exc:
                    mark_error(db, company["id"], "papers", exc)
                    print(json.dumps({"company": company["id"], "source": "papers", "error": str(exc)}))
        for company in (retry if fetch_microsoft_careers.cache_info().currsize else []):
            try:
                jobs, url = fetch_jobs(company)
                outcome = apply_jobs(db, company, jobs, url)
                print(json.dumps({"company": company["id"], "source": "jobs_retry", **outcome}))
            except Exception as exc:
                mark_error(db, company["id"], "jobs", exc)
                print(json.dumps({"company": company["id"], "source": "jobs_retry", "error": str(exc)}))
    relabel_jobs(db)
    result = export(db)
    save_state(db)
    print(json.dumps({"exported": len(result["jobs"]), "events": len(result["events"]), "paper_candidates": len(result["papers"])}))


if __name__ == "__main__":
    main()
