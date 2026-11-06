/** Human-readable date/time from results localPath like 2026-11-06/22-18-11 */
export function formatSnapshotLabel(snapshotId) {
  if (snapshotId == null || snapshotId === "") return "—";
  const s = String(snapshotId);
  const m = s.match(/^(\d{4}-\d{2}-\d{2})\/(\d{2})-(\d{2})-(\d{2})$/);
  if (m) {
    return `${m[1]} ${m[2]}:${m[3]}:${m[4]}`;
  }
  return s;
}
