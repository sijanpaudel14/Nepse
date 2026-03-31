/**
 * background.js — Service Worker (Manifest V3)  ·  NepseAlpha edition
 * ====================================================================
 *
 * NepseAlpha has Cloudflare + session auth, so we do NOT re-fetch chart data
 * from the service worker.  Instead:
 *
 *   inject.js (MAIN world)         — hooks window.fetch/XHR, intercepts
 *       ↓  window.postMessage        NepseAlpha chart responses
 *   content_script.js (isolated)   — receives NEPSE_CHART_DATA, dedupes,
 *       ↓  chrome.runtime.sendMessage  shows loading widget
 *   background.js (SW)             — forwards payload to localhost:8000
 *       ↓  sendResponse              FastAPI backend
 *   content_script.js              — renders result in Shadow DOM widget
 *
 * For resolution changes / refresh, content_script posts NEPSE_FETCH_REQUEST
 * to inject.js which makes a fresh same-origin fetch (browser sends
 * session cookies automatically).  No SW involvement needed.
 */

// ── Backend URL ───────────────────────────────────────────────────────
// Currently pointing at Render (production).
// For local development change back to: 'http://127.0.0.1:8000'
const BACKEND_URL = 'https://nepse-chart-extension.onrender.com'
// const BACKEND_URL = 'http://127.0.0.1:8000'

// ── Installation ──────────────────────────────────────────────────────
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('[NEPSE Analyzer] Extension installed successfully')
  } else if (details.reason === 'update') {
    console.log(
      `[NEPSE Analyzer] Updated to v${chrome.runtime.getManifest().version}`,
    )
  }
})

// ── Message handlers ──────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // ── ANALYZE: forward normalised candle data to local FastAPI backend ──
  // inject.js normalises the TradingView UDF response; content_script sends
  // the full payload here so we can call localhost:8000 from the SW context
  // (avoids mixed-content blocking when the page is served over HTTPS).
  if (message.type === 'ANALYZE') {
    const backendAbort = new AbortController()
    const timer = setTimeout(() => backendAbort.abort(), 25000)
    fetch(`${BACKEND_URL}/analyze`, {
      method: 'POST',
      signal: backendAbort.signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(message.payload),
    })
      .then(async (res) => {
        clearTimeout(timer)
        if (!res.ok) {
          const text = await res.text()
          sendResponse({ error: `Backend error ${res.status}: ${text}` })
          return
        }
        sendResponse({ result: await res.json() })
      })
      .catch((err) => {
        clearTimeout(timer)
        sendResponse({
          error:
            err.name === 'AbortError'
              ? `Backend timed out (${BACKEND_URL}) — is it running?`
              : err.message,
        })
      })
    return true // keep message port open for async sendResponse
  }

  // ── ANALYSIS_RESULT: update the toolbar badge ─────────────────────
  // content_script sends this after successfully rendering a result.
  if (message.type === 'ANALYSIS_RESULT') {
    const tabId = sender.tab?.id
    if (!tabId || !chrome.action) return
    const COLORS = {
      'STRONG BUY': '#16A34A',
      BUY: '#22C55E',
      HOLD: '#6B7280',
      SELL: '#F59E0B',
      'STRONG SELL': '#EF4444',
    }
    chrome.action.setBadgeBackgroundColor({
      color: COLORS[message.verdict] || '#6B7280',
      tabId,
    })
    chrome.action.setBadgeText({
      text:
        message.verdict === 'STRONG BUY'
          ? 'BUY!'
          : (message.verdict || '').slice(0, 4),
      tabId,
    })
  }
})
