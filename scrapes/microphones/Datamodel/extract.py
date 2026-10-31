#!/usr/bin/env python3
"""Extract every scraped RecordingHacks mic profile into microphone.schema.json form.

Usage:
    python3 extract.py                 # extract all pages -> microphones.json
    python3 extract.py --validate      # also validate every record against the schema
    python3 extract.py --limit 50      # extract a sample

The extractor is deliberately conservative: anything it cannot type is preserved
verbatim (specifications.raw_tables, *.raw, links.other, extraction.unmapped_*)
so a record never loses page content.
"""

import os
from urllib.parse import unquote
import re
import json
import argparse
from collections import Counter

from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
SCRAPE_ROOT = os.path.normpath(os.path.join(HERE, '..', 'microphones'))
SCHEMA_PATH = os.path.join(HERE, 'microphone.schema.json')
SCHEMA_VERSION = '1.0.0'
SITE = 'https://recordinghacks.com'

NL = '@@NL@@'   # Survives get_text(strip=True), unlike a bare newline

PATTERN_BASES = [
    'Wide Cardioid', 'Hypercardioid', 'Supercardioid', 'Cardioid',
    'Omnidirectional', 'Bidirectional', 'Shotgun', 'X/Y Stereo',
    'Mid-Side Stereo', 'Blumlein', 'Binaural',
]


# --------------------------------------------------------------------------
# text helpers
# --------------------------------------------------------------------------

