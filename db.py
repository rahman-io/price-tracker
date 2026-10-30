import sqlite3

import pandas as pd

SCHEMA = '''
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY,
    run TEXT NOT NULL,
    url TEXT NOT NULL,
    store TEXT,
    name TEXT,
    sku TEXT,
    price REAL,
    regular_price REAL,
    currency TEXT,
    in_stock INTEGER,
    stock_qty INTEGER,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_checks_url ON checks (url, run);
'''

COLUMNS = ('run', 'url', 'store', 'name', 'sku', 'price', 'regular_price',
           'currency', 'in_stock', 'stock_qty', 'error')


def connect(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def save_checks(con, rows):
    sql = f'INSERT INTO checks ({", ".join(COLUMNS)}) VALUES ({", ".join(":" + c for c in COLUMNS)})'
    with con:
        con.executemany(sql, [{c: row.get(c) for c in COLUMNS} for row in rows])


def last_check(con, url):
    # last successful check of this url (called before the new run is saved)
    row = con.execute(
        'SELECT * FROM checks WHERE url = ? AND error IS NULL ORDER BY id DESC LIMIT 1',
        (url,),
    ).fetchone()
    return dict(row) if row else None


def history(con):
    return pd.read_sql_query(
        'SELECT run, url, store, name, price, currency, in_stock FROM checks WHERE error IS NULL ORDER BY run',
        con,
    )
