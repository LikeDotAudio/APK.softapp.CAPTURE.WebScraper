# Audit of the RecordingHacks microphone scrape

Audit of `scrapes/microphones/` and the data model derived from it.
Every number below comes from parsing the saved HTML — nothing is estimated.
Machine-readable form: [`audit_report.json`](audit_report.json).

Reproduce with:

```bash
python3 audit_pages.py            # inventory the corpus  -> audit_report.json
python3 extract.py --validate     # extract + validate    -> microphones.json
```

---

## 1. What is in the scrape

| Page class | Files | Included in the model |
|---|---:|---|
| **Mic profile pages** (`<Brand>/<Model>`) | **1,761** | yes — one record each |
| Brand listing pages (`<Brand>/index.html`) | 158 | manufacturer names only |
| Tag facet pages (`tag/…`) | 2,045 | no — duplicate listing views |
| Top-level oddities (see §6) | 8 | no |
| **Total files** | **3,972** | |

157 manufacturers are represented. Largest: Audio-Technica (142 profiles),
AKG Acoustics (97), MXL (97), Shure (75), Sennheiser (55), Audix (52).

All 1,761 profile pages parsed with **0 failures** and all contain a `div#column`
main-content block, so the corpus is structurally uniform.

The site's own counter claims 1,659 mic profiles; the scrape holds 1,761 because
that counter excludes the 105 mic-set pages and some mod-shop entries.

### Crawl completeness

The crawl was stopped deliberately after all profile and listing pages were
captured, while it was still descending into `tag/<a>+<b>` facet pages. Those are
combinatorial pairings of the 393-term tag vocabulary that re-list mics already
captured — they add no data a model would need. **No mic profile is missing.**

---

## 2. Anatomy of a profile page

Two page shapes exist, and they need different treatment:

| | Mic profile | Mic set |
|---|---:|---:|
| Pages | 1,656 | 105 |
| Layout | `<th>`-headed specification tables | label/value `<td>` manifest |
| Marker | — | `Included Microphones` heading |

Feature coverage across all 1,761 pages:

| Element | Pages | % |
|---|---:|---:|
| Title (`<h2>`) | 1,761 | 100.0 |
| Subtitle (`<h2 class="sub">`) | 1,761 | 100.0 |
| Pricing & Availability | 1,761 | 100.0 |
| Body description | 1,761 | 100.0 |
| Specification tables | 1,761 | 100.0 |
| Tags | 1,656 | 94.0 |
| Primary photo | 1,653 | 93.9 |
| Permalink | 934 | 53.0 |
| Frequency-response chart | 664 | 37.7 |
| Pull-quote (`<blockquote>`) | 636 | 36.1 |
| Capsule reference link | 14 | 0.8 |

Sidebar/section headings, with page counts:

| Heading | Pages |
|---|---:|
| `Pricing & Availability` | 1,761 |
| `Tags` | 1,656 |
| `Specifications` | 1,656 |
| `<Model> Documentation` | 1,624 |
| `Reviews & News` | 979 |
| `Included Accessories` | 105 |
| `Included Microphones` | 105 |
| `<Model> Awards` | 146 |

Two heading families are **named after the model**, not fixed strings
(`Fat Head Documentation`, `SM58 Awards`), so they must be matched by suffix.

---

## 3. The specification tables

Tables per page: 2 (105 pages — sets), 4 (881), 5 (759), 6 (16).
There are **31 distinct table signatures** built from **36 distinct `<th>` labels**.

Four tables are near-universal:

| Signature | Pages |
|---|---:|
| `Weight` · `Length` · `Max Diameter` · `Interface(s)` | 1,656 |
| `Power Specifications` | 1,656 |
| `Pickup Patterns` · `Pads & Filters` | 1,572 |
| *transducer column* · `Impedance` · `SPL/Noise` | 1,656 |

**The third table's first column is the transducer discriminator** — this is the
single most useful structural finding in the corpus:

