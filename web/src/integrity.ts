import { DatasetError } from "./data";

export async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) {
    throw new DatasetError(["cannot verify artifact integrity: Web Crypto is unavailable here (it needs localhost or https)"]);
  }
  const digest = await subtle.digest("SHA-256", bytes as BufferSource);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

const HEX64 = /^[0-9a-f]{64}$/;

/** The analysis was computed from one exact `events.json`. Hash the bytes that were actually
 * loaded (not a re-serialisation) and compare with the hash recorded in analysis.json. */
export async function verifyEventsBytes(
  eventsBytes: Uint8Array,
  analysisDoc: unknown,
  hasher: (b: Uint8Array) => Promise<string> = sha256Hex,
): Promise<void> {
  const expected =
    typeof analysisDoc === "object" && analysisDoc !== null ? (analysisDoc as Record<string, unknown>).events_sha256 : undefined;
  if (typeof expected !== "string" || !HEX64.test(expected)) {
    throw new DatasetError(["analysis.json has no valid events_sha256, so events.json cannot be verified"]);
  }
  const actual = await hasher(eventsBytes);
  if (actual !== expected) {
    throw new DatasetError([
      `events.json does not match the analysis: loaded bytes hash to ${actual} but analysis.json recorded ${expected}. ` +
        "The two files come from different builds; regenerate them together.",
    ]);
  }
}
