import {
  Dropdown,
  DropdownItem,
  DropdownPopover,
  DropdownSection,
  DropdownSubmenuIndicator,
  DropdownSubmenuTrigger,
  DropdownTrigger,
  toast,
} from "@heroui/react";
import { DropdownMenu } from "@/shared/ui/zoomed-heroui.jsx";

import {
  ArrowClockwise,
  Check,
  Copy,
  DotsThreeVertical,
  DownloadSimple,
  Heart,
  Microphone,
  MusicNote,
  Plus,
  Radio,
  ShareNodes,
  Translate,
  Trash,
  UploadSimple,
  VinylRecord,
} from "@/shared/icons/icons.jsx";
import { translate } from "@/shared/i18n/i18n.js";

// Targets for lyrics translation. The backend hands the code to Google Translate lowercased,
// so anything Google accepts works without a mapping — every entry below was checked against
// the live endpoint rather than taken from a list. Hebrew works as "he"; the legacy "iw" is
// not needed. Sorted by native name, because at this length the list is scanned, not read.
// Module scope: it was previously rebuilt on every render of this menu.
const TRANSLATION_LANGS = [
  { code: "AR", name: "العربية" },
  { code: "BG", name: "Български" },
  { code: "BN", name: "বাংলা" },
  { code: "CA", name: "Català" },
  { code: "CS", name: "Čeština" },
  { code: "DA", name: "Dansk" },
  { code: "DE", name: "Deutsch" },
  { code: "EL", name: "Ελληνικά" },
  { code: "EN", name: "English" },
  { code: "ES", name: "Español" },
  { code: "ET", name: "Eesti" },
  { code: "FA", name: "فارسی" },
  { code: "FI", name: "Suomi" },
  { code: "FR", name: "Français" },
  { code: "HE", name: "עברית" },
  { code: "HI", name: "हिन्दी" },
  { code: "HR", name: "Hrvatski" },
  { code: "HU", name: "Magyar" },
  { code: "ID", name: "Bahasa Indonesia" },
  { code: "IT", name: "Italiano" },
  { code: "JA", name: "日本語" },
  { code: "KO", name: "한국어" },
  { code: "LT", name: "Lietuvių" },
  { code: "LV", name: "Latviešu" },
  { code: "MS", name: "Bahasa Melayu" },
  { code: "NB", name: "Norsk bokmål" },
  { code: "NL", name: "Nederlands" },
  { code: "PL", name: "Polski" },
  { code: "PT", name: "Português" },
  { code: "PT-BR", name: "Português (Brasil)" },
  { code: "RO", name: "Română" },
  { code: "RU", name: "Русский" },
  { code: "SK", name: "Slovenčina" },
  { code: "SL", name: "Slovenščina" },
  { code: "SR", name: "Српски" },
  { code: "SV", name: "Svenska" },
  { code: "SW", name: "Kiswahili" },
  { code: "TH", name: "ไทย" },
  { code: "TL", name: "Tagalog" },
  { code: "TR", name: "Türkçe" },
  { code: "UK", name: "Українська" },
  { code: "VI", name: "Tiếng Việt" },
  { code: "ZH", name: "中文（简体）" },
  { code: "ZH-TW", name: "中文（繁體）" },
].sort((a, b) => a.name.localeCompare(b.name));

