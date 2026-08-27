"""Shared helpers for the Phase 3 URL-discovery pipeline (section 4).

Discovery is deliberately separate from the review-scraping adapters: it
only ever needs a browser, a query, and a way to read back a resulting URL
and displayed hotel name - never review content itself.
"""
from __future__ import annotations

from datetime import datetime, timezone
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_driver(headless: bool = False) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=opts)


def build_query_variants(hotel_name: str, area: str) -> list[str]:
    """Controlled query variations (section 5). Only public search terms -
    no private API, no login bypass, no proxy rotation."""
    variants = [f"{hotel_name} Bodrum"]
    if area:
        variants.append(f"{hotel_name} {area} Bodrum")
    variants.append(f"{hotel_name} Mugla")
    return variants


# --- structural "find the clickable ancestor of a text match" helper -------
# Deliberately avoids hardcoding any rotating/hashed CSS class name (the same
# lesson learned repairing google/yorum.py in phase 2): walks up from a text
# leaf until it finds an element with its own click handler.
_FIND_BEST_MATCH_JS = r"""
const target = arguments[0].toLowerCase();
function norm(s) { return (s || "").trim().toLowerCase(); }
const leaves = Array.from(document.querySelectorAll('*')).filter(e => e.children.length === 0 && norm(e.textContent));
let best = null;
let bestScore = -1;
for (const leaf of leaves) {
    const txt = norm(leaf.textContent);
    if (!txt) continue;
    let score = 0;
    if (txt === target) score = 100;
    else if (txt.includes(target) || target.includes(txt)) score = 60 + Math.min(txt.length, target.length);
    else continue;
    if (score > bestScore) { bestScore = score; best = leaf; }
}
if (!best) return {found: false, text: null};
let node = best;
for (let i = 0; i < 8 && node; i++) {
    if (node.onclick) {
        return {found: true, text: best.textContent.trim().slice(0, 120), clickableIndex: i};
    }
    node = node.parentElement;
}
return {found: false, text: best.textContent.trim().slice(0, 120)};
"""

_CLICK_BEST_MATCH_JS = _FIND_BEST_MATCH_JS.replace(
    "return {found: true, text: best.textContent.trim().slice(0, 120), clickableIndex: i};",
    "node.click(); return {found: true, text: best.textContent.trim().slice(0, 120), clickableIndex: i};",
)


def find_best_text_match(driver, target_text: str) -> dict:
    """Non-mutating lookup: is there a clickable DOM leaf whose text matches
    target_text right now? Returns {"found": bool, "text": str|None} -
    used to poll for an autocomplete dropdown to actually refresh instead
    of trusting a fixed sleep.
    """
    return driver.execute_script(_FIND_BEST_MATCH_JS, target_text)


def click_best_text_match(driver, target_text: str) -> dict:
    """Finds the DOM leaf whose text best matches target_text, walks up to
    the nearest ancestor that has its own click handler, and clicks it.
    Returns {"found": bool, "text": str|None}.
    """
    return driver.execute_script(_CLICK_BEST_MATCH_JS, target_text)


# --- safer alternative: score candidates with real name-similarity server
# side instead of the crude JS includes() heuristic above, which turned out
# to false-match on short generic leaves (e.g. a bare "Hotel" nav label is
# a substring of almost every hotel name) - this was the root cause of the
# Trip.com discovery bug found in the first 20-hotel smoke test, where a
# stale/unrelated suggestion got clicked and its old result silently reused
# for several unrelated hotels in a row. -----------------------------------

_LIST_LEAVES_JS = r"""
const minLen = arguments[0];
const cap = arguments[1];
const seen = new Set();
const out = [];
for (const e of document.querySelectorAll('*')) {
    if (e.children.length !== 0) continue;
    const txt = (e.textContent || '').trim();
    if (txt.length < minLen || seen.has(txt)) continue;
    let node = e, clickable = false;
    for (let i = 0; i < 8 && node; i++) {
        if (node.onclick) { clickable = true; break; }
        node = node.parentElement;
    }
    if (!clickable) continue;
    seen.add(txt);
    out.push(txt);
    if (out.length >= cap) break;
}
return out;
"""

_CLICK_EXACT_LEAF_JS = r"""
const target = arguments[0];
const leaves = Array.from(document.querySelectorAll('*')).filter(
    e => e.children.length === 0 && (e.textContent || '').trim() === target);
if (!leaves.length) return false;
let node = leaves[0];
for (let i = 0; i < 8 && node; i++) {
    if (node.onclick) { node.click(); return true; }
    node = node.parentElement;
}
return false;
"""


def list_clickable_text_leaves(driver, min_len: int = 4, cap: int = 80) -> list[str]:
    """All distinct, reasonably-long DOM leaf text values that have a
    clickable ancestor right now - candidates for an autocomplete/search
    suggestion list, without assuming any particular hashed container
    class."""
    return driver.execute_script(_LIST_LEAVES_JS, min_len, cap)


def click_exact_text_leaf(driver, exact_text: str) -> bool:
    """Clicks the (first) clickable ancestor of the DOM leaf whose text is
    EXACTLY exact_text - used after the caller has already picked the best
    candidate via a real similarity score, so no fuzziness happens at the
    DOM layer."""
    return bool(driver.execute_script(_CLICK_EXACT_LEAF_JS, exact_text))


def reset_browser_state(driver, base_url: str) -> None:
    """Clears cookies + local/session storage for the current domain and
    reloads base_url fresh. Used before every new discovery query on a
    reused browser session so a previous hotel's confirmed selection can
    never leak into the next query (the confirmed root cause of the
    Trip.com discovery staleness bug)."""
    try:
        driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
    except Exception:  # noqa: BLE001 - best-effort, page may not be loaded yet
        pass
    driver.delete_all_cookies()
    driver.get(base_url)
