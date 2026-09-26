/* Classic worker: MediaPipe's WASM loader uses importScripts. Frames stay in the browser. */
let landmarker;
self.onmessage = async ({ data }) => {
  if (data.type === 'init') {
    try {
      importScripts(data.bundleUrl);
      const files = await Vision.FilesetResolver.forVisionTasks(data.wasmUrl);
      landmarker = await Vision.FaceLandmarker.createFromOptions(files, {
        baseOptions: { modelAssetPath: data.modelUrl, delegate: 'CPU' },
        runningMode: 'VIDEO', numFaces: 2,
        minFaceDetectionConfidence: 0.6, minFacePresenceConfidence: 0.6,
        minTrackingConfidence: 0.6,
        outputFaceBlendshapes: false, outputFacialTransformationMatrixes: false,
        canvas: new OffscreenCanvas(320, 240),
      });
      self.postMessage({ type: 'ready' });
    } catch { self.postMessage({ type: 'error', reason: 'MEDIAPIPE_INITIALIZATION_FAILED' }); }
  } else if (data.type === 'frame') {
    try {
      const result = landmarker.detectForVideo(data.bitmap, data.timestamp);
      const face = result.faceLandmarks[0];
      let orientation = null;
      if (result.faceLandmarks.length === 1 && face) {
        const left = face[33], right = face[263], nose = face[1];
        const width = Math.hypot(right.x - left.x, right.y - left.y);
        const height = Math.hypot(face[152].x - face[10].x, face[152].y - face[10].y);
        if (width > 0.02 && height > 0.04) orientation = {
          horizontal: (nose.x - (left.x + right.x) / 2) / width,
          vertical: (nose.y - (left.y + right.y) / 2) / height,
        };
      }
      self.postMessage({ type: 'observation', faceCount: result.faceLandmarks.length, orientation });
    } catch { self.postMessage({ type: 'error', reason: 'TRACKING_FAILED' }); }
    finally { data.bitmap?.close(); }
  } else if (data.type === 'close') { landmarker?.close(); self.close(); }
};
