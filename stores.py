import json
import re
from urllib.parse import urlparse

# domain -> function that takes the page soup and returns a dict with the product data.
# Stores without their own parser go through json_ld(), which works for most
# Shopify / WooCommerce / Magento shops because they put schema.org data in the page.
PARSERS = {}

CURRENCIES = {'$': 'USD', '£': 'GBP', '€': 'EUR'}

PRICE = re.compile(r'(?P<before>[$£€])?\s*(?P<amount>\d[\d.,]*)\s*(?P<after>[$£€])?')


def store(domain):
    def register(func):
        PARSERS[domain] = func
        return func
    return register


def domain_of(url):
    return urlparse(url).netloc.removeprefix('www.')


def get_parser(url):
    return PARSERS.get(domain_of(url), json_ld)


def parse_price(text):
    # '$9.99' -> (9.99, 'USD'), '91,99 €' -> (91.99, 'EUR'), '£1,234.00' -> (1234.0, 'GBP')
    m = PRICE.search(text or '')
    if not m:
        return None, None

    amount = m['amount'].rstrip('.,')
    if re.search(r',\d{2}$', amount):
        # european format, the comma is the decimal point: 1.234,56
        amount = amount.replace('.', '').replace(',', '.')
    else:
        amount = amount.replace(',', '')

    symbol = m['before'] or m['after']
    return float(amount), CURRENCIES.get(symbol)


def product(name, price, currency, regular_price=None, in_stock=True, stock_qty=None, sku=None):
    return {
        'name': name.strip(),
        'sku': sku,
        'price': price,
        'regular_price': regular_price or price,
        'currency': currency,
        'in_stock': in_stock,
        'stock_qty': stock_qty,
    }


@store('web-scraping.dev')
def web_scraping_dev(soup):
    # name and stock come from the schema.org data, but that only has the price range
    # of all the variants, so the actual price is read from the html
    data = json.loads(soup.select_one('script[type="application/ld+json"]').string)
    price, currency = parse_price(soup.select_one('.product-price').text)
    full_price = soup.select_one('.product-price-full')

    return product(
        data['name'],
        price,
        currency or data['offers']['priceCurrency'],
        regular_price=parse_price(full_price.text)[0] if full_price else None,
        in_stock=data['offers']['availability'].endswith('InStock'),
    )


@store('sandbox.oxylabs.io')
def oxylabs_sandbox(soup):
    # next.js site, the product is in the __NEXT_DATA__ json without the price
    game = json.loads(soup.select_one('#__NEXT_DATA__').string)['props']['pageProps']['game']
    price, currency = parse_price(soup.select_one('.price').text)
    return product(game['game_name'], price, currency, in_stock=game['inStock'], sku=str(game['id']))


@store('scrapeme.live')
def woocommerce(soup):
    box = soup.select_one('.summary')
    # on sale: <del>old price</del> <ins>new price</ins>
    price_tag = box.select_one('.price ins') or box.select_one('.price')
    old_price = box.select_one('.price del')
    price, currency = parse_price(price_tag.text)

    # "45 in stock" / "Out of stock" / nothing when the shop doesn't track stock
    stock = box.select_one('.stock')
    in_stock = stock is None or 'out-of-stock' not in stock['class']
    qty = re.search(r'(\d+) in stock', stock.text) if stock else None
    sku = box.select_one('.sku')

    return product(
        box.select_one('.product_title').text,
        price,
        currency,
        regular_price=parse_price(old_price.text)[0] if old_price else None,
        in_stock=in_stock,
        stock_qty=int(qty[1]) if qty else None,
        sku=sku.text if sku else None,
    )


def find_product(data):
    # json-ld can be one object, a list, or an object with everything in "@graph"
    if isinstance(data, list):
        items = data
    else:
        items = data.get('@graph', [data])

    for item in items:
        types = item.get('@type')
        if types == 'Product' or (isinstance(types, list) and 'Product' in types):
            return item
    return None


def json_ld(soup):
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = find_product(json.loads(script.string))
        except (json.JSONDecodeError, TypeError):
            continue
        if data:
            break
    else:
        raise ValueError('no product data found on the page')

    offer = data.get('offers', {})
    if isinstance(offer, list):
        offer = offer[0]

    match offer:
        case {'price': price}:
            pass
        case {'lowPrice': price}:
            pass
        case _:
            raise ValueError('product has no price')

    availability = offer.get('availability', 'InStock')
    return product(
        data['name'],
        float(price),
        offer.get('priceCurrency'),
        in_stock=availability.endswith(('InStock', 'LimitedAvailability')),
        sku=data.get('sku'),
    )
