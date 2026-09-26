import { useCallback, useEffect, useRef, useState } from 'react';
import { transcribeAnswer } from '../services/api';

const MAX_BYTES = 15 * 1024 * 1024;
const MAX_SECONDS = 180;
const MIME_TYPES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/ogg', 'audio/mp4'];

export default function useAudioRecorder(interviewId, onTranscript) {
  const [state, setState] = useState('idle');
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState('');
  const active = useRef(false);
  const stream = useRef(null);
  const recorder = useRef(null);
  const timer = useRef(null);
  const controller = useRef(null);
  const mounted = useRef(true);
  const generation = useRef(0);
  const callback = useRef(onTranscript);
  callback.current = onTranscript;
  const supported = !!(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);

  const release = useCallback(() => {
    clearInterval(timer.current);
    timer.current = null;
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  }, []);

  const cancel = useCallback(() => {
    generation.current += 1;
    controller.current?.abort();
    if (recorder.current) {
      recorder.current.ondataavailable = null;
      recorder.current.onstop = null;
      recorder.current.onerror = null;
      if (recorder.current.state !== 'inactive') recorder.current.stop();
      recorder.current = null;
    }
    release();
    active.current = false;
    if (mounted.current) setState('idle');
  }, [release]);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; cancel(); };
  }, [cancel]);

  const stop = useCallback(() => {
    if (recorder.current?.state === 'recording') {
      setState('processing');
      recorder.current.stop();
      release();
    }
  }, [release]);

  async function start() {
    if (active.current) return;
    if (!supported) { setError('Voice recording is unavailable in this browser. You can continue using text.'); return; }
    active.current = true;
    const version = ++generation.current;
    setError('');
    setSeconds(0);
    setState('requesting_permission');
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mounted.current || version !== generation.current) {
        mediaStream.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = mediaStream;
      const mimeType = MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type));
      const recording = new MediaRecorder(mediaStream, mimeType ? { mimeType } : undefined);
      recorder.current = recording;
      const chunks = [];
      let size = 0;
      recording.ondataavailable = (event) => {
        if (event.data.size) { chunks.push(event.data); size += event.data.size; }
        if (size > MAX_BYTES) {
          cancel();
          setState('error');
          setError('Recording exceeded 15 MB. Please record a shorter answer or type it.');
        }
      };
      recording.onerror = () => {
        cancel(); setState('error');
        setError('Microphone recording failed. Try again or type your answer.');
      };
      recording.onstop = async () => {
        release();
        if (!mounted.current || version !== generation.current) return;
        setState('processing');
        try {
          const blob = new Blob(chunks, { type: recording.mimeType || chunks[0]?.type || 'audio/webm' });
          if (!blob.size) throw new Error('The recording is empty. Please record again or type your answer.');
          controller.current = new AbortController();
          const result = await transcribeAnswer(interviewId, blob, controller.current.signal);
          if (!mounted.current || version !== generation.current) return;
          callback.current(result.text);
          setState('ready');
        } catch (failure) {
          if (mounted.current && version === generation.current) {
            setState('error');
            setError(failure.message || "We couldn't transcribe that recording. Try recording again or type your answer.");
          }
        } finally {
          chunks.length = 0;
          if (version === generation.current) { active.current = false; recorder.current = null; controller.current = null; }
        }
      };
      recording.start(1000);
      setState('recording');
      const started = Date.now();
      timer.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - started) / 1000);
        setSeconds(Math.min(elapsed, MAX_SECONDS));
        if (elapsed >= MAX_SECONDS) stop();
      }, 250);
    } catch (failure) {
      if (!mounted.current || version !== generation.current) return;
      cancel();
      setState('error');
      setError(failure.name === 'NotAllowedError' || failure.name === 'SecurityError'
        ? 'Microphone access was denied. You can still type your answer below.'
        : 'Could not access a microphone. Check your device or type your answer below.');
    }
  }

  return { state, seconds, error, supported, start, stop, cancel,
    busy: ['requesting_permission', 'recording', 'processing'].includes(state) };
}