def cell_text(node):
    """Cell text with <br> and <li> boundaries preserved as newlines."""
    node = BeautifulSoup(str(node), 'html.parser')     # work on a copy
    for br in node.find_all('br'):
        br.replace_with(NL)
    for li in node.find_all('li'):
        li.insert_before(NL)
    text = node.get_text(' ', strip=True)
    text = text.replace(NL, '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    return text.strip()


def lines_of(node):
    return [line.strip(' ;,') for line in cell_text(node).split('\n') if line.strip(' ;,')]


def number(s):
    """First number in a string, or None."""
    if s is None: return None
    m = re.search(r'-?\d+(?:\.\d+)?', str(s).replace(',', ''))
    return float(m.group()) if m else None


def as_int(s):
    v = number(s)
    return int(v) if v is not None and float(v).is_integer() else None


def abs_url(u):
    """Resolve the site's mixed //host, /path and http:// link forms."""
    if not u: return None
    u = u.strip()
    if u.startswith('//'): return 'https:' + u
    if u.startswith('/'):  return SITE + u
    if u.startswith('http://recordinghacks.com'):
        return 'https://' + u[len('http://'):]
    return u


def is_internal(u):
    return bool(u) and 'recordinghacks.com' in u


def nn(s):
    """Normalize a cell value, treating the site's n/a markers as absent."""
    if s is None: return None
    s = s.strip()
    return None if not s or s.lower() in ('n/a', 'n/a.', 'none') else s


# --------------------------------------------------------------------------
# specification column parsers
# --------------------------------------------------------------------------

def parse_pickup_patterns(cell):
    """'Cardioid\\n(18.8 mV/Pa; 20 - 20,000 Hz)' -> one entry per pattern.

    The cell alternates a pattern name line with a parenthesized measurement
    line, and may carry a leading 'CHART' marker when a graph exists.
    """
    out = []
    current = None
    for line in lines_of(cell):
        had_chart = 'CHART' in line
        line = line.replace('CHART', '').strip()
        if not line: continue

        if line.startswith('('):
            # Measurement line belonging to the pattern above it
            if current is None:
                current = {'pattern': 'Unspecified', 'raw': line, 'has_graph': had_chart}
                out.append(current)
            body = line.strip('()')
            sens, freq = None, None
            parts = [p.strip() for p in body.split(';')]
            for p in parts:
                if 'mV/Pa' in p:
                    sens = number(p.replace('n/a', ''))
                elif 'Hz' in p or re.search(r'\d\s*-\s*\d', p):
                    freq = p
            current['sensitivity_mv_pa'] = sens
            fr = {'low_hz': None, 'high_hz': None, 'raw': freq}
            if freq:
                ns = re.findall(r'[\d.,]+', freq.replace(',', ''))
                if len(ns) >= 2:
                    fr['low_hz'], fr['high_hz'] = float(ns[0]), float(ns[1])
            current['frequency_response'] = fr
            current['raw'] = (current.get('raw', '') + ' ' + line).strip()
            if had_chart: current['has_graph'] = True
            current = None
        else:
            base, variant = None, None
            for b in PATTERN_BASES:
                if line.lower().startswith(b.lower()):
                    base = b
                    rest = line[len(b):].strip()
                    m = re.match(r'^\((.*)\)$', rest)
                    variant = (m.group(1) if m else rest) or None
                    if variant: variant = variant.strip('“”"\'')
                    break
            current = {
                'pattern': line, 'pattern_base': base, 'pattern_variant': variant,
                'has_graph': had_chart, 'raw': line,
            }
            out.append(current)
    return out


def parse_pads_filters(cell):
    pads, filters = [], []
    for line in lines_of(cell):
        m = re.match(r'^(Pad|Filter)\s*:\s*(.+)$', line, re.I)
        if not m: continue
        kind, body = m.group(1).lower(), m.group(2).strip()

        mech = None
        mm = re.search(r'\(([^)]*(?:Switch|Remote|switch|remote|Software|App)[^)]*)\)', body)
        if mm:
            mech = mm.group(1).strip()
            body = body.replace(mm.group(0), '').strip()

        entry = {'raw': line, 'mechanism': mech, 'value_db': None,
                 'frequency_hz': None, 'slope': None}
        sl = re.search(r'-?\d+(?:\.\d+)?\s*dB\s*/\s*oct(?:ave)?', body, re.I)
        if sl: entry['slope'] = sl.group().strip()

        if kind == 'pad':
            d = re.search(r'-?\d+(?:\.\d+)?(?=\s*dB)', body)
            entry['value_db'] = float(d.group()) if d else None
            pads.append(entry)
        else:
            f = re.search(r'(\d[\d,.]*)\s*(k?)Hz', body, re.I)
            if f:
                v = float(f.group(1).replace(',', ''))
                entry['frequency_hz'] = v * 1000 if f.group(2).lower() == 'k' else v
            filters.append(entry)
    return pads, filters


def labeled(cell):
    """{'Diaphragm diameter': '27.7mm', ...} for 'Label: value' lines."""
    out = {}
    extras = []
    for line in lines_of(cell):
        m = re.match(r'^([A-Za-z][A-Za-z0-9 /()\'&+.-]{0,40}?)\s*:\s*(.+)$', line)
        if m:
            out[m.group(1).strip().lower()] = m.group(2).strip()
        else:
            extras.append(line)
    return out, extras


def parse_capsule(cell):
    lab, _ = labeled(cell)
    return {
        'diaphragm_diameter_mm': number(nn(lab.get('diaphragm diameter'))),
        'capsule_diameter_mm': number(nn(lab.get('capsule diameter'))),
        'diaphragm_gauge_microns': number(nn(lab.get('diaphragm gauge'))),
        'raw': cell_text(cell),
    }


def parse_ribbon(cell):
    lab, extras = labeled(cell)
    raw = cell_text(cell)
    description = ' '.join(extras) or None
    mat = None
    mm = re.search(r'(aluminum|aluminium|nanofilm|titanium|nickel|duraluminum|steel)', raw, re.I)
    if mm: mat = mm.group(1).lower()
    return {
        'length_mm': number(nn(lab.get('length'))),
        'width_mm': number(nn(lab.get('width'))),
        'gauge_microns': number(nn(lab.get('gauge'))),
        'material': mat,
        'description': description,
        'raw': raw,
    }


def parse_impedance(cell):
    raw = cell_text(cell)
    cat = None
    m = re.search(r'\((Low|Medium|High)\)', raw, re.I)
    if m: cat = m.group(1).capitalize()
    return {'ohms': number(nn(raw)), 'category': cat, 'raw': raw}


def parse_spl_noise(cell):
    lab, _ = labeled(cell)
    spl = nn(lab.get('max spl'))
    noise = nn(lab.get('self-noise')) or nn(lab.get('self noise'))
    return {
        'max_spl_db': number(spl),
        'max_spl_note': spl if spl and number(spl) is None else None,
        'self_noise_dba': number(noise),
        'self_noise_note': noise if noise and number(noise) is None else None,
        'raw': cell_text(cell),
    }


def parse_dimension(cell):
    raw = cell_text(cell)
    v = nn(raw)
    if not v: return {'mm': None, 'inches': None, 'raw': raw}
    mm = re.search(r'([\d.,]+)\s*mm', v)
    inch = re.search(r'\(([\d.,]+)', v)
    return {'mm': number(mm.group(1)) if mm else None,
            'inches': number(inch.group(1)) if inch else None, 'raw': raw}


def parse_mass(cell):
    raw = cell_text(cell)
    v = nn(raw)
    if not v: return {'grams': None, 'ounces': None, 'raw': raw}
    g = re.search(r'([\d.,]+)\s*g', v)
    oz = re.search(r'\(([\d.,]+)\s*oz', v)
    return {'grams': number(g.group(1)) if g else None,
            'ounces': number(oz.group(1)) if oz else None, 'raw': raw}


def parse_interfaces(cell):
    out = []
    for line in lines_of(cell):
        if not nn(line): continue
        m = re.match(r'^(.*?)\s*\((\d+)\)\s*$', line)
        if m:
            out.append({'connector': m.group(1).strip(),
                        'count': int(m.group(2)), 'raw': line})
        else:
            out.append({'connector': line, 'count': None, 'raw': line})
    return out


def parse_power(cell):
    out = {'requires_phantom_power': False, 'phantom_voltage_v': [],
           'includes_tube_power_supply': False, 'has_battery_compartment': False,
           'battery_type': None, 'other': [], 'raw': cell_text(cell)}
    for line in lines_of(cell):
        low = line.lower()
        if 'requires phantom power' in low:
            out['requires_phantom_power'] = True
        elif low.startswith('phantom voltage'):
            out['phantom_voltage_v'] = [float(v) for v in
                                        re.findall(r'\d+(?:\.\d+)?', line)]
        elif 'tube power supply' in low:
            out['includes_tube_power_supply'] = True
        elif 'battery compartment' in low:
            out['has_battery_compartment'] = True
            m = re.search(r'\(([^)]+)\)', line)
            if m: out['battery_type'] = m.group(1).strip()
        elif nn(line):
            out['other'].append(line)
    return out


def parse_compatible_capsules(cell):
    out = []
    for line in lines_of(cell):
        if not nn(line): continue
        pat = next((b for b in PATTERN_BASES if b.lower() in line.lower()), None)
        sens = None
        ms = re.search(r'Sensitivity\s*:\s*([\d.]+)', line)
        if ms: sens = float(ms.group(1))
        dia = None
        md = re.search(r'([\d.]+)\s*mm', line)
        if md: dia = float(md.group(1))
        out.append({'name': line.split(' capsule')[0].strip(), 'url': None,
                    'pattern': pat, 'diameter_mm': dia,
                    'sensitivity_mv_pa': sens, 'raw': line})
    return out


COLUMN_DISPATCH = {
    'Pickup Patterns': 'pickup_patterns',
    'Pads & Filters': 'pads_filters',
    'Capsule Dimensions': 'capsule',
    'Coil Diameter': 'coil',
    'Ribbon Construction': 'ribbon',
    'Impedance': 'impedance',
    'SPL/Noise': 'spl_noise',
    'Weight': 'weight',
    'Length': 'length',
    'Max Diameter': 'max_diameter',
    'Interface(s)': 'interfaces',
    'Power Specifications': 'power',
    'Compatible Capsules': 'compatible_capsules',
}


# --------------------------------------------------------------------------
# page-level extraction
# --------------------------------------------------------------------------

def link_from(a, list_id=None):
    url = abs_url(a.get('href'))
    internal = is_internal(url)
    lt = list_id if list_id in ('www', 'pdf', 'forum', 'film', 'image') else None
    if lt is None and internal: lt = 'internal'
    return {'title': a.get_text(' ', strip=True) or None, 'url': url,
            'link_type': lt, 'is_internal': internal}


def image_from(image, full_url=None):
    if image is None: return None
    return {
        'thumb_url': abs_url(image.get('src')),
        'full_url': abs_url(full_url),
        'alt': image.get('alt') or image.get('title') or None,
        'width': as_int(image.get('width')),
        'height': as_int(image.get('height')),
    }


def classify(subtitle, tags, product_type):
    low = (subtitle or '').lower()
    tagset = {t['name'].lower() for t in tags}

    if 'condenser' in low or 'condenser' in tagset:      tt = 'condenser'
    elif 'ribbon' in low or 'ribbon' in tagset:          tt = 'ribbon'
    elif 'dynamic' in low or 'dynamic' in tagset:        tt = 'dynamic'
    elif 'boundary' in low:                              tt = 'boundary'
    elif 'carbon' in low:                                tt = 'carbon'
    elif 'combination' in low:                           tt = 'combination'
    elif 'hybrid' in low:                                tt = 'hybrid'
    else:                                                tt = 'unknown'

    form = None
    for cand in ('side-address', 'end-address', 'pencil', 'handheld',
                 'boundary', 'shotgun', 'lavalier', 'headworn', 'boom'):
        if cand in tagset or cand.replace('-', ' ') in low:
            form = 'pencil' if cand == 'pencil-mic' else cand
            break
    if form is None and 'pencil' in low: form = 'pencil'

    return {
        'transducer_type': tt,
        'is_tube': 'tube' in low or 'tube' in tagset or 'valve' in low,
        'is_multipattern': 'multi-pattern' in low or 'multipattern' in tagset,
        'is_stereo': 'stereo' in low or 'stereo' in tagset,
        'form_factor': form,
    }


def load_brand_names(root):
    """brand slug -> manufacturer display name, from each brand's listing page.

    The listing page's <h2> is authoritative. Deriving the name from the profile
    title instead is unreliable: 'Alctron/HRM-10' is titled 'Ningbo Alctron
    Electronics Co., Ltd. RM-10', where neither the maker nor the model matches
    the URL slug.
    """
    names = {}
    for dirpath, _, filenames in os.walk(root):
        if 'index.html' not in filenames: continue
        rel = os.path.relpath(dirpath, root)
        if rel in ('.', 'tag') or os.sep in rel: continue
        try:
            with open(os.path.join(dirpath, 'index.html'),
                      encoding='utf-8', errors='replace') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            column = soup.find('div', id='column')
            h2 = column.find('h2') if column else None
            if h2:
                names[rel] = h2.get_text(' ', strip=True)
        except OSError:
            continue
    return names


def extract(path, root, brand_names=None):
    brand_names = brand_names or {}
    rel = os.path.relpath(path, root)
    # Names on disk are percent-encoded where Windows refuses a character
    # (`d%3Afacto`, engine.portable_segment); the slug is the URL's.
    brand_slug, model_slug = (unquote(part) for part in (rel.split(os.sep)[0], rel.split(os.sep)[-1]))

    with open(path, encoding='utf-8', errors='replace') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    column = soup.find('div', id='column')
    if column is None:
        raise ValueError('no div#column')

    warnings, unmapped_sections, unmapped_columns = [], [], []
    sidebar = column.find('div', id='dbsidebarone')

    # --- title, subtitle, pattern icons -----------------------------------
    full_name, subtitle, icons = None, None, []
    for h2 in column.find_all('h2'):
        if 'sub' in (h2.get('class') or []):
            subtitle = subtitle or h2.get_text(' ', strip=True)
        elif full_name is None:
            for image in h2.find_all('img'):
                v = image.get('alt') or image.get('title')
                if v: icons.append(v)
            full_name = h2.get_text(' ', strip=True)

    # --- manufacturer / model --------------------------------------------
    # Titles read '<manufacturer> <model>'. Split on the manufacturer name from
    # the brand listing page, which is authoritative; only if that name is not a
    # prefix of the title do we fall back to matching the URL slug.
    manufacturer = brand_names.get(brand_slug)
    model = None

    if manufacturer and full_name and full_name.startswith(manufacturer):
        model = full_name[len(manufacturer):].strip()

    if not model and full_name:
        loose = re.sub(r'[^a-z0-9]', '', model_slug.lower())
        for i in range(len(full_name)):
            if re.sub(r'[^a-z0-9]', '', full_name[i:].lower()) == loose:
                manufacturer = manufacturer or (full_name[:i].strip() or None)
                model = full_name[i:].strip()
                break

    if not model:
        model = model_slug.replace('-', ' ')
        warnings.append('model name inferred from URL slug')
    if not manufacturer:
        manufacturer = brand_slug.replace('-', ' ')
        warnings.append('manufacturer inferred from URL slug')

    # Take the mic id from this page's own photo. Searching the whole document
    # would instead match the first 'Related Microphones' thumbnail, which
    # belongs to a different mic and appears earlier in the markup.
    mic_id = None
    hero = column.find('img', src=re.compile(r'/images/mics/\d+/'))
    if hero:
        mic_id = re.search(r'/images/mics/(\d+)/', hero['src']).group(1)

    # --- sidebar sections -------------------------------------------------
    pricing = {'msrp_raw': 'MSRP: n/a', 'msrp_amount': None, 'currency': None,
               'availability': 'unknown', 'notes': []}
    links = {'documentation': [], 'reviews_news': [], 'awards': [],
             'related_products': [], 'other': []}
    tags = []

    for h3 in column.find_all('h3'):
        heading = h3.get_text(' ', strip=True)
        low = heading.lower()
        ul = h3.find_next_sibling('ul')

        if 'pricing' in low or 'availability' in low:
            if ul:
                for li in ul.find_all('li'):
                    text = li.get_text(' ', strip=True)
                    lid = li.get('id')
                    if lid == 'money':
                        pricing['msrp_raw'] = text
                        amt = re.search(r'([\d,]+(?:\.\d+)?)', text)
                        if amt and 'n/a' not in text.lower():
                            pricing['msrp_amount'] = float(amt.group(1).replace(',', ''))
                            pricing['currency'] = 'USD' if '$' in text else None
                    elif lid == 'none':
                        pricing['availability'] = 'discontinued'
                    elif text:
                        pricing['notes'].append(text)
                if pricing['availability'] == 'unknown':
                    pricing['availability'] = 'current'
        elif low == 'tags':
            continue                                   # handled below
        elif low == 'specifications':
            continue                                   # handled below
        elif low.endswith('documentation'):
            if ul:
                for li in ul.find_all('li'):
                    for a in li.find_all('a'):
                        links['documentation'].append(link_from(a, li.get('id')))
        elif 'review' in low or 'news' in low:
            if ul:
                for li in ul.find_all('li'):
                    for a in li.find_all('a'):
                        links['reviews_news'].append(link_from(a, li.get('id')))
        elif low.endswith('awards'):
            if ul:
                for li in ul.find_all('li'):
                    for a in li.find_all('a'):
                        links['awards'].append(link_from(a, li.get('id')))
        elif low in ('included accessories', 'included microphones'):
            continue                                   # handled in set section
        else:
            unmapped_sections.append(heading)
            if ul:
                for a in ul.find_all('a'):
                    links['other'].append(link_from(a, None))

    for li in column.find_all('li', class_='tagbutton'):
        for a in li.find_all('a'):
            tags.append({'name': a.get_text(strip=True), 'url': abs_url(a.get('href'))})

    # --- product type -----------------------------------------------------
    is_set = bool(column.find(
        lambda t: t.name == 'h3' and 'Included Microphones' in t.get_text()))
    product_type = 'set' if is_set else 'microphone'

    # --- specification tables --------------------------------------------
    specs = {'raw_tables': []}
    freq_graphs = []

    for table in column.find_all('table'):
        rows = table.find_all('tr')
        if not rows: continue

        # A table may hold several (header row, value row) pairs.
        pending_headers = None
        for tr in rows:
            ths = tr.find_all('th')
            if ths:
                pending_headers = [th.get_text(' ', strip=True) for th in ths]
                continue
            tds = tr.find_all('td')
            if not tds or pending_headers is None:
                continue

            headers, cells = pending_headers, tds
            pending_headers = None

            # Frequency-response tables carry a graph, not spec values.
            if headers and headers[0].startswith('Frequency Response'):
                pattern = re.sub(r'^Frequency Response\s*-\s*', '', headers[0])
                pattern = re.sub(r'Click Graph to Compare!\s*$', '', pattern).strip()
                image = cells[0].find('img')
                a = cells[0].find('a')
                gid = None
                if a and a.get('href'):
                    mg = re.search(r'/frequency-graphs\.php/(\w+)', a['href'])
                    if mg: gid = mg.group(1)
                freq_graphs.append({
                    'pattern': pattern, 'graph_id': gid,
                    'image_url': abs_url(image.get('src')) if image else None,
                    'compare_url': abs_url(a.get('href')) if a else None,
                    'alt': (image.get('alt') if image else None) or None,
                })
                continue

            specs['raw_tables'].append(
                {'headers': headers, 'cells': [cell_text(c) for c in cells]})

            for index, height in enumerate(headers):
                if index >= len(cells): continue
                cell = cells[index]
                key = COLUMN_DISPATCH.get(height)
                if key is None:
                    unmapped_columns.append(height)
                    continue
                if key == 'pickup_patterns':
                    specs.setdefault('pickup_patterns', []).extend(parse_pickup_patterns(cell))
                elif key == 'pads_filters':
                    p, f = parse_pads_filters(cell)
                    specs.setdefault('pads', []).extend(p)
                    specs.setdefault('filters', []).extend(f)
                elif key == 'capsule':
                    specs['capsule'] = parse_capsule(cell)
                elif key == 'coil':
                    specs['coil'] = {'diameter_mm': number(nn(cell_text(cell))),
                                     'raw': cell_text(cell)}
                elif key == 'ribbon':
                    specs['ribbon'] = parse_ribbon(cell)
                elif key == 'impedance':
                    specs['impedance'] = parse_impedance(cell)
                elif key == 'spl_noise':
                    specs['spl_noise'] = parse_spl_noise(cell)
                elif key in ('weight', 'length', 'max_diameter'):
                    phys = specs.setdefault('physical', {})
                    phys[key] = parse_mass(cell) if key == 'weight' else parse_dimension(cell)
                elif key == 'interfaces':
                    specs.setdefault('interfaces', []).extend(parse_interfaces(cell))
                elif key == 'power':
                    specs['power'] = parse_power(cell)
                elif key == 'compatible_capsules':
                    specs.setdefault('compatible_capsules', []).extend(
                        parse_compatible_capsules(cell))

    # --- body content -----------------------------------------------------
    paras = [p for p in column.find_all('p', recursive=False)
             if 'bugblock' not in (p.get('class') or [])]
    description_html = ''.join(str(p) for p in paras)
    description_text = re.sub(r'\s+\n', '\n',
                              '\n\n'.join(p.get_text(' ', strip=True) for p in paras)).strip()

    quotes = []
    for bq in column.find_all('blockquote'):
        cite = bq.find('cite')
        cite_text = cite.get_text(' ', strip=True) if cite else None
        if cite: cite.extract()
        quotes.append({'cite': cite_text, 'text': bq.get_text(' ', strip=True)})

    year = None
    my = re.search(r'released in (\d{4})', description_text)
    if my: year = int(my.group(1))

    permalink = None
    pl = column.find('a', href=re.compile(r'/microphones/'))
    for a in column.find_all('a', href=True):
        previous = (a.previous_sibling or '')
        if isinstance(previous, str) and 'Permalink' in previous:
            permalink = abs_url(a['href'])
            break
    if permalink is None and 'Permalink:' in description_text:
        warnings.append('permalink text present but link not resolved')

    # In-body cross references to other mic profiles
    for p in paras:
        for a in p.find_all('a', href=True):
            u = abs_url(a['href'])
            if u and re.search(r'/microphones/[^/]+/[^/]+$', u):
                links['related_products'].append(link_from(a, None))

    # --- media ------------------------------------------------------------
    primary = None
    if sidebar:
        sb_a = sidebar.find('a', rel='shadowbox')
        if sb_a:
            primary = image_from(sb_a.find('img'), sb_a.get('href'))
        elif sidebar.find('img'):
            primary = image_from(sidebar.find('img'))

    images, seen = [], {primary['thumb_url'] if primary else None}
    for image in column.find_all('img'):
        record = image_from(image)
        if record and record['thumb_url'] not in seen:
            seen.add(record['thumb_url'])
            images.append(record)

    capsule_links = [link_from(a) for a in column.find_all('a', href=re.compile(r'/capsules/'))]

    # --- set manifest -----------------------------------------------------
    set_object = None
    if is_set:
        set_object = {'included_accessories': {}, 'included_microphones': []}
        for h3 in column.find_all('h3'):
            low = h3.get_text(' ', strip=True).lower()
            table = h3.find_next('table')
            if table is None: continue
            if low == 'included accessories':
                keymap = {'stereo bar': 'stereo_bar',
                          'drum rim clamps': 'drum_rim_clamps',
                          'case style': 'case_style'}
                for tr in table.find_all('tr'):
                    tds = tr.find_all('td')
                    if len(tds) >= 2:
                        k = keymap.get(tds[0].get_text(strip=True).rstrip(':').lower())
                        if k:
                            # Keep the published text verbatim. 'None' is a real
                            # answer here ('Drum Rim Clamps: None' means none are
                            # included), so normalizing it to null would make it
                            # indistinguishable from an unstated field.
                            value = tds[1].get_text(' ', strip=True)
                            set_object['included_accessories'][k] = value or None
            elif low == 'included microphones':
                member = None
                for tr in table.find_all('tr'):
                    h4 = tr.find('h4')
                    if h4:
                        a = h4.find('a')
                        h5 = tr.find('h5')
                        member = {
                            'name': (a.get_text(' ', strip=True) if a
                                     else h4.get_text(' ', strip=True)),
                            'url': abs_url(a.get('href')) if a else None,
                            'subtitle': h5.get_text(' ', strip=True) if h5 else None,
                            'image': None, 'quantity_in_set': None,
                            'includes_hard_mounts': None,
                            'includes_shockmounts': None,
                            'includes_foam_windscreens': None,
                        }
                        set_object['included_microphones'].append(member)
                        continue
                    if member is None: continue
                    image = tr.find('img')
                    if image and member['image'] is None:
                        a = tr.find('a')
                        member['image'] = image_from(image, a.get('href') if a else None)
                    tds = tr.find_all('td')
                    for i in range(len(tds) - 1):
                        lab = tds[i].get_text(strip=True).rstrip(':').lower()
                        value = tds[i + 1].get_text(strip=True)
                        if lab == 'quantity in set':
                            member['quantity_in_set'] = as_int(value)
                        elif lab in ('includes hard mount', 'includes hard mounts'):
                            member['includes_hard_mounts'] = value.strip().lower() == 'yes'
                        elif lab in ('includes shockmount', 'includes shockmounts'):
                            member['includes_shockmounts'] = value.strip().lower() == 'yes'
                        elif lab in ('includes foam windscreen', 'includes foam windscreens'):
                            member['includes_foam_windscreens'] = value.strip().lower() == 'yes'

    # --- related microphones (tile strip) ---------------------------------
    # These tiles live in div#content, OUTSIDE div#column, so they are searched
    # from the document root rather than from the main-content block.
    related = []
    for ul in soup.find_all(class_='mictiles'):
        head = ul.find_previous(['h3', 'h4'])
        head_text = head.get_text(' ', strip=True) if head else ''
        is_set_group = 'set' in head_text.lower()
        for li in ul.find_all('li', class_='mictile'):
            a = li.find('a', href=True)
            if not a: continue
            span = a.find('span')
            image = a.find('img')
            related.append({
                'name': span.get_text(' ', strip=True) if span else None,
                'url': abs_url(a['href']),
                'relationship_note': a.get('title') or None,
                'image': image_from(image),
                'is_set': is_set_group,
            })

    derived = classify(subtitle, tags, product_type)

    return {
        'source': {
            'url': f'{SITE}/microphones/{brand_slug}/{model_slug}',
            'permalink': permalink,
            'scraped_file': rel.replace(os.sep, '/'),
            'brand_slug': brand_slug,
            'model_slug': model_slug,
            'mic_id': mic_id,
        },
        'identity': {
            'manufacturer': manufacturer,
            'manufacturer_url': f'{SITE}/microphones/{brand_slug}',
            'model': model,
            'full_name': full_name or f'{manufacturer} {model}',
        },
        'classification': {
            'subtitle': subtitle or '',
            'product_type': product_type,
            'pattern_icons': icons,
            'tags': tags,
            **derived,
        },
        'pricing': pricing,
        'specifications': specs,
        'frequency_graphs': freq_graphs,
        'related_microphones': related,
        'content': {
            'description_text': description_text,
            'description_html': description_html,
            'quotes': quotes,
            'release_year': year,
        },
        'links': links,
        'media': {
            'primary_photo': primary,
            'images': images,
            'capsule_links': capsule_links,
        },
        **({'set': set_object} if set_object is not None else {}),
        'extraction': {
            'schema_version': SCHEMA_VERSION,
            'unmapped_sections': sorted(set(unmapped_sections)),
            'unmapped_columns': sorted(set(unmapped_columns)),
            'warnings': warnings,
        },
    }


def find_profiles(root):
    out = []
    for dirpath, _, filenames in os.walk(root):
        if os.sep + 'tag' in dirpath or dirpath.endswith(os.sep + 'tag'):
            continue
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            if fn == 'index.html': continue
            if len(os.path.relpath(full, root).split(os.sep)) == 2:
                out.append(full)
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--validate', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--out', default=os.path.join(HERE, 'microphones.json'))
    args = ap.parse_args()

    profiles = find_profiles(SCRAPE_ROOT)
    if args.limit: profiles = profiles[:args.limit]

    brand_names = load_brand_names(SCRAPE_ROOT)
    print(f'Loaded {len(brand_names)} manufacturer names from brand listing pages')

    records, failures = [], []
    for i, p in enumerate(profiles):
        try:
            records.append(extract(p, SCRAPE_ROOT, brand_names))
        except Exception as e:                                  # noqa: BLE001
            failures.append({'page': os.path.relpath(p, SCRAPE_ROOT), 'error': repr(e)})
        if (i + 1) % 400 == 0:
            print(f'  ...{i + 1}/{len(profiles)}')

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=1, ensure_ascii=False)
    print(f'\nExtracted {len(records)} records -> {args.out}')
    if failures:
        print(f'Extraction failures: {len(failures)}')
        for f_ in failures[:10]: print('  ', f_)

    # Coverage + leftovers, so gaps in the model are visible rather than silent.
    unmapped_cols = Counter()
    unmapped_secs = Counter()
    warns = Counter()
    for r in records:
        for c in r['extraction']['unmapped_columns']: unmapped_cols[c] += 1
        for s in r['extraction']['unmapped_sections']: unmapped_secs[s] += 1
        for w in r['extraction']['warnings']: warns[w] += 1
    print(f'Unmapped spec columns: {dict(unmapped_cols) or "none"}')
    print(f'Unmapped sections: {dict(unmapped_secs.most_common(5)) or "none"}')
    print(f'Warnings: {dict(warns) or "none"}')

    if args.validate:
        import jsonschema
        with open(SCHEMA_PATH, encoding='utf-8') as f:
            schema = json.load(f)
        validator = jsonschema.Draft202012Validator(schema)
        errs = []
        for r in records:
            for e in validator.iter_errors(r):
                errs.append((r['source']['scraped_file'],
                             '/'.join(str(x) for x in e.absolute_path), e.message))
        print(f'\nSchema validation: {len(records) - len({e[0] for e in errs})}'
              f'/{len(records)} records valid')
        if errs:
            print(f'{len(errs)} errors; first 20:')
            for e in errs[:20]: print('  ', e)
        else:
            print('All records conform to microphone.schema.json')


if __name__ == '__main__':
    main()
