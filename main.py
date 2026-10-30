import argparse
import logging
import os
from collections import Counter
from datetime import datetime

import db
from notify import money, send_discord
from report import build_rows, save_csv, save_excel
from tracker import check_all, compare, load_watchlist


def main():
    parser = argparse.ArgumentParser(description='Check the prices of the products in a watchlist')
    parser.add_argument('--watchlist', default='watchlist.csv', help='csv with url,target_price (default: watchlist.csv)')
    parser.add_argument('--db', default='prices.db', help='sqlite file with the price history (default: prices.db)')
    parser.add_argument('--out', default='output', help='output folder (default: output)')
    parser.add_argument('--delay', type=float, default=1.0, help='seconds between requests to the same store (default 1)')
    parser.add_argument('--proxy', help='e.g. http://user:pass@host:port')
    parser.add_argument('--webhook', default=os.environ.get('DISCORD_WEBHOOK_URL'),
                        help='discord webhook for the changes (or set DISCORD_WEBHOOK_URL)')
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(message)s')

    items = load_watchlist(args.watchlist)
    run = datetime.now().isoformat(timespec='seconds')
    print(f'Checking {len(items)} products')

    rows = check_all(items, delay=args.delay, proxy=args.proxy)

    con = db.connect(args.db)
    previous = {}
    for row in rows:
        row['run'] = run
        previous[row['url']] = db.last_check(con, row['url'])
        row['status'] = ', '.join(compare(row, previous[row['url']]))
    db.save_checks(con, rows)

    latest = build_rows(rows, previous)
    history = db.history(con)
    con.close()
    print(f'\nSaved {len(rows)} checks to {args.db}')

    counts = Counter(s for row in latest for s in row['status'].split(', ') if s)
    errors = counts.pop('error', 0)
    out_of_stock = sum(row['in_stock'] == 'no' for row in latest)
    print(f'{len(latest) - errors} checked, {errors} errors, {out_of_stock} out of stock')
    for status, n in counts.most_common():
        print(f'  {status}: {n}')

    for row in latest:
        if row['status'] not in ('new', '', 'error'):
            print(f'  {row["name"]}: {money(row["price"], row["currency"])} ({row["status"]})')

    os.makedirs(args.out, exist_ok=True)
    save_excel(os.path.join(args.out, 'prices.xlsx'), latest, history)
    save_csv(os.path.join(args.out, 'latest.csv'), latest)
    print(f'\nSaved prices.xlsx and latest.csv to {args.out}/')

    if args.webhook:
        sent = send_discord(args.webhook, latest)
        print(f'Sent {sent} message(s) to discord' if sent else 'Nothing changed, no message sent')


if __name__ == '__main__':
    main()
