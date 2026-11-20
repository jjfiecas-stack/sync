import { ContentType } from 'stremio-addon-sdk';
import { Context, CountryCode } from '../types';
import { Fetcher, getTmdbId, Id } from '../utils';
import { Source, SourceResult } from './Source';

export class Vidzee extends Source {
  public readonly id = 'vidzee';

  public readonly label = 'VidZee';

  public readonly contentTypes: ContentType[] = ['movie', 'series'];

  public readonly countryCodes: CountryCode[] = [CountryCode.multi];

  public readonly baseUrl = 'https://player.vidzee.wtf';

  private readonly fetcher: Fetcher;

  public constructor(fetcher: Fetcher) {
    super();

    this.fetcher = fetcher;
  }

  public async handleInternal(ctx: Context, _type: string, id: Id): Promise<SourceResult[]> {
    const tmdbId = await getTmdbId(ctx, this.fetcher, id);

    const path = tmdbId.season
      ? `/streams/tv/${tmdbId.id}/${tmdbId.season}/${tmdbId.episode}`
      : `/streams/movie/${tmdbId.id}`;
    const apiUrl = new URL(path, 'https://core.vidzee.wtf');
    apiUrl.searchParams.set('s', 'dcloud');
    apiUrl.searchParams.set('e', '0');

    try {
      const response = await this.fetcher.json(ctx, apiUrl, { headers: { Referer: `${this.baseUrl}/` } }) as { url?: string };
      if (!response?.url) return [];

      return [{
        url: new URL(response.url),
        meta: { countryCodes: [CountryCode.multi], title: 'VidZee' },
      }];
    } catch {
      return [];
    }
  }
}
