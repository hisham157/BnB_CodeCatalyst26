import { useCallback, useEffect, useRef, useState } from 'react';

export default function useSpeechSynthesis() {
  const supported = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
  const [speaking, setSpeaking] = useState(false);
  const [error, setError] = useState('');
  const utterance = useRef(null);

  const stop = useCallback(() => {
    if (utterance.current) {
      utterance.current.onstart = null;
      utterance.current.onend = null;
      utterance.current.onerror = null;
    }
    utterance.current = null;
    if (supported) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, [supported]);

  const speak = useCallback((text) => {
    if (!supported || !text?.trim()) return;
    stop();
    setError('');
    try {
      const speech = new SpeechSynthesisUtterance(text);
      const voice = window.speechSynthesis.getVoices().find((item) => /^en(?:-|_)/i.test(item.lang));
      if (voice) speech.voice = voice;
      speech.lang = voice?.lang || 'en-US';
      speech.rate = 1;
      speech.onstart = () => setSpeaking(true);
      speech.onend = () => { setSpeaking(false); utterance.current = null; };
      speech.onerror = (event) => {
        setSpeaking(false);
        utterance.current = null;
        if (!['canceled', 'interrupted'].includes(event.error)) setError('Speech playback was unavailable. Click Speak Question to retry, or read the question.');
      };
      utterance.current = speech;
      window.speechSynthesis.speak(speech);
    } catch {
      setSpeaking(false);
      setError('Speech playback is unavailable. You can read the question and continue.');
    }
  }, [stop, supported]);

  useEffect(() => () => { stop(); }, [stop]);
  return { supported, speaking, error, speak, stop };
}
