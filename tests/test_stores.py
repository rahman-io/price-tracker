import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from fake_shops import oxylabs_page, web_scraping_dev_page, woocommerce_page
from stores import get_parser, json_ld, parse_price


def soup(html):
    return BeautifulSoup(html, 'html.parser')


@pytest.mark.parametrize('text, expected', [
    ('$9.99 ', (9.99, 'USD')),
    ('91,99 €', (91.99, 'EUR')),
    ('91,99\xa0€', (91.99, 'EUR')),
    ('£1,234.00', (1234.0, 'GBP')),
    ('1.234,56 €', (1234.56, 'EUR')),
    ('from $12.99', (12.99, 'USD')),
    ('Price: 15', (15.0, None)),
    ('sold out', (None, None)),
])
def test_parse_price(text, expected):
    assert parse_price(text) == expected


def test_parser_by_domain():
    assert get_parser('https://web-scraping.dev/product/1').__name__ == 'web_scraping_dev'
    assert get_parser('https://www.scrapeme.live/shop/Pikachu/').__name__ == 'woocommerce'
    assert get_parser('https://some-shopify-store.com/products/mug') is json_ld


def test_web_scraping_dev():
    page = web_scraping_dev_page(1, 'Box of Chocolate Candy', 9.99, 12.99, 9.99, 19.99)
    data = get_parser('https://web-scraping.dev/product/1')(soup(page))
    assert data['name'] == 'Box of Chocolate Candy'
    assert data['price'] == 9.99 and data['regular_price'] == 12.99
    assert data['currency'] == 'USD' and data['in_stock'] is True


def test_web_scraping_dev_no_discount():
    page = web_scraping_dev_page(2, 'Dark Red Energy Potion', 4.99, None, 4.99, 25.99)
    data = get_parser('https://web-scraping.dev/product/2')(soup(page))
    # 25.99 is the highest variant price in the json-ld, not the regular price
    assert data['price'] == data['regular_price'] == 4.99


def test_oxylabs():
    page = oxylabs_page(2, 'Super Mario Galaxy', 'Nintendo', 91.99, False)
    data = get_parser('https://sandbox.oxylabs.io/products/2')(soup(page))
    assert data == {
        'name': 'Super Mario Galaxy', 'sku': '2', 'price': 91.99, 'regular_price': 91.99,
        'currency': 'EUR', 'in_stock': False, 'stock_qty': None,
    }


def test_woocommerce():
    page = woocommerce_page('Bulbasaur', 63.00, None, 45, '4391')
    data = get_parser('https://scrapeme.live/shop/Bulbasaur/')(soup(page))
    assert (data['name'], data['price'], data['currency']) == ('Bulbasaur', 63.0, 'GBP')
    assert data['stock_qty'] == 45 and data['in_stock'] and data['sku'] == '4391'


def test_woocommerce_sale_and_out_of_stock():
    page = woocommerce_page('Pikachu', 37.00, 29.50, 0, '1333')
    data = get_parser('https://scrapeme.live/shop/Pikachu/')(soup(page))
    assert data['price'] == 29.5 and data['regular_price'] == 37.0
    assert data['in_stock'] is False and data['stock_qty'] is None


def test_json_ld_graph():
    # how yoast / woocommerce put it on the page
    page = '''<script type="application/ld+json">{"@context":"https://schema.org/","@graph":[
      {"@type":"BreadcrumbList","itemListElement":[]},
      {"@type":"Product","name":"Coffee Mug","sku":"MUG-01","offers":[{"@type":"Offer","price":"12.50",
       "priceCurrency":"EUR","availability":"http://schema.org/OutOfStock"}]}]}</script>'''
    data = json_ld(soup(page))
    assert (data['name'], data['price'], data['currency'], data['sku']) == ('Coffee Mug', 12.5, 'EUR', 'MUG-01')
    assert data['in_stock'] is False


def test_json_ld_skips_broken_scripts():
    page = '''<script type="application/ld+json">{ not json</script>
    <script type="application/ld+json">{"@type":["Product","Thing"],"name":"Lamp","offers":{"lowPrice":"20"}}</script>'''
    assert json_ld(soup(page))['price'] == 20.0


def test_json_ld_missing():
    with pytest.raises(ValueError):
        json_ld(soup('<html><body>no data here</body></html>'))
