import { TogetherDebug } from "@/features/together/index.js";
import { Button } from "@heroui/react";
import { DebugTab } from "../settings-support.jsx";
import { EyeSlash } from "@/shared/icons/icons.jsx";
export function DebugSettingsTab({ setDebugUnlocked, setTab, t }) {
  return (
    <>
      <TogetherDebug />
      <DebugTab t={t} />
      <div className="mt-6">
        <Button
          variant="ghost"
          size="sm"
          onPress={() => {
            localStorage.removeItem("kiyoshi-debug-unlocked");
            setDebugUnlocked(false);
            window.dispatchEvent(
              new CustomEvent("kiyoshi-debug-change", {
                detail: {
                  unlocked: false,
                },
              })
            );
            setTab("darstellung");
          }}
        >
          <EyeSlash size={15} />
          {t("hideDebugMenu")}
        </Button>
      </div>
    </>
  );
}
