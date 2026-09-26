export const INTEGRITY_CONFIG = {
  SAMPLE_MS: 200,
  LOOK_AWAY_MIN_DURATION_MS: 1500,
  FACE_MISSING_MIN_DURATION_MS: 2000,
  MULTIPLE_FACE_MIN_DURATION_MS: 1000,
  RECOVERY_GRACE_MS: 400,
  MAX_SAMPLE_GAP_MS: 1500,
  HORIZONTAL_DELTA: 0.22,
  VERTICAL_DELTA: 0.14,
  CALIBRATION_SAMPLES: 10,
};

export function orientationScore(value, baseline) {
  if (!value || !baseline) return null;
  return Math.max(
    Math.abs(value.horizontal - baseline.horizontal) / INTEGRITY_CONFIG.HORIZONTAL_DELTA,
    Math.abs(value.vertical - baseline.vertical) / INTEGRITY_CONFIG.VERTICAL_DELTA,
  );
}
