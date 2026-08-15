# Provider composition

`ProviderCollection` is the typed composition boundary for external providers.
Only the application composition root may call `use()`. Routes never resolve or
register providers, and services receive only the protocol for the capability
they use.

```python
providers = ProviderCollection()
providers.use(
    YoutubeCapabilities(
        catalog=youtube_catalog,
        library=youtube_library,
        playlists=youtube_playlists,
    )
)
providers.use(SongStatisticsCapabilities(provider=song_statistics))

search_service = SearchService(catalog=providers.youtube.catalog)
statistics_service = StatisticsService(statistics=providers.song_statistics)
```

Resolve every required namespace while constructing services. A missing or
duplicate namespace then fails application startup instead of a request. Do not
put the collection in Flask globals or pass it to a route or service.

Top-level namespaces identify a cohesive provider family or independently
replaceable capability, such as `youtube` and `song_statistics`. Nested YouTube
capabilities use domain language—`catalog`, `library`, and `playlists`—rather
than generic operation groups such as `crud`.

Capability implementations must:

- implement the corresponding narrow `Protocol`;
- return the immutable models from `models.py`, not vendor dictionaries;
- translate selected vendor exceptions to the safe errors in `errors.py`;
- avoid Flask types and imports;
- perform external I/O only inside capability methods, never constructors or
  registration.

YouTube adapters depend on `YoutubeMusicSession` and obtain its active client
for each operation. They do not own authentication, active-profile state, or
client lifecycle.

## Migration pattern

Song statistics is the first production capability and establishes the flow:

```text
Flask route -> SongStatisticsService -> SongStatisticsProvider
            -> ReturnYoutubeDislikeProvider -> HttpTransport
```

The provider owns upstream HTTP and runtime payload validation, then returns a
normalized `SongStatistics`. The service owns Kodama's abbreviated-count
formatting. `create_app()` registers the provider bundle, resolves the narrow
protocol once, and places only `SongStatisticsService` in Flask extensions.

The YouTube catalog now follows the same boundary:

```text
Search/album route -> SearchService/AlbumDetailsService
                   -> MusicCatalogProvider -> YoutubeMusicCatalogProvider
                   -> YoutubeMusicSession -> ytmusicapi
```

`YoutubeMusicCatalogProvider` owns vendor filters, payload validation, search
normalization, album normalization, and YouTube-specific audio-version
resolution. `SearchService` owns frontend search formatting and suggestion
deduplication. `AlbumDetailsService` owns album-response formatting and cache
policy. Both services receive the catalog capability during application
construction and never resolve it from `ProviderCollection` during a request.
