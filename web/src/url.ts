/** A link is offered only for a parsed https URL whose hostname is exactly earthquake.usgs.gov,
 * with no credentials, no explicit port, and no whitespace, control characters or backslashes. */
export function isSafeUsgsUrl(value: unknown): value is string {
  if (typeof value !== "string" || value.length === 0) return false;
  // eslint-disable-next-line no-control-regex
  if (/[\u0000- \u007f\\]/.test(value)) return false;
  let u: URL;
  try {
    u = new URL(value);
  } catch {
    return false;
  }
  return (
    u.protocol === "https:" &&
    u.hostname === "earthquake.usgs.gov" &&
    u.username === "" &&
    u.password === "" &&
    u.port === "" &&
    !value.includes("@")
  );
}
