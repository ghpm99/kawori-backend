import inspect
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.utils import timezone

from classification import views
from classification.models import Answer, AnswerSummary, Question
from facetexture.models import BDOClass


class ClassificationViewsRegressionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="classification-reg",
            email="classification-reg@test.com",
            password="123",
        )
        cls.bdo_class = BDOClass.objects.create(
            name="Warrior", abbreviation="WR", color="#111111"
        )
        cls.question = Question.objects.create(
            question_text="Pergunta?",
            question_details="Detalhes",
            pub_date=timezone.now() - timedelta(days=1),
        )

    def setUp(self):
        self.rf = RequestFactory()

    def _call(self, fn, method="get", data=None, user=None):
        request_factory_method = getattr(self.rf, method.lower())
        if method.lower() == "get":
            request = request_factory_method("/", data=data or {})
        else:
            request = request_factory_method(
                "/", data=json.dumps(data or {}), content_type="application/json"
            )
        target = inspect.unwrap(fn)
        if "user" in target.__code__.co_varnames:
            return target(request, user=user or self.user)
        return target(request)

    def test_get_all_questions_and_answers(self):
        Answer.objects.create(
            question=self.question,
            bdo_class=self.bdo_class,
            combat_style=Answer.AWAKENING,
            user=self.user,
            vote=5,
        )

        questions_resp = self._call(views.get_all_questions, method="get")
        self.assertEqual(questions_resp.status_code, 200)
        questions_payload = json.loads(questions_resp.content)["data"]
        self.assertEqual(len(questions_payload), 1)
        self.assertEqual(questions_payload[0]["question_text"], "Pergunta?")

        answers_resp = self._call(views.get_all_answers, method="get")
        self.assertEqual(answers_resp.status_code, 200)
        answers_payload = json.loads(answers_resp.content)["data"]
        self.assertEqual(len(answers_payload), 1)
        self.assertEqual(answers_payload[0]["bdo_class"], "WR")
        self.assertEqual(answers_payload[0]["vote"], 5)

    def test_register_answer_validation_branches_and_success(self):
        resp_no_question = self._call(views.register_answer, method="post", data={})
        self.assertEqual(resp_no_question.status_code, 400)

        with patch("classification.views.Question.objects.get", return_value=None):
            resp_question_none = self._call(
                views.register_answer, method="post", data={"question_id": 1}
            )
        self.assertEqual(resp_question_none.status_code, 404)

        resp_no_combat = self._call(
            views.register_answer, method="post", data={"question_id": self.question.id}
        )
        self.assertEqual(resp_no_combat.status_code, 400)

        resp_invalid_combat = self._call(
            views.register_answer,
            method="post",
            data={"question_id": self.question.id, "combat_style": "x"},
        )
        self.assertEqual(resp_invalid_combat.status_code, 400)

        resp_no_class = self._call(
            views.register_answer,
            method="post",
            data={"question_id": self.question.id, "combat_style": 1},
        )
        self.assertEqual(resp_no_class.status_code, 400)

        with patch("classification.views.BDOClass.objects.get", return_value=None):
            resp_class_none = self._call(
                views.register_answer,
                method="post",
                data={
                    "question_id": self.question.id,
                    "combat_style": 1,
                    "bdo_class_id": 999,
                },
            )
        self.assertEqual(resp_class_none.status_code, 404)

        resp_no_vote = self._call(
            views.register_answer,
            method="post",
            data={
                "question_id": self.question.id,
                "combat_style": 1,
                "bdo_class_id": self.bdo_class.id,
            },
        )
        self.assertEqual(resp_no_vote.status_code, 400)

        resp_vote_invalid = self._call(
            views.register_answer,
            method="post",
            data={
                "question_id": self.question.id,
                "combat_style": 1,
                "bdo_class_id": self.bdo_class.id,
                "vote": "x",
            },
        )
        self.assertEqual(resp_vote_invalid.status_code, 400)

        success = self._call(
            views.register_answer,
            method="post",
            data={
                "question_id": self.question.id,
                "combat_style": 1,
                "bdo_class_id": self.bdo_class.id,
                "vote": 8,
            },
        )
        self.assertEqual(success.status_code, 200)
        self.assertEqual(Answer.objects.filter(user=self.user, vote=8).count(), 1)

    def test_get_bdo_class_total_votes_and_answer_by_class(self):
        other_class = BDOClass.objects.create(name="Witch", abbreviation="WT", color="")
        Answer.objects.create(
            question=self.question,
            bdo_class=self.bdo_class,
            combat_style=1,
            user=self.user,
            vote=10,
        )
        Answer.objects.create(
            question=self.question,
            bdo_class=other_class,
            combat_style=2,
            user=self.user,
            vote=4,
        )

        with patch(
            "classification.views.get_bdo_class_image_url",
            side_effect=lambda cid: f"img-{cid}",
        ), patch(
            "classification.views.get_bdo_class_symbol_url",
            side_effect=lambda cid: f"sym-{cid}",
        ):
            class_resp = self._call(views.get_bdo_class, method="get")

        self.assertEqual(class_resp.status_code, 200)
        class_payload = json.loads(class_resp.content)["class"]
        self.assertEqual(len(class_payload), 2)
        self.assertIn("class_image", class_payload[0])
        self.assertIn("class_symbol", class_payload[0])

        votes_resp = self._call(views.total_votes, method="get")
        self.assertEqual(votes_resp.status_code, 200)
        self.assertEqual(json.loads(votes_resp.content)["total_votes"], 2)

        by_class_resp = self._call(views.answer_by_class, method="get")
        self.assertEqual(by_class_resp.status_code, 200)
        by_class_payload = json.loads(by_class_resp.content)["data"]
        self.assertEqual(len(by_class_payload), 2)
        self.assertEqual(sum(item["answers_count"] for item in by_class_payload), 2)

    def test_process_helpers_and_get_answer_summary(self):
        resume = {
            "awakening": {
                "q1": {
                    "question_text": "Q1",
                    "question_details": "D1",
                    "avg_votes": 7.5,
                    "answer": "A1",
                }
            }
        }
        summary = AnswerSummary.objects.create(bdo_class=self.bdo_class, resume=resume)

        style_result = views.process_style_resume(resume["awakening"])
        self.assertEqual(style_result[0]["text"], "Q1")

        resume_result = views.process_resume({"awakening": resume["awakening"]})
        self.assertEqual(resume_result["awakening"][0]["answer"], "A1")

        response = self._call(views.get_answer_summary, method="get")
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], summary.id)
