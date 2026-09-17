import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.getenv('DATABASE_PATH', os.path.join(BASE_DIR, 'phishing_simulator.db'))


@contextmanager
def connection():
    conn = sqlite3.connect(DB_NAME, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def init_db():
    with connection() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL,
            event_type TEXT NOT NULL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        columns = {row['name'] for row in conn.execute('PRAGMA table_info(events)')}
        additions = {'campaign_id': 'INTEGER', 'recipient_id': 'INTEGER',
                     'template_version': 'TEXT', 'source': 'TEXT', 'metadata': "TEXT DEFAULT '{}'",
                     'ip_address': 'TEXT', 'user_agent': 'TEXT', 'browser': 'TEXT',
                     'os': 'TEXT', 'device': 'TEXT', 'suspected_automated': 'INTEGER DEFAULT 0'}
        for name, declaration in additions.items():
            if name not in columns:
                conn.execute(f'ALTER TABLE events ADD COLUMN {name} {declaration}')
        conn.execute('''CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, template TEXT NOT NULL,
            template_version TEXT NOT NULL, created_at TEXT NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS recipients (
            id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
            email TEXT NOT NULL, token TEXT UNIQUE NOT NULL,
            UNIQUE(campaign_id, email))''')
        conn.execute('CREATE INDEX IF NOT EXISTS events_recipient_type ON events(recipient_id, event_type)')


def create_campaign(name, template, version, emails):
    with connection() as conn:
        campaign_id = conn.execute('INSERT INTO campaigns (name, template, template_version, created_at) VALUES (?, ?, ?, ?)',
                                   (name, template, version, now())).lastrowid
        for email in emails:
            conn.execute('INSERT INTO recipients (campaign_id, email, token) VALUES (?, ?, ?)',
                         (campaign_id, email, secrets.token_urlsafe(32)))
    return [r for r in get_recipients() if r['campaign_id'] == campaign_id]


def delete_campaign(campaign_id):
    """Delete a campaign and its dependent data in one transaction."""
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT 1 FROM campaigns WHERE id=?', (campaign_id,)).fetchone():
            return False
        conn.execute('DELETE FROM events WHERE campaign_id=?', (campaign_id,))
        conn.execute('DELETE FROM recipients WHERE campaign_id=?', (campaign_id,))
        conn.execute('DELETE FROM campaigns WHERE id=?', (campaign_id,))
    return True


def get_recipients():
    with connection() as conn:
        return [dict(r) for r in conn.execute('''SELECT r.*, c.template, c.template_version, c.name AS campaign_name
            FROM recipients r JOIN campaigns c ON c.id = r.campaign_id ORDER BY r.id''')]


def get_recipient(token):
    with connection() as conn:
        row = conn.execute('''SELECT r.*, c.template, c.template_version FROM recipients r
            JOIN campaigns c ON c.id=r.campaign_id WHERE r.token=?''', (token,)).fetchone()
        return dict(row) if row else None


def _insert(conn, recipient, event_type, source, metadata, details, timestamp=None):
    details = details or {}
    conn.execute('''INSERT INTO events (email, event_type, timestamp, campaign_id, recipient_id,
        template_version, source, metadata, ip_address, user_agent, browser, os, device, suspected_automated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (recipient['email'], event_type, timestamp or now(), recipient['campaign_id'], recipient['id'],
         recipient['template_version'], source, json.dumps(metadata or {}),
         details.get('ip_address'), details.get('user_agent'), details.get('browser'),
         details.get('os'), details.get('device'), int(details.get('suspected_automated', False))))


def log_event(recipient, event_type, source='web', metadata=None, details=None, timestamp=None):
    with connection() as conn:
        _insert(conn, recipient, event_type, source, metadata, details, timestamp)


def save_quiz(recipient, answers, correct, details):
    missed = [key for key, value in correct.items() if answers[key] != value]
    score = len(correct) - len(missed)
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        attempt = conn.execute("SELECT COUNT(*) FROM events WHERE recipient_id=? AND event_type='quiz_submitted'",
                               (recipient['id'],)).fetchone()[0] + 1
        _insert(conn, recipient, 'quiz_submitted', 'web',
                {'answers': answers, 'score': score, 'total': len(correct), 'attempt': attempt,
                 'missed_questions': missed, 'quiz_version': '1'}, details)
        completed = conn.execute("SELECT 1 FROM events WHERE recipient_id=? AND event_type='training_completed'",
                                 (recipient['id'],)).fetchone()
        if not missed and not completed:
            _insert(conn, recipient, 'training_completed', 'web', {'quiz_version': '1'}, details)
    return {'score': score, 'total': len(correct), 'passed': not missed, 'attempt': attempt}


def get_results():
    with connection() as conn:
        return [dict(r) for r in conn.execute('''SELECT e.*, c.name AS campaign_name, c.template
            FROM events e LEFT JOIN campaigns c ON c.id=e.campaign_id ORDER BY e.timestamp DESC, e.id DESC''')]


def get_campaign_summaries():
    events = get_results()
    recipients = get_recipients()
    with connection() as conn:
        campaigns = [dict(r) for r in conn.execute('SELECT * FROM campaigns ORDER BY id DESC')]
    for campaign in campaigns:
        rows = [e for e in events if e['campaign_id'] == campaign['id']]
        def ids(kind):
            return {e['recipient_id'] for e in rows if e['event_type'] == kind}
        accepted, clicks, reports = ids('email_accepted'), ids('clicked_link'), ids('phishing_reported')
        viewed, completed = ids('viewed_training'), ids('training_completed')
        before = 0
        for recipient_id in reports:
            report_time = min(e['timestamp'] for e in rows if e['recipient_id'] == recipient_id and e['event_type'] == 'phishing_reported')
            click_times = [e['timestamp'] for e in rows if e['recipient_id'] == recipient_id and e['event_type'] == 'clicked_link']
            before += not click_times or report_time < min(click_times)
        quizzes = [json.loads(e['metadata']) for e in rows if e['event_type'] == 'quiz_submitted']
        campaign.update(targets=sum(r['campaign_id'] == campaign['id'] for r in recipients),
                        accepted=len(accepted), failed=len(ids('email_failed')),
                        unique_opens=len(ids('email_opened')), unique_clicks=len(clicks),
                        password_viewed=len(ids('password_form_viewed')),
                        password_started=len(ids('password_form_started')),
                        password_submitted=len(ids('password_change_submitted')),
                        scenario_viewed=len(ids('scenario_page_viewed')),
                        scenario_submitted=len(ids('scenario_action_submitted')),
                        all_submitted=len(ids('password_change_submitted') | ids('scenario_action_submitted')),
                        click_requests=sum(e['event_type'] == 'clicked_link' for e in rows),
                        suspected_clicks=sum(e['event_type'] == 'clicked_link' and e['suspected_automated'] for e in rows),
                        unique_reports=len(reports), reported_before_click=before,
                        training_viewed=len(viewed), completed=len(completed),
                        click_rate=round(100 * len(clicks & accepted) / len(accepted), 1) if accepted else None,
                        report_rate=round(100 * len(reports & accepted) / len(accepted), 1) if accepted else None,
                        completion_rate=round(100 * len(completed & viewed) / len(viewed), 1) if viewed else None,
                        average_score=round(sum(q['score'] for q in quizzes) / len(quizzes), 2) if quizzes else None)
        report_times = [e['timestamp'] for e in rows if e['event_type'] == 'phishing_reported']
        campaign['seconds_to_first_report'] = round((datetime.fromisoformat(min(report_times)) - datetime.fromisoformat(campaign['created_at'])).total_seconds()) if report_times else None
    return campaigns
