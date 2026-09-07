import { useState } from "react";
import {
  cn,
  Button,
  ModalBackdrop,
  ModalContainer,
  ModalHeader,
  ModalIcon,
  ModalHeading,
  ModalBody,
  ModalFooter,
  ModalCloseTrigger,
} from "@heroui/react";
import { ModalDialog, ModalRoot } from "@/shared/ui/zoomed-heroui.jsx";
import { renderNewsBody } from "@/shared/ui/news-body.jsx";
import { Megaphone, Star, ArrowClockwise } from "@/shared/icons/icons.jsx";

export function NewsModal({ news, unreadIds, onRefresh, onClose, t }) {
  const [refreshing, setRefreshing] = useState(false);
  const doRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      await onRefresh?.();
    } finally {
      setRefreshing(false);
    }
  };
  const badgeFor = (type) => {
    if (type === "beta")
      return {
        label: t("newsBeta") || "Closed Beta",
        bg: "color-mix(in srgb, #f4a020 20%, transparent)",
        fg: "#f4b840",
      };
    if (type === "note")
      return {
        label: t("newsNote") || "Hinweis",
        bg: "rgba(255,255,255,0.08)",
        fg: "var(--text-secondary)",
      };
    if (type === "fix")
      return {
        label: t("newsFix") || "Fix",
        bg: "color-mix(in srgb, #1d9e75 22%, transparent)",
        fg: "#3ec79a",
      };
    return {
      label: t("newsUpdate") || "Update",
      bg: "color-mix(in srgb, var(--accent) 20%, transparent)",
      fg: "var(--accent)",
    };
  };
  const list = news || [];
  const [selectedId, setSelectedId] = useState(() => list[0]?.id || null);
  const selected = list.find((n) => n.id === selectedId) || list[0] || null;
  const sb = selected ? badgeFor(selected.type) : null;

  return (
    <ModalRoot
      isOpen
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <ModalBackdrop className="z-[300]!">
        <ModalContainer placement="center" size="xl" className="w-[880px] max-w-[94vw]">
          <ModalDialog>
            <ModalHeader>
              <ModalIcon>
                <Megaphone size={18} />
              </ModalIcon>
              <ModalCloseTrigger />
              <ModalHeading>{t("news") || "Neuigkeiten"}</ModalHeading>
            </ModalHeader>
            <ModalBody className="p-0! overflow-hidden">
              {list.length === 0 ? (
                <div className="text-t13 text-muted text-center py-12">
                  {t("newsEmpty") || "Keine Neuigkeiten."}
                </div>
              ) : (
                <div className="flex" style={{ height: "62vh" }}>
                  {/* Left: entry list */}
                  <div className="w-[268px] shrink-0 border-r border-border overflow-y-auto overflow-x-hidden">
                    {list.map((n) => {
                      const b = badgeFor(n.type);
                      const unread = unreadIds?.has(n.id);
                      const active = n.id === selected?.id;
                      return (
                        <button
                          key={n.id}
                          onClick={() => setSelectedId(n.id)}
                          className={cn(
                            "w-full text-left flex gap-2.5 px-3 py-2.5 border-b border-border transition-colors duration-100",
                            active ? "bg-accent-dim" : "hover:bg-hover"
                          )}
                        >
                          {n.image ? (
                            <img
                              src={n.image}
                              alt=""
                              className="w-11 h-11 rounded-lg object-cover shrink-0"
                            />
                          ) : (
                            <div
                              className="w-11 h-11 rounded-lg shrink-0 flex items-center justify-center"
                              style={{ background: b.bg }}
                            >
                              <Megaphone size={16} style={{ color: b.fg }} />
                            </div>
                          )}
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5 mb-0.5">
                              <span
                                className="text-[9px] font-bold px-1.5 py-0.5 rounded"
                                style={{ background: b.bg, color: b.fg }}
                              >
                                {b.label}
                              </span>
                              {n.important && (
                                <Star size={10} weight="fill" className="text-accent shrink-0" />
                              )}
                              {unread && (
                                <span
                                  className="w-1.5 h-1.5 rounded-full ml-auto shrink-0"
                                  style={{ background: "var(--accent)" }}
                                />
                              )}
                            </div>
                            <div
                              className="text-t13 font-semibold truncate"
                              style={{ color: active ? "var(--accent)" : "var(--text-primary)" }}
                            >
                              {n.title || "—"}
                            </div>
                            <div className="text-t10 text-muted truncate">
                              {n.date}
                              {n.min_version ? ` · ab ${n.min_version}` : ""}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                  {/* Right: full entry */}
                  <div className="flex-1 min-w-0 overflow-y-auto">
                    {selected && (
                      <>
                        {selected.image && (
                          <img
                            src={selected.image}
                            alt=""
                            className="w-full block"
                            style={{ maxHeight: 220, objectFit: "cover" }}
                          />
                        )}
                        <div className="px-6 py-5">
                          <div className="flex items-center gap-2 mb-2.5 flex-wrap">
                            <span
                              className="text-t10 font-bold px-2 py-0.5 rounded-md"
                              style={{ background: sb.bg, color: sb.fg }}
                            >
                              {sb.label}
                            </span>
                            {selected.important && (
                              <Star size={13} weight="fill" className="text-accent" />
                            )}
                            {selected.date && (
                              <span className="text-t12 text-muted">{selected.date}</span>
                            )}
                            {selected.min_version && (
                              <span className="text-t11 text-muted">
                                · ab {selected.min_version}
                                {selected.max_version ? ` – ${selected.max_version}` : ""}
                              </span>
                            )}
                          </div>
                          <div className="text-t20 font-bold mb-3 leading-snug">
                            {selected.title || "—"}
                          </div>
                          {selected.body && (
                            <div className="text-t14 text-secondary leading-relaxed">
                              {renderNewsBody(selected.body)}
                            </div>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )}
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                className="mr-auto"
                isDisabled={refreshing}
                onPress={doRefresh}
              >
                <span className="flex items-center gap-1.5">
                  <ArrowClockwise
                    size={14}
                    style={refreshing ? { animation: "spin2 0.8s linear infinite" } : undefined}
                  />
                  {t("refresh") || "Aktualisieren"}
                </span>
              </Button>
              <Button color="accent" variant="solid" onPress={onClose}>
                {t("close") || "Schließen"}
              </Button>
            </ModalFooter>
          </ModalDialog>
        </ModalContainer>
      </ModalBackdrop>
    </ModalRoot>
  );
}
