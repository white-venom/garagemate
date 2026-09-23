"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { convertToWav } from "@/lib/wav";

type RecorderState = "idle" | "recording" | "processing";

export function useVoiceRecorder(onRecorded: (file: File) => void, maxSeconds = 60) {
  const [state, setState] = useState<RecorderState>("idle");
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const cancelledRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  const onRecordedRef = useRef(onRecorded);

  useEffect(() => {
    onRecordedRef.current = onRecorded;
  }, [onRecorded]);

  const stopTimer = () => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state === "recording") recorder.stop();
  }, []);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    stop();
  }, [stop]);

  const start = useCallback(async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Voice recording isn't supported in this browser. You can upload an audio file instead.");
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("Microphone access was blocked. Allow it in your browser settings to record the sound.");
      return;
    }

    const recorder = new MediaRecorder(stream);
    chunksRef.current = [];
    cancelledRef.current = false;

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };

    recorder.onstop = async () => {
      stopTimer();
      stream.getTracks().forEach((track) => track.stop());
      if (cancelledRef.current || chunksRef.current.length === 0) {
        setState("idle");
        return;
      }

      setState("processing");
      const recording = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
      const stamp = Date.now();
      let file: File;
      try {
        const wav = await convertToWav(recording);
        file = new File([wav], `voice-note-${stamp}.wav`, { type: "audio/wav" });
      } catch {
        // couldn't decode it here, send the original recording and let the backend deal with it
        const type = recording.type.split(";")[0] || "audio/webm";
        const extension = type.includes("mp4") ? "m4a" : "webm";
        file = new File([recording], `voice-note-${stamp}.${extension}`, { type });
      }
      setState("idle");
      onRecordedRef.current(file);
    };

    recorderRef.current = recorder;
    recorder.start();
    setSeconds(0);
    setState("recording");

    const startedAt = Date.now();
    timerRef.current = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      setSeconds(elapsed);
      if (elapsed >= maxSeconds && recorder.state === "recording") recorder.stop();
    }, 250);
  }, [maxSeconds]);

  // stop the mic if the component goes away mid recording
  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      stopTimer();
      const recorder = recorderRef.current;
      if (recorder && recorder.state === "recording") recorder.stop();
    };
  }, []);

  return { state, seconds, maxSeconds, error, start, stop, cancel, clearError: () => setError(null) };
}
