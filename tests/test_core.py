import sqlite3
import tempfile
import unittest
from pathlib import Path
from radar.core import apply_jobs, connect, mark_error, save_state, restore_state, normalize_job


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = connect(Path(self.temp.name) / "radar.sqlite3")
        self.company = {"id":"example"}
        self.job = {"id":"1","title":"Research Scientist, Robotics","location":"SF","url":"https://example.com/1","published_at":None,"topics":["Robotics"],"relevant":True}

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


if __name__ == "__main__":
    unittest.main()
