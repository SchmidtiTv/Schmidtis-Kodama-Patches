import { useEffect, useState } from "react";
import { requestJson } from "@/shared/api/client.js";

export function useBackendVersions() {
  const [versions, setVersions] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    requestJson("/status", { signal: controller.signal })
      .then((status) => {
        if (
          !controller.signal.aborted &&
          status?.versions &&
          typeof status.versions.ytmusicapi === "string"
        ) {
          setVersions(status.versions);
        }
      })
      .catch(() => {});
    return () => controller.abort();
  }, []);
  return versions;
}
