"""Shared copy for email and landing-page simulation scenarios."""
SCENARIOS = {
    'password': dict(brand='Account Security', title='Review your account security',
        subject='Account security: password review requested', category='ACCOUNT NOTICE', color='#245db5',
        intro='A password review has been requested for your campus account. Review your account settings before your next sign-in.',
        action='Review account security', status='Review requested', detail='Campus account access',
        note='Email, learning tools and campus services'),
    'parking': dict(brand='Campus Parking Services', title='Review your parking permit',
        subject='Parking services: permit details need review', category='PERMIT SERVICES', color='#28664f',
        intro='Your parking permit profile is ready for review. Confirm your permit preferences for the current academic term.',
        action='Review permit', status='Pending review', detail='Campus parking permit',
        note='Current academic term'),
    'package': dict(brand='Campus Mail Services', title='Review your collection notice',
        subject='Mail services: a collection notice is available', category='MAILROOM NOTICE', color='#9a571e',
        intro='A collection notice is available in your campus mail profile. Review the notice and acknowledge the collection instructions.',
        action='View collection notice', status='Notice available', detail='Campus mail collection',
        note='Collection location: campus mailroom'),
    'payroll': dict(brand='People & Payroll', title='Review your payroll profile',
        subject='Payroll services: profile review requested', category='EMPLOYEE SERVICES', color='#674a95',
        intro='Your payroll profile has a pending review request. Open the employee services page to acknowledge the profile notice.',
        action='Review payroll profile', status='Acknowledgment requested', detail='Employee payroll profile',
        note='Profile review only'),
    'storage': dict(brand='Campus Cloud Storage', title='Review your storage usage',
        subject='Cloud storage: review your account usage', category='STORAGE NOTICE', color='#266a99',
        intro='Your cloud storage usage is approaching its allocated capacity. Review the storage notice and your account options.',
        action='Review storage usage', status='Capacity notice', detail='Cloud storage account',
        note='Files, shared folders and synced documents'),
}


def email_html(scenario):
    from html import escape
    s = {k: escape(v) for k, v in scenario.items()}
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#f2f5f8;font-family:Arial,sans-serif;color:#203149">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:white;border:1px solid #dce3ec;border-radius:10px">
<tr><td style="padding:26px 32px;border-bottom:1px solid #e5eaf0;color:{s['color']};font-size:19px;font-weight:bold">{s['brand']}</td></tr>
<tr><td style="padding:32px"><p style="font-size:11px;letter-spacing:2px;color:#61738a">{s['category']}</p>
<h1 style="font-size:26px;line-height:1.3;margin:14px 0 20px">{s['title']}</h1>
<p style="line-height:1.7;color:#526277">{s['intro']}</p>
<table role="presentation" width="100%" style="margin:24px 0;background:#f6f8fb"><tr><td style="padding:18px;font-size:14px;line-height:1.7"><strong>{s['detail']}</strong><br>{s['note']}<br>Status: {s['status']}</td></tr></table>
<a href="{{link}}" style="display:inline-block;padding:14px 22px;border-radius:5px;background:{s['color']};color:white;text-decoration:none;font-weight:bold">{s['action']}</a>
<p style="font-size:12px;color:#687a8e;margin-top:28px">This mailbox is not monitored. For help, contact your campus service desk through your usual support channel.</p></td></tr>
<tr><td style="padding:18px 32px;border-top:1px solid #e5eaf0;font-size:12px;color:#738195">{s['brand']} · Account notifications</td></tr>
</table></td></tr></table></body></html>'''
