const PROTOTYPE_MODE_KEY = "agenthive.runtime.prototype_mode";

export function isPrototypeModeAvailable() {
  return import.meta.env.DEV;
}

export function getStoredPrototypeMode() {
  return isPrototypeModeAvailable() && window.sessionStorage.getItem(PROTOTYPE_MODE_KEY) === "enabled";
}

export function activatePrototypeMode() {
  if (!isPrototypeModeAvailable()) {
    return false;
  }
  window.sessionStorage.setItem(PROTOTYPE_MODE_KEY, "enabled");
  return true;
}

export function clearPrototypeMode() {
  window.sessionStorage.removeItem(PROTOTYPE_MODE_KEY);
}
