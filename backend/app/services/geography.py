"""Destination-country analytics and an offline Python-rendered SVG world map.

Natural Earth label points are cartographic anchors, never customer locations.
"""
from functools import lru_cache
from pathlib import Path
import json
import math
import unicodedata
from xml.etree import ElementTree as ET
from pyspark.sql import functions as F

ASSET = Path(__file__).resolve().parents[1] / 'assets/world_countries.json'
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
ALIASES = {
    'myanmar birmania': 'Myanmar', 'republica de gambia': 'Gambia',
    'macedonia': 'North Macedonia', 'suazilandia': 'eSwatini',
    'rumania': 'Romania', 'canada': 'Canada',
    'arabia saudi': 'Saudi Arabia',
}


def normalize(value):
    text = unicodedata.normalize('NFKD', str(value)).casefold()
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in text if not unicodedata.combining(c)).split())


def prepare_orders(raw, eligible):
    """Attach optional mapping metadata without changing eligible/model rows."""
    base = eligible.select('order_id', 'order_date', 'region', 'shipping_mode', 'delayed')
    if 'Order Country' not in raw.columns:
        return base.withColumn('destination_country', F.lit('Unknown'))
    destinations = raw.select(F.col('Order Id').cast('double').alias('order_id'),
        F.when(F.trim(F.col('Order Country')) != '', F.trim(F.col('Order Country'))).alias('country'))
    destinations = destinations.filter((F.col('order_id') > 0) & (F.col('order_id') == F.floor('order_id'))
        & (F.abs(F.col('order_id')) != float('inf'))).withColumn('order_id', F.col('order_id').cast('long'))
    destinations = destinations.groupBy('order_id').agg(
        F.countDistinct('country').alias('country_count'), F.first('country', ignorenulls=True).alias('country'))
    destinations = destinations.select('order_id', F.when(F.col('country_count') == 1, F.col('country'))
        .otherwise(F.lit('Unknown')).alias('destination_country'))
    return base.join(destinations, 'order_id', 'left').fillna('Unknown', subset=['destination_country'])


@lru_cache(maxsize=1)
def world():
    data = json.loads(ASSET.read_text(encoding='utf8'))
    index = {}
    # Country-level anchors win before map-unit fallbacks (e.g. UK vs Scotland).
    for record in [f['properties'] for f in data['features']] + data['additional_reference_points']:
        lon, lat = record.get('LABEL_X'), record.get('LABEL_Y')
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            continue
        if not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
            continue
        name = record.get('NAME_EN') or record['NAME']
        point = dict(country=name, code=record.get('GU_A3') or record.get('ADM0_A3') or name,
                     longitude=float(lon), latitude=float(lat))
        for key in ['NAME', 'NAME_EN', 'NAME_ES', 'NAME_LONG']:
            if record.get(key):
                index.setdefault(normalize(record[key]), point)
    return data, index


def resolve_country(label):
    _, index = world()
    key = normalize(label)
    if key in ALIASES:
        key = normalize(ALIASES[key])
    return index.get(key)


def mapped_data(rows):
    mapped, unmapped = {}, []
    total = delayed = 0
    for row in rows:
        count, late = int(row['total_orders']), int(row['delayed_orders'])
        if count <= 0 or not 0 <= late <= count:
            raise ValueError('Invalid country aggregate counts')
        total += count; delayed += late
        point = resolve_country(row['country'])
        if point is None:
            unmapped.append(dict(country=row['country'], total_orders=count, delayed_orders=late))
            continue
        record = mapped.setdefault(point['code'], dict(**point, source_labels=[], total_orders=0, delayed_orders=0))
        record['total_orders'] += count; record['delayed_orders'] += late
        record['source_labels'].append(row['country'])
    countries = sorted(mapped.values(), key=lambda row: (-row['delayed_orders'], row['country']))
    for row in countries:
        row['delay_rate'] = row['delayed_orders'] / row['total_orders']
    return dict(total_orders=total, delayed_orders=delayed, countries=countries,
                unmapped=unmapped, unmapped_orders=sum(r['total_orders'] for r in unmapped),
                unmapped_delayed_orders=sum(r['delayed_orders'] for r in unmapped))


