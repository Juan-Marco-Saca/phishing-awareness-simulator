import json
import unittest
from datetime import datetime, timezone


class LearningAnalyticsTests(unittest.TestCase):
    def test_response_times_dropoff_quiz_improvement_and_session_dedup(self):
        from learning_analytics import summarize_learning
        def event(kind, hour, metadata=None):
            return dict(id=hour, event_type=kind, timestamp=f'2026-09-16T{hour:02}:00:00+00:00', metadata=json.dumps(metadata or {}))
        events = [event('email_accepted', 1), event('clicked_link', 2), event('phishing_reported', 3),
                  event('password_change_submitted', 4), event('viewed_training', 5),
                  event('quiz_submitted', 6, {'score': 2, 'missed_questions': ['q1', 'q3', 'q5']}),
                  event('quiz_submitted', 7, {'score': 4}),
                  event('training_activity', 8, {'session_id': 'a', 'active_seconds': 20}),
                  event('training_activity', 9, {'session_id': 'a', 'active_seconds': 30}),
                  event('training_activity', 10, {'session_id': 'b', 'active_seconds': 10}),
                  event('training_section_viewed', 11, {'section': 'warning_signs'})]
        metrics = summarize_learning(events, datetime(2026, 9, 18, tzinfo=timezone.utc))
        self.assertEqual(metrics['click_seconds'], 3600)
        self.assertEqual(metrics['report_seconds'], 7200)
        self.assertEqual(metrics['report_order'], 'Before submission')
        self.assertEqual(metrics['training_status'], 'Incomplete after 24 hours')
        self.assertEqual(metrics['quiz_change'], 2)
        self.assertEqual(metrics['active_seconds'], 40)
        self.assertEqual(metrics['sections'], ['warning_signs'])

    def test_missing_data_stays_missing_and_completion_overrides_dropoff(self):
        from learning_analytics import summarize_learning
        metrics = summarize_learning([])
        self.assertIsNone(metrics['click_seconds'])
        self.assertIsNone(metrics['active_seconds'])
        self.assertEqual(metrics['training_status'], 'Not opened')
        self.assertIsNone(metrics['quiz_change'])
        events = [dict(id=1, event_type='viewed_training', timestamp='2026-09-01T10:00:00+00:00', metadata='{}'),
                  dict(id=2, event_type='training_completed', timestamp='2026-09-01T10:05:00+00:00', metadata='{}')]
        self.assertEqual(summarize_learning(events)['training_status'], 'Completed')
