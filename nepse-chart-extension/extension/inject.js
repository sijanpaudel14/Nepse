/**
 * inject.js — MAIN WORLD Fetch/XHR Interceptor
 * ===============================================
 * Declared as "world": "MAIN" in manifest.json, so this runs DIRECTLY
 * in the same JavaScript context as NepseAlpha's own page code.
 *
 * NO chrome.* APIs available here — only window / DOM APIs.
 *
 * HOW IT WORKS:
 *   1. Patches window.fetch and XMLHttpRequest.prototype.open/send
 *   2. For any NepseAlpha /trading/1/history request:
 *      a. Clone the response (so the chart still renders normally)
 *      b. Parse the JSON (TradingView UDF format: {s,t,o,h,l,c,v})
 *      c. Normalize to [{time,open,high,low,close,volume}]
 *      d. Send to content_script.js via window.postMessage
 *   3. Listens for NEPSE_FETCH_REQUEST from content_script (resolution changes)
 *      and makes a same-origin fetch (session cookies auto-included).
 *
 * API: https://nepsealpha.com/trading/1/history
 *   ?fsk=<key>&symbol=<SYM>&resolution=<RES>&frame=1000
 *   Confirmed working resolutions: 1S (1-second), 1 (1-minute), 1D (daily)
 */

