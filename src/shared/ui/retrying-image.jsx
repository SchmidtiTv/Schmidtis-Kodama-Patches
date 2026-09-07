import { forwardRef, useEffect, useMemo, useState } from "react";

const INITIAL_RETRY_DELAY_MS = 2_000;
const MAX_RETRY_DELAY_MS = 30_000;
const PLACEHOLDER_IMAGE =
  "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";

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
  {
    src,
    onError,
    onLoad,
    style,
    className,
    loading = "lazy",
    decoding = "async",
    maxRetries = 2,
    ...props
  },
  ref
) {
  const [attempt, setAttempt] = useState(0);
  const [waitingToRetry, setWaitingToRetry] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setAttempt(0);
    setWaitingToRetry(false);
    setFailed(false);
  }, [src]);

  useEffect(() => {
    if (!waitingToRetry || failed) return undefined;

    const timer = window.setTimeout(
      () => {
        setAttempt((currentAttempt) => currentAttempt + 1);
        setWaitingToRetry(false);
      },
      retryDelay(attempt + 1)
    );

    return () => window.clearTimeout(timer);
  }, [attempt, failed, waitingToRetry]);

  const resolvedSrc = useMemo(
    () => (failed ? PLACEHOLDER_IMAGE : retryUrl(src, attempt)),
    [src, attempt, failed]
  );

  return (
    <img
      {...props}
      ref={ref}
      src={resolvedSrc}
      className={[className, failed && "img-failed"].filter(Boolean).join(" ")}
      loading={loading}
      decoding={decoding}
      style={{ ...style, visibility: waitingToRetry ? "hidden" : style?.visibility }}
      onError={(event) => {
        onError?.(event);
        if (attempt >= maxRetries) {
          setWaitingToRetry(false);
          setFailed(true);
          return;
        }
        setWaitingToRetry(true);
      }}
      onLoad={(event) => {
        if (!failed) onLoad?.(event);
        setWaitingToRetry(false);
      }}
    />
  );
});
