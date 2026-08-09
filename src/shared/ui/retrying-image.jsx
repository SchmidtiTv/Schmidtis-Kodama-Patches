import { forwardRef, useEffect, useMemo, useState } from "react";

const INITIAL_RETRY_DELAY_MS = 2_000;
const MAX_RETRY_DELAY_MS = 30_000;

function retryUrl(src, attempt) {
  if (!attempt) return src;

  const url = new URL(src, window.location.href);
  url.searchParams.set("__kodama_image_retry", String(attempt));
  return url.toString();
}

function retryDelay(attempt) {
  return Math.min(INITIAL_RETRY_DELAY_MS * 2 ** (attempt - 1), MAX_RETRY_DELAY_MS);
}

// Keeps transient proxy/network failures from leaving a browser broken-image marker in the UI.
// Each retry has a unique query parameter so the browser does not reuse the failed response.
export const RetryingImage = forwardRef(function RetryingImage(
  { src, onError, onLoad, style, loading = "lazy", decoding = "async", ...props },
  ref
) {
  const [attempt, setAttempt] = useState(0);
  const [waitingToRetry, setWaitingToRetry] = useState(false);

  useEffect(() => {
    setAttempt(0);
    setWaitingToRetry(false);
  }, [src]);

  useEffect(() => {
    if (!waitingToRetry) return undefined;

    const timer = window.setTimeout(
      () => {
        setAttempt((currentAttempt) => currentAttempt + 1);
        setWaitingToRetry(false);
      },
      retryDelay(attempt + 1)
    );

    return () => window.clearTimeout(timer);
  }, [attempt, waitingToRetry]);

  const resolvedSrc = useMemo(() => retryUrl(src, attempt), [src, attempt]);

  return (
    <img
      {...props}
      ref={ref}
      src={resolvedSrc}
      loading={loading}
      decoding={decoding}
      style={{ ...style, visibility: waitingToRetry ? "hidden" : style?.visibility }}
      onError={(event) => {
        onError?.(event);
        setWaitingToRetry(true);
      }}
      onLoad={(event) => {
        onLoad?.(event);
        setWaitingToRetry(false);
      }}
    />
  );
});
