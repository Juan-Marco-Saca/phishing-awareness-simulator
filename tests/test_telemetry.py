import importlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import database
import email_sender


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_patch = patch.object(database, 'DB_NAME', str(Path(self.tmp.name) / 'test.db'))
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.module = importlib.import_module('app')
        database.init_db()
        self.module.app.config.update(TESTING=True, COLLECT_REQUEST_DETAILS=True, ADMIN_PASSWORD='test-password')
        self.client = self.module.app.test_client()
        self.client.environ_base['HTTP_AUTHORIZATION'] = 'Basic YWRtaW46dGVzdC1wYXNzd29yZA=='

    def rows(self, table):
        with closing(sqlite3.connect(database.DB_NAME)) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute('SELECT * FROM ' + table)]

    def campaign(self):
        with patch.object(self.module, 'send_simulation_email'):
            response = self.client.post('/campaign', data={
                'name': 'Class test', 'template': 'password',
                'targets': 'one@example.com\ntwo@example.com\none@example.com'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(any(e['event_type'] == 'email_accepted' for e in self.rows('events')))
        return self.rows('recipients')[0]['token']

    def test_send_outcomes_and_recipient_deduplication(self):
        with self.assertLogs(self.module.app.logger, level='WARNING'), patch.object(self.module, 'send_simulation_email', side_effect=[OSError('private detail'), None]):
            self.client.post('/campaign', data={'template': 'password', 'targets': 'a@example.com\nb@example.com\na@example.com'})
        events = self.rows('events')
        self.assertEqual([e['event_type'] for e in events],
                         ['email_send_attempted', 'email_failed', 'email_send_attempted', 'email_accepted'])
        self.assertEqual(len(self.rows('recipients')), 2)
        self.assertNotIn('private detail', json.dumps(events))

    def test_email_contains_token_link_and_tracking_pixel(self):
        with patch.object(email_sender, 'SENDER_EMAIL', 'sender@example.com'), patch.object(email_sender, 'APP_PASSWORD', 'test-only'), patch.object(email_sender.smtplib, 'SMTP') as smtp:
            smtp.return_value.__enter__.return_value.send_message.return_value = {}
            email_sender.send_simulation_email('recipient@example.com', 'password', 'test-token')
            message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
            html = message.get_payload()[0].get_payload(decode=True).decode()
            self.assertIn('/login?token=test-token', html)
            self.assertIn('/track?token=test-token', html)
            self.assertNotIn('recipient@example.com', html)

    def test_invalid_token_and_campaign_do_not_log(self):
        self.assertEqual(self.client.get('/login?token=invalid').status_code, 400)
        self.assertEqual(self.client.post('/campaign', data={'template': 'password', 'targets': 'invalid'}).status_code, 400)
        self.assertEqual(self.rows('events'), [])

    def test_admin_routes_require_authentication(self):
        public = self.module.app.test_client()
        self.assertEqual(public.get('/').status_code, 401)
        self.assertEqual(public.get('/campaign').status_code, 401)
        self.assertEqual(public.post('/report', data={'recipient_id': 1, 'channel': 'email'}).status_code, 401)
        self.assertEqual(public.get('/training').status_code, 200)
        self.module.app.config['ADMIN_PASSWORD'] = ''
        with self.assertLogs(self.module.app.logger, level='ERROR'):
            self.assertEqual(public.get('/').status_code, 503)

    def test_cross_site_admin_posts_are_rejected(self):
        response = self.client.post('/report', headers={'Origin': 'https://unrelated.example'}, data={'recipient_id': 1, 'channel': 'email'})
        self.assertEqual(response.status_code, 403)

    def test_admin_forms_preserve_same_origin_metadata(self):
        for path in ('/', '/campaign'):
            self.assertEqual(self.client.get(path).headers['Referrer-Policy'], 'same-origin')
        self.assertEqual(self.client.get('/training').headers['Referrer-Policy'], 'no-referrer')
        with patch.object(self.module, 'send_simulation_email'):
            response = self.client.post('/campaign', base_url='http://127.0.0.1:5000',
                headers={'Origin': 'http://127.0.0.1:5000', 'Sec-Fetch-Site': 'same-origin'},
                data={'template': 'password', 'targets': 'test@example.com'})
        self.assertEqual(response.status_code, 302)

    def test_null_origin_is_still_rejected(self):
        response = self.client.post('/report', headers={'Origin': 'null'},
                                    data={'recipient_id': 1, 'channel': 'email'})
        self.assertEqual(response.status_code, 403)

    def test_suspected_automation_is_flagged_not_silently_discarded(self):
        token = self.campaign()
        self.client.get('/login?token=' + token, headers={'User-Agent': 'Example link scanner'})
        event = self.rows('events')[-1]
        self.assertEqual(event['suspected_automated'], 1)
        self.assertEqual(database.get_campaign_summaries()[0]['suspected_clicks'], 1)

    def test_event_write_failure_returns_retryable_error(self):
        token = self.campaign()
        with self.assertLogs(self.module.app.logger, level='ERROR'), patch.object(self.module, 'log_event', side_effect=sqlite3.OperationalError('private database detail')):
            response = self.client.get('/login?token=' + token)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'private database detail', response.data)

    def test_tracking_tokens_metadata_and_unique_metrics(self):
        token = self.campaign()
        for _ in range(2):
            self.assertEqual(self.client.get('/login?token=' + token, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0) Chrome/120.0'}).status_code, 200)
        events = [e for e in self.rows('events') if e['event_type'] == 'clicked_link']
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['ip_address'], '127.0.0.1')
        self.assertEqual(events[0]['os'], 'Windows')
        self.assertEqual(database.get_campaign_summaries()[0]['unique_clicks'], 1)
        self.assertEqual(self.client.get('/login?email=spoof@example.com').status_code, 400)

    def test_tracking_pixel_and_untracked_preview(self):
        token = self.campaign()
        response = self.client.get('/track?token=' + token)
        self.assertEqual(response.mimetype, 'image/gif')
        self.assertIn('no-store', response.headers['Cache-Control'])
        count = len(self.rows('events'))
        self.assertEqual(self.client.get('/training').status_code, 200)
        self.assertEqual(len(self.rows('events')), count)

    def test_quiz_is_server_graded_and_completion_is_once(self):
        token = self.campaign()
        self.assertEqual(self.client.post('/quiz?token=' + token, json={'q1': 'a'}).status_code, 400)
        answers = {'q1': 'a', 'q2': 'b', 'q3': 'c', 'q4': 'b', 'q5': 'a', 'password': 'never-store'}
        wrong = dict(answers, q1='b', score=5)
        self.assertEqual(self.client.post('/quiz?token=' + token, json=wrong).json['score'], 4)
        for _ in range(2):
            self.assertEqual(self.client.post('/quiz?token=' + token, json=answers).json['score'], 5)
        events = self.rows('events')
        self.assertEqual(sum(e['event_type'] == 'training_completed' for e in events), 1)
        attempts = [json.loads(e['metadata'])['attempt'] for e in events if e['event_type'] == 'quiz_submitted']
        self.assertEqual(attempts, [1, 2, 3])
        self.assertNotIn('never-store', json.dumps(events))

    def test_report_is_manual_and_before_click(self):
        token = self.campaign()
        recipient = self.rows('recipients')[0]
        response = self.client.post('/report', data={'recipient_id': recipient['id'], 'channel': 'in_person'})
        self.assertEqual(response.status_code, 302)
        self.client.get('/login?token=' + token)
        summary = database.get_campaign_summaries()[0]
        self.assertEqual(summary['unique_reports'], 1)
        self.assertEqual(summary['reported_before_click'], 1)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_details_can_be_disabled(self):
        token = self.campaign()
        self.module.app.config['COLLECT_REQUEST_DETAILS'] = False
        self.client.get('/login?token=' + token)
        event = self.rows('events')[-1]
        self.assertIsNone(event['ip_address'])
        self.assertIsNone(event['user_agent'])

    def test_password_simulation_records_only_allowed_metadata(self):
        token = self.campaign()
        response = self.client.post('/interaction?token=' + token, json={
            'event': 'password_change_submitted', 'elapsed_ms': 2400,
            'current_filled': True, 'new_filled': True, 'confirmation_filled': True})
        self.assertEqual(response.status_code, 200)
        event = self.rows('events')[-1]
        self.assertEqual(event['event_type'], 'password_change_submitted')
        self.assertEqual(event['ip_address'], '127.0.0.1')
        self.assertEqual(json.loads(event['metadata'])['elapsed_ms'], 2400)
        self.assertEqual(database.get_campaign_summaries()[0]['password_submitted'], 1)

    def test_password_simulation_rejects_credentials_and_invalid_events(self):
        token = self.campaign()
        count = len(self.rows('events'))
        for body in ({'event': 'password_change_submitted', 'password': 'secret-value'},
                     {'event': 'training_completed'},
                     {'event': 'password_form_started', 'elapsed_ms': -1}):
            self.assertEqual(self.client.post('/interaction?token=' + token, json=body).status_code, 400)
        self.assertEqual(len(self.rows('events')), count)
        self.assertEqual(self.client.post('/interaction?token=invalid', json={'event': 'password_form_started'}).status_code, 400)

    def test_password_form_view_and_interaction_are_attributed(self):
        token = self.campaign()
        response = self.client.get('/login?token=' + token)
        self.assertIn(b'Change your password', response.data)
        self.assertEqual(self.rows('events')[-1]['event_type'], 'password_form_viewed')
        self.assertEqual(self.client.post('/interaction?token=' + token,
            json={'event': 'password_form_started', 'elapsed_ms': 100}).status_code, 200)
        self.assertEqual(database.get_campaign_summaries()[0]['password_started'], 1)

    def test_tracking_test_opens_real_flow_without_sending_email(self):
        with patch.object(self.module, 'send_simulation_email') as sender:
            response = self.client.post('/tracking-test')
        self.assertEqual(response.status_code, 302)
        sender.assert_not_called()
        self.assertIn('/login?token=', response.location)
        self.client.get(response.location)
        events = self.rows('events')
        self.assertTrue(any(e['event_type'] == 'password_form_viewed' and e['ip_address'] for e in events))
        self.assertEqual(self.rows('campaigns')[0]['name'], 'Tracking test (no email sent)')

    def test_tracking_test_is_admin_only(self):
        self.assertEqual(self.module.app.test_client().post('/tracking-test').status_code, 401)

    def test_campaign_detail_groups_users_and_excludes_other_campaigns(self):
        token = self.campaign()
        self.client.get('/login?token=' + token)
        self.client.post('/interaction?token=' + token, json={'event': 'password_change_submitted', 'elapsed_ms': 1200, 'current_filled': True})
        database.create_campaign('Unrelated campaign', 'password', '1', ['outsider@example.com'])
        response = self.client.get('/campaign/1')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for expected in ('one@example.com', 'two@example.com', '127.0.0.1', 'Password change submitted', '1.2 seconds', 'No browser activity yet'):
            self.assertIn(expected, html)
        self.assertNotIn('outsider@example.com', html)
        self.assertNotIn('Unrelated campaign', html)
        self.assertIn('href="/campaign/1"', self.client.get('/').get_data(as_text=True))

    def test_campaign_detail_requires_admin_and_handles_missing_campaign(self):
        self.assertEqual(self.module.app.test_client().get('/campaign/1').status_code, 401)
        self.assertEqual(self.client.get('/campaign/9999').status_code, 404)

    def test_delete_campaign_removes_only_selected_campaign_data(self):
        token = self.campaign()
        self.client.get('/login?token=' + token)
        other = database.create_campaign('Keep this campaign', 'password', '1', ['keep@example.com'])[0]
        database.log_event(other, 'email_accepted', source='smtp')
        response = self.client.post('/campaign/1/delete', data={'confirm': 'delete'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual([c['name'] for c in self.rows('campaigns')], ['Keep this campaign'])
        self.assertEqual([r['email'] for r in self.rows('recipients')], ['keep@example.com'])
        self.assertEqual([e['email'] for e in self.rows('events')], ['keep@example.com'])
        self.assertEqual(self.client.get('/login?token=' + token).status_code, 400)
        self.assertEqual(self.client.get('/campaign/1').status_code, 404)

    def test_delete_campaign_requires_admin_confirmation_and_same_origin(self):
        self.campaign()
        public = self.module.app.test_client()
        self.assertEqual(public.post('/campaign/1/delete', data={'confirm': 'delete'}).status_code, 401)
        self.assertEqual(self.client.get('/campaign/1/delete').status_code, 405)
        self.assertEqual(self.client.post('/campaign/1/delete').status_code, 400)
        self.assertEqual(self.client.post('/campaign/1/delete', data={'confirm': 'delete'},
            headers={'Origin': 'https://unrelated.example'}).status_code, 403)
        self.assertEqual(len(self.rows('campaigns')), 1)
        self.assertEqual(self.client.post('/campaign/999/delete', data={'confirm': 'delete'}).status_code, 404)

    def test_dashboard_explains_no_visits_and_displays_readable_telemetry(self):
        token = self.campaign()
        page = self.client.get('/').get_data(as_text=True)
        self.assertIn('No participant visits recorded yet', page)
        self.assertIn('IP and device collection is on', page)
        self.client.get('/login?token=' + token)
        self.client.post('/interaction?token=' + token, json={
            'event': 'password_change_submitted', 'elapsed_ms': 2400,
            'current_filled': True, 'new_filled': True, 'confirmation_filled': False})
        page = self.client.get('/').get_data(as_text=True)
        self.assertIn('Password change submitted', page)
        self.assertIn('2.4 seconds', page)
        self.assertIn('127.0.0.1', page)
        self.assertIn('Current password: filled', page)
        self.module.app.config['COLLECT_REQUEST_DETAILS'] = False
        self.assertIn('IP and device collection is off', self.client.get('/').get_data(as_text=True))

    def test_legacy_events_survive_idempotent_migration(self):
        with closing(sqlite3.connect(database.DB_NAME)) as conn:
            conn.execute('DROP TABLE events')
            conn.execute('CREATE TABLE events (id INTEGER PRIMARY KEY, email TEXT NOT NULL, event_type TEXT NOT NULL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
            conn.execute("INSERT INTO events (email, event_type) VALUES ('legacy@example.com', 'clicked_link')")
            conn.commit()
        database.init_db()
        database.init_db()
        event = self.rows('events')[0]
        self.assertEqual(event['email'], 'legacy@example.com')
        self.assertIn('campaign_id', event)


if __name__ == '__main__':
    unittest.main()
