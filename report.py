import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

GREEN = PatternFill('solid', fgColor='C6EFCE')
RED = PatternFill('solid', fgColor='FFC7CE')
GREY = PatternFill('solid', fgColor='E7E6E6')
HEADER = PatternFill('solid', fgColor='1F4E78')

GOOD = ('price down', 'back in stock', 'below target')
BAD = ('price up', 'out of stock', 'error')

LATEST_COLUMNS = {
    'name': 'Product',
    'store': 'Store',
    'sku': 'SKU',
    'price': 'Price',
    'currency': 'Currency',
    'regular_price': 'Regular price',
    'discount': 'Discount %',
    'previous_price': 'Previous price',
    'change': 'Change',
    'change_pct': 'Change %',
    'in_stock': 'In stock',
    'stock_qty': 'Stock qty',
    'target_price': 'Target price',
    'status': 'Status',
    'url': 'URL',
    'error': 'Error',
}


def percent(new, old):
    if not new or not old:
        return None
    return round((new - old) / old * 100, 1)


def build_rows(rows, previous):
    # rows: this run, previous: {url: last check or None}
    out = []
    for row in rows:
        old = previous.get(row['url'])
        old_price = old['price'] if old else None
        price = row.get('price')
        regular = row.get('regular_price')
        out.append({
            **row,
            'previous_price': old_price,
            'change': round(price - old_price, 2) if price is not None and old_price is not None else None,
            'change_pct': percent(price, old_price),
            'discount': -percent(price, regular) if regular and price and regular > price else None,
            'in_stock': None if row.get('error') else ('yes' if row.get('in_stock') else 'no'),
        })
    return out


def style_sheet(ws, money_columns=()):
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = HEADER
        cell.alignment = Alignment(vertical='center')
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions

    for i, column in enumerate(ws.columns, start=1):
        width = max(len(str(c.value)) if c.value is not None else 0 for c in column)
        ws.column_dimensions[get_column_letter(i)].width = min(width + 2, 60)

    headers = [c.value for c in ws[1]]
    for name in money_columns:
        if name in headers:
            col = headers.index(name) + 1
            for row in ws.iter_rows(min_row=2, min_col=col, max_col=col):
                row[0].number_format = '#,##0.00'


def color_rows(ws):
    headers = [c.value for c in ws[1]]
    if 'Status' not in headers:
        return
    status_col = headers.index('Status')
    for row in ws.iter_rows(min_row=2):
        status = row[status_col].value or ''
        if 'error' in status:
            fill = GREY
        elif any(s in status for s in BAD):
            fill = RED
        elif any(s in status for s in GOOD):
            fill = GREEN
        else:
            continue
        for cell in row:
            cell.fill = fill


def to_frame(latest):
    df = pd.DataFrame(latest)[list(LATEST_COLUMNS)]
    # without this pandas turns the column into floats (45.0) because some stores have no stock count
    df['stock_qty'] = df['stock_qty'].astype('Int64')
    return df


def save_excel(path, latest, history):
    df = to_frame(latest).rename(columns=LATEST_COLUMNS)
    # "new" alone isn't a change, it just means it's the first time the product is checked
    changed = [set(status.split(', ')) - {'new'} != set() for status in df['Status']]
    changes = df[changed].drop(columns='Error')
    errors = df[df['Error'].notna()][['Product', 'Store', 'URL', 'Error']]
    df = df.drop(columns='Error')

    # one column per run, so you can see how a price moved over time
    history = history.assign(run=history['run'].str[:16].str.replace('T', ' '))
    pivot = history.pivot_table(index=['name', 'store'], columns='run', values='price', aggfunc='last')
    pivot = pivot.reset_index().rename(columns={'name': 'Product', 'store': 'Store'})

    money = ('Price', 'Regular price', 'Previous price', 'Change', 'Target price')
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Latest', index=False)
        changes.to_excel(writer, sheet_name='Changes', index=False)
        pivot.to_excel(writer, sheet_name='Price history', index=False)
        if len(errors):
            errors.to_excel(writer, sheet_name='Errors', index=False)

        for ws in writer.sheets.values():
            style_sheet(ws, money)
            color_rows(ws)
        for row in writer.sheets['Price history'].iter_rows(min_row=2, min_col=3):
            for cell in row:
                cell.number_format = '#,##0.00'


def save_csv(path, latest):
    to_frame(latest).to_csv(path, index=False, encoding='utf-8-sig')
