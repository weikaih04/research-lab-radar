import sqlite3
import tempfile
import unittest
from pathlib import Path
from radar.core import apply_jobs, connect, mark_error, save_state, restore_state, normalize_job, relabel_jobs
from radar.classify import classify_job
from radar.google_careers import parse_results
from radar.microsoft_careers import fetch_microsoft_careers, is_named_msr
from unittest.mock import patch


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = connect(Path(self.temp.name) / "radar.sqlite3")
        self.company = {"id":"example"}
        self.job = {"id":"1","title":"Research Scientist, Robotics","location":"SF","url":"https://example.com/1","published_at":None,"topics":["Robotics"],"relevant":True,"role_family":"research","topic_evidence":{"Robotics":"Robotics"},"unit_hint":""}

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_baseline_and_real_new_event(self):
        outcome = apply_jobs(self.db,self.company,[self.job],"https://example.com", "2026-09-01T00:00:00+00:00")
        self.assertTrue(outcome["baseline"])
        self.assertEqual(0,self.db.execute("SELECT count(*) FROM events").fetchone()[0])
        second = dict(self.job,id="2",title="Research Engineer, LLM")
        apply_jobs(self.db,self.company,[self.job,second],"https://example.com", "2026-09-02T00:00:00+00:00")
        self.assertEqual(["new"],[r[0] for r in self.db.execute("SELECT kind FROM events")])
        apply_jobs(self.db,self.company,[self.job,second],"https://example.com", "2026-09-03T00:00:00+00:00")
        self.assertEqual(1,self.db.execute("SELECT count(*) FROM events").fetchone()[0])

    def test_failed_source_keeps_last_good_snapshot(self):
        apply_jobs(self.db,self.company,[self.job],"https://example.com", "2026-09-01T00:00:00+00:00")
        mark_error(self.db,"example","jobs","timeout", "2026-09-02T00:00:00+00:00")
        self.assertEqual(1,self.db.execute("SELECT count(*) FROM jobs WHERE active=1").fetchone()[0])
        row = self.db.execute("SELECT status,last_success FROM sources").fetchone()
        self.assertEqual("error",row["status"])
        self.assertEqual("2026-09-01T00:00:00+00:00",row["last_success"])

    def test_snapshot_restores_history_on_fresh_runner(self):
        apply_jobs(self.db,self.company,[self.job],"https://example.com", "2026-09-01T00:00:00+00:00")
        snapshot = Path(self.temp.name) / "snapshot.json"
        save_state(self.db,snapshot)
        other = connect(Path(self.temp.name) / "fresh.sqlite3")
        restore_state(other,snapshot)
        self.assertEqual(1,other.execute("SELECT count(*) FROM jobs WHERE active=1").fetchone()[0])
        self.assertIsNotNone(other.execute("SELECT last_success FROM sources WHERE company_id='example'").fetchone()[0])
        other.close()

    def test_nonresearch_ai_sales_is_not_counted(self):
        company = {"id":"example","jobs":{"type":"ashby"}}
        sales = normalize_job(company,{"id":"1","title":"Account Executive, AI Native","jobUrl":"https://example.com","descriptionPlain":""})
        scientist = normalize_job(company,{"id":"2","title":"Research Scientist, Robotics","jobUrl":"https://example.com","descriptionPlain":""})
        self.assertFalse(sales["relevant"])
        self.assertTrue(scientist["relevant"])

    def test_workday_job_keeps_official_link(self):
        company = {"id":"nvidia","jobs":{"type":"workday","host":"nvidia.wd5.myworkdayjobs.com","site":"NVIDIAExternalCareerSite"}}
        job = normalize_job(company,{"title":"Research Scientist, Robotics","externalPath":"/job/Test/Research-Scientist_JR42","bulletFields":["JR42"],"locationsText":"Santa Clara"})
        self.assertEqual("JR42",job["id"])
        self.assertEqual("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/Test/Research-Scientist_JR42",job["url"])

    def test_title_classifier_separates_research_and_nonresearch(self):
        self.assertEqual("other", classify_job("Internal Communications, Research and Product")["role_family"])
        self.assertEqual("other", classify_job("Principal UX Researcher")["role_family"])
        self.assertEqual("other", classify_job("Market Research Lead")["role_family"])
        self.assertEqual("ai_engineering", classify_job("Applied AI Engineer, Startups")["role_family"])
        result = classify_job("Research Scientist, Robotics")
        self.assertEqual("research", result["role_family"])
        self.assertEqual(["Robotics"], result["topics"])
        self.assertIn("Robotics", result["topic_evidence"])

    def test_old_snapshot_title_is_reclassified(self):
        old = dict(self.job,title="Internal Communications, Research and Product",relevant=True)
        apply_jobs(self.db,self.company,[old],"https://example.com", "2026-09-01T00:00:00+00:00")
        self.db.execute("UPDATE jobs SET relevant=1,role_family='research' WHERE id='1'")
        relabel_jobs(self.db)
        row = self.db.execute("SELECT relevant,role_family FROM jobs WHERE id='1'").fetchone()
        self.assertEqual((0,"other"),tuple(row))

    def test_one_missing_snapshot_does_not_claim_job_removed(self):
        apply_jobs(self.db,self.company,[self.job],"https://example.com", "2026-09-01T00:00:00+00:00")
        second = dict(self.job,id="2",title="Research Engineer, LLM")
        apply_jobs(self.db,self.company,[self.job,second],"https://example.com", "2026-09-02T00:00:00+00:00")
        apply_jobs(self.db,self.company,[self.job],"https://example.com", "2026-09-03T00:00:00+00:00")
        self.assertEqual(1,self.db.execute("SELECT active FROM jobs WHERE id='2'").fetchone()[0])
        self.assertEqual(0,self.db.execute("SELECT count(*) FROM events WHERE kind='removed'").fetchone()[0])
        apply_jobs(self.db,self.company,[self.job],"https://example.com", "2026-09-04T00:00:00+00:00")
        self.assertEqual(0,self.db.execute("SELECT active FROM jobs WHERE id='2'").fetchone()[0])
        self.assertEqual(1,self.db.execute("SELECT count(*) FROM events WHERE kind='removed'").fetchone()[0])

    def test_google_cards_have_stable_id_and_original_link(self):
        html = '''<span class="SWhIm">1</span> jobs matched
          <li class="lLd3Je" ssk='18:12345'><h3 class="QJPWVe">Research Scientist, Robotics</h3>
          <span class="RP7SMd"><i>corporate_fare</i><span>DeepMind</span></span>
          <span class="r0wTof">London</span><a href="jobs/results/12345-research-scientist-robotics?q=research"></a></li>'''
        count, cards = parse_results(html)
        self.assertEqual(1,count)
        self.assertEqual("12345",cards[0]["id"])
        self.assertEqual("DeepMind",cards[0]["organization"])
        self.assertEqual("https://www.google.com/about/careers/applications/jobs/results/12345-research-scientist-robotics",cards[0]["url"])

    def test_microsoft_pagination_and_named_msr_subset(self):
        def page(query,start):
            positions = [{"id":i,"name":("Researcher - Microsoft Research" if i == 1 else "Researcher"),
                          "positionUrl":f"/careers/job/{i}","standardizedLocations":["Redmond"],"postedTs":1780000000}
                         for i in range(start,min(start+10,12))]
            return {"count":12,"positions":positions}
        fetch_microsoft_careers.cache_clear()
        with patch("radar.microsoft_careers._page",side_effect=page):
            jobs,_ = fetch_microsoft_careers()
        self.assertEqual(12,len(jobs))
        self.assertEqual(1,sum(is_named_msr(job) for job in jobs))
        fetch_microsoft_careers.cache_clear()


if __name__ == "__main__":
    unittest.main()