export function PlayerActionsMenu(props) {
  const {
    buildShareLink,
    cachedSongIds,
    downloadingIds,
    expanded,
    fetchMoreBrowseIds,
    fetchedBrowseIds,
    isCustomLyrics,
    isLiked,
    language,
    lyricsTranslationLang,
    onAddToPlaylist,
    onDownloadSong,
    onExpandToggle,
    onExportSong,
    onImportLyrics,
    onOpenLyricsBrowser,
    onOpenAlbum,
    onOpenArtist,
    onRefetchLyrics,
    onRemoveCustomLyrics,
    onStartSongRadio,
    onSetLyricsTranslationLang,
    showLyricsTranslation,
    t,
    toggleLike,
    track,
  } = props;

  const fetched = fetchedBrowseIds[track?.videoId] || {};
  const albumId = track.albumBrowseId || fetched.albumBrowseId;
  const artistId = track.artistBrowseId || fetched.artistBrowseId;
  const downloaded = cachedSongIds?.has(track.videoId);
  const downloading = downloadingIds?.has(track.videoId);
  return (
    <Dropdown
      onOpenChange={(open) => {
        if (open) fetchMoreBrowseIds();
      }}
    >
      <DropdownTrigger
        data-testid="player-actions-menu"
        className="shrink-0 w-9 h-9 rounded-full flex items-center justify-center transition-colors duration-150 text-secondary hover:text-primary hover:bg-hover"
        style={{ contain: "layout style" }}
      >
        <DotsThreeVertical size={18} />
      </DropdownTrigger>
      <DropdownPopover
        placement="top end"
        className="min-w-60 data-[entering]:animate-in data-[entering]:fade-in-0 data-[entering]:zoom-in-95 data-[entering]:slide-in-from-bottom-2 data-[entering]:duration-200 data-[exiting]:animate-out data-[exiting]:fade-out-0 data-[exiting]:zoom-out-95 data-[exiting]:duration-150"
      >
        <DropdownMenu aria-label="More">
          {/* Add to Playlist (submenu) + Like */}
          <DropdownSection>
            <DropdownItem
              textValue={t("addToPlaylist")}
              onAction={() => onAddToPlaylist?.([track])}
            >
              <Plus size={14} />
              {t("addToPlaylist")}
            </DropdownItem>
            <DropdownItem
              textValue={isLiked ? t("unlike") : t("like")}
              onAction={() => toggleLike()}
              className={isLiked ? "text-accent" : undefined}
            >
              <Heart size={14} weight={isLiked ? "fill" : "regular"} />
              {isLiked ? t("unlike") : t("like")}
            </DropdownItem>
            <DropdownItem
              textValue={translate(language, "startRadio")}
              onAction={() => onStartSongRadio?.(track)}
            >
              <Radio size={14} />
              {translate(language, "startRadio")}
            </DropdownItem>
          </DropdownSection>

          {/* Navigation */}
          {albumId || artistId ? (
            <DropdownSection className="w-full border-t border-border mt-1 pt-1">
              {albumId && onOpenAlbum ? (
                <DropdownItem
                  textValue={translate(language, "goToAlbum")}
                  onAction={() => {
                    if (expanded) onExpandToggle();
                    onOpenAlbum({ browseId: albumId, title: track.album });
                  }}
                >
                  <VinylRecord size={14} />
                  {translate(language, "goToAlbum")}
                </DropdownItem>
              ) : null}
              {artistId && onOpenArtist ? (
                <DropdownItem
                  textValue={translate(language, "goToArtist")}
                  onAction={() => {
                    if (expanded) onExpandToggle();
                    onOpenArtist({ browseId: artistId, artist: track.artists });
                  }}
                >
                  <Microphone size={14} />
                  {translate(language, "goToArtist")}
                </DropdownItem>
              ) : null}
            </DropdownSection>
          ) : null}

          {/* Lyrics actions */}
          <DropdownSection className="w-full border-t border-border mt-1 pt-1">
            <DropdownItem
              textValue={translate(language, "refetchLyrics")}
              onAction={() => onRefetchLyrics?.()}
            >
              <ArrowClockwise size={14} />
              {translate(language, "refetchLyrics")}
            </DropdownItem>
            <DropdownItem
              textValue={translate(language, "importLyrics")}
              onAction={() => onImportLyrics?.()}
            >
              <UploadSimple size={14} />
              {translate(language, "importLyrics")}
            </DropdownItem>
            {isCustomLyrics ? (
              <DropdownItem
                textValue={translate(language, "removeCustomLyrics")}
                onAction={() => onRemoveCustomLyrics?.()}
                className="text-[var(--status-danger)]"
              >
                <Trash size={14} />
                {translate(language, "removeCustomLyrics")}
              </DropdownItem>
            ) : null}
            {/* The on/off toggle lives on the lyrics view itself, next to the source chip
                (see LyricsToolChips) — both read and write the same showLyricsTranslation
                state, so a second toggle here would only duplicate it. The language stays
                here: it is a long list, and a submenu suits it better than a control in the
                corner of the lyrics view. */}
            {showLyricsTranslation ? (
              <DropdownSubmenuTrigger>
                <DropdownItem textValue="Language">
                  <Translate size={14} />
                  {TRANSLATION_LANGS.find((l) => l.code === lyricsTranslationLang)?.name ||
                    lyricsTranslationLang}
                  <DropdownSubmenuIndicator className="ml-auto" />
                </DropdownItem>
                {/* Inline height, not max-h-80: HeroUI sizes its popover from the available
                    viewport space, and that wins over the utility class — with 44 entries the
                    menu grew to the full window height. */}
                <DropdownPopover className="min-w-40 overflow-y-auto scrollable" style={{ maxHeight: 320 }}>
                  <DropdownMenu aria-label="Language">
                    {TRANSLATION_LANGS.map(({ code, name }) => (
                      <DropdownItem
                        key={code}
                        textValue={name}
                        onAction={() => onSetLyricsTranslationLang?.(code)}
                        className={
                          lyricsTranslationLang === code ? "text-primary" : "text-secondary"
                        }
                      >
                        {name}
                        {lyricsTranslationLang === code && (
                          <Check size={12} className="ml-auto text-accent" />
                        )}
                      </DropdownItem>
                    ))}
                  </DropdownMenu>
                </DropdownPopover>
              </DropdownSubmenuTrigger>
            ) : null}
          </DropdownSection>

          {/* Dedicated lyrics browser and preview. */}
          <DropdownSection className="w-full border-t border-border mt-1 pt-1">
            <DropdownItem
              textValue={translate(language, "browseLyrics")}
              onAction={() => onOpenLyricsBrowser?.()}
            >
              <Microphone size={14} />
              {translate(language, "browseLyrics")}
            </DropdownItem>
          </DropdownSection>

          {/* Download / Export */}
          <DropdownSection className="w-full border-t border-border mt-1 pt-1">
            {downloaded ? (
              <DropdownItem textValue={translate(language, "downloaded")} isDisabled>
                <DownloadSimple size={14} />
                {translate(language, "downloaded")}
              </DropdownItem>
            ) : downloading ? (
              <DropdownItem textValue={translate(language, "downloading")} isDisabled>
                <DownloadSimple size={14} />
                {translate(language, "downloading")}
              </DropdownItem>
            ) : (
              <DropdownItem
                textValue={translate(language, "download")}
                onAction={() => onDownloadSong?.(track)}
              >
                <DownloadSimple size={14} />
                {translate(language, "download")}
              </DropdownItem>
            )}
            <DropdownItem
              textValue={translate(language, "saveAsMp3")}
              onAction={() => onExportSong?.(track, "mp3")}
            >
              <MusicNote size={14} />
              {translate(language, "saveAsMp3")}
            </DropdownItem>
            <DropdownItem
              textValue={translate(language, "saveAsOpus")}
              onAction={() => onExportSong?.(track, "opus")}
            >
              <MusicNote size={14} />
              {translate(language, "saveAsOpus")}
            </DropdownItem>
          </DropdownSection>

          <DropdownSection className="w-full border-t border-border mt-1 pt-1">
            <DropdownSubmenuTrigger>
              <DropdownItem textValue={translate(language, "share")}>
                <ShareNodes size={14} />
                {translate(language, "share")}
                <DropdownSubmenuIndicator className="ml-auto" />
              </DropdownItem>
              <DropdownPopover className="min-w-56">
                <DropdownMenu aria-label={translate(language, "share")}>
                  <DropdownSection>
                    <DropdownItem
                      textValue={translate(language, "copyShareLink")}
                      onAction={() =>
                        navigator.clipboard
                          .writeText(buildShareLink(track))
                          .then(() => toast.success(translate(language, "linkCopied")))
                          .catch(() => {})
                      }
                    >
                      <ShareNodes size={14} />
                      {translate(language, "copyShareLink")}
                    </DropdownItem>
                    <DropdownItem
                      textValue={translate(language, "copyKodamaLink")}
                      onAction={() =>
                        navigator.clipboard
                          .writeText(`kodama://song/${track.videoId}`)
                          .then(() => toast.success(translate(language, "linkCopied")))
                          .catch(() => {})
                      }
                    >
                      <Copy size={14} />
                      {translate(language, "copyKodamaLink")}
                    </DropdownItem>
                    <DropdownItem
                      textValue={translate(language, "copyYtMusicLink")}
                      onAction={() =>
                        navigator.clipboard
                          .writeText(`https://music.youtube.com/watch?v=${track.videoId}`)
                          .then(() => toast.success(translate(language, "linkCopied")))
                          .catch(() => {})
                      }
                    >
                      <Copy size={14} />
                      {translate(language, "copyYtMusicLink")}
                    </DropdownItem>
                    <DropdownItem
                      textValue={translate(language, "copyYoutubeLink")}
                      onAction={() =>
                        navigator.clipboard
                          .writeText(`https://youtube.com/watch?v=${track.videoId}`)
                          .then(() => toast.success(translate(language, "linkCopied")))
                          .catch(() => {})
                      }
                    >
                      <Copy size={14} />
                      {translate(language, "copyYoutubeLink")}
                    </DropdownItem>
                  </DropdownSection>
                </DropdownMenu>
              </DropdownPopover>
            </DropdownSubmenuTrigger>
          </DropdownSection>
        </DropdownMenu>
      </DropdownPopover>
    </Dropdown>
  );
}
