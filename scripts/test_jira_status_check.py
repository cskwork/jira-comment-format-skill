"""jira_status_check.next_step 회귀 시험 (오프라인). 실행: python3 -m unittest test_jira_status_check"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jira_status_check  # noqa: E402
from jira_status_check import next_step  # noqa: E402

# config.env의 JIRA_STATUS_ORDER와 관계없이 기본 워크플로로 시험한다.
DEFAULT_ORDER = ["백로그", "할 일", "진행 중", "개발 QA 요청", "개발 검수 완료", "스테이징 QA 요청"]


class NextStep(unittest.TestCase):
    def setUp(self):
        self._order, jira_status_check.ORDER = jira_status_check.ORDER, DEFAULT_ORDER

    def tearDown(self):
        jira_status_check.ORDER = self._order

    def test_never_jumps_to_prod_states(self):
        # 실제 전환 목록 형태: 목록 마지막(운영 검수 완료)을 고르면 안 된다
        self.assertEqual(next_step("할 일", "스테이징 QA 요청", ["백로그", "진행 중"]), "진행 중")
        self.assertEqual(next_step("진행 중", "스테이징 QA 요청", ["개발 QA 요청", "할 일", "운영 검수 완료"]), "개발 QA 요청")
        self.assertEqual(next_step("개발 QA 요청", "스테이징 QA 요청", ["개발 검수 완료", "진행 중"]), "개발 검수 완료")

    def test_takes_furthest_allowed_up_to_target(self):
        self.assertEqual(next_step("진행 중", "스테이징 QA 요청", ["개발 QA 요청", "개발 검수 완료"]), "개발 검수 완료")
        self.assertEqual(next_step("진행 중", "개발 QA 요청", ["개발 QA 요청", "개발 검수 완료"]), "개발 QA 요청")

    def test_backlog_goes_to_todo_first(self):
        self.assertEqual(next_step("백로그", "개발 QA 요청", ["할 일"]), "할 일")

    def test_target_outside_order_stops(self):
        self.assertIsNone(next_step("진행 중", "없는 상태", ["개발 QA 요청"]))

    def test_stop_when_no_in_order_move(self):
        self.assertIsNone(next_step("진행 중", "스테이징 QA 요청", ["할 일", "운영 검수 완료", "핫픽스 대기"]))


if __name__ == "__main__":
    unittest.main()