def project(lon, lat):
    return (lon + 180) / 360 * 1200, 28 + (85 - lat) / 145 * 540


def element(parent, tag, text=None, **attributes):
    node = ET.SubElement(parent, f'{{{NS}}}{tag}', {k.replace('_', '-'): str(v) for k, v in attributes.items()})
    if text is not None: node.text = str(text)
    return node


@lru_cache(maxsize=1)
def basemap():
    data, _ = world()
    root = ET.Element(f'{{{NS}}}svg', {'viewBox':'0 0 1200 640', 'role':'img',
        'aria-label':'World map of delayed orders by destination country', 'preserveAspectRatio':'xMidYMid meet'})
    element(root, 'title', 'Historical late deliveries by destination country')
    element(root, 'desc', 'Bubble sizes show delayed eligible-order counts at country reference points, not exact shipment coordinates.')
    element(root, 'rect', width=1200, height=640, fill='#0a1d2b')
    defs = element(root, 'defs'); clip = element(defs, 'clipPath', id='world-clip')
    element(clip, 'rect', x=0, y=25, width=1200, height=552)
    land = element(root, 'g', clip_path='url(#world-clip)')
    for lat in [-30, 0, 30, 60]:
        y = project(0, lat)[1]
        element(land, 'line', x1=0, x2=1200, y1=y, y2=y, stroke='#223e50', stroke_width=.6)
    for feature in data['features']:
        if feature['properties']['NAME'] == 'Antarctica': continue
        geometry = feature['geometry']
        polygons = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
        parts = []
        for polygon in polygons:
            for ring in polygon:
                for i, (lon, lat) in enumerate(ring):
                    x, y = project(lon, lat)
                    parts.append(f'{"M" if i == 0 else "L"}{x:.1f},{y:.1f}')
                parts.append('Z')
        polygon = element(land, 'path', d=' '.join(parts), fill='#293e4d', stroke='#607482', stroke_width=.5, fill_rule='evenodd')
        element(polygon, 'title', feature['properties'].get('NAME_EN') or feature['properties']['NAME'])
    element(root, 'text', 'Delayed eligible orders by destination country', x=24, y=25, fill='#f4f7fa', font_family='Arial, sans-serif', font_size=17)
    element(root, 'text', 'Natural Earth 5.1.2 · country reference points · equirectangular projection', x=24, y=623, fill='#b6c8d5', font_family='Arial, sans-serif', font_size=12)
    return ET.tostring(root, encoding='unicode')


def render_map(population):
    root = ET.fromstring(basemap())
    group = element(root, 'g')
    maximum = max((r['delayed_orders'] for r in population['countries']), default=0)
    # Large bubbles first so small countries remain hoverable on top.
    for row in population['countries']:
        x, y = project(row['longitude'], row['latitude'])
        radius = max(2.0, 30 * math.sqrt(row['delayed_orders'] / maximum)) if maximum else 2.0
        circle = element(group, 'circle', cx=f'{x:.2f}', cy=f'{y:.2f}', r=f'{radius:.2f}',
                         fill='#f04a43' if row['delayed_orders'] else 'none', fill_opacity=.65,
                         stroke='#ffaaa4', stroke_width=1, tabindex=0)
        label = (f"{row['country']} ({', '.join(row['source_labels'])}): {row['delayed_orders']:,} delayed / "
                 f"{row['total_orders']:,} eligible orders · {row['delay_rate']:.1%} delay rate")
        if row['total_orders'] < 30: label += ' · small sample (n < 30)'
        element(circle, 'title', label)
        circle.set('aria-label', label)
    element(root, 'circle', cx=35, cy=593, r=6, fill='#f04a43', fill_opacity=.65)
    element(root, 'text', 'Circle area scales with delayed count (2 px minimum). Hover for rate and denominator.',
            x=50, y=597, fill='#e1eaf0', font_family='Arial, sans-serif', font_size=13)
    return ET.tostring(root, encoding='unicode')
