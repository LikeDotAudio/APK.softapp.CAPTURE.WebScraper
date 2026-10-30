# Part of the APK.audio project — http://APK.audio — made by Anthony Kuzub
# MIT Licence. Free, for everyone, for ever. Full text in LICENSE at the root.
"""Mirror one website to Markdown under `scrapes/`, politely.

Owns: fetching a site's HTML, converting each page to Markdown with
`markdownify`, and writing it under `scrapes/<host>/` in a directory tree that
mirrors the URL path. Four worker threads, one queue of URLs, one queue of
Markdown to write.

MUST NOT, and each of these is a constant below rather than a suggestion:
  * exceed MAX_FILE_SIZE_MB (2) on any single fetch
  * drop below REQUEST_DELAY (0.5 s) between requests from a worker
  * run more than NUMBER_DOWNLOAD_THREADS (4) concurrently
  * fetch any URL whose path starts with a DISALLOWED_PATHS prefix
  * parse a NON_PAGE_EXTENSIONS target as HTML

THE NON-OBVIOUS ONE, and the mistake the next person will make: DISALLOWED_PATHS
is a TRANSCRIPTION OF ONE SPECIFIC SITE'S robots.txt -- a microphone database,
which is why `/mic_share`, `/microphones/tag/condenser` and
`/images/albumcovers/` are in it. It is therefore WRONG FOR ANY OTHER TARGET.
Pointing this at a new host without re-reading that host's robots.txt and
replacing the tuple is how this becomes an impolite crawler wearing a polite
User-Agent.

EVERY FETCH LEAVES A MANIFEST, AND ONLY A FETCH DOES. `provenance.write()` puts
a `<file>.provenance.json` beside each page and each media file as it is
written, carrying the source URL, retrieval time, status, length and digest. The
Markdown conversion gets NONE: it was not fetched, and a manifest on it would
assert a retrieval that never happened. PLAN-314.01.

"""
import os
import re
import time
import argparse
import requests
import threading
import queue
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from markdownify import markdownify

import provenance

# --- CONFIGURATION ---
MAX_FILE_SIZE_MB = 2
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) WebScraper/1.0 (personal archive)"
HEADERS = {"User-Agent": USER_AGENT}
REQUEST_DELAY = 0.5   # Seconds to pause after each request, to stay polite
NUMBER_DOWNLOAD_THREADS = 4

# The URL is what this is for. The trees already in `scrapes/` predate the
# manifests and record it only in the directory path -- `scrapes/is-07-MD/https:/
# specs.amwa.tv/is-07/...` -- and, because the tree mirrors the site's URL path,
# tag pages such as `tag/12at7+12ax7` become paths: 3,245 tracked paths under
# `scrapes/microphones*/` contain `|` or `+` (`git ls-files | grep -c '[|+]'`,
# 2026-10-30). A path is not a field; every new fetch also gets a manifest.

# What it writes is not source. `scrapes/` is 342 MB and 8,945 tracked files --
# other people's pages, kept on purpose as the EVENT/intake lane, named in the
# root `.ignore` so ripgrep and fd de-rank it (CLAUDE.md sections 4 and 1; the
# 3,245 paths under it with `|` or `+` must be quoted). Three files here are
# authored -- this one, `provenance.py` and `harvest-manifest.schema.json` -- and
# the ratio is the point: the tool is a rounding error in its own directory.

# Paths (relative to the site root) that robots.txt disallows, or that are not
# worth fetching. Checked against the URL path with startswith().
DISALLOWED_PATHS = (
    "/wp-admin/", "/wp-includes/", "/wp-images/", "/feed/", "/category/",
    "/internal/", "/scripts/", "/sendmessage.php", "/mic_share", "/page/",
    "/rnf", "/regional", "/images/albumcovers/",
    "/microphones/tag/condenser", "/microphones/tag/side-address",
)

# Link targets that are not pages, so should not be crawled as HTML.
NON_PAGE_EXTENSIONS = (
    ".pdf", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".mp3", ".wav", ".aif", ".aiff", ".mp4", ".mov", ".css", ".js", ".ico",
)

