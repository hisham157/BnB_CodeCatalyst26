import { useEffect, useRef, useState } from 'react';
import { INTEGRITY_CONFIG as CONFIG, orientationScore } from '../services/integrityConfig';

export default function useFaceLandmarker(videoRef, enabled, onObservation, onUnavailable) {
  const [status, setStatus] = useState('Waiting for interview');
  const [debug, setDebug] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const callbacks = useRef({ onObservation, onUnavailable });
  callbacks.current = { onObservation, onUnavailable };

  useEffect(() => {
    if (!enabled) { setStatus('Monitoring stopped'); return; }
    let cancelled = false, stream, worker, animation, timer;
    let ready = false, processing = false, lastSent = 0, lastReceived = performance.now();
    let baseline = null, calibration = [], lastVideoTime = -1;
    const video = videoRef.current;
    const release = () => {
      cancelAnimationFrame(animation); clearInterval(timer);
      stream?.getTracks().forEach((track) => { track.onended = null; track.stop(); });
      if (video) video.srcObject = null;
      worker?.postMessage({ type: 'close' }); worker?.terminate();
    };
    const fail = (reason) => {
      if (cancelled) return;
      setStatus(reason === 'CAMERA_PERMISSION_DENIED' ? 'Camera access unavailable. Integrity monitoring is disabled.' : 'Integrity monitoring unavailable. You can continue the interview.');
      callbacks.current.onUnavailable(reason);
      release(); cancelled = true;
    };
    const visibility = () => {
      if (!document.hidden) lastReceived = performance.now();
      if (document.hidden && !cancelled) {
        callbacks.current.onUnavailable('PAGE_HIDDEN');
        setStatus('Monitoring paused while this page is hidden');
      }
    };
    document.addEventListener('visibilitychange', visibility);
    async function frame(now) {
      if (cancelled) return;
      animation = requestAnimationFrame(frame);
      if (document.hidden || !ready || processing || now - lastSent < CONFIG.SAMPLE_MS) return;
      if (video.readyState < 2 || video.currentTime === lastVideoTime) return;
      processing = true; lastSent = now; lastVideoTime = video.currentTime;
      try {
        const bitmap = await createImageBitmap(video, { resizeWidth: 320, resizeHeight: 240 });
        if (cancelled) { bitmap.close(); return; }
        worker.postMessage({ type: 'frame', bitmap, timestamp: now }, [bitmap]);
      } catch { processing = false; fail('TRACKING_FAILED'); }
    }
    async function start() {
      if (!navigator.mediaDevices?.getUserMedia || !window.Worker || !window.OffscreenCanvas || !window.createImageBitmap) {
        fail('UNSUPPORTED_BROWSER'); return;
      }
      setStatus('Requesting camera permission…');
      try { stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 320 }, height: { ideal: 240 }, facingMode: 'user' }, audio: false }); }
      catch (error) { fail(error.name === 'NotAllowedError' ? 'CAMERA_PERMISSION_DENIED' : 'CAMERA_UNAVAILABLE'); return; }
      if (cancelled) { stream.getTracks().forEach((track) => track.stop()); return; }
      stream.getVideoTracks().forEach((track) => { track.onended = () => fail('CAMERA_DISCONNECTED'); });
      video.srcObject = stream;
      try {
        await video.play();
        if (cancelled) return;
        setStatus('Loading local face tracking…');
        const base = new URL(import.meta.env.BASE_URL, window.location.href);
        worker = new Worker(new URL('integrity-worker.js', base));
        worker.onerror = () => fail('MEDIAPIPE_INITIALIZATION_FAILED');
        worker.onmessage = ({ data }) => {
          if (cancelled) return;
          if (data.type === 'error') { fail(data.reason); return; }
          if (data.type === 'ready') { ready = true; lastReceived = performance.now(); setStatus('Face camera normally for two seconds to calibrate.'); return; }
          if (data.type !== 'observation') return;
          processing = false;
          const now = performance.now();
          if (document.hidden) return;
          if (now - lastReceived > CONFIG.MAX_SAMPLE_GAP_MS) callbacks.current.onUnavailable('FRAME_GAP');
          lastReceived = now;
          if (data.faceCount === 1 && !data.orientation) {
            setStatus('Face orientation temporarily unavailable. Move closer to the camera.');
            callbacks.current.onUnavailable('TRACKING_FAILED');
            return;
          }
          if (!baseline && data.faceCount === 1 && data.orientation && Math.abs(data.orientation.horizontal) < 0.15) {
            calibration.push(data.orientation);
            if (calibration.length >= CONFIG.CALIBRATION_SAMPLES) {
              const horizontal = calibration.map((item) => item.horizontal), vertical = calibration.map((item) => item.vertical);
              if (Math.max(...horizontal) - Math.min(...horizontal) < 0.06 && Math.max(...vertical) - Math.min(...vertical) < 0.06) {
                baseline = { horizontal: horizontal.reduce((a, b) => a + b) / horizontal.length, vertical: vertical.reduce((a, b) => a + b) / vertical.length };
              } else calibration.shift();
            }
          } else if (!baseline) calibration = [];
          const score = orientationScore(data.orientation, baseline);
          const rawState = data.faceCount === 0 ? 'FACE_MISSING' : data.faceCount >= 2 ? 'MULTIPLE_FACES' : score === null ? 'CALIBRATING' : score > 1 ? 'LOOKING_AWAY' : 'FACE_PRESENT';
          setStatus(data.faceCount === 0 ? 'Active · No face currently detected' : data.faceCount >= 2 ? 'Active · Multiple faces visible' : !baseline ? 'Active · Face camera normally to calibrate orientation' : 'Active · Face tracking available');
          setDebug({ faceCount: data.faceCount, orientation_score: score === null ? null : Number(score.toFixed(2)), rawState });
          callbacks.current.onObservation({ faceCount: data.faceCount, orientationScore: score });
        };
        worker.postMessage({ type: 'init', bundleUrl: new URL('mediapipe/vision_bundle.js', base).href, wasmUrl: new URL('mediapipe/wasm', base).href, modelUrl: new URL('mediapipe/face_landmarker.task', base).href });
        const loadingStarted = performance.now();
        timer = setInterval(() => {
          if (!ready && performance.now() - loadingStarted > 30000) fail('MEDIAPIPE_INITIALIZATION_FAILED');
          else if (ready && !document.hidden && performance.now() - lastReceived > 5000) fail('TRACKING_FAILED');
        }, 1000);
        animation = requestAnimationFrame(frame);
      } catch { fail('MEDIAPIPE_INITIALIZATION_FAILED'); }
    }
    start();
    return () => { cancelled = true; document.removeEventListener('visibilitychange', visibility); release(); };
  }, [enabled, attempt, videoRef]);
  return { status, debug, retry: () => setAttempt((value) => value + 1) };
}
