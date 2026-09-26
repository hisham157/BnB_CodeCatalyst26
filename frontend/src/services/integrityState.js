import { INTEGRITY_CONFIG as CONFIG } from './integrityConfig.js';

export function createIntegrityTracker(emit, config = CONFIG) {
  const limits = { LOOKING_AWAY: config.LOOK_AWAY_MIN_DURATION_MS, FACE_MISSING: config.FACE_MISSING_MIN_DURATION_MS, MULTIPLE_FACES: config.MULTIPLE_FACE_MIN_DURATION_MS };
  const states = new Map();
  let lastSample = null;
  function close(type, entry, end, reason) {
    if (!entry.confirmed) return;
    const started = entry.start / 1000, ended = Math.max(entry.start, end) / 1000;
    emit({ event_type: type, turn_number: entry.turn, started_at_seconds: started,
      ended_at_seconds: ended, duration_seconds: ended - started,
      metadata: { orientation_method: 'normalized_landmark_ratios', monitoring_quality: 'heuristic', threshold_ms: limits[type], end_reason: reason } });
  }
  function flush(now, reason = 'monitoring_stopped') {
    for (const [type, entry] of states) close(type, entry, entry.recovery ?? Math.min(now, lastSample ?? now), reason);
    states.clear(); lastSample = null;
  }
  return {
    flush,
    update(observation, now, turn) {
      if (lastSample !== null && now - lastSample > config.MAX_SAMPLE_GAP_MS) flush(lastSample, 'frame_gap');
      lastSample = now;
      const flags = {
        LOOKING_AWAY: observation.faceCount === 1 && observation.orientationScore !== null && observation.orientationScore > 1,
        FACE_MISSING: observation.faceCount === 0,
        MULTIPLE_FACES: observation.faceCount >= 2,
      };
      for (const [type, matching] of Object.entries(flags)) {
        let entry = states.get(type);
        if (matching) {
          if (!entry) { entry = { start: now, turn: turn ?? null, confirmed: false, recovery: null }; states.set(type, entry); }
          entry.recovery = null;
          if (now - entry.start >= limits[type]) entry.confirmed = true;
        } else if (entry) {
          if (!entry.confirmed) { states.delete(type); continue; }
          entry.recovery ??= now;
          if (now - entry.recovery >= config.RECOVERY_GRACE_MS) {
            close(type, entry, entry.recovery, 'recovered'); states.delete(type);
          }
        }
      }
    },
  };
}
