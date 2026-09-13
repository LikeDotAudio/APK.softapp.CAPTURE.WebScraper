# Part of the APK.audio project — http://APK.audio — made by Anthony Kuzub
# MIT Licence. Free, for everyone, for ever. Full text in LICENSE at the root.
"""Write the sidecar that says where a harvested file came from.

Owns: building and writing `<file>.provenance.json` beside a file a fetcher just
wrote, against `harvest-manifest.schema.json` in this directory.

MUST NOT:
  * be called for a DERIVATIVE. A manifest records a FETCH. The Markdown
    rendering of a page was not fetched -- it was converted from something that
    was -- and giving it its own manifest would assert a retrieval that never
    happened. Derivatives are covered by their source's manifest.
  * invent a field. Anything not observed at fetch time is `null`, and a record
    a human backfilled says `"provenance": "reconstructed"` rather than wearing
    a fetched one's clothes.
  * restate the schema. The required-field list is READ from the JSON file at
    import, so a field added there and not here is a hard failure on the next
    write instead of a sidecar that silently omits it.

THE NON-OBVIOUS ONE: the sidecar goes beside the file with the file's FULL name
plus the suffix -- `is-07.html.provenance.json`, never `is-07.provenance.json`.
Two files in one directory can differ only by extension, and stripping it makes
one manifest describe both.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "harvest-manifest.schema.json")
SUFFIX = ".provenance.json"

with open(SCHEMA_PATH, encoding="utf-8") as _f:
    SCHEMA = json.load(_f)

REQUIRED = tuple(SCHEMA["required"])
SCHEMA_VERSION = SCHEMA["properties"]["schemaVersion"]["const"]


def manifest_path(filepath):
    """The sidecar beside `filepath`. Full name plus suffix -- see the header."""
    return filepath + SUFFIX


def is_manifest(filepath):
    return filepath.endswith(SUFFIX)


def build(filepath, source_url, fetcher, http_status=None, content_type=None,
          provenance="fetched", note=None):
    """The manifest for a file already on disk. Digest and length are read back
    off the bytes rather than taken from the response, so what is recorded is
    what was actually written."""
    with open(filepath, "rb") as handle:
        payload = handle.read()

    record = {
        "schemaVersion": SCHEMA_VERSION,
        "source_url": source_url,
        # Z-suffixed UTC. `datetime.utcnow()` is naive and prints without the Z,
        # which is the shape the timestamp census counts as `civil-utc` -- a
        # moment that cannot say what zone it is in.
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "http_status": http_status,
        "content_type": content_type,
        "content_length": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "fetcher": fetcher,
        "provenance": provenance,
        "note": note,
    }

    missing = [key for key in REQUIRED if record.get(key) in (None, "")]
    if missing:
        # A manifest missing a required field is worse than none: it reads as a
        # record. Fail at the write rather than leave one behind.
        raise ValueError(f"manifest for {filepath} is missing {missing}")
    return record


def write(filepath, source_url, fetcher, **kwargs):
    """Build and write the sidecar. Returns its path, or None if the file it
    describes is unreadable -- a fetch that produced nothing gets no manifest."""
    try:
        record = build(filepath, source_url, fetcher, **kwargs)
    except (OSError, ValueError) as error:
        print(f"[provenance] no manifest for '{filepath}': {error}")
        return None

    target = manifest_path(filepath)
    try:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
            handle.write("\n")
    except OSError as error:
        print(f"[provenance] could not write '{target}': {error}")
        return None
    return target
