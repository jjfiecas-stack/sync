#!/usr/bin/env python3
"""Rebuild-time fixes for peterdsp/Magnetio's scraper.

The upstream tree is checked out fresh on every build, so the fixes live here
and are re-applied to that checkout. Each edit is anchored on upstream text and
fails the build if the anchor is gone, instead of silently shipping a scraper
that returns nothing.

Usage: magnetio-patch.py <path to _source/scraper>
"""
import pathlib
import sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "_source/scraper")
addon_root = root.parent / "addon"


def sub(path, old, new, base=None):
    p = (base if base is not None else root) / path
    text = p.read_text()
    if new in text:
        print(f"already patched: {p}")
        return
    if old not in text:
        sys.exit(f"patch anchor missing in {p}: {old.splitlines()[0][:70]!r}")
    p.write_text(text.replace(old, new, 1))
    print(f"patched: {p}")


def rewrite(path, anchor, new):
    """Replace a whole provider file, but only if upstream still looks known."""
    p = root / path
    text = p.read_text()
    if text == new:
        print(f"already patched: {p}")
        return
    if anchor not in text:
        sys.exit(f"rewrite anchor missing in {p}: {anchor[:70]!r}")
    p.write_text(new)
    print(f"rewrote: {p}")


# TorrentGalaxy mirrors now title search pages "<query> torrents in <category>";
# the upstream check only accepted the old "<title>Search for" wording, so every
# valid response was discarded and the provider reported "all domains exhausted".
sub(
    "providers/torrentgalaxy.js",
    "      validate: ({ data }) => typeof data === 'string' && /<title>\\s*Search for\\b/i.test(data),",
    "      validate: ({ data }) =>\n"
    "        typeof data === 'string' && /<title>[^<]*(?:torrents in|Search for)\\b/i.test(data),",
)

# katcr.to and torrentgalaxy.one sit behind Cloudflare's challenge; the mirrors
# that still serve HTML are kickasstorrents.to and torrentgalaxy.info.
sub(
    "lib/domainRotation.js",
    "  kickasstorrents: [\n    'https://katcr.to',\n    'https://kickasstorrents.to',",
    "  kickasstorrents: [\n    'https://kickasstorrents.to',\n    'https://katcr.to',",
)
sub(
    "lib/domainRotation.js",
    "  torrentgalaxy: [\n    'https://torrentgalaxy.one',\n    'https://torrentgalaxy.info',",
    "  torrentgalaxy: [\n    'https://torrentgalaxy.info',\n    'https://torrentgalaxy.one',",
)

# KickassTorrents search rows no longer embed magnet links; the info hash is on
# the detail page, so collect the rows first and fetch the hashes afterwards.
sub(
    "providers/kickasstorrents.js",
    """    const { data } = await tryDomains(DOMAINS, async (base) => {
      const url = `${base}/usearch/${encodeURIComponent(query)}/`;
      return get(url, { limiterKey: 'kickasstorrents' });
    }, 'KAT');

    const $ = cheerio.load(data);
    const results = [];

    $('tr.odd, tr.even').each((_, row) => {
      const $row    = $(row);
      const title   = $row.find('a.cellMainLink').first().text().trim();
      const magnet  = $row.find('a[href^="magnet:"]').first().attr('href') ?? '';
      const infoHash = extractInfoHash(magnet);

      if (!infoHash || !title) return;

      const seeders  = parseInt($row.find('td.green.center').first().text().trim(), 10) || 0;
      const leechers = parseInt($row.find('td.red.center').first().text().trim(), 10) || 0;
      const sizeText = $row.find('td').eq(1).text().trim();
      const size     = parseSize(sizeText);

      results.push({
        infoHash,
        title,
        seeders,
        leechers,
        size,
        provider: 'KickassTorrents',
        imdbId:   meta.imdbId,
        ...parseTitle(title),
      });
    });

    return results;
""",
    """    let base = DOMAINS[0];
    const { data } = await tryDomains(DOMAINS, async (b) => {
      base = b;
      const url = `${b}/usearch/${encodeURIComponent(query)}/`;
      return get(url, { limiterKey: 'kickasstorrents' });
    }, 'KAT');

    const $ = cheerio.load(data);
    const rows = [];

    $('tr.odd, tr.even').each((_, row) => {
      const $row    = $(row);
      const titleEl = $row.find('a.cellMainLink').first();
      const title   = titleEl.text().trim();
      const href    = titleEl.attr('href');

      if (!href || !title) return;

      const seeders  = parseInt($row.find('td.green.center').first().text().trim(), 10) || 0;
      const leechers = parseInt($row.find('td.red.center').first().text().trim(), 10) || 0;
      const sizeText = $row.find('td').eq(1).text().trim();
      const size     = parseSize(sizeText);

      rows.push({
        title,
        url: href.startsWith('http') ? href : `${base}${href}`,
        seeders,
        leechers,
        size,
      });
    });

    const settled = await Promise.allSettled(
      rows.slice(0, 20).map(r => fetchInfoHash(r.url))
    );

    return settled.flatMap((s, i) => {
      if (s.status !== 'fulfilled' || !s.value) return [];
      const { title, seeders, leechers, size } = rows[i];
      return [{
        infoHash: s.value,
        title,
        seeders,
        leechers,
        size,
        provider: 'KickassTorrents',
        imdbId:   meta.imdbId,
        ...parseTitle(title),
      }];
    });
""",
)

