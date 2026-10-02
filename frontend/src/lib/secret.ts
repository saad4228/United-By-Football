/**
 * Hidden page, opened by typing a phrase into the search box.
 *
 * The phrase is matched on letters and digits only, so spacing and capitals don't matter
 * ("Secret Vault 000" works as well as the run-together version). Matching happens
 * in the browser before the search request is built, so the phrase never reaches the API,
 * never lands in the server log, and never counts against the search rate limit.
 *
 * This is an easter egg, not a security control: the phrase ships in the JS bundle and anyone
 * reading it can find the page. Nothing sensitive belongs here.
 */
const PHRASE = "secretvault000";
const STORAGE_KEY = "ubf-secret";

export const SECRET_PATH = "/tabahi";

// Keep digits: the phrase ends in numbers, and stripping them would make it unmatchable.
const squash = (value: string) => value.toLowerCase().replace(/[^a-z0-9]/g, "");

export const isSecretPhrase = (query: string) => squash(query) === PHRASE;

/** Remembered so the page can be reopened directly once it has been found. */
export function unlockSecret(): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, "1");
  } catch {
    /* storage blocked: the page still opens for this visit */
  }
}

export function isSecretUnlocked(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}
