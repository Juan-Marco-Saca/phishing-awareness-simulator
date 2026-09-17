"""Learning metrics derived from existing events and optional browser signals."""
import json
from datetime import datetime, timezone

SECTIONS = {'phishing': 'What is phishing?', 'warning_signs': 'Warning signs',
            'response': 'How to respond', 'quiz': 'Knowledge quiz'}


def event_time(event):
    value = datetime.fromisoformat(event['timestamp'])
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def metadata(event):
    try:
        result = json.loads(event.get('metadata') or '{}')
        return result if isinstance(result, dict) else {}
    except (TypeError, ValueError):
        return {}


def summarize_learning(events, current_time=None):
    current_time = current_time or datetime.now(timezone.utc)
    ordered = sorted(events, key=lambda e: (event_time(e), e['id']))
    def first(*kinds):
        return next((event_time(e) for e in ordered if e['event_type'] in kinds), None)
    accepted, clicked, reported = first('email_accepted'), first('clicked_link'), first('phishing_reported')
    submitted = first('password_change_submitted', 'scenario_action_submitted')
    started, completed = first('viewed_training'), first('training_completed')
    def elapsed(start, end):
        return round((end-start).total_seconds(), 1) if start and end and end >= start else None
    sessions, sections, quizzes = {}, set(), []
    for event in ordered:
        data = metadata(event)
        if event['event_type'] == 'training_activity' and type(data.get('active_seconds')) is int:
            key = data.get('session_id')
            if key:
                sessions[key] = max(sessions.get(key, 0), data['active_seconds'])
        if event['event_type'] == 'training_section_viewed' and data.get('section') in SECTIONS:
            sections.add(data['section'])
        if event['event_type'] == 'quiz_submitted' and type(data.get('score')) is int:
            quizzes.append(data)
    status = 'Completed' if completed else 'Not opened' if not started else (
        'Incomplete after 24 hours' if (current_time-started).total_seconds() >= 86400 else 'In progress (under 24 hours)')
    return dict(click_seconds=elapsed(accepted, clicked), report_seconds=elapsed(accepted, reported),
        report_order='Not reported' if not reported else 'No submission recorded' if not submitted else
            'Before submission' if reported < submitted else 'After submission' if reported > submitted else 'Same recorded time',
        training_status=status, first_score=quizzes[0]['score'] if quizzes else None,
        latest_score=quizzes[-1]['score'] if quizzes else None,
        quiz_change=quizzes[-1]['score']-quizzes[0]['score'] if len(quizzes) > 1 else None,
        first_missed=quizzes[0].get('missed_questions', []) if quizzes else [],
        active_seconds=sum(sessions.values()) if sessions else None, sections=sorted(sections),
        section_names=[SECTIONS[key] for key in sorted(sections)],
        tracking_failures=sum(metadata(e).get('count', 1) for e in ordered if e['event_type'] == 'client_request_failed'),
        training_link=first('training_link_clicked') is not None,
        clicked=clicked is not None, reported=reported is not None, completed=completed is not None)


def learning_charts(participants):
    metrics = [p['learning'] for p in participants]
    definitions = [
        ('dropoff', 'Training follow-through', 'Unique participants. Incomplete means training was opened at least 24 hours ago without completion.',
         {status: sum(m['training_status'] == status for m in metrics) for status in
          ('Not opened', 'In progress (under 24 hours)', 'Incomplete after 24 hours', 'Completed')}),
        ('missed', 'Questions missed on first attempt', 'Each participant contributes only their first quiz attempt. Counts reflect mistakes, not unanswered training sessions.',
         {f'Question {i}': sum(f'q{i}' in m['first_missed'] for m in metrics) for i in range(1, 6)}),
        ('improvement', 'Quiz improvement', 'First versus latest quiz scores, only for participants with at least two valid attempts.',
         {'Improved': sum(m['quiz_change'] is not None and m['quiz_change'] > 0 for m in metrics),
          'Unchanged': sum(m['quiz_change'] == 0 for m in metrics),
          'Lower score': sum(m['quiz_change'] is not None and m['quiz_change'] < 0 for m in metrics)})]
    charts = []
    for key, title, note, counts in definitions:
        scale = max(counts.values(), default=0)
        charts.append(dict(key=key, title=title, note=note, scale=scale, has_data=any(counts.values()),
            rows=[dict(label=label, value=value, width=round(100*value/scale, 2) if scale else 0) for label, value in counts.items()]))
    return charts
