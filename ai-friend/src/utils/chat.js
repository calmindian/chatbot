export function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function isImageRequest(msg) {
  return /\b(?:image|picture|photo|pic|selfie|show me|send me|draw|take a photo|take a picture)\b/i
    .test(msg);
}

export function isGifRequest(msg) {
  return ['gif','animate','dancing','walking','moving','motion','video','action']
    .some(k => msg.toLowerCase().includes(k));
}
