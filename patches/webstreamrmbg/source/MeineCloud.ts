import { ContentType } from 'stremio-addon-sdk';
import { Context, CountryCode } from '../types';
import { Fetcher, getImdbId, Id } from '../utils';
import { Source, SourceResult } from './Source';

interface EmbedSource {
  url: string;
  name?: string;
}

interface EmbedLinksResponse {
  ok?: boolean;
  sources?: EmbedSource[];
  tv?: {
    seasons?: {
      episodes?: { sources?: EmbedSource[] }[];
    }[];
  };
}

export class MeineCloud extends Source {
  public readonly id = 'meinecloud';
  public readonly label = 'MeineCloud';
  public readonly contentTypes: ContentType[] = ['movie', 'series'];
  public readonly countryCodes: CountryCode[] = [CountryCode.de];
  public readonly baseUrl = 'https://devideosrc.co';

  private readonly fetcher: Fetcher;

  public constructor(fetcher: Fetcher) {
    super();
    this.fetcher = fetcher;
  }

  public async handleInternal(ctx: Context, _type: string, id: Id): Promise<SourceResult[]> {
    const imdbId = await getImdbId(ctx, this.fetcher, id);
    const season = id.season;
    const pageUrl = new URL(`/${season ? 'serial' : 'movie'}/${imdbId.id}`, this.baseUrl);

    const html = await this.fetcher.text(ctx, pageUrl, { headers: { Referer: `${this.baseUrl}/` } });
    const token = html.match(/token\s*:\s*["']([^"']+)["']/)?.[1];
    if (!token) {
      return [];
    }

    const body = JSON.stringify({ type: season ? 'tv' : 'movie', id: imdbId.id, token });
    const responseText = await this.fetcher.textPost(ctx, new URL('/api/embed-links', this.baseUrl), body, {
      headers: {
        'Content-Type': 'application/json',
        'Referer': `${this.baseUrl}/`,
      },
    });

    let response: EmbedLinksResponse;
    try {
      response = JSON.parse(responseText) as EmbedLinksResponse;
    } catch {
      return [];
    }

    let sources = response.sources ?? [];
    if (season) {
      const episodes = response.tv?.seasons?.[season - 1]?.episodes ?? [];
      sources = episodes[id.episode ? id.episode - 1 : 0]?.sources ?? [];
    }

    return sources
      .map(source => new URL(source.url))
      .map(url => ({ url, meta: { countryCodes: [CountryCode.de], referer: this.baseUrl } }));
  }
}
