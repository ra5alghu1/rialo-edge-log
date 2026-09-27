(() => {
  function summarize(batches, hours, now = Date.now()) {
    const start = now - hours * 3600000;
    const points = batches.map(batch => ({batch, time: Date.parse(batch.created_at_utc)}))
      .filter(p => Number.isFinite(p.time) && p.time >= start && p.time <= now)
      .sort((a, b) => a.time - b.time);
    const segments = [];
    let previous = null;
    let segment = [];
    let minimum = Infinity, maximum = -Infinity, sum = 0, count = 0;
    for (const point of points) {
      const b = point.batch, t = b.temperature;
      if (!t || ![t.minimum, t.average, t.maximum].every(v => typeof v === 'number' && Number.isFinite(v))) {
        if (segment.length) segments.push(segment);
        segment = []; previous = null; continue;
      }
      if (previous && (point.time - previous.time > 10 * 60000 ||
          b.boot_id !== previous.batch.boot_id || b.simulated !== previous.batch.simulated ||
          b.first_sequence !== previous.batch.last_sequence + 1)) {
        if (segment.length) segments.push(segment);
        segment = [];
      }
      segment.push(point); previous = point;
      minimum = Math.min(minimum, t.minimum); maximum = Math.max(maximum, t.maximum);
      sum += t.average; count++;
    }
    if (segment.length) segments.push(segment);
    return {start, end: now, segments, count, minimum: count ? minimum : null,
      maximum: count ? maximum : null, average: count ? sum / count : null};
  }
  globalThis.RialoHistory = {summarize};
})();
