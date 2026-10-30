# Local copies of the product pages, trimmed down to the parts the parsers use.
# Same html structure and data as the real sites (October 2026).

import json

WEB_SCRAPING_DEV = {
    # id: (name, price, full price, low, high)
    1: ('Box of Chocolate Candy', 9.99, 12.99, 9.99, 19.99),
    2: ('Dark Red Energy Potion', 4.99, None, 4.99, 25.99),
    6: ('Dragon Energy Potion', 4.99, None, 4.99, 25.99),
    7: ('Hiking Boots for Outdoor Adventures', 89.99, 99.99, 89.99, 89.99),
    8: ("Women's High Heel Sandals", 59.99, 69.99, 59.99, 59.99),
    9: ('Running Shoes for Men', 49.99, 59.99, 49.99, 49.99),
    11: ('Classic Leather Sneakers', 79.99, 89.99, 79.99, 79.99),
    12: ('Cat-Ear Beanie', 14.99, 19.99, 14.99, 14.99),
}

OXYLABS = {
    # id: (name, developer, price, in stock)
    1: ('The Legend of Zelda: Ocarina of Time', 'Nintendo', 91.99, True),
    2: ('Super Mario Galaxy', 'Nintendo', 91.99, False),
    3: ('Super Mario Galaxy 2', 'Nintendo EAD Tokyo', 91.99, True),
    4: ('Metroid Prime', 'Retro Studios', 89.99, False),
    5: ('Super Mario Odyssey', 'Nintendo', 89.99, True),
    6: ('Halo: Combat Evolved', 'Bungie Software', 87.99, False),
    9: ('Uncharted 2: Among Thieves', 'Naughty Dog', 88.99, True),
    10: ('Tekken 3', 'Namco', 91.99, False),
}

SCRAPEME = {
    # name: (price, sale price, stock, sku)
    'Bulbasaur': (63.00, None, 45, '4391'),
    'Charmander': (48.00, None, 206, '9086'),
    'Squirtle': (130.00, None, 178, '6094'),
    'Charizard': (156.00, None, 31, '8840'),
    'Pikachu': (37.00, None, 254, '1333'),
    'Blastoise': (76.00, None, 88, '5212'),
    'Weedle': (25.00, None, 65, '7525'),
    'Butterfree': (162.00, None, 242, '9507'),
}


def web_scraping_dev_page(id, name, price, full_price, low, high, in_stock=True):
    data = {
        '@context': 'https://schema.org/',
        '@type': 'Product',
        'name': name,
        'brand': {'@type': 'Brand', 'name': 'web-scraping.dev'},
        'offers': {
            '@type': 'AggregateOffer',
            'url': f'https://web-scraping.dev/product/{id}',
            'priceCurrency': 'USD',
            'lowPrice': f'{low:.2f}',
            'highPrice': f'{high:.2f}',
            'offerCount': '4',
            'availability': 'https://schema.org/' + ('InStock' if in_stock else 'OutOfStock'),
        },
        'aggregateRating': {'@type': 'AggregateRating', 'ratingValue': '4.7', 'reviewCount': '10'},
    }
    full = ''
    if full_price:
        full = f'<small class="align-top text-center">from <span class="product-price-full">${full_price:.2f}</span></small>'
    return f'''<html><head><title>web-scraping.dev product {name}</title>
<script type="application/ld+json">
{json.dumps(data, indent=2)}
</script></head><body>
<div class="row product-data"><div class="col-lg-7 col-md-7 col-sm-6">
<h4 class="box-title">Description</h4>
<div class="price">
<span class="product-price mt-5 fs-1 text-success">${price:.2f} </span>
{full}
</div>
<button class="btn btn-secondary btn-rounded me-3 add-to-cart" data-product-id="{id}">Add to Cart</button>
</div></div></body></html>'''


def oxylabs_page(id, name, developer, price, in_stock):
    next_data = {
        'props': {'pageProps': {
            'game': {'game_name': name, 'developer': developer, 'type': 'singleplayer', 'id': id, 'inStock': in_stock},
            'relatedGames': [],
        }},
        'page': '/products/[id]',
    }
    price_text = f'{price:,.2f}'.replace(',', ' ').replace('.', ',')
    return f'''<html><head><title>{name} | Oxylabs Scraping Sandbox</title></head><body>
<div class="product-info-wrapper css-m2w3q2 emlf3670">
<h2 class="title css-1k75zwy e1pl6npa11">{name}</h2>
<div class="brand-wrapper css-1f150rr e15c0rei0"><span class="brand developer"><strong>Developer:</strong> <!-- -->{developer}</span></div>
<div class="price css-o7uf8d e1pl6npa6">{price_text} €</div>
<p class="availability css-qequvl e1pl6npa1">{'In stock' if in_stock else 'Out of stock'}</p>
</div>
<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>
</body></html>'''


def woocommerce_page(name, price, sale_price, stock, sku):
    if sale_price:
        price_html = (f'<del aria-hidden="true"><span class="woocommerce-Price-amount amount"><bdi><span class="woocommerce-Price-currencySymbol">£</span>{price:.2f}</bdi></span></del> '
                      f'<ins><span class="woocommerce-Price-amount amount"><bdi><span class="woocommerce-Price-currencySymbol">£</span>{sale_price:.2f}</bdi></span></ins>')
    else:
        price_html = f'<span class="woocommerce-Price-amount amount"><bdi><span class="woocommerce-Price-currencySymbol" translate="no">£</span>{price:.2f}</bdi></span>'

    if stock:
        stock_html = f'<p class="stock in-stock">{stock} in stock</p>'
    else:
        stock_html = '<p class="stock out-of-stock">Out of stock</p>'

    return f'''<html><head><title>{name} – ScrapeMe</title></head><body>
<div class="summary entry-summary">
<h1 class="product_title entry-title">{name}</h1><p class="price">{price_html}</p>
<div class="woocommerce-product-details__short-description"><p>...</p></div>
{stock_html}
<form class="cart" action="index.html" method="post" enctype="multipart/form-data">
<button type="submit" name="add-to-cart" value="759" class="single_add_to_cart_button button alt">Add to basket</button>
</form>
<div class="product_meta">
<span class="sku_wrapper">SKU: <span class="sku">{sku}</span></span>
<span class="posted_in">Categories: <a href="../../product-category/pokemon/page/1/index.html" rel="tag">Pokemon</a></span>
</div>
</div></body></html>'''


def build_site(web_scraping_dev=WEB_SCRAPING_DEV, oxylabs=OXYLABS, scrapeme=SCRAPEME, scheme='http'):
    pages = {}
    for id, values in web_scraping_dev.items():
        pages[f'{scheme}://web-scraping.dev/product/{id}'] = web_scraping_dev_page(id, *values)
    for id, values in oxylabs.items():
        pages[f'{scheme}://sandbox.oxylabs.io/products/{id}'] = oxylabs_page(id, *values)
    for name, values in scrapeme.items():
        pages[f'{scheme}://scrapeme.live/shop/{name}/'] = woocommerce_page(name, *values)
    return pages
