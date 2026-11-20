import * as cheerio from 'cheerio';
import { ContentType } from 'stremio-addon-sdk';
import { Context, CountryCode } from '../types';
import { Fetcher, getTmdbId, getTmdbNameAndYear, Id, TmdbId } from '../utils';
import { Source, SourceResult } from './Source';

interface ResolveSource {
  url: string;
  name?: string;
}

interface ResolveResponse {
  sources?: ResolveSource[];
  title?: string;
}

export class CineHDPlus extends Source {
  public readonly id = 'cinehdplus';

  public readonly label = 'CineHDPlus';

  public readonly contentTypes: ContentType[] = ['movie', 'series'];

  public readonly countryCodes: CountryCode[] = [CountryCode.es, CountryCode.mx];

  public readonly baseUrl = 'https://cinehdplus.you';

  private readonly fetcher: Fetcher;

  public constructor(fetcher: Fetcher) {
    super();
    this.fetcher = fetcher;
  }

  public async handleInternal(ctx: Context, _type: string, id: Id): Promise<SourceResult[]> {
    const tmdbId = await getTmdbId(ctx, this.fetcher, id);

    let name: string;
    try {
      [name] = await getTmdbNameAndYear(ctx, this.fetcher, tmdbId, 'es');
    } catch {
      return [];
    }

    const pageUrl = await this.fetchPageUrl(ctx, tmdbId, name);
    if (!pageUrl) return [];

    const html = await this.fetcher.text(ctx, pageUrl);
    const $ = cheerio.load(html);
    const iframeSrc = $('iframe[src*="playlatinsrc"]').first().attr('src');
    const imdbId = iframeSrc?.match(/tt\d+/)?.[0];
    if (!imdbId) return [];

    const season = tmdbId.season ?? 1;
    const episode = tmdbId.episode ?? 1;
    const customPath = tmdbId.season
      ? `/custom/serial/${imdbId}/${season}/${episode}`
      : `/custom/movie/${imdbId}`;
    const customUrl = new URL(customPath, 'https://playlatinsrc.co');

    const customHtml = await this.fetcher.text(ctx, customUrl);
    const token = customHtml.match(/data-resolve-token=["']([^"']+)["']/)?.[1];
    const endpoint = customHtml.match(/data-resolve-endpoint=["']([^"']+)["']/)?.[1] ?? '/api/resolve';
    if (!token) return [];

    const payload = JSON.stringify({
      type: tmdbId.season ? 'serial' : 'movie',
      id: imdbId,
      season,
      episode,
      mode: 'custom',
      token,
    });

    let responseText: string;
    try {
      responseText = await this.fetcher.textPost(ctx, new URL(endpoint, customUrl.origin), payload, {
        headers: { 'Content-Type': 'application/json', 'Referer': customUrl.href },
      });
    } catch {
      return [];
    }

    let response: ResolveResponse;
    try {
      response = JSON.parse(responseText) as ResolveResponse;
    } catch {
      return [];
    }

    const countryCodes = html.includes('Latino') ? [CountryCode.mx] : [CountryCode.es];
    const title = `${response.title ?? name}${tmdbId.season ? ` ${tmdbId.formatSeasonAndEpisode()}` : ''}`;

    return (response.sources ?? [])
      .map(source => new URL(source.url))
      .map(url => ({ url, meta: { countryCodes, referer: pageUrl.href, title } }));
  }

  private fetchPageUrl = async (ctx: Context, tmdbId: TmdbId, name: string): Promise<URL | undefined> => {
    const searchUrl = new URL(`/buscar?q=${encodeURIComponent(name)}`, this.baseUrl);
    const html = await this.fetcher.text(ctx, searchUrl);
    const $ = cheerio.load(html);
    const slug = tmdbId.season ? 'serie' : 'film';

    const href = $(`a[href*="/${slug}/${tmdbId.id}-"]`).first().attr('href');
    if (!href) return undefined;

    const pageUrl = new URL(href, this.baseUrl);
    return tmdbId.season
      ? new URL(`temporada-${tmdbId.season}/episodio-${tmdbId.episode}`, `${pageUrl.href.replace(/\/$/, '')}/`)
      : pageUrl;
  };
}
