// SubDivX browser-session capture for service.subtitles.universalsubs.
//
// SubDivX is behind a Cloudflare managed challenge, so the add-on cannot reach it on its own.
// The browser can: it solves the challenge and keeps the clearance cookie, which Cloudflare binds
// to the user agent it was issued to.
//
// 1. Make sure Kodi is running.
// 2. Open http://127.0.0.1:39517/ in a browser; that page explains these steps and has a Copy
//    button for this script.
// 3. Open https://www.subdivx.com/ and wait for the page to finish loading (the Cloudflare check
//    must have passed).
// 4. Run this script in the **subdivx.com tab** (F12 -> Console -> paste -> Enter). Cookies are
//    scoped to their origin, so it does nothing on the local instruction page.
//
// Only the challenge/session cookies are copied, and the session is sent to 127.0.0.1:39517
// automatically. If Kodi cannot be reached the blob is copied to the clipboard and printed, and
// can be pasted into Settings -> Advanced -> SubDivX browser session. The session expires: repeat
// these steps when SubDivX stops returning results. Anyone holding the blob can act as this
// browser session, so do not share it.
(() => {
  if (!/(^|\.)subdivx\.com$/i.test(location.hostname)) {
    alert("Run this script in the subdivx.com tab, not on " + location.hostname + ".");
    return;
  }
  const wanted = ["cf_clearance", "PHPSESSID", "__cf_bm"];
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .filter((part) => wanted.includes(part.split("=")[0]))
    .join("; ");
  if (!/(^|;\s*)cf_clearance=/.test(cookie)) {
    alert("No cf_clearance cookie found. Reload subdivx.com until the Cloudflare check passes, " +
          "or copy cf_clearance from the developer tools (Application -> Cookies) and paste it in " +
          "Settings > Advanced > SubDivX browser session.");
    return;
  }
  const blob = btoa(unescape(encodeURIComponent(JSON.stringify({ cookie: cookie, ua: navigator.userAgent }))));
  const fallback = () => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(blob);
    }
    console.log(blob);
    alert("Kodi was not reachable. The session was copied/printed; paste it in Settings > Advanced > " +
          "SubDivX browser session.");
  };
  fetch("http://127.0.0.1:39517/subdivx-session", {
    method: "POST",
    headers: { "Content-Type": "text/plain" },
    body: blob,
  })
    .then((response) => response.json())
    .then((result) => {
      if (result && result.ok) {
        console.log("SubDivX session sent to Kodi.");
        alert("SubDivX session sent to Kodi.");
      } else {
        fallback();
      }
    })
    .catch(fallback);
  return blob;
})();
