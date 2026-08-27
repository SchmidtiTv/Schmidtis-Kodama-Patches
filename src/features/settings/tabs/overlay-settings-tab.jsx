import { ArrowSquareOut, Copy, Globe, Link, ScreencastSimple } from "@/shared/icons/icons.jsx";
import { Button, InputRoot, TextFieldRoot, toast } from "@heroui/react";
import { useIntegrationSettings } from "../settings-context.jsx";
import { SettingRow, Toggle } from "@/shared/ui/settings-controls.jsx";

export function OverlaySettingsTab({ onOpenOverlayEditor, t }) {
  const { obsEnabled, obsPort, obsPortInput, setObsPortInput, toggleObs, onObsPortSave } =
    useIntegrationSettings();
  const overlayUrl = `http://localhost:${obsPort}/overlay`;

  return (
    <div className="flex flex-col gap-4">
      <SettingRow
        label={t("ovlOpenEditorBtn")}
        description={t("ovlOpenEditorDesc")}
        icon={<ScreencastSimple />}
      >
        <Button
          data-testid="open-overlay-editor"
          size="sm"
          variant="solid"
          color="accent"
          className="flex items-center gap-1.5"
          onPress={() => onOpenOverlayEditor?.()}
        >
          <ArrowSquareOut size={14} />
          {t("ovlOpenEditorBtn")}
        </Button>
      </SettingRow>
      <SettingRow label={t("overlayEnable")} description={t("overlayEnableDesc")} icon={<Globe />}>
        <Toggle value={obsEnabled} onChange={toggleObs} />
      </SettingRow>
      <SettingRow label={t("overlayPort")} description={t("overlayPortDesc")} icon={<Link />}>
        <div className="flex items-center gap-1.5">
          <TextFieldRoot
            value={obsPortInput}
            onChange={(value) => setObsPortInput(String(value).replace(/[^0-9]/g, ""))}
            aria-label={t("overlayPort")}
            className="w-[76px]"
          >
            <InputRoot className="text-t12! h-8!" />
          </TextFieldRoot>
          <Button size="sm" variant="secondary" onPress={() => onObsPortSave(obsPortInput)}>
            {t("save")}
          </Button>
        </div>
      </SettingRow>
      <SettingRow label={t("overlayUrl")} description={overlayUrl} icon={<Copy />}>
        <Button
          size="sm"
          variant="secondary"
          className="flex items-center gap-1.5"
          onPress={() => {
            navigator.clipboard?.writeText(overlayUrl).catch(() => {});
            toast.success(t("copied"));
          }}
        >
          <Copy size={14} />
          {t("copy")}
        </Button>
      </SettingRow>
    </div>
  );
}