| First column | Pages | Implies |
|---|---:|---|
| `Capsule Dimensions` | 1,128 | condenser |
| `Coil Diameter` | 286 | dynamic |
| `Ribbon Construction` | 159 | ribbon |
| `Pads & Filters` | 83 | no capsule data published |

`Compatible Capsules` appears on 84 pages (modular bodies with detachable
capsules). `Frequency Response - <Pattern>` tables hold charts rather than
values and are modeled separately.

### Value grammar inside each column

This is what the schema's typed fields are built from.

| Column | Structure | Counts |
|---|---|---|
| `Pickup Patterns` | pattern name line, then `(<sens> mV/Pa; <freq range>)`; repeats per pattern; optional `CHART` marker | Cardioid 793, Bidirectional 335, Omnidirectional 326, Hypercardioid 75, Supercardioid 72 |
| `Pads & Filters` | `Pad: -10dB (Via Switch)` / `Filter: 100Hz` | Filter 638, Pad 557 |
| `Capsule Dimensions` | labeled lines | Diaphragm diameter 592, Capsule diameter 457, Diaphragm gauge 371; 351 read only `Diameter n/a` |
| `Ribbon Construction` | part labeled, part prose (`50x5mm, 2-micron aluminum ribbon`) | Gauge 44, Length 38, Width 31 |
| `Impedance` | `<n> Ohms (<Low\|Medium\|High>)` | 200Ω 552, 150Ω 158, 50Ω 95, 100Ω 89 |
| `SPL/Noise` | labeled lines | Max SPL 1,189, Self-noise 866; 220 read only `SPL n/a` |
| `Weight` | `500g (17.64oz)` | metric + imperial |
| `Length` / `Max Diameter` | `213mm (8.39'')` | metric + imperial |
| `Interface(s)` | `<connector> (<count>)` | 3-pin XLR male 1,435; USB 51; 5-pin XLR 39 |
| `Power Specifications` | flag lines + labeled `Phantom voltage` | Requires phantom 899, Phantom voltage 807, tube PSU 254, battery 22+ |

**`Coil Diameter` reads `n/a` on all 286 pages that have it.** The site never
populates this column. It is modeled for completeness but will never carry data.

---

## 4. Tags, links, and media

**Tags** — 393 distinct terms, 9,574 assignments. Most frequent: `condenser`
(1,037), `side-address` (848), `large-diaphragm` (595), `transformerless` (568),
`end-address` (541), `transformer-coupled` (497), `multipattern` (291),
`dynamic` (291), `hpf` (268), `tube` (257). Full table in `audit_report.json`.

**Links** — 8,203 captured. The list-item `id` encodes the medium, which is worth
preserving because it distinguishes a manual PDF from a forum thread:

| `id` | Occurrences | Meaning |
|---|---:|---|
| `www` | 3,330 | web page |
| `pdf` | 1,831 | manual / spec sheet / FR analysis |
| `forum` | 155 | forum thread |
| `film` | 112 | video |
| `image` | 60 | image |

**Frequency graphs** — 664 pages, 933 charts. Each carries a site graph id
(`/frequency-graphs.php/0542`) and a rendered PNG
(`/images/graphs/_gen/small/0/0542.png`), so charts are addressable per pattern.

**Pattern icons** beside the title include two summary markers that are *not*
patterns and must not be parsed as such: `9 polar patterns` (80 pages) and
`continuously variable pattern selection` (44).

**Related microphones — the product-lineage graph.** 1,326 pages (75.3%) carry a
`ul.mictiles` strip under `Related Microphones` (1,199) or
`Related Microphone Sets` (95+). It yields **3,058 tiles, every one of which has
an editorial relationship note** in its `title` attribute:

> *"The SF-1 is the mono version of the SF-12."*
> *"The KM-69 was designed to reproduce the sound of the KM-84."*
> *"The 251-T is the three-pattern version of the 251 Au."*

