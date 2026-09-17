import base64
import os
import re
import sqlite3
import secrets
from datetime import datetime, timezone

from flask import Flask, Response, abort, jsonify, render_template, request, redirect, url_for
from database import (init_db, log_event, get_results, create_campaign, get_recipient,
                      get_recipients, get_campaign_summaries, save_quiz, delete_campaign)
from email_sender import send_simulation_email, TEMPLATES, template_version
from telemetry import request_details
from dashboard_view import dashboard_data

app = Flask(__name__)
app.config.update(COLLECT_REQUEST_DETAILS=os.getenv('COLLECT_REQUEST_DETAILS', 'true').lower() == 'true',
                  ADMIN_PASSWORD=os.getenv('ADMIN_PASSWORD', ''),
                  MAX_CONTENT_LENGTH=256 * 1024)
init_db()
CORRECT = {'q1': 'a', 'q2': 'b', 'q3': 'c', 'q4': 'b', 'q5': 'a'}
ADMIN_ENDPOINTS = ('dashboard', 'campaign', 'report', 'tracking_test', 'campaign_detail', 'campaign_delete')


@app.before_request
def protect_admin():
    if request.endpoint not in ADMIN_ENDPOINTS:
        return None
    password = app.config['ADMIN_PASSWORD']
    if not password:
        return 'Set ADMIN_PASSWORD in your .env file and restart the app to enable administration.', 503
    auth = request.authorization
    if not auth or auth.type != 'basic' or auth.username != 'admin' or not secrets.compare_digest(
            (auth.password or '').encode(), password.encode()):
        return Response('Administrator sign-in required.', 401,
                        {'WWW-Authenticate': 'Basic realm="Campaign administration", charset="UTF-8"'})
    if request.method == 'POST':
        origin = request.headers.get('Origin')
        if request.headers.get('Sec-Fetch-Site') == 'cross-site' or (origin and origin != request.host_url.rstrip('/')):
            abort(403, 'Cross-site administration requests are not allowed.')


def participant(required=True):
    token = request.args.get('token', '')
    if not token and not required:
        return None
    recipient = get_recipient(token)
    if not recipient:
        abort(400, 'Missing or invalid participant token. Use a link from a new campaign.')
    return recipient


def record(recipient, kind):
    details = request_details(request, app.config['COLLECT_REQUEST_DETAILS'])
    log_event(recipient, kind, details=details,
              metadata={'automation_reason': details['automation_reason']})


@app.after_request
def response_headers(response):
    # Suppressing referrers on admin forms can make browser POST Origin null.
    # Preserve same-origin form metadata without leaking participant link tokens.
    response.headers['Referrer-Policy'] = (
        'same-origin' if request.endpoint in ADMIN_ENDPOINTS else 'no-referrer'
    )
    response.headers['Cache-Control'] = 'no-store'
    if response.status_code >= 500:
        app.logger.error('Request failed: endpoint=%s status=%s', request.endpoint, response.status_code)
    return response


@app.errorhandler(sqlite3.Error)
def database_error(error):
    app.logger.error('Database operation failed: %s', type(error).__name__)
    return 'Unable to save or load campaign data. Please try again.', 503


@app.route('/')
def dashboard():
    data = dashboard_data(get_results(), app.config['COLLECT_REQUEST_DETAILS'])
    return render_template('dashboard.html', results=data['events'], telemetry=data,
                           campaigns=get_campaign_summaries(), recipients=get_recipients())


@app.post('/tracking-test')
def tracking_test():
    recipient = create_campaign('Tracking test (no email sent)', 'password',
                                template_version('password'), ['local-check@simulation.invalid'])[0]
    return redirect(url_for('fake_login', token=recipient['token']))


@app.get('/campaign/<int:campaign_id>')
def campaign_detail(campaign_id):
    selected = next((c for c in get_campaign_summaries() if c['id'] == campaign_id), None)
    if selected is None:
        abort(404, 'Campaign not found.')
    events = dashboard_data([e for e in get_results() if e['campaign_id'] == campaign_id],
                            app.config['COLLECT_REQUEST_DETAILS'])['events']
    participants = []
    for recipient in get_recipients():
        if recipient['campaign_id'] != campaign_id:
            continue
        history = [e for e in events if e['recipient_id'] == recipient['id']]
        kinds = {e['event_type'] for e in history}
        browser_events = [e for e in history if e['source'] == 'web' and e['event_type'] != 'email_opened']
        latest_request = next((e for e in browser_events if e['ip_address']), None)
        participants.append({'email': recipient['email'], 'id': recipient['id'], 'events': history,
            'browser_events': browser_events, 'latest_request': latest_request,
            'accepted': 'email_accepted' in kinds, 'failed': 'email_failed' in kinds,
            'clicked': 'clicked_link' in kinds, 'submitted': 'password_change_submitted' in kinds,
            'completed': 'training_completed' in kinds, 'reported': 'phishing_reported' in kinds})
    return render_template('campaign_detail.html', campaign=selected, participants=participants)


