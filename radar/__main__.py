import argparse
import json
from .core import apply_jobs, apply_papers, companies, connect, export, fetch_jobs, fetch_papers, mark_error, save_state


def main():
    parser = argparse.ArgumentParser(description="Collect public research lab signals")
    parser.add_argument("command", choices=["collect", "export"])
    parser.add_argument("--jobs-only", action="store_true", help="Skip OpenAlex paper candidates")
    args = parser.parse_args()
    db = connect()
    if args.command == "collect":
        for company in companies():
            if company["jobs"]:
                try:
                    jobs, url = fetch_jobs(company)
                    outcome = apply_jobs(db, company, jobs, url)
                    print(json.dumps({"company": company["id"], "source": "jobs", **outcome}))
                except Exception as exc:
                    mark_error(db, company["id"], "jobs", exc)
                    print(json.dumps({"company": company["id"], "source": "jobs", "error": str(exc)}))
            if not args.jobs_only and company["openalex_ids"]:
                try:
                    papers, url = fetch_papers(company)
                    apply_papers(db, company, papers, url)
                    print(json.dumps({"company": company["id"], "source": "papers", "count": len(papers)}))
                except Exception as exc:
                    mark_error(db, company["id"], "papers", exc)
                    print(json.dumps({"company": company["id"], "source": "papers", "error": str(exc)}))
    result = export(db)
    save_state(db)
    print(json.dumps({"exported": len(result["jobs"]), "events": len(result["events"]), "paper_candidates": len(result["papers"])}))


if __name__ == "__main__":
    main()