This is the richest relational data on the site — an explicit, human-written
lineage graph across 1,761 products — and it is easy to lose: **the strip sits in
`div#content`, outside `div#column`**, so any extractor scoped to the main content
block drops all of it. It is modeled as top-level `related_microphones`.
Each strip also ends in a `li.mictile_vendor` "More \<Brand\> microphones" link,
which is not a product and is skipped.

**Mic sets** — all 105 use the same three accessory fields (`Stereo Bar`,
`Drum Rim Clamps`, `Case Style`) and per-member fields `Quantity in set`,
`Includes hard mount(s)`, `Includes shockmount(s)`, `Includes foam windscreen(s)`.
Singular and plural label variants both occur and must both be accepted.

---

## 5. Scrape quality issues found and fixed

Three defects in `Scraper.py` were found and corrected during this work; they are
listed here because they affected what the corpus contains:

1. **Scope gate rejected the seed URL** — `startswith` compared
   `…/microphones` against `…/microphones/`, ending the crawl before the first
   fetch.
2. **Mixed URL schemes lost pages** — the site links its own profiles as
   `//host/…`, `http://…` and `https://…`; the `http://` form failed the scope
   check and the others could be fetched twice.
3. **Pages overwrote each other** — when `/microphones/Cascade` existed as a file
   and `/microphones/Cascade/Fathead` needed `Cascade` as a directory, the
   listing page was migrated to `Cascade/index.html` and then the *mic* page was
   written over it. Every brand's mics would have collapsed into one file.

The corpus audited here was produced *after* these fixes, which is why all
1,761 profiles are present and distinct.

---

## 6. Remaining anomalies in the corpus

| Anomaly | Detail | Handling |
|---|---|---|
| Case-duplicate brand | `microphones/shure` and `microphones/Shure` are the same 75-mic listing under different casing | excluded; `Shure` is canonical |
| Mod-shop pages | 7 pages (`Hamptone`, `Oktavamod`, `Talking-Dog`, `Terry-Setter`, `Marik`, `Fox-Audio-Research`, `MicShop`) are mod/repair listings with 0 mic profiles | excluded from the model |
| Model name ≠ URL slug | `Alctron/HRM-10` is titled `… RM-10`; `AKG-Acoustics/C-747` is titled `C 747 (C 747 V11)` | manufacturer taken from the brand listing `<h2>`, model from the title remainder — never from the slug |
| Manufacturer name ≠ brand slug | slug `Alctron` → `Ningbo Alctron Electronics Co., Ltd.`; slug `797-Audio` → `Beijing 797 Audio Co. Ltd.` | same |
| Mic id trap | related-mic thumbnails appear **before** the page's own photo in the markup, so a document-wide `/images/mics/(\d+)/` match returns another mic's id (ADK Cremona-251-Au resolved to `01607`, its sibling 251-T, instead of `01705`) | id taken from the hero image inside `div#column` |
| Empty `Coil Diameter` | `n/a` on all 286 pages | modeled, always null |
| Unlabeled prose in `Ribbon Construction` | ~60 cells are free text | typed fields where parseable, `description` + `raw` otherwise |

---

## 7. The data model

[`microphone.schema.json`](microphone.schema.json) — JSON Schema (Draft 2020-12).
Top-level structure:

```
source              provenance: url, permalink, file, brand/model slug, mic_id
identity            manufacturer, manufacturer_url, model, full_name
classification      subtitle, product_type, transducer_type, is_tube,
                    is_multipattern, is_stereo, form_factor, pattern_icons, tags[]
pricing             msrp_raw, msrp_amount, currency, availability, notes[]
specifications      pickup_patterns[], pads[], filters[], capsule, coil, ribbon,
                    impedance, spl_noise, physical{weight,length,max_diameter},
                    interfaces[], power, compatible_capsules[], raw_tables[]
frequency_graphs[]  pattern, graph_id, image_url, compare_url, alt
related_microphones[]  name, url, relationship_note, image, is_set
content             description_text, description_html, quotes[], release_year
links               documentation[], reviews_news[], awards[],
                    related_products[], other[]
media               primary_photo, images[], capsule_links[]
set                 included_accessories, included_microphones[]   (sets only)
extraction          schema_version, unmapped_sections[], unmapped_columns[], warnings[]
```