@app.post('/campaign/<int:campaign_id>/delete')
def campaign_delete(campaign_id):
    if request.form.get('confirm') != 'delete':
        abort(400, 'Confirm campaign deletion before continuing.')
    if not delete_campaign(campaign_id):
        abort(404, 'Campaign not found.')
    return redirect(url_for('dashboard'))


@app.route('/campaign', methods=['GET', 'POST'])
def campaign():
    if request.method == 'POST':
        template = request.form.get('template', '')
        emails = list(dict.fromkeys(e.strip() for e in request.form.get('targets', '').splitlines() if e.strip()))
        if template not in TEMPLATES or not emails or len(emails) > 500 or any(
                not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', e) for e in emails):
            abort(400, 'Choose a valid template and provide 1–500 valid email addresses.')
        name = request.form.get('name', '').strip()[:120] or TEMPLATES[template]['subject']
        recipients = create_campaign(name, template, template_version(template), emails)
        for recipient in recipients:
            log_event(recipient, 'email_send_attempted', source='smtp')
            try:
                send_simulation_email(recipient['email'], template, recipient['token'])
            except (OSError, ValueError) as error:
                log_event(recipient, 'email_failed', source='smtp', metadata={'error_type': type(error).__name__})
                app.logger.warning('Email send failed: campaign=%s recipient=%s type=%s',
                                   recipient['campaign_id'], recipient['id'], type(error).__name__)
            else:
                log_event(recipient, 'email_accepted', source='smtp')
        return redirect(url_for('dashboard'))
    return render_template('campaign.html')


@app.route('/track')
def track_open():
    record(participant(), 'email_opened')
    return Response(base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'), mimetype='image/gif')


@app.route('/login')
def fake_login():
    recipient = participant()
    record(recipient, 'clicked_link')
    record(recipient, 'password_form_viewed')
    return render_template('landing.html', token=recipient['token'])


@app.post('/interaction')
def interaction():
    recipient = participant()
    body = request.get_json(silent=True)
    allowed = {'event', 'elapsed_ms', 'current_filled', 'new_filled', 'confirmation_filled'}
    if not isinstance(body, dict) or set(body) - allowed:
        return jsonify(error='Unsupported interaction data.'), 400
    kind = body.get('event')
    if kind not in ('password_form_started', 'password_change_submitted'):
        return jsonify(error='Unsupported interaction event.'), 400
    elapsed = body.get('elapsed_ms', 0)
    if type(elapsed) is not int or not 0 <= elapsed <= 86400000:
        return jsonify(error='Invalid elapsed time.'), 400
    metadata = {'elapsed_ms': elapsed, 'timing_source': 'client', 'form_version': '1'}
    for field in ('current_filled', 'new_filled', 'confirmation_filled'):
        if field in body:
            if type(body[field]) is not bool:
                return jsonify(error='Field state must be a boolean.'), 400
            metadata[field] = body[field]
    details = request_details(request, app.config['COLLECT_REQUEST_DETAILS'])
    log_event(recipient, kind, source='web', metadata=metadata, details=details)
    return jsonify(saved=True)


@app.route('/training')
def training():
    recipient = participant(required=False)
    if recipient:
        record(recipient, 'viewed_training')
    return render_template('training.html', token=recipient['token'] if recipient else None)


@app.post('/quiz')
def quiz():
    recipient = participant(required=False)
    submitted = request.get_json(silent=True)
    if not isinstance(submitted, dict) or any(submitted.get(key) not in ('a', 'b', 'c') for key in CORRECT):
        return jsonify(error='Answer all five questions before submitting.'), 400
    answers = {key: submitted[key] for key in CORRECT}
    if recipient:
        result = save_quiz(recipient, answers, CORRECT, request_details(request, app.config['COLLECT_REQUEST_DETAILS']))
    else:
        score = sum(answers[key] == value for key, value in CORRECT.items())
        result = {'score': score, 'total': 5, 'passed': score == 5, 'preview': True}
    return jsonify(result)


@app.post('/report')
def report():
    recipient = next((r for r in get_recipients() if str(r['id']) == request.form.get('recipient_id')), None)
    channel = request.form.get('channel')
    if not recipient or channel not in ('email', 'report_button', 'in_person', 'phone', 'other'):
        abort(400, 'Choose a participant and reporting channel.')
    timestamp = None
    if request.form.get('reported_at'):
        try:
            reported = datetime.fromisoformat(request.form['reported_at']).replace(tzinfo=timezone.utc)
            campaign = next(c for c in get_campaign_summaries() if c['id'] == recipient['campaign_id'])
            if not datetime.fromisoformat(campaign['created_at']) <= reported <= datetime.now(timezone.utc):
                raise ValueError()
            timestamp = reported.isoformat(timespec='microseconds')
        except ValueError:
            abort(400, 'Report time must be UTC, after campaign creation, and not in the future.')
    log_event(recipient, 'phishing_reported', source='admin_manual', metadata={'channel': channel}, timestamp=timestamp)
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG') == '1')
