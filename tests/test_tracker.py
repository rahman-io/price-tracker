# The scraper is pointed at a local server with --proxy, so the urls in the watchlist
# stay the real ones (http instead of https) and every request ends up here.

import http.server
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
import db
import fake_shops
from tracker import check_all, compare, load_watchlist

SITE = {}
WEBHOOK = []


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = SITE.get(self.path)
        if body is None:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(body.encode('utf-8'))

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        WEBHOOK.append(json.loads(self.rfile.read(length)))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture(scope='module')
def server():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()


@pytest.fixture
def site():
    SITE.clear()
    SITE.update(fake_shops.build_site())
    WEBHOOK.clear()
    return SITE


@pytest.fixture
def watchlist(tmp_path):
    # the real watchlist, with http urls for the local server
    text = (ROOT / 'watchlist.csv').read_text().replace('https://', 'http://')
    path = tmp_path / 'watchlist.csv'
    path.write_text(text)
    return path


def run_main(server, tmp_path, watchlist, *args):
    result = subprocess.run(
        [sys.executable, str(ROOT / 'main.py'), '--watchlist', str(watchlist), '--db', str(tmp_path / 'prices.db'),
         '--out', str(tmp_path / 'output'), '--delay', '0', '--proxy', server, *args],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def test_load_watchlist(tmp_path):
    path = tmp_path / 'list.csv'
    path.write_text('url,target_price\nhttps://a.com/1,10\n\nhttps://a.com/2,\n# old one\nhttps://a.com/1,12\n')
    items = load_watchlist(path)
    assert items == [{'url': 'https://a.com/1', 'target_price': 12.0}, {'url': 'https://a.com/2', 'target_price': None}]
    assert len(load_watchlist(ROOT / 'watchlist.csv')) == 24


def test_check_all(server, site, watchlist):
    rows = check_all(load_watchlist(watchlist), delay=0, proxy=server)
    assert len(rows) == 24
    assert all(row['error'] is None for row in rows)
    assert [row['store'] for row in rows[::8]] == ['web-scraping.dev', 'sandbox.oxylabs.io', 'scrapeme.live']
    assert sum(not row['in_stock'] for row in rows) == 4
    assert rows[0]['name'] == 'Box of Chocolate Candy' and rows[0]['regular_price'] == 12.99


def test_broken_link(server, site):
    rows = check_all([{'url': 'http://scrapeme.live/shop/Mewtwo/', 'target_price': None}], delay=0, proxy=server)
    assert rows[0]['error'] == 'page not found (404)'


def test_compare():
    old = {'price': 10.0, 'in_stock': 1}
    assert compare({'error': None, 'price': 8.0, 'in_stock': True}, old) == ['price down']
    assert compare({'error': None, 'price': 12.0, 'in_stock': False}, old) == ['price up', 'out of stock']
    assert compare({'error': None, 'price': 10.0, 'in_stock': True}, None) == ['new']
    assert compare({'error': None, 'price': 9.0, 'in_stock': True, 'target_price': 9.0}, old) == ['price down', 'below target']
    # out of stock items don't count as below target
    assert compare({'error': None, 'price': 5.0, 'in_stock': False, 'target_price': 9.0}, {'price': 5.0, 'in_stock': 0}) == []
    assert compare({'error': 'timeout'}, old) == ['error']


def test_first_run(server, site, watchlist, tmp_path):
    out = run_main(server, tmp_path, watchlist)
    assert '24 checked, 0 errors' in out
    assert 'new: 24' in out and 'below target: 6' in out

    wb = load_workbook(tmp_path / 'output' / 'prices.xlsx')
    assert wb.sheetnames == ['Latest', 'Changes', 'Price history']
    assert wb['Latest'].max_row == 25
    assert wb['Changes'].max_row == 7  # only the 6 below target, "new" isn't a change

    headers = [c.value for c in wb['Latest'][1]]
    first = {h: c.value for h, c in zip(headers, wb['Latest'][2])}
    assert first['Discount %'] == 23.1  # 9.99 instead of 12.99


def test_second_run_finds_changes(server, site, watchlist, tmp_path):
    run_main(server, tmp_path, watchlist)

    # prices and stock change on the "sites" between the two runs
    wsd = dict(fake_shops.WEB_SCRAPING_DEV)
    wsd[7] = ('Hiking Boots for Outdoor Adventures', 79.99, 99.99, 79.99, 79.99)
    oxy = dict(fake_shops.OXYLABS)
    oxy[2] = ('Super Mario Galaxy', 'Nintendo', 91.99, True)
    oxy[3] = ('Super Mario Galaxy 2', 'Nintendo EAD Tokyo', 91.99, False)
    shop = dict(fake_shops.SCRAPEME)
    shop['Charizard'] = (156.00, 139.00, 31, '8840')
    shop['Pikachu'] = (42.00, None, 254, '1333')
    site.clear()
    site.update(fake_shops.build_site(wsd, oxy, shop))
    del site['http://scrapeme.live/shop/Weedle/']

    out = run_main(server, tmp_path, watchlist, '--webhook', server + '/webhook')
    assert '23 checked, 1 errors' in out
    assert 'price down: 2' in out and 'price up: 1' in out
    assert 'back in stock: 1' in out and 'out of stock: 1' in out

    wb = load_workbook(tmp_path / 'output' / 'prices.xlsx')
    assert wb.sheetnames == ['Latest', 'Changes', 'Price history', 'Errors']
    history = wb['Price history']
    assert history.max_row == 25
    assert history.max_column >= 3

    changes = {row[0]: row for row in wb['Changes'].iter_rows(min_row=2, values_only=True)}
    headers = [c.value for c in wb['Changes'][1]]
    boots = dict(zip(headers, changes['Hiking Boots for Outdoor Adventures']))
    assert boots['Previous price'] == 89.99 and boots['Change'] == -10 and boots['Change %'] == -11.1
    assert boots['Status'] == 'price down, below target'
    assert wb['Latest']['A2'].fill.fgColor.rgb.endswith('C6EFCE')  # chocolate, below target

    con = db.connect(tmp_path / 'prices.db')
    assert con.execute('SELECT COUNT(*) FROM checks').fetchone()[0] == 48
    assert con.execute('SELECT COUNT(*) FROM checks WHERE error IS NOT NULL').fetchone()[0] == 1

    message = WEBHOOK[0]['content']
    assert '**Charizard** (scrapeme.live): £156.00 -> £139.00, price down, below target' in message
    assert 'Super Mario Galaxy 2' in message and 'Weedle' not in message


def test_no_changes_no_message(server, site, watchlist, tmp_path):
    run_main(server, tmp_path, watchlist)
    # remove the targets, so the second run has nothing to report
    header, *lines = watchlist.read_text().splitlines()
    watchlist.write_text('\n'.join([header] + [line.split(',')[0] + ',' for line in lines]))
    out = run_main(server, tmp_path, watchlist, '--webhook', server + '/webhook')
    assert 'Nothing changed, no message sent' in out
    assert WEBHOOK == []
