"""Real immutable-Pool SQLite/Runtime check of spaced review."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from api import seed_u1
from api.feedback_runtime import LearnerFeedbackRuntime
from api.sqlite_d1 import SqliteD1Database
from apps.runtime_vnext.worker.runtime_http import compose_vnext_runtime_service
from learning_kernel.knowledge_packs.math_u1_vnext.pack import U1_PACK
from learning_kernel.knowledge_packs.math_u1_vnext.scope import PACK_ID, PACK_VERSION

ORIGIN="http://localhost:18085"
FAMILY="u1-1/family/direct-prime-composite-classification"
PLACE="u1-1/prime-number"


class FutureDateTime(datetime):
    @classmethod
    def now(cls,tz=None):
        return datetime.now(tz)+timedelta(days=8)


def capture(surface,value):
    ix=surface["execution"]["stepIndex"]
    step=surface["surface"]["payload"]["steps"][ix]
    point=next(p for p in surface["lineage"]["reportableObservationPoints"] if p["stepIndex"]==ix)
    block=next(b for b in step["blocks"] if b["capability"].startswith("response."))
    return {
        "schemaVersion":surface["surface"]["observationCaptureVersion"],
        "decisionId":surface["lineage"]["decisionId"],
        "activityId":surface["surface"]["payload"]["activityId"],
        "stepIndex":ix,"stepId":step["stepId"],
        "observationPointId":point["observationPointRef"]["localId"],
        "response":{"capability":block["capability"],"value":value},
        "attempt":{"attemptId":f"attempt/{uuid.uuid4()}","attemptOrdinal":1,"attemptCount":1,"activeWorkDurationMs":800},
        "support":{"hintIdsUsed":[],"revealIdsUsed":[],"retryCount":0,"assistanceLevel":"independent"},
        "capturedAt":datetime.now(UTC).isoformat().replace("+00:00","Z"),
        "practiceMode":surface["execution"]["practiceMode"],
    }


class ReviewE2E(unittest.IsolatedAsyncioTestCase):
    async def test_exhaust_new_pool_review_after_cooldown_store_fresh_evidence(self):
        root=Path(__file__).resolve().parents[1]/"vendor"/"learning-kernel-sdk"
        migrations=root/"apps"/"runtime_vnext"/"migrations"
        artifacts=root/"artifacts"/"knowledge-packs"/PACK_ID/PACK_VERSION
        learner="owner-review-learner-a"
        other="owner-review-learner-b"
        environment="isolated-review"
        with tempfile.TemporaryDirectory(prefix="lk-owner-review-") as td:
            db_path=Path(td)/"runtime.sqlite3"
            with patch.object(seed_u1,"ARTIFACT_DIR",artifacts),patch.dict(os.environ,{"LK_RUNTIME_MIGRATIONS_DIR":str(migrations)}):
                await seed_u1.seed(db_path,learner,environment)
            db=SqliteD1Database.open(db_path)
            try:
                conn=db.connection
                count=conn.execute("SELECT COUNT(*) FROM vnext_activity_pool_entries WHERE task_family_id=?",(FAMILY,)).fetchone()[0]
                self.assertEqual(count,10,"Expected exactly 10 original immutable Pool entries")
                runtime=LearnerFeedbackRuntime(compose_vnext_runtime_service(db,surface_cors_origin=ORIGIN),db)
                context={"currentContext":{"currentPlaceLocalId":PLACE,"todayPractice":False,"learnerExplorationTaskFamilyIds":[FAMILY]}}
                def path_for(learner_id):
                    return f"/api/learners/{quote(learner_id,safe='')}/environments/{quote(environment,safe='')}/packs/{quote(PACK_ID,safe='')}"
                async def surface(learner_id=learner):
                    return await runtime.handle_request(method="POST",path=path_for(learner_id)+"/surface",body=json.dumps(context),origin=ORIGIN)
                async def submit(payload,answer):
                    return await runtime.handle_request(method="POST",path=path_for(learner)+"/observations",body=json.dumps(capture(payload,answer),ensure_ascii=False),origin=ORIGIN)
                pool=seed_u1._pool_payloads(U1_PACK.lifecycle.content_digest)
                expected={
                    e["generatedActivityArtifact"]["local_id"]:
                    e["generatedActivityArtifact"]["validation_payload"]["correct_classification"]
                    for e in pool if e["generatedActivityArtifact"]["task_family"]["local_id"]==FAMILY
                }
                self.assertEqual(len(expected),10)
                seen=[]
                for index in range(10):
                    issued=await surface()
                    self.assertEqual(issued.status,200,f"fresh {index}: {issued.body}")
                    payload=json.loads(issued.body)
                    activity=payload["surface"]["payload"]["activityId"]
                    self.assertIn(activity,expected)
                    self.assertNotIn(activity,seen)
                    seen.append(activity)
                    if index==9:
                        unanswered=await surface()
                        self.assertEqual(unanswered.status,503,unanswered.body)
                    result=await submit(payload,expected[activity])
                    self.assertEqual(result.status,202,result.body)
                    self.assertEqual(json.loads(result.body)["feedback"]["verdict"],"correct")
                no_due=await surface()
                self.assertEqual(no_due.status,503,no_due.body)
                with patch("apps.runtime_vnext.worker.runtime_http.datetime",FutureDateTime):
                    first_review=await surface()
                    next_review=await surface()
                self.assertEqual(first_review.status,200,first_review.body)
                self.assertEqual(next_review.status,200,next_review.body)
                first_json=json.loads(first_review.body)
                next_json=json.loads(next_review.body)
                first_id=first_json["surface"]["payload"]["activityId"]
                second_id=next_json["surface"]["payload"]["activityId"]
                self.assertIn(first_id,seen)
                self.assertIn(second_id,seen)
                self.assertNotEqual(first_id,second_id,"Never immediately repeat the same issued review question")
                self.assertNotEqual(first_json["lineage"]["decisionId"],next_json["lineage"]["decisionId"])
                response=await submit(first_json,expected[first_id])
                self.assertEqual(response.status,202,response.body)
                self.assertEqual(json.loads(response.body)["feedback"]["verdict"],"correct")
                immediate=await surface()
                self.assertEqual(immediate.status,503,immediate.body)
                issued_count=conn.execute("SELECT COUNT(*) FROM vnext_issued_activity_bindings WHERE learner_id=?",(learner,)).fetchone()[0]
                observations=conn.execute("SELECT COUNT(*) FROM vnext_learner_records WHERE learner_id=? AND record_kind='observation'",(learner,)).fetchone()[0]
                evidence=conn.execute("SELECT COUNT(*) FROM vnext_learner_evidence WHERE learner_id=?",(learner,)).fetchone()[0]
                self.assertEqual((issued_count,observations,evidence),(12,11,11))
                other_release=f"/api/packs/{quote(PACK_ID,safe='')}/releases/{quote(PACK_VERSION,safe='')}"
                active=await runtime.handle_request(method="POST",path=other_release+"/activate",body=json.dumps({"learnerId":other,"environmentId":environment,"regionIds":[r.local_id for r in U1_PACK.learning_map.regions]}))
                self.assertEqual(active.status,200,active.body)
                other_first=await surface(other)
                self.assertEqual(other_first.status,200,other_first.body)
                self.assertEqual(json.loads(other_first.body)["surface"]["payload"]["activityId"],seen[0])
                self.assertEqual(conn.execute("PRAGMA quick_check").fetchone()[0],"ok")
                print("REAL_REVIEW_E2E_PASS",json.dumps({"first_review":first_id,"second_review":second_id,"issued":issued_count,"observations":observations,"evidence":evidence,"other_learner_fresh":True},ensure_ascii=False))
            finally:
                db.connection.close()


if __name__=="__main__":
    unittest.main()