# --- GLOBAL VARIABLES ---
visited_urls = set()
visited_lock = threading.Lock() # visited_urls is touched by several threads
fs_lock = threading.Lock()      # Guards the file/directory conflict migration
md_queue = queue.Queue()
url_queue = queue.Queue() # Queue for URLs to be processed by download_page

def sanitize_folder_name(url_part):
    """Converts a URL part into a safe directory name."""
    safe_name = re.sub(r'[^a-zA-Z0-9]', '-', url_part) # Replace non-alphanumeric with hyphens
    safe_name = re.sub(r'-+', '-', safe_name)         # Replace multiple hyphens with a single hyphen
    return safe_name.strip('-')                       # Remove leading/trailing hyphens

def normalize_url(url):
    """Canonicalizes a URL so the same page is never fetched twice.

    Sites often mix 'http://', 'https://' and protocol-relative '//host/path'
    links to their own pages. Without collapsing those to one form, the scope
    check rejects valid pages and visited_urls fails to deduplicate.
    """
    parsed = urlparse(url)
    scheme = "https"                                  # Force one scheme
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."): netloc = netloc[4:] # Force one host spelling
    path = parsed.path.rstrip('/') or '/'             # Force one trailing-slash style
    return f"{scheme}://{netloc}{path}"

def is_in_scope(url, base_url):
    """True if `url` is a crawlable page at or below `base_url`."""
    base = base_url.rstrip('/')
    if url != base and not url.startswith(base + '/'):
        return False

    path = urlparse(url).path
    if any(path.startswith(p) for p in DISALLOWED_PATHS):
        return False
    if path.lower().endswith(NON_PAGE_EXTENSIONS):
        return False
    return True

def extract_main_content(soup):
    """Returns the page's main content, so boilerplate stays out of the Markdown.

    Without this, every one of the ~1800 pages contributes the same masthead,
    search form, ad slots and footer to the combined archive.
    """
    for junk in soup.find_all(['script', 'style', 'noscript']):
        junk.decompose()

    for selector in [{'id': 'column'}, {'id': 'content'}]:
        main = soup.find('div', attrs=selector)
        if main: return str(main)

    main = soup.find('main') or soup.find('article') or soup.body
    return str(main) if main else str(soup)

def markdown_worker(output_directory_md):
    """Runs in a second thread to convert HTML to Markdown."""
    print("[Thread 2] Markdown conversion worker started.")
    while True:
        item = md_queue.get()
        
        if item is None: # Sentinel value to stop the worker
            md_queue.task_done()
            break
            
        html_content, relative_path = item

        # Only strip a genuine HTML extension. Blind splitext() would turn a
        # slug such as 'microphones/t.bone' into 't.md', losing the page name.
        stem, extension = os.path.splitext(relative_path)
        md_path = (stem if extension.lower() in ('.html', '.htm') else relative_path) + '.md'
        filepath = os.path.join(output_directory_md, md_path)
        
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
        except FileExistsError: pass # Robustness check
        except OSError as e:
            print(f"[Thread 2] Error creating directory for '{filepath}': {e}")
            md_queue.task_done() # Ensure task is done even on error
            continue
        
        md_content = markdownify(html_content, heading_style="ATX")
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content.strip())
            print(f"[Thread 2] Saved MD: {filepath}")
            # DELIBERATELY no provenance sidecar. This file is a conversion of a
            # page that already has one; a manifest here would claim a fetch
            # that did not happen. See provenance.py's header.
        except IOError as e:
            print(f"[Thread 2] Error writing markdown file '{filepath}': {e}")
            
        md_queue.task_done()

