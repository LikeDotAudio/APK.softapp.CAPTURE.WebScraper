#!/usr/bin/env python3
"""Audit the scraped RecordingHacks mic pages to derive an empirical data model.

Walks every mic profile page and inventories the structures that a schema has
to cover: spec-table shapes, the column headers used, the 'Label: value'
prefixes that appear inside each column, sidebar sections, pricing markers,
tags, and per-page field coverage.

Output: audit_report.json (machine-readable) + a summary printed to stdout.
"""

import os
import re
import json
import sys
from collections import Counter, defaultdict

try:
    from bs4 import BeautifulSoup
except ImportError as _bs4_missing:      # said plainly at run time (ROAD-3522), not as a traceback
    BeautifulSoup = None
    _BS4_MISSING = _bs4_missing

SCRAPE_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'microphones')
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# A mic profile lives at microphones/<Brand>/<Model>. Brand listings are
# index.html, and everything under tag/ is a facet listing, not a profile.
def find_profile_pages(root):
    profiles, listings, other = [], [], []
    for dirpath, dirnames, filenames in os.walk(root):
        if os.sep + 'tag' in dirpath or dirpath.endswith(os.sep + 'tag'):
            continue
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            parts = rel.split(os.sep)
            if fn == 'index.html':
                listings.append(full)
            elif len(parts) == 2:
                profiles.append(full)
            else:
                other.append(full)
    return sorted(profiles), sorted(listings), sorted(other)


# get_text(strip=True) discards whitespace-only strings, so a bare '\n' marker
# would vanish and every line in a cell would collapse into one. Use a token
# that survives stripping, then convert it back to a newline.
NL = '@@NL@@'


