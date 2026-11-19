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


def sub(path, old, new):
    p = root / path
    text = p.read_text()
    if new in text:
        print(f"already patched: {p}")
        return
    if old not in text:
        sys.exit(f"patch anchor missing in {p}: {old.splitlines()[0][:70]!r}")
    p.write_text(text.replace(old, new, 1))
    print(f"patched: {p}")


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
