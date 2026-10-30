import requests

SYMBOLS = {'USD': '$', 'GBP': '£', 'EUR': '€'}
MAX_LENGTH = 2000  # discord message limit


def money(value, currency):
    if value is None:
        return '-'
    return f'{SYMBOLS.get(currency, "")}{value:,.2f}'


def build_lines(latest):
    lines = []
    for row in latest:
        status = [s for s in row['status'].split(', ') if s and s not in ('new', 'error')]
        if not status:
            continue
        price = money(row['price'], row['currency'])
        if row['previous_price'] is not None and row['previous_price'] != row['price']:
            price = f'{money(row["previous_price"], row["currency"])} -> {price}'
        lines.append(f'**{row["name"]}** ({row["store"]}): {price}, {", ".join(status)}\n<{row["url"]}>')
    return lines


def split_messages(lines):
    messages, current = [], ''
    for line in lines:
        if len(current) + len(line) + 1 > MAX_LENGTH:
            messages.append(current)
            current = ''
        current += line + '\n'
    if current:
        messages.append(current)
    return messages


def send_discord(webhook_url, latest):
    lines = build_lines(latest)
    if not lines:
        return 0

    messages = split_messages(lines)
    for text in messages:
        r = requests.post(webhook_url, json={'content': text}, timeout=20)
        r.raise_for_status()
    return len(messages)
