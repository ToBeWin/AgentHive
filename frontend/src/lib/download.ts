export function downloadTextFile(content: string, filename: string, type: string) {
  const blob = new Blob([content], { type });
  downloadBlobFile(blob, filename);
}

export function downloadBlobFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