def cell_text(node):
    """Readable text for a table cell, keeping <br>/<li> boundaries as newlines."""
    for br in node.find_all('br'):
        br.replace_with(NL)
    for li in node.find_all('li'):
        li.insert_before(NL)
    text = node.get_text(' ', strip=True)
    text = text.replace(NL, '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    return text.strip()


def split_lines(node):
    """The individual value lines inside a cell (one per <br> or <li>)."""
    raw = cell_text(node)
    lines = [line.strip(' ;') for line in raw.split('\n')]
    return [line for line in lines if line and line.lower() != 'n/a']


# 'Diaphragm diameter: 27.7mm' -> 'Diaphragm diameter'
LABEL_RE = re.compile(r'^([A-Za-z][A-Za-z0-9 /()\.\'&+-]{0,40}?)\s*:\s*(.+)$', re.S)


def main():
    root = os.path.normpath(SCRAPE_ROOT)
    profiles, listings, other = find_profile_pages(root)

    stats = {
        'counts': {
            'profile_pages': len(profiles),
            'brand_listing_pages': len(listings),
            'unexpected_depth_pages': len(other),
        },
        'brands': {},
    }

    # --- Inventories ---
    th_counter = Counter()                      # every distinct <th> label
    table_signatures = Counter()                # tuple of <th> labels per table
    tables_per_page = Counter()
    column_labels = defaultdict(Counter)           # th label -> 'Label:' prefixes inside it
    column_unlabeled = defaultdict(Counter)        # th label -> bare (unlabeled) value samples
    column_samples = defaultdict(list)             # th label -> raw cell samples
    colspan_seen = Counter()

    h3_counter = Counter()                      # section headings (main + sidebar)
    pricing_ids = Counter()                     # <li id=...> in Pricing & Availability
    pricing_samples = defaultdict(list)
    review_ids = Counter()                      # <li id=...> in Reviews & News / docs
    tag_counter = Counter()
    subtitle_counter = Counter()                # h2.sub, e.g. 'Cardioid Condenser Microphone'
    pattern_icon_counter = Counter()            # pattern icons next to the title
    document_heading_counter = Counter()             # '<Model> Documentation' style headings

    presence = Counter()                        # how many pages have each feature
    per_page = []                               # compact per-page record for coverage stats
    parse_failures = []

    for i, path in enumerate(profiles):
        rel = os.path.relpath(path, root)
        brand = rel.split(os.sep)[0]
        stats['brands'][brand] = stats['brands'].get(brand, 0) + 1

        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                html = f.read()
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as e:                                  # noqa: BLE001
            parse_failures.append({'page': rel, 'error': str(e)})
            continue

        column = soup.find('div', id='column')
        if not column:
            parse_failures.append({'page': rel, 'error': 'no div#column'})
            continue

        sidebar = column.find('div', id='dbsidebarone')
        record = {'page': rel, 'brand': brand, 'fields': []}

        # --- Title / subtitle / pattern icons ---
        h2s = column.find_all('h2')
        title = None
        for h2 in h2s:
            if 'sub' in (h2.get('class') or []):
                sub = h2.get_text(' ', strip=True)
                if sub:
                    subtitle_counter[sub] += 1
                    record['fields'].append('subtitle')
            elif title is None:
                title = h2.get_text(' ', strip=True)
                for image in h2.find_all('img'):
                    alt = image.get('alt') or image.get('title')
                    if alt: pattern_icon_counter[alt] += 1
        if title: record['fields'].append('title')

        # --- Sidebar sections ---
        for h3 in column.find_all('h3'):
            heading = h3.get_text(' ', strip=True)
            # Per-model documentation headings are named after the mic, e.g.
            # 'Fat Head Documentation'. Normalize so they group together.
            if heading.lower().endswith('documentation'):
                document_heading_counter[heading] += 1
                heading = '<MODEL> Documentation'
            h3_counter[heading] += 1

            # The <ul> following the heading holds that section's items.
            ul = h3.find_next_sibling('ul')
            if not ul: continue
            low = heading.lower()
            if 'pricing' in low or 'availability' in low:
                for li in ul.find_all('li'):
                    key = li.get('id') or '(no-id)'
                    pricing_ids[key] += 1
                    if len(pricing_samples[key]) < 12:
                        pricing_samples[key].append(li.get_text(' ', strip=True))
                record['fields'].append('pricing')
            elif 'documentation' in low or 'review' in low or 'news' in low:
                for li in ul.find_all('li'):
                    review_ids[li.get('id') or '(no-id)'] += 1

        # --- Tags ---
        tags = [a.get_text(strip=True)
                for li in column.find_all('li', class_='tagbutton')
                for a in li.find_all('a')]
        for t in tags: tag_counter[t] += 1
        if tags: record['fields'].append('tags')
        record['n_tags'] = len(tags)

        # --- Spec tables ---
        tables = column.find_all('table')
        tables_per_page[len(tables)] += 1
        record['n_tables'] = len(tables)
        if tables: record['fields'].append('spec_tables')

        for table in tables:
            rows = table.find_all('tr')
            if not rows: continue
            headers = [th.get_text(' ', strip=True) for th in rows[0].find_all('th')]
            if not headers: continue
            table_signatures[tuple(headers)] += 1
            for header in headers: th_counter[header] += 1

            # Value row: align tds to ths positionally.
            value_cells = rows[1].find_all('td') if len(rows) > 1 else []
            for cell in value_cells:
                if cell.get('colspan'): colspan_seen[cell.get('colspan')] += 1

            for index, header in enumerate(headers):
                if index >= len(value_cells): continue
                cell = value_cells[index]
                raw = cell_text(cell)
                if len(column_samples[header]) < 25 and raw:
                    column_samples[header].append(raw)
                for line in split_lines(cell):
                    m = LABEL_RE.match(line)
                    if m:
                        column_labels[header][m.group(1).strip()] += 1
                    else:
                        column_unlabeled[header][line[:60]] += 1

        # --- Other page features ---
        if column.find('blockquote'): record['fields'].append('quote')
        if column.find('a', rel='shadowbox'): record['fields'].append('photo')
        if re.search(r'Permalink:', column.get_text()): record['fields'].append('permalink')
        # Body prose = <p> directly under #column, excluding the bug-report footer
        paras = [p for p in column.find_all('p', recursive=False)
                 if 'bugblock' not in (p.get('class') or [])]
        if paras: record['fields'].append('description')
        # Count real charts only. A regex for 'freq' false-positives badly: the
        # YAHOO.freq tooltip script is emitted on nearly every page whether or
        # not a graph exists. A chart is a table headed 'Frequency Response'.
        n_graphs = 0
        for t in tables:
            for th in t.find_all('th'):
                if th.get_text(' ', strip=True).startswith('Frequency Response'):
                    n_graphs += 1
        record['n_frequency_graphs'] = n_graphs
        if n_graphs: record['fields'].append('frequency_graph')
        if column.find_all(['audio', 'source']): record['fields'].append('audio')
        if column.find('a', href=re.compile(r'/capsules/')): record['fields'].append('capsule_link')

        for f in record['fields']: presence[f] += 1
        per_page.append(record)

        if (i + 1) % 400 == 0:
            print(f'  ...{i + 1}/{len(profiles)} pages', file=sys.stderr)

    n = len(per_page)
    report = {
        'summary': stats['counts'],
        'pages_analyzed': n,
        'parse_failures': parse_failures,
        'brand_page_counts': dict(sorted(stats['brands'].items(), key=lambda kv: -kv[1])),
        'field_presence': {k: {'pages': v, 'pct': round(100.0 * v / n, 1)}
                           for k, v in presence.most_common()},
        'tables_per_page': dict(sorted(tables_per_page.items())),
        'table_signatures': [{'headers': list(k), 'pages': v}
                             for k, v in table_signatures.most_common()],
        'th_labels': dict(th_counter.most_common()),
        'column_value_labels': {header: dict(c.most_common())
                                for header, c in sorted(column_labels.items())},
        'column_unlabeled_values': {header: dict(c.most_common(30))
                                    for header, c in sorted(column_unlabeled.items())},
        'column_samples': dict(column_samples),
        'colspan_seen': dict(colspan_seen),
        'section_headings': dict(h3_counter.most_common()),
        'documentation_heading_examples': dict(document_heading_counter.most_common(20)),
        'pricing_list_ids': dict(pricing_ids.most_common()),
        'pricing_samples': dict(pricing_samples),
        'review_list_ids': dict(review_ids.most_common()),
        'subtitles': dict(subtitle_counter.most_common()),
        'pattern_icons': dict(pattern_icon_counter.most_common()),
        'tags': dict(tag_counter.most_common()),
    }

    out = os.path.join(OUT_DIR, 'audit_report.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f'\nPages: {n} profiles, {len(listings)} brand listings')
    print(f'Parse failures: {len(parse_failures)}')
    print(f'Distinct <th> labels: {len(th_counter)}')
    print(f'Distinct table signatures: {len(table_signatures)}')
    print(f'Distinct tags: {len(tag_counter)}')
    print(f'Distinct subtitles: {len(subtitle_counter)}')
    print(f'\nWrote {out}')


def _run():
    if BeautifulSoup is None:
        raise _BS4_MISSING
    if not os.path.isdir(SCRAPE_ROOT):
        fail('file_unreadable', detail=f'{os.path.normpath(SCRAPE_ROOT)}: no such folder', subject='scrape',
             fix=['Scrape RecordingHacks first (Scraper.py https://recordinghacks.com/microphones/), '
                  'so its pages sit beside this Datamodel folder.'])
    main()


if __name__ == '__main__':
    # A common mistake (bs4 / jsonschema not installed, no scrape beside this folder)
    # prints apkaudio_contracts.problems' problem_text, not a traceback: the
    # repository's apk_webscraper/cli_problems.py, three folders up.
    import sys
    sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')))
    from apk_webscraper.cli_problems import fail, guarded
    sys.exit(guarded(_run))
