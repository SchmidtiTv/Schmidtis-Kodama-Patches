import { useTogether, roomRemove, myRole } from "./together.js";
import { buildListenerRoomQueue } from "./room-session.js";
import {
  TogetherRoomHeader,
  TogetherPeopleTab,
  SuggestionRow,
  AddedBy,
} from "./TogetherRoomTab.jsx";

export { TogetherSidebar } from "./TogetherSidebar.jsx";
export { TogetherDebug } from "./TogetherDebug.jsx";

/** Public presentation adapter consumed by the player queue dock. */
export function useTogetherQueueAdapter() {
  const room = useTogether();
  const active = room.status === "open" || room.status === "reconnecting";
  return {
    active,
    listener: active && !room.isHost,
    currentTrack: room.state?.track,
    queue: room.queue,
    played: room.played,
    header: <TogetherRoomHeader />,
    people: <TogetherPeopleTab />,
    suggestions:
      room.suggestions.length > 0 ? (
        <div className="px-3 py-2 max-h-40 overflow-y-auto shrink-0 scrollable">
          {room.suggestions.map((suggestion) => (
            <SuggestionRow key={suggestion.id} sg={suggestion} />
          ))}
        </div>
      ) : null,
    hasSuggestions: room.suggestions.length > 0,
    buildListenerQueue: buildListenerRoomQueue,
    canRemove: (track) =>
      myRole() === "cohost" || (track.addedBy?.id && track.addedBy.id === room.you?.id),
    onRemove: roomRemove,
    renderAddedBy: (addedBy) => (addedBy ? <AddedBy addedBy={addedBy} /> : null),
  };
}
