"""Readable dashboard data, without changing stored event evidence."""
import json

LABELS = {
    'training_link_clicked': 'Training link followed', 'training_section_viewed': 'Training section reached',
    'training_activity': 'Training active-time checkpoint', 'client_request_failed': 'Browser request failure reported',
    'scenario_page_viewed': 'Service page viewed', 'scenario_action_submitted': 'Service action submitted',
    'email_send_attempted': 'Email sending started', 'email_accepted': 'Email accepted by mail server',
    'email_failed': 'Email could not be sent', 'email_opened': 'Email image loaded (estimated open)',
    'clicked_link': 'Campaign link visited', 'password_form_viewed': 'Password form viewed',
    'password_form_started': 'Password form started', 'password_change_submitted': 'Password change submitted',
    'viewed_training': 'Training opened', 'quiz_submitted': 'Quiz submitted',
    'training_completed': 'Training completed', 'phishing_reported': 'Phishing report recorded',
}


def dashboard_data(events, enabled):
    for event in events:
        event['label'] = LABELS.get(event['event_type'], event['event_type'].replace('_', ' ').capitalize())
        try:
            metadata = json.loads(event.get('metadata') or '{}')
        except (ValueError, TypeError):
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        details = []
        if 'active_seconds' in metadata:
            details.append(f"Active time: {metadata['active_seconds']} seconds (session total)")
        if 'section' in metadata:
            details.append('Section: ' + metadata['section'].replace('_', ' '))
        if 'operation' in metadata:
            details.append(f"Failed {metadata['operation']} requests: {metadata.get('count', 1)} (client-reported)")
        if metadata.get('scenario'):
            details.append('Scenario: ' + metadata['scenario'].capitalize())
        if 'elapsed_ms' in metadata:
            details.append(f"{metadata['elapsed_ms'] / 1000:g} seconds after opening the page")
        for key, label in [('current_filled', 'Current password'), ('new_filled', 'New password'), ('confirmation_filled', 'Confirmation')]:
            if key in metadata:
                details.append(f"{label}: {'filled' if metadata[key] else 'empty'}")
        if 'score' in metadata:
            details.append(f"Quiz score: {metadata['score']}/{metadata.get('total', 5)} · Attempt {metadata.get('attempt', 1)}")
        if metadata.get('missed_questions'):
            details.append('Review questions: ' + ', '.join(metadata['missed_questions']))
        if 'channel' in metadata:
            details.append('Reported via: ' + metadata['channel'].replace('_', ' '))
        if 'error_type' in metadata:
            details.append('Send error: ' + metadata['error_type'])
        event['readable_details'] = details
        if event['ip_address']:
            event['ip_note'] = 'This computer (local test)' if event['ip_address'] in ('127.0.0.1', '::1') else 'Connection IP address'
        elif event['source'] in ('smtp', 'admin_manual'):
            event['ip_note'] = 'Not applicable — no participant browser request'
        elif not event['source']:
            event['ip_note'] = 'Older event — request details were not recorded'
        else:
            event['ip_note'] = 'Not recorded for this event' if enabled else 'Collection is currently disabled'
    visits = [e for e in events if e['source'] == 'web' and e['event_type'] != 'email_opened']
    return {'events': events, 'visits': len(visits), 'with_ip': sum(bool(e['ip_address']) for e in visits),
            'last_visit': visits[0]['timestamp'] if visits else None, 'details_enabled': enabled}
