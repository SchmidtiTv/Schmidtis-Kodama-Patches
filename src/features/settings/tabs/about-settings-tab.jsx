import { useState } from "react";
import { LegalModal, LegalLinks } from "../legal.jsx";
import { APP_VERSION } from "../settings-support.jsx";
import {
  BrandBluesky,
  BrandDiscord,
  BrandGithub,
  BrandTiktok,
  BrandTwitch,
  BrandYoutube,
  Globe,
  Link,
  MugHot,
} from "@/shared/icons/icons.jsx";
import { Button, CardRoot } from "@heroui/react";
import { openUrl } from "@tauri-apps/plugin-opener";
export function AboutSettingsTab({ t }) {
  const [legalPage, setLegalPage] = useState(null);
  return (
    <>
      {/* Logo + App Info */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
          padding: "12px 0 28px",
        }}
      >
        <img
          src="/Kodama%20Logo%20Full.svg"
          alt="Kodama"
          style={{
            width: 200,
            height: "auto",
            marginBottom: 12,
          }}
        />
        <div
          style={{
            fontSize: "var(--t13)",
            color: "var(--text-muted)",
            marginBottom: 12,
          }}
        >
          v{APP_VERSION}
        </div>
        <div
          style={{
            fontSize: "var(--t13)",
            color: "var(--text-secondary)",
            maxWidth: 420,
            lineHeight: 1.6,
            marginBottom: 20,
          }}
        >
          {t("aboutDesc")}
        </div>
        <div className="flex gap-2.5 flex-wrap justify-center">
          <Button
            variant="secondary"
            size="sm"
            onPress={() => openUrl("https://kiyoshithedevil.github.io/Kodama/")}
          >
            <Globe size={14} />
            Website
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onPress={() => openUrl("https://github.com/KiyoshiTheDevil/Kodama")}
          >
            <BrandGithub size={14} />
            GitHub
          </Button>
          <Button
            size="sm"
            className="bg-[#5865F2]! text-white! font-semibold"
            onPress={() => openUrl("https://discord.gg/PzSsPF7KW")}
          >
            <BrandDiscord size={14} />
            Discord
          </Button>
          <Button
            size="sm"
            className="bg-[#FFDD00]! text-black! font-semibold"
            onPress={() => openUrl("https://buymeacoffee.com/kiyoshi_the_devil")}
          >
            ☕ Buy me a coffee
          </Button>
          <Button
            size="sm"
            className="bg-[#FF5E5B]! text-white! font-semibold"
            onPress={() => openUrl("https://ko-fi.com/kiyoshi_the_devil")}
          >
            <MugHot size={14} />
            Ko-fi
          </Button>
        </div>
        <div className="mt-2.5">
          <LegalLinks onPage={setLegalPage} t={t} />
        </div>
        <LegalModal page={legalPage} onPage={setLegalPage} t={t} />
      </div>

      {/* Contributors */}
      <div
        style={{
          height: "0.5px",
          background: "var(--border)",
          marginBottom: 24,
        }}
      />
      <div
        style={{
          fontSize: "var(--t11)",
          fontWeight: 700,
          color: "var(--text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          marginBottom: 14,
        }}
      >
        {t("contributors")}
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          marginBottom: 28,
        }}
      >
        {[
          {
            name: "Kiyoshi The Devil",
            role: t("contributorRoleDev"),
            avatar: "KiyoshiTheDevil_ProfileImage.png",
            links: [
              {
                icon: <BrandTwitch size={13} />,
                url: "https://twitch.tv/kiyoshi_the_devil",
              },
              {
                icon: <BrandYoutube size={13} />,
                url: "https://www.youtube.com/@kiyoshi_the_devil",
              },
              {
                icon: <BrandBluesky size={13} />,
                url: "https://bsky.app/profile/kiyoshi-the-devil.bsky.social",
              },
            ],
          },
          {
            name: "Grains Of Art",
            role: t("contributorRoleAlphaTesterArtist"),
            avatar: "GrainsOfArt_ProfileImage.png",
            links: [
              {
                icon: <BrandTwitch size={13} />,
                url: "https://www.twitch.tv/greekgeekgames",
              },
              {
                icon: <BrandYoutube size={13} />,
                url: "https://www.youtube.com/@GrainsOfArt",
              },
              {
                icon: <Link size={13} />,
                url: "https://linktr.ee/GrainsOfArt",
              },
            ],
          },
          {
            name: "LMary52",
            role: t("contributorRoleAlphaTester"),
            avatar: "LMary52_ProfileImage.png",
            links: [
              {
                icon: <BrandTwitch size={13} />,
                url: "https://www.twitch.tv/lmary52",
              },
              {
                icon: <BrandYoutube size={13} />,
                url: "https://www.youtube.com/@LMary52",
              },
              {
                icon: <BrandTiktok size={13} />,
                url: "https://www.tiktok.com/@lmary52",
              },
              {
                icon: <BrandBluesky size={13} />,
                url: "https://bsky.app/profile/lmary52.bsky.social",
              },
            ],
          },
        ].map((c) => (
          <CardRoot
            key={c.name}
            variant="secondary"
            className="bg-surface-1 flex flex-row items-center gap-3.5 px-4 py-3"
          >
            {c.avatar ? (
              <img
                src={`/${c.avatar}`}
                alt={c.name}
                className="w-9 h-9 rounded-full shrink-0 object-cover"
              />
            ) : (
              <div
                className="w-9 h-9 rounded-full shrink-0 flex items-center justify-center text-t13 font-bold text-white"
                style={{
                  background: "linear-gradient(135deg, var(--accent), #FF008C)",
                }}
              >
                {c.name[0].toUpperCase()}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <div className="text-t13 font-semibold">{c.name}</div>
              <div className="text-t11 text-muted mt-0.5">{c.role}</div>
            </div>
            <div className="flex gap-0.5 shrink-0">
              {c.links.map((l, i) => (
                <Button
                  key={i}
                  variant="ghost"
                  size="sm"
                  isIconOnly
                  className="text-muted hover:text-accent"
                  onPress={() => openUrl(l.url)}
                >
                  {l.icon}
                </Button>
              ))}
            </div>
          </CardRoot>
        ))}
      </div>

      {/* Tools */}
      <div
        style={{
          fontSize: "var(--t11)",
          fontWeight: 700,
          color: "var(--text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          marginBottom: 10,
        }}
      >
        {t("tools")}
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 2,
        }}
      >
        {[
          {
            name: "Claude",
            link: "https://claude.ai",
          },
          {
            name: "Figma",
            link: "https://figma.com",
          },
          {
            name: "Font Awesome",
            link: "https://fontawesome.com",
          },
        ].map((tool) => (
          <button
            key={tool.name}
            onClick={() => openUrl(tool.link)}
            style={{
              background: "none",
              border: "none",
              padding: "4px 0",
              fontSize: "var(--t13)",
              color: "var(--text-secondary)",
              fontFamily: "var(--font)",
              cursor: "default",
              textAlign: "left",
              transition: "color 0.15s",
              width: "fit-content",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--accent)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
          >
            {tool.name}
          </button>
        ))}
      </div>

      {/* Legal */}
      <div
        style={{
          marginTop: 28,
          paddingTop: 20,
          borderTop: "0.5px solid var(--border)",
          display: "flex",
          justifyContent: "center",
          gap: 6,
          alignItems: "center",
        }}
      >
        <span
          style={{
            fontSize: "var(--t11)",
            color: "var(--text-muted)",
          }}
        >
          © {new Date().getFullYear()} KiyoshiTheDevil ·
        </span>
        <button
          onClick={() => openUrl("https://github.com/KiyoshiTheDevil/Kodama/blob/master/LICENSE")}
          style={{
            background: "none",
            border: "none",
            padding: 0,
            cursor: "default",
            fontSize: "var(--t11)",
            color: "var(--text-muted)",
            fontFamily: "var(--font)",
            transition: "color 0.15s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--accent)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
        >
          GNU General Public License v3.0
        </button>
      </div>
    </>
  );
}