sub(
    "providers/kickasstorrents.js",
    "function extractInfoHash(magnet) {",
    """async function fetchInfoHash(url) {
  const { data } = await get(url, { limiterKey: 'kickasstorrents' });
  const magnet = (typeof data === 'string' ? data : '').match(/magnet:\\?[^"']+/i)?.[0] ?? '';
  return extractInfoHash(magnet);
}

function extractInfoHash(magnet) {""",
)

# TorLock's HTML search is behind Cloudflare, but its official Torznab feed is
# open and returns 100 results with magnets and seed counts inline.
rewrite(
    "providers/torlock.js",
    "TorLock provider -- scrapes torlock2.com search results via HTML.",
    r'''/**
 * TorLock provider -- reads the official Torznab feed instead of the HTML site.
 * The site hides every search behind a Cloudflare challenge, but /torznab/api
 * serves the same index as XML, with magnet links and seed counts inline.
 */
import { get } from '../lib/httpClient.js';
import { parseTitle, buildSearchQuery } from '../lib/titleHelper.js';
import { logger } from '../lib/logger.js';

const API = 'https://www.torlock.com/torznab/api';
const MAX_RESULTS = 30;

export const id   = 'torlock';
export const name = 'TorLock';
// Content types this provider can answer for.
export const types = ['movie', 'series', 'anime'];

export async function scrape(meta) {
  if (!meta?.name) return [];

  try {
    const query = buildSearchQuery(meta);
    const { data } = await get(API, {
      limiterKey: 'torlock',
      params: { t: 'search', q: query },
    });

    const items = String(data).match(/<item>[\s\S]*?<\/item>/g) ?? [];
    const results = [];

    for (const item of items) {
      const title = decode((item.match(/<title>([\s\S]*?)<\/title>/) ?? [])[1] ?? '');
      const link  = decode((item.match(/<link>([\s\S]*?)<\/link>/) ?? [])[1] ?? '');
      const infoHash = extractInfoHash(link);
      if (!title || !infoHash) continue;

      const size = parseInt((item.match(/<size>(\d+)<\/size>/) ?? [])[1] ?? '0', 10) || 0;
      const attr = (name) =>
        parseInt((item.match(new RegExp(`name="${name}"\\s+value="(\\d+)"`)) ?? [])[1] ?? '0', 10) || 0;

      results.push({
        infoHash,
        title,
        seeders:  attr('seeders'),
        leechers: attr('leechers'),
        size,
        provider: 'TorLock',
        imdbId:   meta.imdbId,
        ...parseTitle(title),
      });
      if (results.length >= MAX_RESULTS) break;
    }

    return results;
  } catch (err) {
    logger.warn(`[TorLock] ${err.message}`);
    return [];
  }
}

function decode(s) {
  return s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').trim();
}

function extractInfoHash(magnet) {
  const match = magnet.match(/xt=urn:btih:([a-fA-F0-9]{40}|[a-zA-Z2-7]{32})/i);
  return match ? match[1].toLowerCase() : null;
}
''',
)

# AIOStreams drops an addon response after ~6.5s. Upstream resolves up to 20
# cached debrid streams, four at a time, with an 8s per-stream timeout, so a
# cold response takes 30-45s. Bound the work and parallelise it instead.
sub(
    "moch/moch.js",
    "const RESOLVE_TIMEOUT_MS = 8_000;",
    "const RESOLVE_TIMEOUT_MS = 2_200;",
    addon_root,
)
sub(
    "moch/moch.js",
    "const resolveLimit = pLimit(4);",
    "const resolveLimit = pLimit(10);",
    addon_root,
)
sub(
    "moch/moch.js",
    """          streams
            .filter(stream => stream.infoHash && cachedMap.has(stream.infoHash?.toLowerCase()))
            .map(stream => resolveLimit(async () => {""",
    """          streams
            .filter(stream => stream.infoHash && cachedMap.has(stream.infoHash?.toLowerCase()))
            .slice(0, 10)
            .map(stream => resolveLimit(async () => {""",
    addon_root,
)
# TorBox readiness polling sleeps 2s between checks; halve the poll interval
# and cap retries so cached torrents resolve inside the latency budget.
sub(
    "moch/torbox.js",
    "async function _waitForReady(torrentId, apiKey, retries = 10, delayMs = 2000)",
    "async function _waitForReady(torrentId, apiKey, retries = 8, delayMs = 250)",
    addon_root,
)

# LimeTorrents search rows already carry the info hash; the 12 detail-page
# fetches upstream adds blow the 15s provider budget when the site is reached
# through WARP. Use the hash from the row and skip the detail round-trip.
sub(
    "providers/limetorrents.js",
    """    const settled = await Promise.allSettled(
      rows.slice(0, 12).map(row => fetchDetail(row, meta))
    );

    return settled.flatMap(result =>
      result.status === 'fulfilled' && result.value ? [result.value] : []
    );
""",
    """    return rows.slice(0, 20).map(row => ({
      infoHash: row.infoHash,
      title: row.title,
      seeders: row.seeders,
      leechers: row.leechers,
      size: row.size,
      provider: 'LimeTorrents',
      imdbId: meta.imdbId,
      ...parseTitle(row.title),
    }));
""",
)
