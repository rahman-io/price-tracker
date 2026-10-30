# price-tracker

Checks the price and stock of a list of product URLs from different online stores, keeps the history in a SQLite database and shows what changed since the last run: price drops, price increases, products going out of stock or coming back, and prices below the target you set. Meant to be run every day or week (cron / Task Scheduler) and optionally posts the changes to a Discord channel.

The watchlist is a plain csv, so you can keep it in Excel:

```
url,target_price
https://web-scraping.dev/product/7,90
https://sandbox.oxylabs.io/products/5,90
https://scrapeme.live/shop/Charizard/,150
```

## Stores

Every store shows its prices differently, so each one has its own parser in `stores.py`:

| Store | How the data is read |
|---|---|
| web-scraping.dev | schema.org JSON-LD for name and stock, the sale and regular price from the html |
| sandbox.oxylabs.io | Next.js site: product data from the `__NEXT_DATA__` json, price from the html (`91,99 €` format) |
| scrapeme.live | WooCommerce: sale / regular price, stock count ("45 in stock"), SKU |
| anything else | generic JSON-LD parser, works on most Shopify and WooCommerce shops |

Adding a store is one function:

```python
@store('example-shop.com')
def example_shop(soup):
    price, currency = parse_price(soup.select_one('.price').text)
    return product(soup.select_one('h1').text, price, currency)
```

## Output

- `output/prices.xlsx`
  - **Latest** - every product with price, regular price, discount %, previous price, change, stock and status. Green rows are good news (price down, below target, back in stock), red rows are price up / out of stock
  - **Changes** - only the products where something changed
  - **Price history** - one column per run
  - **Errors** - links that didn't work (404, timeout, page layout changed), only when there are any
- `output/latest.csv`
- `prices.db` - every check, so the history survives between runs

First run with the watchlist in this repo:

```
Checking 24 products
web-scraping.dev: 8 products
sandbox.oxylabs.io: 8 products
scrapeme.live: 8 products

Saved 24 checks to prices.db
24 checked, 0 errors, 4 out of stock
  new: 24
  below target: 6
  Box of Chocolate Candy: $9.99 (new, below target)
  Hiking Boots for Outdoor Adventures: $89.99 (new, below target)
  Cat-Ear Beanie: $14.99 (new, below target)
  Super Mario Odyssey: €89.99 (new, below target)
  Charmander: £48.00 (new, below target)
  Weedle: £25.00 (new, below target)

Saved prices.xlsx and latest.csv to output/
```

When something changed on the next run it looks like this:

```
  Super Mario Galaxy: €91.99 (back in stock)
  Charizard: £139.00 (price down, below target)
  Pikachu: £42.00 (price up)
```

## Setup

```
pip install -r requirements.txt
```

Needs Python 3.10 or newer.

## Usage

```
python main.py
```

On a Mac use `python3` instead of `python`.

```
python main.py --watchlist my_products.csv   # another list (default watchlist.csv)
python main.py --delay 2                     # seconds between requests to the same store (default 1)
python main.py --proxy http://user:pass@host:port
python main.py --webhook https://discord.com/api/webhooks/...
```

The webhook can also be set as an environment variable (`DISCORD_WEBHOOK_URL`). Nothing is sent when nothing changed.

The stores are checked at the same time (one thread per store), the products of one store one after another with the delay in between. A broken link is logged and saved as an error, it doesn't stop the run.

### Running it every day

Mac / Linux, `crontab -e`:

```
0 8 * * * cd /path/to/price-tracker && /usr/bin/python3 main.py >> tracker.log 2>&1
```

On Windows use Task Scheduler with `python main.py` and the project folder as "Start in".

## Tests

```
pip install pytest
python -m pytest
```

The tests use local copies of the product pages behind a fake proxy (`--proxy`), so they don't send requests to the real stores. They also change prices and stock between two runs to check the change detection, the Excel file and the Discord message.

Built with requests, BeautifulSoup, SQLite, pandas and openpyxl.