def download_media(soup, current_url, media_directory):
    """Finds and downloads media files from the page."""
    media_tags = soup.find_all(['img', 'video', 'audio', 'source'])
    
    for tag in media_tags:
        source = tag.get('src')
        if not source: continue

        media_url = urljoin(current_url, source)
        clean_media_url = media_url.split('?')[0].split('#')[0] # Remove query/fragment

        if urlparse(clean_media_url).path.startswith(DISALLOWED_PATHS): continue

        with visited_lock:
            if clean_media_url in visited_urls: continue
            visited_urls.add(clean_media_url)

        print(f"[Downloader] Downloading media: {clean_media_url}")

        filepath = clean_media_url # Fallback for error messages before path is built
        try:
            response = requests.get(clean_media_url, headers=HEADERS, stream=True, timeout=30)
            response.raise_for_status()

            parsed_url = urlparse(clean_media_url)
            path = parsed_url.path.lstrip('/') # Path component for filename
            
            if not path: continue # Skip if no path component
                
            filepath = os.path.join(media_directory, path)
            
            try:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
            except FileExistsError: pass # Robustness check
            except OSError as e:
                print(f"[Main Thread] Error creating directory for media '{filepath}': {e}. Skipping media.")
                continue
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            provenance.write(filepath, clean_media_url, 'Scraper.py',
                             http_status=response.status_code,
                             content_type=response.headers.get('Content-Type'))

        except requests.RequestException as e:
            print(f"[Downloader] Failed to download media '{clean_media_url}': {e}")
        except IOError as e:
            print(f"[Downloader] Error writing media file '{filepath}': {e}")
        finally:
            time.sleep(REQUEST_DELAY)

def download_page_worker(base_directory_html, scrape_media_flag, media_directory):
    """Worker function to process URLs from the url_queue."""
    while True:
        item = url_queue.get()
        if item is None: # Sentinel value to stop the worker
            url_queue.task_done()
            break

        url, base_url = item

        url = normalize_url(url)

        if not is_in_scope(url, base_url):
            url_queue.task_done()
            continue

        # Claim the URL under a lock, so two threads cannot both pass the
        # membership test and download the same page.
        with visited_lock:
            if url in visited_urls:
                url_queue.task_done()
                continue
            visited_urls.add(url)

        print(f"[Downloader] Downloading: {url}")

        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"[Downloader] Failed to download '{url}': {e}")
            url_queue.task_done()
            continue
        finally:
            time.sleep(REQUEST_DELAY)

        if 'html' not in response.headers.get('Content-Type', 'text/html'):
            print(f"[Downloader] Skipping non-HTML response: {url}")
            url_queue.task_done()
            continue

        # --- Determine the target file path and handle file/directory conflicts ---
        # Mirror the site's own path layout under the output directory.
        relative_path_from_base = urlparse(url).path.lstrip('/')

        target_relative_path = relative_path_from_base or 'index.html'
        resolved_filepath = os.path.join(base_directory_html, target_relative_path)

        # --- Conflict Resolution Logic: File vs. Directory ---
        # A site path can be both a page and a parent of other pages. For
        # example '/microphones/Alesis' is a listing page, and
        # '/microphones/Alesis/AM51' is a page beneath it. On disk 'Alesis'
        # cannot be both a file and a directory, so whichever role is needed
        # second forces a migration:
        #
        #   - Parent needed as a directory but exists as a file: move that file
        #     down into the new directory as 'index.html'.
        #   - This page's own path already exists as a directory: save this
        #     page as 'index.html' inside it.
        #
        # Note the current page always keeps its OWN target path. Redirecting it
        # to the parent's 'index.html' would overwrite the listing page that was
        # just migrated there, and lose this page entirely.
        try:
            with fs_lock: # Serialize the rename/makedirs sequence across threads
                parent_directory = os.path.dirname(resolved_filepath)
                if parent_directory and os.path.isfile(parent_directory):
                    print(f"[Downloader] Conflict: '{parent_directory}' exists as a file but is needed as a directory. Moving it to its own index.html.")
                    temp_path = parent_directory + ".tmp"
                    os.rename(parent_directory, temp_path)
                    os.makedirs(parent_directory, exist_ok=True)
                    moved_to = os.path.join(parent_directory, "index.html")
                    os.rename(temp_path, moved_to)
                    # its manifest follows it, or the sidecar would name a file
                    # that is no longer there and the moved page would have none
                    old_manifest = provenance.manifest_path(parent_directory)
                    if os.path.isfile(old_manifest):
                        os.rename(old_manifest, provenance.manifest_path(moved_to))

                if os.path.isdir(resolved_filepath):
                    resolved_filepath = os.path.join(resolved_filepath, 'index.html')

                # Ensure the parent directory of the FINAL resolved filepath exists.
                parent_directory = os.path.dirname(resolved_filepath)
                if parent_directory:
                    os.makedirs(parent_directory, exist_ok=True)
        except OSError as e:
            print(f"[Downloader] Filesystem error preparing path for '{url}': {e}. Skipping.")
            url_queue.task_done()
            continue
        # --- END OF CONFLICT RESOLUTION ---

        # Write the HTML content to the finally resolved filepath.
        try:
            with open(resolved_filepath, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"[Main Thread] Saved HTML to: {resolved_filepath}")
            # Written HERE and not after the loop: the manifest describes the
            # bytes just written, and `resolved_filepath` is rewritten by the
            # conflict resolution above on the next iteration.
            provenance.write(resolved_filepath, url, 'Scraper.py',
                             http_status=response.status_code,
                             content_type=response.headers.get('Content-Type'))
        except IOError as e:
            print(f"[Main Thread] Error writing HTML file '{resolved_filepath}': {e}")
            url_queue.task_done()
            continue # Skip processing further for this URL

        # Parse HTML and find links for recursive downloading
        soup = BeautifulSoup(response.text, 'html.parser')

        if scrape_media_flag:
            download_media(soup, url, media_directory)

        # Add newly found links to the URL queue for processing.
        # Links are resolved and normalized here so that 'http://', 'https://'
        # and '//host/path' forms of the same page collapse into one entry.
        for link in soup.find_all('a', href=True):
            next_url = normalize_url(urljoin(url, link['href']))
            if is_in_scope(next_url, base_url) and next_url not in visited_urls:
                url_queue.put((next_url, base_url))

        # Feed the markdown conversion task to the worker thread.
        # Note: extract_main_content() mutates `soup`, so it runs after the
        # link scan above.
        relative_path_for_md = os.path.relpath(resolved_filepath, base_directory_html)
        md_queue.put((extract_main_content(soup), relative_path_for_md))

        url_queue.task_done() # Mark this URL as processed

