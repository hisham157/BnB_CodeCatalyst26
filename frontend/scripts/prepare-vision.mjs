import { cp, mkdir, access, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const destination = path.join(root, 'public', 'mediapipe');
await mkdir(destination, { recursive: true });
await cp(path.join(root, 'node_modules/@mediapipe/tasks-vision/wasm'), path.join(destination, 'wasm'), { recursive: true });
await cp(path.join(root, 'node_modules/@mediapipe/tasks-vision/vision_bundle.js'), path.join(destination, 'vision_bundle.js'));
const model = path.join(destination, 'face_landmarker.task');
try { await access(model); } catch {
  const response = await fetch('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task');
  if (!response.ok) throw new Error(`Face model download failed (${response.status}). Run npm.cmd run prepare:vision again.`);
  await writeFile(model, Buffer.from(await response.arrayBuffer()));
}
console.log('MediaPipe runtime and official face model ready locally.');