;(function () {
  'use strict'

  const MSG_TYPE = 'NEPSE_CHART_DATA'
  console.log('[NEPSE Analyzer] inject.js loaded (MAIN world)')

  // ── URL Detection ─────────────────────────────────────────────────

  function isNepseAlphaDomain(url) {
    return url.includes('nepsealpha.com')
  }

  /**
   * Match NepseAlpha chart history requests:
   *   https://nepsealpha.com/trading/1/history?fsk=...&symbol=...&resolution=...
   */
  function looksLikeChartUrl(url) {
    if (typeof url !== 'string' || !url.startsWith('http')) return false
    return (
      isNepseAlphaDomain(url) &&
      url.includes('/trading/') &&
      url.includes('/history')
    )
  }

  /**
   * Secondary validation: does the parsed JSON look like OHLCV data?
   */
  function looksLikeOHLCV(json) {
    if (!json) return false
    // TradingView UDF success format: {s: "ok", t: [...], c: [...], ...}
    if (json.s === 'ok' && Array.isArray(json.t) && json.t.length >= 5)
      return true
    // TradingView UDF without 's' field: {t: [...], c: [...], ...}
    if (Array.isArray(json.t) && Array.isArray(json.c) && json.t.length >= 5)
      return true
    // Array of candle objects: [{time, open, high, low, close}, ...]
    if (Array.isArray(json) && json.length >= 5) {
      const first = json[0]
      if (!first) return false
      return (
        typeof first.close === 'number' ||
        typeof first.c === 'number' ||
        (typeof first.time === 'number' && typeof first.open === 'number')
      )
    }
    return false
  }

  // ── Metadata Extraction ───────────────────────────────────────────

  function isLiveDataUrl(url) {
    return (
      typeof url === 'string' &&
      url.includes('live.nepsealpha.com') &&
      url.includes('lv_data')
    )
  }

  function isTargetUrl(url) {
    return looksLikeChartUrl(url)
  }

  // Persist the fsk key seen in intercepted URLs for use in manual re-fetches
  let _lastFsk = Date.now().toString()

  // ── Today's live bar cache ─────────────────────────────────────────
  // Populated when the chart fetches live.nepsealpha.com/lv_data.
  // Keyed by SYMBOL, each value is a normalised candle object.
  const _liveBarCache = {}

  // Maps display resolution → actual NepseAlpha API resolution param.
  // Confirmed working: '1S' (1-sec), '1' (1-min), '1D' (daily).
  // Others are tried as-is — NepseAlpha may accept standard TradingView codes.
  // Resolutions confirmed: '1S', '1', '1D', '1W'. Others tried as-is (NepseAlpha uses standard TV codes).
  const FRAME_MAP = {
    '1S': '1S', // ✅ confirmed
    '10S': '1S',
    '15S': '1S',
    '20S': '1S',
    '30S': '1S',
    '45S': '1S',
    1: '1', // ✅ confirmed
    2: '1', // derived from 1-min base, resampled client-side
    3: '1',
    5: '1',
    10: '1',
    15: '1',
    30: '1',
    45: '1',
    60: '1', // 1H — resampled from 1-min
    120: '1', // 2H
    180: '1', // 3H
    240: '1', // 4H
    '1D': '1D', // ✅ confirmed
    '2D': '1D',
    '3D': '1D',
    '4D': '1D',
    // Weekly/monthly: fetch daily bars, resample client-side.
    '1W': '1D',
    '2W': '1D',
    '1M': '1D',
    '2M': '1D',
    '3M': '1D',
    '6M': '1D',
  }
  function getApiRes(resolution) {
    return FRAME_MAP[resolution] || resolution
  }

  // ── History URL builder ───────────────────────────────────────────
  // NepseAlpha only serves 3 actual API resolutions: 1S, 1 (minute), 1D.
  // All other timeframes are resampled client-side (same as TradingView does).
  // Always use frame=1000 — the only confirmed-working frame value.
  function buildHistoryUrl(apiRes, symbol, fsk) {
    const useFsk = Date.now().toString()
    return (
      `https://nepsealpha.com/trading/1/history` +
      `?fsk=${encodeURIComponent(useFsk)}` +
      `&symbol=${encodeURIComponent(symbol)}` +
      `&resolution=${apiRes}` +
      `&frame=1000`
    )
  }

  function extractMetadata(url) {
    try {
      const p = new URL(url).searchParams
      const fsk = p.get('fsk')
      if (fsk) _lastFsk = fsk
      return {
        symbol: (p.get('symbol') || 'UNKNOWN')
          .toUpperCase()
          .replace(/[^A-Z0-9]/g, ''),
        resolution: p.get('resolution') || '1D',
        countback: p.get('frame') || p.get('countback') || '1000',
        isAdjust: 'false',
        time: '',
      }
    } catch {
      return {
        symbol: 'UNKNOWN',
        resolution: '1D',
        countback: '1000',
        isAdjust: 'false',
        time: '',
      }
    }
  }

  // ── OHLCV Format Normalization ────────────────────────────────────

  /**
   * Convert any known format to [{time, open, high, low, close, volume}].
   *
   * Handles:
   *   A) TradingView UDF: {s:"ok", t:[...], o:[...], h:[...], l:[...], c:[...], v:[...]}
   *   B) Column arrays without 's': {t:[...], c:[...], ...}
   *   C) Object arrays: [{time, open, high, low, close, volume}, ...]
   *   D) Short-key object arrays: [{t, o, h, l, c, v}, ...]
   */
  function normalizeCandles(raw) {
    // Formats A & B — column arrays
    if (raw && Array.isArray(raw.t) && raw.t.length >= 5) {
      const len = raw.t.length
      const candles = []
      for (let i = 0; i < len; i++) {
        const c = Number(raw.c[i])
        const o = raw.o ? Number(raw.o[i]) : c
        candles.push({
          time: Number(raw.t[i]),
          open: o,
          high: raw.h ? Number(raw.h[i]) : Math.max(o, c),
          low: raw.l ? Number(raw.l[i]) : Math.min(o, c),
          close: c,
          volume: raw.v ? Number(raw.v[i]) : 0,
        })
      }
      return candles.length >= 5 ? candles : null
    }

    // Formats C & D — arrays of objects (long keys)
    if (Array.isArray(raw) && raw.length >= 5) {
      const first = raw[0]
      if (!first) return null

      if (typeof first.close === 'number') {
        return raw.map((b) => ({
          time: b.time || b.t || 0,
          open: b.open || b.o || b.close,
          high: b.high || b.h || b.close,
          low: b.low || b.l || b.close,
          close: b.close,
          volume: b.volume || b.v || 0,
        }))
      }

      if (typeof first.c === 'number') {
        return raw.map((b) => ({
          time: b.time || b.t || 0,
          open: b.o || b.open || b.c,
          high: b.h || b.high || b.c,
          low: b.l || b.low || b.c,
          close: b.c,
          volume: b.v || b.volume || 0,
        }))
      }
    }

    return null
  }

  // ── Client-side resampling (weekly / monthly) ─────────────────────
  // Used when the display resolution maps to a coarser timeframe than
  // the fetched API resolution (e.g. '1W' and '1M' both fetch daily bars).

  /**
   * Return Unix-second timestamp for the Monday of the week containing ts.
   * ts must be in Unix seconds.
   */
  function _weekStartTs(ts) {
    const ms = ts > 1e10 ? ts : ts * 1000 // handle both s and ms
    const d = new Date(ms)
    const dayOfWeek = d.getUTCDay() || 7 // Mon=1 … Sun=7
    return (
      Date.UTC(
        d.getUTCFullYear(),
        d.getUTCMonth(),
        d.getUTCDate() - (dayOfWeek - 1),
      ) / 1000
    )
  }

  /**
   * Return Unix-second timestamp for the first day of the month containing ts.
   */
  function _monthStartTs(ts) {
    const ms = ts > 1e10 ? ts : ts * 1000
    const d = new Date(ms)
    return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1) / 1000
  }

  /**
   * Aggregate candles using a bucket key function.
   * Each bucket's time = the key (start of week/month).
   * open = first bar, high = max, low = min, close = last bar, volume = sum.
   */
  function _aggregateBars(candles, keyFn) {
    const buckets = new Map()
    for (const c of candles) {
      const key = keyFn(c.time)
      if (!buckets.has(key)) {
        buckets.set(key, {
          time: key,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
        })
      } else {
        const b = buckets.get(key)
        b.high = Math.max(b.high, c.high)
        b.low = Math.min(b.low, c.low)
        b.close = c.close // last day of period is the close
        b.volume += c.volume
      }
    }
    return Array.from(buckets.values())
  }

  /**
   * Resample candles to the display resolution, if needed.
   * apiRes = what was fetched ('1', '1S', '1D').
   * displayRes = what the user sees ('60', '15', '1W', '1M', etc.).
   */
  function resampleCandles(candles, displayRes, apiRes) {
    if (!candles || candles.length < 5) return candles

    // ── Intraday: 1-minute base → N-minute bars ──────────────────────
    if (apiRes === '1') {
      const minsMap = {
        2: 2,
        3: 3,
        5: 5,
        10: 10,
        15: 15,
        30: 30,
        45: 45,
        60: 60,
        120: 120,
        180: 180,
        240: 240,
      }
      const N = minsMap[String(displayRes)]
      if (N) {
        return _aggregateBars(
          candles,
          (ts) => Math.floor(ts / (N * 60)) * (N * 60),
        )
      }
      return candles // displayRes === '1' — already 1-min, no resampling
    }

    // ── Seconds: 1S base → multi-second bars ─────────────────────────
    if (apiRes === '1S') {
      const secsMap = { '10S': 10, '15S': 15, '20S': 20, '30S': 30, '45S': 45 }
      const S = secsMap[displayRes]
      if (S) return _aggregateBars(candles, (ts) => Math.floor(ts / S) * S)
      return candles
    }

    // ── Daily base: multi-day / weekly / monthly aggregation ─────────
    // 2D/3D/4D — aggregate every N calendar days
    const multiDayMap = { '2D': 2, '3D': 3, '4D': 4 }
    const ND = multiDayMap[displayRes]
    if (ND) {
      return _aggregateBars(
        candles,
        (ts) => Math.floor(ts / (ND * 86400)) * (ND * 86400),
      )
    }
    if (displayRes === '1W' || displayRes === '2W') {
      return _aggregateBars(candles, _weekStartTs)
    }
    if (
      displayRes === '1M' ||
      displayRes === '2M' ||
      displayRes === '3M' ||
      displayRes === '6M'
    ) {
      return _aggregateBars(candles, _monthStartTs)
    }

    return candles
  }

  // ── Message Dispatch ──────────────────────────────────────────────

  // metaOverride lets callers correct the resolution/symbol when the URL
  // contains the API resolution (e.g. '1D') but the user's display choice
  // differs (e.g. '1W' which we map to '1D' for the API call).
  // Post an error message to content_script so the loading widget never spins forever.
  function postFetchError(symbol, resolution, message) {
    window.postMessage(
      { type: 'NEPSE_FETCH_ERROR', symbol, resolution, message },
      '*',
    )
    console.log(`[NEPSE Analyzer] ❌ ${symbol} (${resolution}): ${message}`)
  }

  async function dispatch(url, json, metaOverride) {
    // API wraps OHLCV in {success, code, message, data: {...ohlcv...}}
    const payload = looksLikeOHLCV(json)
      ? json
      : json && looksLikeOHLCV(json.data)
        ? json.data
        : null
    if (!payload) {
      if (metaOverride && metaOverride.symbol) {
        postFetchError(
          metaOverride.symbol,
          metaOverride.resolution,
          'No chart data returned for this resolution — NepseAlpha may not support it',
        )
      }
      return
    }
    const rawCandles = normalizeCandles(payload)
    if (!rawCandles || rawCandles.length < 5) return

    const urlMeta = extractMetadata(url)
    // apiRes = what was actually fetched (1, 1S, or 1D from URL)
    const apiResFromUrl = urlMeta.resolution
    // displayRes = what the user is viewing (from override or page URL)
    const displayRes =
      (metaOverride && metaOverride.resolution) || _readInterval()
    const metadata = { ...urlMeta, ...metaOverride, resolution: displayRes }

    const candles = resampleCandles(rawCandles, displayRes, apiResFromUrl)
    console.log(
      `[NEPSE Analyzer] 📊 dispatch: apiRes=${apiResFromUrl} displayRes=${displayRes} raw=${rawCandles.length} resampled=${candles ? candles.length : 0}`,
    )
    if (!candles || candles.length < 5) {
      console.log(
        `[NEPSE Analyzer] ⛔ dispatch skipped: too few candles (${candles ? candles.length : 0}) for ${displayRes}`,
      )
      return
    }

    // ── Merge today's live bar for 1D charts ──────────────────────────────
    // NepseAlpha history has a delay after market close before today's completed
    // bar appears. We check: if the last history bar is not from today, proactively
    // fetch live.nepsealpha.com/lv_data (browser context = real session cookies,
    // Cloudflare not triggered). This covers both during-market and post-close.
    let finalCandles = candles
    const dispRes = (displayRes || '').toUpperCase()
    if (dispRes === '1D' || dispRes === 'D') {
      const sym = metadata.symbol
      const lastTs = finalCandles[finalCandles.length - 1].time

      // today's 05:45 UTC = NepseAlpha's daily bar timestamp convention
      const now = new Date()
      const todayBarTs =
        Date.UTC(
          now.getUTCFullYear(),
          now.getUTCMonth(),
          now.getUTCDate(),
          5,
          45,
          0,
        ) / 1000

      // Check cache first; if not cached OR history bar is stale, re-fetch lv_data
      let liveBar = _liveBarCache[sym]
      if (!liveBar || lastTs < todayBarTs) {
        try {
          const fs = Math.floor(Date.now() / 1000).toString() + '0000'
          const lvUrl = `https://live.nepsealpha.com/lv_data?symbol=${encodeURIComponent(sym)}&resolution=1D&fs=${fs}&tck=pass`
          const lvResp = await originalFetch(lvUrl, {
            headers: {
              accept: 'application/json',
              origin: 'https://nepsealpha.com',
              referer: 'https://nepsealpha.com/',
            },
            credentials: 'include',
          })
          const lvJson = await lvResp.json()
          const ts = lvJson && lvJson.t
          const c = lvJson && lvJson.c
          if (Array.isArray(ts) && ts.length && Array.isArray(c) && c.length) {
            liveBar = {
              time: parseInt(ts[0], 10),
              open: lvJson.o ? parseFloat(lvJson.o[0]) : parseFloat(c[0]),
              high: lvJson.h ? parseFloat(lvJson.h[0]) : parseFloat(c[0]),
              low: lvJson.l ? parseFloat(lvJson.l[0]) : parseFloat(c[0]),
              close: parseFloat(c[0]),
              volume: lvJson.v
                ? parseFloat(String(lvJson.v[0]).replace(/,/g, ''))
                : 0,
            }
            _liveBarCache[sym] = liveBar
            console.log(
              `[NEPSE Analyzer] 📡 lv_data fetched: ${sym} close=${liveBar.close}`,
            )
          }
        } catch (e) {
          console.log(
            `[NEPSE Analyzer] ⚠️ lv_data fetch failed: ${e && e.message}`,
          )
        }
      }

      if (liveBar && liveBar.time > lastTs) {
        finalCandles = finalCandles.concat([liveBar])
        console.log(
          `[NEPSE Analyzer] 📌 today's bar merged: ${sym} close=${liveBar.close}`,
        )
      }
    }

    window._nepseGotData = true
    window.postMessage(
      { type: MSG_TYPE, payload: { metadata, data: finalCandles } },
      '*',
    )
    console.log(
      `[NEPSE Analyzer] ✅ ${finalCandles.length} candles · ${metadata.symbol} · ${displayRes}${
        finalCandles.length !== rawCandles.length
          ? ` (resampled from ${rawCandles.length} ${apiResFromUrl}-bars)`
          : ''
      }`,
    )
  }

  // ── Patch window.fetch ───────────────────────────────────────────
  const originalFetch = window.fetch
  window.fetch = async function (...args) {
    const request = args[0]
    const url =
      typeof request === 'string'
        ? request
        : request instanceof Request
          ? request.url
          : request instanceof URL
            ? request.href
            : String(request || '')

    // DIAGNOSTIC: log NepseAlpha chart history hits
    if (url.includes('nepsealpha.com') && url.includes('/history')) {
      console.log('[NEPSE Analyzer] 🌐 fetch hit:', url.substring(0, 160))
    }

    // Intercept live.nepsealpha.com/lv_data — cache today's bar
    if (isLiveDataUrl(url)) {
      try {
        const liveResp = await originalFetch.apply(this, args)
        const liveClone = liveResp.clone()
        const liveJson = await liveClone.json()
        const ts = liveJson && liveJson.t
        const c = liveJson && liveJson.c
        if (Array.isArray(ts) && ts.length && Array.isArray(c) && c.length) {
          const symParam = new URL(url).searchParams.get('symbol')
          const sym = symParam ? symParam.toUpperCase() : null
          if (sym) {
            _liveBarCache[sym] = {
              time: parseInt(ts[0], 10),
              open: liveJson.o ? parseFloat(liveJson.o[0]) : parseFloat(c[0]),
              high: liveJson.h ? parseFloat(liveJson.h[0]) : parseFloat(c[0]),
              low: liveJson.l ? parseFloat(liveJson.l[0]) : parseFloat(c[0]),
              close: parseFloat(c[0]),
              volume: liveJson.v
                ? parseFloat(String(liveJson.v[0]).replace(/,/g, ''))
                : 0,
            }
            console.log(
              `[NEPSE Analyzer] 📡 lv_data cached: ${sym} close=${c[0]}`,
            )
          }
        }
        return liveResp
      } catch (e) {
        // fall through to original fetch
      }
    }

    const response = await originalFetch.apply(this, args)

    if (looksLikeChartUrl(url)) {
      try {
        const clone = response.clone()
        const json = await clone.json()
        if (!looksLikeOHLCV(json) && !(json && looksLikeOHLCV(json.data))) {
          const dataKeys =
            json && json.data
              ? Object.keys(json.data).slice(0, 8).join(',')
              : 'none'
          console.log(
            '[NEPSE Analyzer] ⚠️ URL matched but JSON is NOT OHLCV. Top keys:',
            Object.keys(json || {})
              .slice(0, 8)
              .join(','),
            '| data keys:',
            dataKeys,
          )
        }
        dispatch(url, json)
      } catch (err) {
        console.log(
          '[NEPSE Analyzer] ⚠️ fetch dispatch error:',
          err && err.message,
        )
      }
    }

    return response
  }

  // ── Patch XMLHttpRequest ─────────────────────────────────────────
  const XHROpen = XMLHttpRequest.prototype.open
  const XHRSend = XMLHttpRequest.prototype.send

  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this._nepseUrl = typeof url === 'string' ? url : String(url || '')
    // DIAGNOSTIC: log NepseAlpha chart history XHR hits
    if (
      this._nepseUrl.includes('nepsealpha.com') &&
      this._nepseUrl.includes('/history')
    ) {
      console.log(
        '[NEPSE Analyzer] 📡 XHR hit:',
        this._nepseUrl.substring(0, 160),
      )
    }
    return XHROpen.call(this, method, url, ...rest)
  }

  XMLHttpRequest.prototype.send = function (...args) {
    if (looksLikeChartUrl(this._nepseUrl)) {
      const capturedUrl = this._nepseUrl
      this.addEventListener('load', function () {
        try {
          const json = JSON.parse(this.responseText)
          dispatch(capturedUrl, json)
        } catch (err) {
          console.log(
            '[NEPSE Analyzer] ⚠️ XHR dispatch error:',
            err && err.message,
          )
        }
      })
    }
    return XHRSend.apply(this, args)
  }

  // ── Shared helpers used by all interception patches ──────────────

  function scanForChartData(obj, depth) {
    if (depth > 5 || obj === null || typeof obj !== 'object') return
    if (looksLikeOHLCV(obj)) {
      dispatchFromWorkerData(obj)
      return
    }
    const keys = Array.isArray(obj)
      ? [...obj.keys()].slice(0, 5)
      : Object.keys(obj).slice(0, 20)
    for (const k of keys) {
      scanForChartData(obj[k], depth + 1)
    }
  }

  function dispatchFromWorkerData(raw) {
    const candles = normalizeCandles(raw)
    if (!candles || candles.length < 5) return

    const pathParts = window.location.pathname.split('/').filter(Boolean)
    const symbol =
      (pathParts[pathParts.length - 1] || 'UNKNOWN')
        .toUpperCase()
        .replace(/[^A-Z0-9]/g, '') || 'UNKNOWN'
    const resolution =
      new URLSearchParams(window.location.search).get('resolution') || '1D'

    window.postMessage(
      {
        type: MSG_TYPE,
        payload: {
          metadata: {
            symbol,
            resolution,
            countback: String(candles.length),
            isAdjust: 'false',
            time: '',
          },
          data: candles,
        },
      },
      '*',
    )
    console.log(
      `[NEPSE Analyzer] ✅ Intercepted: ${candles.length} candles · ${symbol} · ${resolution}`,
    )
  }

  // MessagePort patching removed — fetch + XHR interception handles all chart data.

  // ── Patch Worker constructor ─────────────────────────────────────
  ;(function patchWorker() {
    const NativeWorker = window.Worker
    if (!NativeWorker) return

    let _n = 0
    window.Worker = function (url, opts) {
      const w = new NativeWorker(url, opts)
      const id = ++_n
      console.log(
        `[NEPSE Analyzer] 👷 Worker#${id} created:`,
        String(url).substring(0, 80),
      )
      w.addEventListener('message', function (e) {
        if (e && e.data && typeof e.data === 'object') {
          try {
            scanForChartData(e.data, 0)
          } catch {}
        }
      })
      return w
    }
    window.Worker.prototype = NativeWorker.prototype
  })()

  // ── Patch SharedWorker constructor ───────────────────────────────
  ;(function patchSharedWorker() {
    const NativeSW = window.SharedWorker
    if (!NativeSW) return
    window.SharedWorker = function (url, opts) {
      const sw = new NativeSW(url, opts)
      console.log(
        '[NEPSE Analyzer] 🔗 SharedWorker created:',
        String(url).substring(0, 80),
      )
      sw.port.addEventListener('message', function (e) {
        if (e && e.data && typeof e.data === 'object') {
          try {
            scanForChartData(e.data, 0)
          } catch {}
        }
      })
      sw.port.start()
      return sw
    }
    window.SharedWorker.prototype = NativeSW.prototype
  })()

  // ── Manual fetch trigger (resolution changes / refresh from widget) ──
  // content_script posts {type:'NEPSE_FETCH_REQUEST', symbol, resolution}.
  // Since all resolutions map to one of 3 confirmed API endpoints (1S, 1, 1D),
  // direct fetch always works — no 422 possible.
  window.addEventListener('message', (event) => {
    if (event.source !== window) return
    if (!event.data || event.data.type !== 'NEPSE_FETCH_REQUEST') return
    const { symbol, resolution } = event.data
    const apiRes = getApiRes(resolution)
    const url = buildHistoryUrl(apiRes, symbol)
    console.log(
      `[NEPSE Analyzer] 🔄 Manual fetch: ${symbol} (${resolution}→api:${apiRes})`,
    )
    originalFetch(url, {
      headers: {
        accept: 'application/json, text/plain, */*',
        'cache-control': 'no-cache',
        pragma: 'no-cache',
        'x-requested-with': 'XMLHttpRequest',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
      },
      credentials: 'include',
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((json) => dispatch(url, json, { symbol, resolution }))
      .catch((err) =>
        postFetchError(symbol, resolution, `Fetch failed: ${err.message}`),
      )
  })

  // ── SPA navigation watcher — auto-re-fetch when symbol/interval changes ──
  // NepseAlpha is a SPA; switching stocks or intervals updates the URL via
  // history.pushState without a full page reload. We patch the History API
  // and also listen to popstate so every navigation triggers a fresh fetch.

  // Resolution aliases — NepseAlpha / TradingView sometimes uses short codes.
  const _RES_ALIASES = { D: '1D', W: '1W', M: '1M', H: '60', '2H': '120' }

  /**
   * Read current interval from the page URL.
   * Tries multiple extraction strategies in order of precedence:
   *   1. Query param  ?interval=   (standard TradingView SPA)
   *   2. Query param  ?resolution= (alternative TradingView param)
   *   3. URL path segment          (e.g. /trading/chart/SGHC/60)
   *   4. Hash param   #interval=   (some hash-router SPA setups)
   *   5. Fallback '1D'
   */
  function _readInterval() {
    const q = new URLSearchParams(window.location.search)
    const fromQ =
      q.get('interval') || q.get('resolution') || q.get('chart_resolution')
    if (fromQ) return _RES_ALIASES[fromQ] || fromQ

    // Path-based: /trading/chart/SYMBOL/INTERVAL
    const parts = window.location.pathname.split('/').filter(Boolean)
    if (parts.length >= 4) {
      const seg = parts[3]
      // Only treat it as a resolution if it looks like one (digits, or known code)
      if (
        /^\d+$/.test(seg) ||
        /^[0-9]+[SMHDWM]$/.test(seg) ||
        ['1D', '1W', '1M'].includes(seg)
      ) {
        return _RES_ALIASES[seg] || seg
      }
    }

    // Hash-based: nepsealpha.com/trading/chart#interval=60
    const hash = window.location.hash.slice(1)
    if (hash) {
      const fromH =
        new URLSearchParams(hash).get('interval') ||
        new URLSearchParams(hash).get('resolution')
      if (fromH) return _RES_ALIASES[fromH] || fromH
    }

    return '1D'
  }

  function _readSymbol() {
    const q = new URLSearchParams(window.location.search)
    const fromQ = q.get('symbol')
    if (fromQ) return fromQ.toUpperCase().replace(/[^A-Z0-9]/g, '') || 'NEPSE'
    const parts = window.location.pathname.split('/').filter(Boolean)
    // Path-based: /trading/chart/SYMBOL or /trading/chart/SYMBOL/INTERVAL
    if (parts.length >= 3) {
      const seg = parts[2]
      if (/^[A-Z0-9]+$/.test(seg.toUpperCase()) && !/^\d+$/.test(seg)) {
        return seg.toUpperCase().replace(/[^A-Z0-9]/g, '') || 'NEPSE'
      }
    }
    return 'NEPSE'
  }

  function getCurrentUrlState() {
    return { symbol: _readSymbol(), resolution: _readInterval() }
  }
  let _currentUrlState = getCurrentUrlState()

  // ── Auto-fetch (page load + SPA navigation) ──────────────────────
  function autoFetch(displayRes, symbolOverride) {
    const symbol = symbolOverride || _readSymbol()
    const displayResolution = displayRes || _readInterval()
    const apiRes = getApiRes(displayResolution)
    const fsk =
      window.fsk ||
      window._fsk ||
      (window.nepsealpha && window.nepsealpha.fsk) ||
      _lastFsk
    const url = buildHistoryUrl(apiRes, symbol, fsk)
    console.log(
      `[NEPSE Analyzer] 🔍 Auto-fetch: ${symbol} (display=${displayResolution} → api=${apiRes}) url=${url.substring(0, 120)}`,
    )
    originalFetch(url, {
      headers: {
        accept: 'application/json, text/plain, */*',
        'cache-control': 'no-cache',
        pragma: 'no-cache',
        'x-requested-with': 'XMLHttpRequest',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
      },
      credentials: 'include',
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((json) => {
        console.log(
          `[NEPSE Analyzer] ✅ autoFetch got JSON for ${symbol} (${displayResolution})`,
        )
        dispatch(url, json, { symbol, resolution: displayResolution })
      })
      .catch((err) =>
        postFetchError(
          symbol,
          displayResolution,
          `Fetch failed: ${err.message}`,
        ),
      )
  }

  function onSpaNavigate() {
    if (!isChartPage()) return
    const next = getCurrentUrlState()
    console.log(
      `[NEPSE Analyzer] 🗺️ SPA nav → symbol=${next.symbol} res=${next.resolution} | prev: symbol=${_currentUrlState.symbol} res=${_currentUrlState.resolution}`,
    )
    if (
      next.symbol !== _currentUrlState.symbol ||
      next.resolution !== _currentUrlState.resolution
    ) {
      const symChanged = next.symbol !== _currentUrlState.symbol
      _currentUrlState = next
      console.log(
        `[NEPSE Analyzer] 🔀 ${symChanged ? 'Symbol' : 'Interval'} → ${next.symbol} (${next.resolution})`,
      )
      window.postMessage(
        {
          type: 'NEPSE_SYMBOL_CHANGED',
          symbol: next.symbol,
          resolution: next.resolution,
        },
        '*',
      )
      setTimeout(() => autoFetch(next.resolution, next.symbol), 300)
    }
  }

  const _origPushState = history.pushState.bind(history)
  const _origReplaceState = history.replaceState.bind(history)
  history.pushState = (...a) => {
    _origPushState(...a)
    setTimeout(onSpaNavigate, 150)
  }
  history.replaceState = (...a) => {
    _origReplaceState(...a)
    setTimeout(onSpaNavigate, 150)
  }
  window.addEventListener('popstate', () => setTimeout(onSpaNavigate, 150))
  window.addEventListener('hashchange', () => setTimeout(onSpaNavigate, 150))

  // ── URL-polling fallback ──────────────────────────────────────────
  // NepseAlpha may change the active interval without calling pushState/replaceState
  // (e.g. a client-side router that mutates window.location differently).
  // Poll every 1.5 s as a safety net.
  ;(function startUrlPoll() {
    let _lastHref = window.location.href
    setInterval(() => {
      const cur = window.location.href
      if (cur !== _lastHref) {
        _lastHref = cur
        onSpaNavigate()
      }
    }, 1500)
  })()

  // ── Detect chart pages ──────────────────────────────────────────
  // Accept: /trading/chart  /nepse-chart  /chart  or any page with ?symbol=
  function isChartPage() {
    const path = window.location.pathname.toLowerCase()
    const hasSymbol = !!new URLSearchParams(window.location.search).get(
      'symbol',
    )
    return path.includes('chart') || hasSymbol
  }

  // Initial fetch 500 ms after page ready (let session cookies settle)
  console.log(
    '[NEPSE Analyzer] 📍 pathname:',
    window.location.pathname,
    '| isChartPage:',
    isChartPage(),
  )
  if (isChartPage()) {
    let _dispatched = false
    const _origDispatch = dispatch
    // Track if dispatch succeeds so fallback knows whether to retry
    window._nepseDispatched = () => {
      _dispatched = true
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () =>
        setTimeout(autoFetch, 500),
      )
    } else {
      setTimeout(autoFetch, 500)
    }

    // Fallback: if no data arrived after 4s, try once more
    // (catches cases where page loaded before extension, delaying DOMContentLoaded hook)
    setTimeout(() => {
      if (!window._nepseGotData) {
        console.log('[NEPSE Analyzer] ⏱️ Fallback fetch (no data yet after 4s)')
        autoFetch()
      }
    }, 4000)
  }

  console.log(
    '[NEPSE Analyzer] 🚀 NepseAlpha interceptor active on',
    location.hostname,
  )
})()
