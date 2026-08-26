import { readdirSync, readFileSync } from "node:fs";

/** Read the real split CSS source tree used by main.tsx for static workflow checks. */
export function readStylesSource() {
  const stylesDirectory = new URL("../src/styles/", import.meta.url);
  return readdirSync(stylesDirectory)
    .filter((name) => name.endsWith(".css"))
    .sort()
    .map((name) => readFileSync(new URL(name, stylesDirectory), "utf8"))
    .join("\n");
}
