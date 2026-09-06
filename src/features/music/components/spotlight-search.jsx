import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  SearchFieldClearButton,
  SearchFieldGroup,
  SearchFieldInput,
  SearchFieldRoot,
  SearchFieldSearchIcon,
} from "@heroui/react";

import { API } from "@/shared/api/client.js";
import { MagnifyingGlass } from "@/shared/icons/icons.jsx";
import { IS_MAC } from "@/shared/lib/platform.js";
import { useLang } from "@/shared/i18n/context.jsx";

const isPlaylistLink = (query) => {
  const urlMatch = query.match(/[?&]list=([A-Za-z0-9_-]+)/);
  if (urlMatch && /(?:music\.)?youtube\.com|youtu\.be/i.test(query)) return urlMatch[1];
  return /^(VL)?(PL|OLAK5uy_|RDCLAK|RDAMPL)[A-Za-z0-9_-]{10,}$/.test(query) ? query : null;
};

export function SpotlightSearch({
  onSearch,
  onOpenPlaylist,
  onCloseOverlay,
  shortcutParts,
  launcherStyle,
  showLauncher = true,
}) {
  const t = useLang();
  const inputRef = useRef(null);
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const [tetoVisible, setTetoVisible] = useState(false);
  const [tetoLeaving, setTetoLeaving] = useState(false);
  const tetoTimerRef = useRef(null);

  useEffect(() => {
    const openSearch = () => setIsOpen(true);
    window.addEventListener("kodama-open-search", openSearch);
    return () => window.removeEventListener("kodama-open-search", openSearch);
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    const focusInput = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(focusInput);
  }, [isOpen]);

  useEffect(() => {
    const trimmedQuery = query.trim();
    if (trimmedQuery.length < 2) return;
    const requestId = setTimeout(() => {
      fetch(`${API}/search/suggestions?q=${encodeURIComponent(trimmedQuery)}`)
        .then((response) => response.json())
        .then((data) => setSuggestions(Array.isArray(data.suggestions) ? data.suggestions : []))
        .catch(() => setSuggestions([]));
    }, 180);
    return () => clearTimeout(requestId);
  }, [query]);

  useEffect(() => () => clearTimeout(tetoTimerRef.current), []);

  const close = () => {
    setIsOpen(false);
    setActiveSuggestion(-1);
  };
  const hideTeto = () => {
    setTetoLeaving(true);
    clearTimeout(tetoTimerRef.current);
    tetoTimerRef.current = setTimeout(() => {
      setTetoVisible(false);
      setTetoLeaving(false);
    }, 450);
  };
  const submit = (value) => {
    const trimmedQuery = value.trim();
    if (!trimmedQuery) return;
    const playlistId = isPlaylistLink(trimmedQuery);
    if (playlistId) onOpenPlaylist?.({ playlistId: playlistId.replace(/^VL/, "") });
    else onSearch(trimmedQuery);
    onCloseOverlay?.();
    if (trimmedQuery.toLowerCase().includes("teto")) {
      clearTimeout(tetoTimerRef.current);
      setTetoLeaving(false);
      setTetoVisible(true);
    } else if (tetoVisible) {
      hideTeto();
    }
    setQuery("");
    close();
  };
  const handleKeyDown = (event) => {
    if (event.nativeEvent.isComposing) return;
    if (event.key === "ArrowDown" && suggestions.length > 0) {
      event.preventDefault();
      setActiveSuggestion((index) => (index + 1) % suggestions.length);
    } else if (event.key === "ArrowUp" && suggestions.length > 0) {
      event.preventDefault();
      setActiveSuggestion((index) => (index <= 0 ? suggestions.length - 1 : index - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      submit(suggestions[activeSuggestion] || query);
    } else if (event.key === "Escape") {
      event.preventDefault();
      close();
    }
  };

  return (
    <>
      {showLauncher && (
        <button
          type="button"
          data-testid="spotlight-search-trigger"
          aria-label={t("search")}
          onClick={() => setIsOpen(true)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            width: "100%",
            padding: "8px 12px",
            border: "1px solid var(--border)",
            borderRadius: "999px",
            background: "color-mix(in srgb, var(--bg-elevated) 88%, transparent)",
            boxShadow: "0 5px 16px rgba(0,0,0,0.18)",
            color: "var(--text-secondary)",
            cursor: "default",
            fontFamily: "var(--font)",
            fontSize: "var(--t13)",
            ...launcherStyle,
          }}
        >
          <MagnifyingGlass size={16} />
          <span style={{ flex: 1, textAlign: "left" }}>{t("search")}</span>
          {shortcutParts?.length > 0 && (
            <kbd
              style={{
                padding: "2px 5px",
                borderRadius: "var(--r-sm)",
                background: "var(--bg-hover)",
                color: "var(--text-muted)",
                fontSize: "var(--t11)",
              }}
            >
              {shortcutParts.join(IS_MAC ? "" : " ")}
            </kbd>
          )}
        </button>
      )}

      {isOpen &&
        createPortal(
          <div
            data-testid="spotlight-search"
            role="presentation"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) close();
            }}
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 10000,
              display: "flex",
              justifyContent: "center",
              alignItems: "flex-start",
              paddingTop: "min(18vh, 150px)",
              background: "rgba(0, 0, 0, 0.42)",
              backdropFilter: "blur(8px)",
            }}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-label={t("search")}
              style={{
                width: "min(640px, calc(100vw - 32px))",
                overflow: "hidden",
                border: "1px solid var(--border)",
                borderRadius: "var(--r-xl)",
                background: "var(--bg-elevated)",
                boxShadow: "0 24px 64px rgba(0,0,0,0.45)",
              }}
            >
              <SearchFieldRoot
                value={query}
                onChange={(value) => {
                  setQuery(value);
                  setActiveSuggestion(-1);
                  if (value.trim().length < 2) setSuggestions([]);
                }}
                onSubmit={() => submit(query)}
              >
                <SearchFieldGroup style={{ border: "none", borderRadius: 0, minHeight: 54 }}>
                  <SearchFieldSearchIcon>
                    <MagnifyingGlass size={18} />
                  </SearchFieldSearchIcon>
                  <SearchFieldInput
                    ref={inputRef}
                    data-testid="spotlight-search-input"
                    placeholder={t("search")}
                    onKeyDown={handleKeyDown}
                    style={{ fontSize: "var(--t16)" }}
                  />
                  <SearchFieldClearButton />
                </SearchFieldGroup>
              </SearchFieldRoot>
              {suggestions.length > 0 && (
                <div style={{ borderTop: "1px solid var(--border)", padding: 6 }}>
                  {suggestions.map((suggestion, index) => (
                    <button
                      key={suggestion}
                      type="button"
                      onMouseEnter={() => setActiveSuggestion(index)}
                      onClick={() => submit(suggestion)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        width: "100%",
                        gap: 10,
                        padding: "9px 10px",
                        border: "none",
                        borderRadius: 7,
                        background: activeSuggestion === index ? "var(--bg-hover)" : "transparent",
                        color: "var(--text-secondary)",
                        cursor: "default",
                        fontFamily: "var(--font)",
                        fontSize: "var(--t13)",
                        textAlign: "left",
                      }}
                    >
                      <MagnifyingGlass size={14} style={{ opacity: 0.55, flexShrink: 0 }} />
                      <span
                        style={{
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {suggestion}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>,
          document.body
        )}
      {tetoVisible &&
        createPortal(
          <img
            src="/Teto_Drinking_Boba.png"
            alt="Kasane Teto"
            className="fixed bottom-18 right-0 w-auto h-64 pointer-events-none z-9500"
            style={{
              animation: tetoLeaving
                ? "tetoSlideOut 0.45s cubic-bezier(0.4,0,0.2,1) forwards"
                : "tetoSlideIn 0.5s cubic-bezier(0.34,1.56,0.64,1) forwards",
            }}
          />,
          document.body
        )}
    </>
  );
}
