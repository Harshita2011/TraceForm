/** Recovery copies use a separate key for every editor so tabs cannot erase each other's work. */
export interface DeviceCopy { content: string; savedAt?: string; label: string }
export const recoveryPrefix = (artifactId: string, owner: string) => `traceform-recovery:${artifactId}:${encodeURIComponent(owner)}`;

export function readDeviceCopies(storage: Storage, artifactId: string, owner: string, serverContent: string) {
  const copies: DeviceCopy[] = []; let damaged = false;
  const parse = (key: string) => { try { return JSON.parse(storage.getItem(key) || 'null'); } catch { damaged = true; return null; } };
  const add = (item: unknown, label: string, skipCurrent = false) => {
    const value = item as DeviceCopy | null;
    if (typeof value?.content === 'string' && (!skipCurrent || value.content !== serverContent) && !copies.some(c => c.content === value.content)) copies.push({...value, label});
  };
  const prefix = recoveryPrefix(artifactId, owner);
  for (let i = 0; i < storage.length; i++) {
    const key = storage.key(i);
    if (key && (key.startsWith(prefix + ':') || key === prefix || key === `traceform-recovery:${artifactId}:${owner}`)) add(parse(key), 'Unsaved recovery copy', true);
  }
  add(parse(`traceform-draft:${artifactId}`), 'Browser draft from an earlier version');
  const history = parse(`traceform-draft:${artifactId}:versions`);
  if (Array.isArray(history)) for (const item of history) add(item, 'Earlier browser draft');
  return {copies, damaged};
}

export function clearAcknowledgedRecovery(storage: Storage, key: string, content: string) {
  const value = JSON.parse(storage.getItem(key) || 'null');
  if (value?.content === content) storage.removeItem(key);
}