Three design decisions worth stating:

- **Every parsed value keeps its `raw` string.** `impedance.ohms: 200` sits beside
  `impedance.raw: "200 Ohms (Low)"`. Normalization never destroys the source text.
- **`specifications.raw_tables` captures every spec table verbatim** — headers
  plus aligned cell text. This is the guarantee that the model fits everything:
  anything the typed fields do not recognize is still recoverable.
- **`extraction.unmapped_*` makes gaps loud.** If the site adds a column, it lands
  in `unmapped_columns` rather than being silently dropped.

Units are explicit in field names (`diaphragm_diameter_mm`, `self_noise_dba`,
`sensitivity_mv_pa`, `phantom_voltage_v`), so no unit ambiguity survives into
downstream use.

---

## 8. Validation result

`extract.py --validate` over the whole corpus:

```
Loaded 157 manufacturer names from brand listing pages
Extracted 1761 records -> microphones.json
Unmapped spec columns: none
Unmapped sections:     none
Warnings:              none

Schema validation: 1761/1761 records valid
All records conform to microphone.schema.json
```

Output: `microphones.json`, 22.7 MB, 1,761 records — 6,624 spec tables,
9,574 tag assignments, 8,203 links, 933 frequency charts, 3,058 annotated
related-product edges.

**Populated-value coverage.** Structural validity is not the same as data
presence, so this is what the fields actually contain. Percentages track the
publishing rate on the site, not extractor loss — each matches its §3 count.

| Field | Coverage | | Field | Coverage |
|---|---:|---|---|---:|
| `identity.model` | 100.0% | | `interfaces` ≥1 | 89.4% |
| `classification.subtitle` | 100.0% | | `pickup_patterns` ≥1 | 87.8% |
| `content.description` | 100.0% | | `pricing.msrp_amount` | 87.2% |
| `links.related_products` | 99.8% | | ↳ with freq range | 83.7% |
| `media.primary_photo` | 99.3% | | ↳ with sensitivity | 78.3% |
| `tags` ≥1 | 94.0% | | `impedance.ohms` | 76.4% |
| `links.documentation` | 90.8% | | `physical.length.mm` | 75.8% |
| `related_microphones` ≥1 | 75.3% | | `physical.weight.grams` | 73.1% |
| `spl_noise.max_spl_db` | 67.5% | | | |
| `links.reviews_news` | 55.4% | | `power.requires_phantom` | 51.1% |
| `content.release_year` | 50.5% | | `spl_noise.self_noise_dba` | 49.2% |
| `power.phantom_voltage` | 45.8% | | `frequency_graphs` ≥1 | 37.7% |
| `content.quotes` | 36.1% | | `capsule.diaphragm_diameter` | 33.6% |
| `pricing` discontinued | 28.9% | | `filters` ≥1 | 26.9% |
| `pads` ≥1 | 25.3% | | `ribbon` block | 9.0% |
| `links.awards` | 8.3% | | `set` manifest | 6.0% |
| `compatible_capsules` | 4.8% | | | |

Derived transducer classification: condenser 1,194 · dynamic 286 · ribbon 160 ·
boundary 15 · hybrid 1 · unknown 105. The 105 `unknown` are exactly the mic-set
pages, whose subtitles (`Stereo Mic Set`) name no transducer — correct rather
than missing, since a set can mix types.

---

## 9. Files

| File | Purpose |
|---|---|
| `AUDIT.md` | this document |
| `audit_pages.py` | corpus inventory script |
| `audit_report.json` | full machine-readable inventory (all 393 tags, 81 subtitles, 31 table signatures, per-column value frequencies) |
| `microphone.schema.json` | the data model, JSON Schema Draft 2020-12 |
| `extract.py` | HTML → conforming JSON, with `--validate` |
| `microphones.json` | all 1,761 extracted records |
