import json
import unittest


class CampaignChartTests(unittest.TestCase):
    def test_unique_counts_latest_score_and_missing_devices(self):
        import campaign_charts
        def event(kind, recipient, timestamp, **extra):
            return dict(event_type=kind, recipient_id=recipient, timestamp=timestamp,
                        id=extra.pop('id', 1), metadata=json.dumps(extra.pop('metadata', {})),
                        device=extra.pop('device', None), source='web', **extra)
        events = [event('clicked_link', 1, '2026-09-16T10:00:00+00:00', device='Mobile'),
                  event('clicked_link', 1, '2026-09-16T11:00:00+00:00', device='Desktop'),
                  event('clicked_link', 2, '2026-09-16T11:00:00+00:00'),
                  event('quiz_submitted', 1, '2026-09-16T12:00:00+00:00', metadata={'score': 2}),
                  event('quiz_submitted', 1, '2026-09-16T13:00:00+00:00', metadata={'score': 5}),
                  event('scenario_action_submitted', 2, '2026-09-16T13:00:00+00:00', metadata={'elapsed_ms': 2000})]
        charts = {c['key']: c for c in campaign_charts.build_charts(events, 3)}
        values = lambda key: {r['label']: r['value'] for r in charts[key]['rows']}
        self.assertEqual(values('participation')['Link visited'], 2)
        self.assertEqual(values('scores')['5 / 5'], 1)
        self.assertEqual(values('scores')['2 / 5'], 0)
        self.assertEqual(values('devices'), {'Desktop': 1, 'Not recorded': 1})
        self.assertEqual(values('timing')['Under 10 seconds'], 1)
        self.assertEqual(values('activity')['2026-09-16'], 6)

    def test_empty_campaign_has_no_invented_observations(self):
        import campaign_charts
        charts = campaign_charts.build_charts([], 0)
        self.assertTrue(all(not chart['has_data'] for chart in charts))
        self.assertTrue(all(row['width'] == 0 for chart in charts for row in chart['rows']))
