"""Best-effort request context; never treat user-agent claims as proof."""


def request_details(request, enabled):
    ua = request.headers.get('User-Agent', '')[:512]
    lower = ua.lower()
    automated = any(word in lower for word in ('bot', 'crawler', 'spider', 'scanner', 'headless', 'safelinks'))
    details = {'suspected_automated': automated, 'automation_reason': 'user_agent_hint' if automated else None}
    if not enabled:
        return details
    browser = next((label for marker, label in [('edg/', 'Edge'), ('opr/', 'Opera'), ('chrome/', 'Chrome'),
                   ('firefox/', 'Firefox'), ('safari/', 'Safari')] if marker in lower), 'Unknown')
    os_name = next((label for marker, label in [('android', 'Android'), ('iphone', 'iOS'), ('ipad', 'iOS'),
                   ('windows', 'Windows'), ('mac os', 'macOS'), ('linux', 'Linux')] if marker in lower), 'Unknown')
    device = 'Tablet' if 'ipad' in lower or ('android' in lower and 'mobile' not in lower) else (
        'Mobile' if 'mobile' in lower or 'iphone' in lower else 'Desktop' if os_name != 'Unknown' else 'Unknown')
    details.update(ip_address=request.remote_addr, user_agent=ua, browser=browser, os=os_name, device=device)
    return details