def concatenate_markdown_files(md_directory):
    """Stitches MD files together using the global MAX_FILE_SIZE_MB setting."""
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    part_number = 1
    current_size = 0
    
    print("-" * 40)
    print(f"Stitching all Markdown files (Max {MAX_FILE_SIZE_MB}MB per part)...")
    
    def get_output_filepath(part):
        return os.path.join(md_directory, f"COMBINED_ARCHIVE_part{part}.md")
        
    output_filepath = get_output_filepath(part_number)
    try:
        outfile = open(output_filepath, 'w', encoding='utf-8')
    except IOError as e:
        print(f"Error opening output file '{output_filepath}': {e}")
        return

    for root, _, files in os.walk(md_directory):
        for file in sorted(files): # Sort files for consistent ordering
            if file.endswith('.md') and not file.startswith("COMBINED_ARCHIVE"):
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, md_directory)
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as infile:
                        content = infile.read()
                except IOError as e:
                    print(f"Error reading file '{filepath}': {e}")
                    continue
                
                # Corrected f-string for multi-line content using triple quotes
                block_to_add = f"""
-----------------
{rel_path}
------------------------

{content}
"""
                block_bytes = len(block_to_add.encode('utf-8'))
                
                if current_size + block_bytes > max_bytes and current_size > 0:
                    outfile.close()
                    part_number += 1
                    output_filepath = get_output_filepath(part_number)
                    try:
                        outfile = open(output_filepath, 'w', encoding='utf-8')
                        current_size = 0 
                    except IOError as e:
                        print(f"Error opening output file '{output_filepath}': {e}")
                        return
                    
                outfile.write(block_to_add)
                current_size += block_bytes
                    
    outfile.close()
    print(f"Stitching complete! Created {part_number} archive file(s) in: ./{md_directory}/")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download HTML, convert to MD, and concatenate.")
    parser.add_argument("url", help="The starting URL to scrape")
    args = parser.parse_args()

    # --- Robust Base URL and Folder Name Determination ---
    initial_url = args.url
    parsed_initial_url = urlparse(initial_url)
    
    base_url = f"{parsed_initial_url.scheme}://{parsed_initial_url.netloc}"
    
    path_parts = [part for part in parsed_initial_url.path.split('/') if part]
    base_path_for_folder = ""
    if path_parts:
        if len(path_parts) > 1 and re.match(r'^v\d+(\.\d+){0,2}$', path_parts[-1]): # e.g., v1.0.0
            base_path_for_folder = "/".join(path_parts[:-1]) # Take parts up to version
        elif len(path_parts) > 0 and path_parts[0] != "releases": 
            base_path_for_folder = "/".join(path_parts)
        else:
             base_path_for_folder = "/".join(path_parts)
    
    # Ensure base_url ends with a slash for urljoin
    if not base_url.endswith('/'): base_url += '/'
    
    # Normalized so the scope check and visited-set share one canonical form
    effective_base_url = normalize_url(urljoin(base_url, base_path_for_folder))

    folder_name_part = urlparse(effective_base_url).path.strip('/')
    folder_name = sanitize_folder_name(folder_name_part)
    
    if not folder_name: folder_name = sanitize_folder_name(parsed_initial_url.netloc)
    if not folder_name: folder_name = "root" # Ultimate fallback
    # --- End of Robust Base URL and Folder Name Determination ---

    user_input = input("""
Do you want to scrape media files (images, videos, audio) as well? (y/n): """).strip().lower()
    scrape_media_flag = user_input in ['y', 'yes']

    master_folder = "scrapes"
    
    html_directory = os.path.join(master_folder, folder_name)
    md_directory = os.path.join(master_folder, folder_name + "-MD")
    media_directory = os.path.join(master_folder, folder_name + "-MEDIA")
    
    # Create top-level directories, with error handling
    try: os.makedirs(html_directory, exist_ok=True)
    except OSError as e: print(f"Error creating directory '{html_directory}': {e}")
    try: os.makedirs(md_directory, exist_ok=True)
    except OSError as e: print(f"Error creating directory '{md_directory}': {e}")
    if scrape_media_flag:
        try: os.makedirs(media_directory, exist_ok=True)
        except OSError as e: print(f"Error creating directory '{media_directory}': {e}")
    
    print("-" * 40)
    print(f"Target URL: {initial_url}")
    print(f"Effective Base URL for scraping: {effective_base_url}")
    print(f"HTML Output directory: ./{html_directory}/")
    print(f"Markdown Output directory: ./{md_directory}/")
    if scrape_media_flag:
        print(f"Media Output directory: ./{media_directory}/")
    print("-" * 40)
    
    # 1. Start the markdown converter thread
    converter_thread = threading.Thread(target=markdown_worker, args=(md_directory,), daemon=True)
    converter_thread.start()
    
    # 2. Start the HTML (and optionally Media) downloads using a worker pool
    number_download_threads = NUMBER_DOWNLOAD_THREADS
    download_threads = []
    for _ in range(number_download_threads):
        t = threading.Thread(target=download_page_worker, args=(html_directory, scrape_media_flag, media_directory), daemon=True)
        t.start()
        download_threads.append(t)

    # Enqueue the initial URL
    url_queue.put((normalize_url(initial_url), effective_base_url))

    # Wait for all URLs in the queue to be processed
    url_queue.join()

    # Signal download workers to stop
    for _ in range(number_download_threads):
        url_queue.put(None)
    for t in download_threads:
        t.join()
    
    # 3. Signal the markdown worker to stop
    print("-" * 40)
    print("[Main Thread] Scraping finished. Waiting for Markdown converter to catch up...")
    md_queue.put(None)
    converter_thread.join()
    
    # 4. Concatenate all the generated markdown files
    concatenate_markdown_files(md_directory)
    
    print("All tasks complete!")
