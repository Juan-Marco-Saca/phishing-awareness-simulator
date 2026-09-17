"""Campaign-scoped, privacy-preserving aggregates for server-rendered charts."""
import json
from collections import Counter
from datetime import datetime, timezone


def build_charts(events, participant_count):
    charts = []

    def chart(key, title, note, counts, scale=None):
        maximum = max(counts.values(), default=0) if scale is None else scale
        charts.append(dict(key=key, title=title, note=note, has_data=any(counts.values()),
            scale=maximum, rows=[dict(label=label, value=value,
                width=round(100 * value / maximum, 2) if maximum else 0)
                for label, value in counts.items()]))

    def unique(*kinds):
        return len({e['recipient_id'] for e in events if e['event_type'] in kinds and e['recipient_id'] is not None})

    chart('participation', 'Participant actions',
          f'Unique recipients per action, out of {participant_count} participants. Actions overlap and are not a required sequence. Opens are estimates; clicks may include scanners.',
          {'Email accepted': unique('email_accepted'), 'Estimated open': unique('email_opened'),
           'Link visited': unique('clicked_link'), 'Action submitted': unique('password_change_submitted', 'scenario_action_submitted'),
           'Training opened': unique('viewed_training'), 'Training completed': unique('training_completed'),
           'Phishing reported': unique('phishing_reported')}, participant_count)

    def timestamp(event):
        parsed = datetime.fromisoformat(event['timestamp'])
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)

    # Stable chronological order also resolves quiz attempts sharing a timestamp.
    ordered = sorted(events, key=lambda e: (timestamp(e), e['id']))
    daily = Counter()
    devices, scores, timings = {}, {}, {}
    for event in ordered:
        kind, recipient = event['event_type'], event['recipient_id']
        if event['source'] == 'web' and kind != 'email_opened':
            daily[timestamp(event).date().isoformat()] += 1
            if recipient is not None:
                devices[recipient] = event.get('device') or devices.get(recipient, 'Not recorded')
        try:
            metadata = json.loads(event.get('metadata') or '{}')
        except (TypeError, ValueError):
            metadata = {}
        if not isinstance(metadata, dict) or recipient is None:
            continue
        score = metadata.get('score')
        if kind == 'quiz_submitted' and type(score) is int and 0 <= score <= 5:
            scores[recipient] = score
        elapsed = metadata.get('elapsed_ms')
        if kind in ('password_change_submitted', 'scenario_action_submitted') and type(elapsed) is int and 0 <= elapsed <= 86400000:
            timings.setdefault(recipient, elapsed / 1000)

    chart('activity', 'Browser activity by day',
          'Recorded browser events per UTC day with activity. Includes repeat events and page views; excludes email pixels, sends and manual reports. Dates with no activity are omitted.',
          dict(sorted(daily.items())))
    chart('scores', 'Latest quiz score',
          f'One latest valid score per participant who submitted a quiz ({len(scores)} participants). Participants without a quiz are excluded.',
          {f'{score} / 5': sum(value == score for value in scores.values()) for score in range(6)})
    chart('devices', 'Devices used',
          'One latest available device category per participant with browser activity. Missing details are shown explicitly. Categories are User-Agent estimates, not verified hardware.',
          dict(sorted(Counter(devices.values()).items())))
    buckets = {'Under 10 seconds': 0, '10–29 seconds': 0, '30–59 seconds': 0, '1–4 minutes': 0, '5 minutes or more': 0}
    for seconds in timings.values():
        index = 0 if seconds < 10 else 1 if seconds < 30 else 2 if seconds < 60 else 3 if seconds < 300 else 4
        buckets[list(buckets)[index]] += 1
    chart('timing', 'Time to first submission',
          'One first recorded submission per participant, measured from that page load. Client-reported timing; missing timings are excluded. This is not time since the email was sent.', buckets)
    return charts
