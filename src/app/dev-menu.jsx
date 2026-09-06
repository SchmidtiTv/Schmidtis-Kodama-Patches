import {
  Dropdown,
  DropdownItem,
  DropdownPopover,
  DropdownSection,
  DropdownTrigger,
} from "@heroui/react";

import { DropdownMenu } from "@/shared/ui/zoomed-heroui.jsx";
import { ArrowClockwise, Bug, MusicNote, Queue, Trash } from "@/shared/icons/icons.jsx";

function clearStorageAndReload() {
  const confirmed = window.confirm(
    "Clear all local and session storage, then reload Kodama? This resets local preferences and cached UI state."
  );
  if (!confirmed) return;

  window.localStorage.clear();
  window.sessionStorage.clear();
  window.location.reload();
}

export default function DevMenu({ player, addToast }) {
  const clearQueue = () => {
    player.setQueue([]);
    addToast("Queue cleared", "success");
  };

  const resetPlayback = async () => {
    await player.stopPlayback();
    player.setCurrentTrack(null);
    player.setQueue([]);
    addToast("Playback state cleared", "success");
  };

  return (
    <div className="fixed left-4 bottom-30 z-100000">
      <Dropdown>
        <DropdownTrigger
          data-testid="dev-menu-trigger"
          className="min-w-0 h-8 gap-1.5 rounded-full border border-border bg-elevated/95 px-3 shadow-lg backdrop-blur-xl text-secondary hover:text-primary hover:bg-hover"
          aria-label="Open development menu"
        >
          <Bug size={13} />
          <span className="text-t10 font-bold tracking-wider">DEV</span>
        </DropdownTrigger>
        <DropdownPopover
          placement="top start"
          className="[--dd-min-w:15rem] data-[entering]:animate-in data-[entering]:fade-in-0 data-[entering]:zoom-in-95 data-[entering]:slide-in-from-bottom-2 data-[entering]:duration-150"
        >
          <DropdownMenu aria-label="Development tools">
            <DropdownSection>
              <DropdownItem textValue="Clear queue" onAction={clearQueue}>
                <Queue size={14} />
                Clear queue
              </DropdownItem>
              <DropdownItem textValue="Reset playback" onAction={resetPlayback}>
                <MusicNote size={14} />
                Reset playback
              </DropdownItem>
            </DropdownSection>
            <DropdownSection className="w-full border-t border-border mt-1 pt-1">
              <DropdownItem textValue="Reload app" onAction={() => window.location.reload()}>
                <ArrowClockwise size={14} />
                Reload app
              </DropdownItem>
              <DropdownItem
                textValue="Clear browser state and reload"
                onAction={clearStorageAndReload}
                className="text-[var(--status-danger)]"
              >
                <Trash size={14} />
                Clear browser state & reload
              </DropdownItem>
            </DropdownSection>
          </DropdownMenu>
        </DropdownPopover>
      </Dropdown>
    </div>
  );
}
