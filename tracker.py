import csv
import logging
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

from stores import domain_of, get_parser

log = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/130.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}


def load_watchlist(path):
    # url,target_price  (target_price can be empty)
    items = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        for line in csv.DictReader(f):
            url = line['url'].strip()
            if not url or url.startswith('#'):
                continue
            target = (line.get('target_price') or '').strip()
            items.append({'url': url, 'target_price': float(target) if target else None})

    # same url twice in the sheet happens more often than you'd think
    unique = {item['url']: item for item in items}
    return list(unique.values())


def fetch(session, url, retries=3):
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, timeout=20)
            if r.status_code == 404:
                raise ValueError('page not found (404)')
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            if attempt == retries:
                raise
            log.warning('%s: %s, retry %d', url, e, attempt)
            time.sleep(2 * attempt)


def check(session, item):
    url = item['url']
    row = {'url': url, 'store': domain_of(url), 'target_price': item['target_price'], 'error': None}
    try:
        soup = BeautifulSoup(fetch(session, url), 'html.parser')
        row.update(get_parser(url)(soup))
    except Exception as e:
        # one broken link or changed page shouldn't stop the whole run
        log.error('%s: %s', url, e)
        row['error'] = str(e) or type(e).__name__
    return row


def check_store(items, delay, proxy):
    # one session per store, with a pause between requests to the same site
    session = requests.Session()
    session.headers.update(HEADERS)
    if proxy:
        session.proxies = {'http': proxy, 'https': proxy}
        # otherwise HTTP_PROXY / HTTPS_PROXY from the environment win over session.proxies
        session.trust_env = False

    rows = []
    with session:
        for i, item in enumerate(items):
            if i:
                time.sleep(delay)
            rows.append(check(session, item))
    return rows


def check_all(items, delay=1.0, proxy=None):
    # stores are checked at the same time, the products of one store one after another
    by_store = defaultdict(list)
    for item in items:
        by_store[domain_of(item['url'])].append(item)

    for domain, store_items in by_store.items():
        print(f'{domain}: {len(store_items)} products')

    with ThreadPoolExecutor(max_workers=len(by_store) or 1) as pool:
        results = pool.map(check_store, by_store.values(), [delay] * len(by_store), [proxy] * len(by_store))

    # keep the order of the watchlist
    found = {row['url']: row for rows in results for row in rows}
    return [found[item['url']] for item in items]


def compare(row, old):
    # what changed since the last check, e.g. ['price down', 'below target']
    if row['error']:
        return ['error']

    changes = []
    if old is None:
        changes.append('new')
    else:
        if old['price'] is not None and row['price'] != old['price']:
            changes.append('price down' if row['price'] < old['price'] else 'price up')
        if old['in_stock'] and not row['in_stock']:
            changes.append('out of stock')
        elif not old['in_stock'] and row['in_stock']:
            changes.append('back in stock')

    target = row.get('target_price')
    if target is not None and row['in_stock'] and row['price'] <= target:
        changes.append('below target')
    return changes
