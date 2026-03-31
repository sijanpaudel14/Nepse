/**
 * content_script.js — Bridge & UI Injector
 * ==========================================
 * Runs in Chrome's ISOLATED WORLD on ShareHub pages.
 *
 * RESPONSIBILITIES:
 * 1. Listen for intercepted chart data from inject.js via window.postMessage
 *    (inject.js runs in MAIN world via manifest.json "world": "MAIN" — no script injection needed)
 * 2. Forward data to background service worker via chrome.runtime.sendMessage
 *    (background worker makes the actual HTTP request to localhost:8000, bypassing
 *     mixed-content restrictions that block HTTP from an HTTPS page)
 * 3. Render the analysis results in a Shadow DOM floating widget
 */

;(function () {
  'use strict'
  console.log('[NEPSE Analyzer] content_script.js loaded (isolated world)')

  // ── Show loading widget immediately on chart pages ───────────────
  // inject.js auto-fetches 500 ms after load; show a loading state right away
  // so the user sees something is happening instead of just the pill.
  function showInitialLoading() {
    const params = new URLSearchParams(window.location.search)
    const symbol = (params.get('symbol') || 'NEPSE').toUpperCase()
    const resolution = params.get('interval') || '1D'
    if (window.location.pathname.toLowerCase().includes('chart')) {
      // Small delay to let Shadow DOM host attach to body
      setTimeout(() => renderWidget({ loading: true, symbol, resolution }), 600)
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', showInitialLoading)
  } else {
    showInitialLoading()
  }

  // ── Show "Active" pill immediately ───────────────────────────────
  // This lets the user see the extension IS loaded even before any chart data.
  function showReadyPill() {
    if (document.getElementById('nepse-ready-pill')) return
    const pill = document.createElement('div')
    pill.id = 'nepse-ready-pill'
    pill.style.cssText = [
      'position:fixed',
      'bottom:12px',
      'right:12px',
      'z-index:2147483647',
      'background:#1e293b',
      'color:#94a3b8',
      'font:12px/1 monospace',
      'padding:5px 10px',
      'border-radius:20px',
      'border:1px solid #334155',
      'pointer-events:none',
      'user-select:none',
      'letter-spacing:.5px',
    ].join(';')
    pill.textContent = '▶ NEPSE Active'
    document.documentElement.appendChild(pill)
    // Auto-remove after 5 s — widget will take over once data arrives
    setTimeout(() => pill.remove(), 5000)
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', showReadyPill)
  } else {
    showReadyPill()
  }

  // ── Guard: detect when the extension has been reloaded mid-session ─
  // After an extension update/reload, chrome.runtime.id becomes undefined in
  // the stale content script. Any chrome.runtime call then throws
  // "Extension context invalidated". This helper lets every call bail out
  // silently instead of crashing with an unhandled error.
  function isContextValid() {
    return !!(typeof chrome !== 'undefined' && chrome.runtime?.id)
  }

  // ── PRIMARY: Receive analysis results pushed from background.js ───
  // background.js uses chrome.webRequest to intercept the chart API call,
  // re-fetches the data, calls the backend, and pushes the result here.
  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'RENDER_RESULT') {
      renderWidget(message.result)
    } else if (message.type === 'RENDER_ERROR') {
      renderWidget({
        error: true,
        errorMessage: message.message,
        symbol: message.symbol || 'UNKNOWN',
        resolution: '?',
      })
    }
  })

  // ── FALLBACK: Listen for Intercepted Chart Data from inject.js ────
  // This path fires if the datafeed happens to run on the main thread.
  // inject.js sends data via window.postMessage with type "NEPSE_CHART_DATA"

  // Debounce: only re-analyze if symbol/resolution changed or 30s have elapsed.
  const _lastAnalysis = new Map() // key -> timestamp

  // Track last intercepted symbol/resolution so resolution changes and
  // refresh can trigger the correct inject.js re-fetch.
  let _lastCapturedSymbol = 'NEPSE'
  let _lastCapturedResolution = '1D'

  window.addEventListener('message', (event) => {
    // Security: only accept messages from the same page
    if (event.source !== window) return

    // inject.js fires NEPSE_SYMBOL_CHANGED when user navigates to a different
    // stock or interval (SPA pushState). Show loading immediately.
    if (event.data && event.data.type === 'NEPSE_SYMBOL_CHANGED') {
      const { symbol, resolution } = event.data
      _lastCapturedSymbol = symbol
      _lastCapturedResolution = normalizeResolution(resolution)
      _lastAnalysis.clear()
      renderWidget({
        loading: true,
        symbol,
        resolution: _lastCapturedResolution,
      })
      return
    }

    // inject.js fires NEPSE_FETCH_ERROR when proactive or manual fetch fails,
    // or when the API returns no OHLCV data for the requested resolution.
    if (event.data && event.data.type === 'NEPSE_FETCH_ERROR') {
      const { symbol, resolution, message } = event.data
      renderWidget({
        error: true,
        errorMessage: message || 'Fetch failed',
        symbol: symbol || _lastCapturedSymbol,
        resolution: resolution || _lastCapturedResolution,
      })
      return
    }

    if (!event.data || event.data.type !== 'NEPSE_CHART_DATA') return

    const payload = event.data.payload
    if (!payload || !payload.metadata || !payload.data) return

    const { symbol, resolution } = payload.metadata
    _lastCapturedSymbol = symbol
    _lastCapturedResolution = resolution
    const dedupeKey = `${symbol}:${resolution}`
    const now = Date.now()
    const lastTime = _lastAnalysis.get(dedupeKey) || 0
    if (now - lastTime < 5000) return // skip — same symbol+resolution within 5 s (debounce)
    _lastAnalysis.set(dedupeKey, now)

    console.log(
      `[NEPSE Analyzer] (fallback path) ${payload.data.length} candles for ${symbol}`,
    )

    // Show loading state in widget
    renderWidget({
      loading: true,
      symbol,
      resolution,
    })

    // Forward to background service worker — it makes the actual HTTP fetch
    // to localhost:8000 so we avoid mixed-content blocking (HTTPS → HTTP).
    if (!isContextValid()) return
    try {
      chrome.runtime.sendMessage({ type: 'ANALYZE', payload }, (response) => {
        if (chrome.runtime.lastError) {
          renderWidget({
            error: true,
            errorMessage: chrome.runtime.lastError.message,
            symbol,
            resolution,
          })
          return
        }
        if (response && response.error) {
          renderWidget({
            error: true,
            errorMessage: response.error,
            symbol,
            resolution,
          })
          return
        }
        if (response && response.result) {
          renderWidget(response.result)
          if (isContextValid()) {
            try {
              chrome.runtime.sendMessage({
                type: 'ANALYSIS_RESULT',
                verdict: response.result.verdict,
                symbol: response.result.symbol,
              })
            } catch (_e) {}
          }
        }
      })
    } catch (_e) {
      // Context was invalidated between the guard check and the actual call
    }
  })

  // ── 2. Shadow DOM Widget Renderer ────────────────────────────────

  let widgetHost = null
  let shadowRoot = null
  let _lastResultData = null // Store last result for refresh button
  let _loadingTimeoutId = null // Safety net to prevent stuck loading state

  // Resolutions ordered by trading importance.
  // ★ = highest priority for consistent profit (NEPSE context)
  // Data sources: 1S→seconds, 1→minutes, 1D→daily (NepseAlpha confirmed).
  // Hour/day/week/month resolutions map to 1D API internally.
  const RESOLUTIONS = [
    // ── Daily / weekly / monthly ─────────────────────────────────────
    { value: '1D', label: '1D ★' },
    { value: '2D', label: '2D' },
    { value: '3D', label: '3D' },
    { value: '4D', label: '4D' },
    { value: '1W', label: '1W' },
    { value: '2W', label: '2W' },
    { value: '1M', label: '1M' },
    { value: '2M', label: '2M' },
    { value: '3M', label: '3M' },
    { value: '6M', label: '6M' },
    // ── Hours ────────────────────────────────────────────────────────
    { value: '240', label: '4H' },
    { value: '180', label: '3H' },
    { value: '120', label: '2H' },
    { value: '60', label: '1H ★' },
    // ── Minutes ──────────────────────────────────────────────────────
    { value: '45', label: '45m' },
    { value: '30', label: '30m' },
    { value: '15', label: '15m ★' },
    { value: '10', label: '10m' },
    { value: '5', label: '5m' },
    { value: '3', label: '3m' },
    { value: '2', label: '2m' },
    { value: '1', label: '1m' },
    // ── Seconds ──────────────────────────────────────────────────────
    { value: '45S', label: '45S' },
    { value: '30S', label: '30S' },
    { value: '20S', label: '20S' },
    { value: '15S', label: '15S' },
    { value: '10S', label: '10S' },
    { value: '1S', label: '1S' },
  ]

  // NepseAlpha's URL uses TradingView interval codes which match our values.
  // Map any aliases that might appear from page URL or intercept.
  function normalizeResolution(r) {
    const aliases = { D: '1D', W: '1W', M: '1M', '2H': '120', H: '60' }
    return aliases[r] || r
  }

  /**
   * Create or update the floating analysis widget on the page.
   * Uses Shadow DOM to completely isolate our styles from ShareHub's CSS.
   * @param {object} data - Analysis result from backend, or loading/error state
   */
  function renderWidget(data) {
    // Track last successful result for refresh
    if (!data.loading && !data.error) {
      _lastResultData = data
    }

    // Cancel any in-flight loading timeout whenever the widget updates
    if (_loadingTimeoutId !== null) {
      clearTimeout(_loadingTimeoutId)
      _loadingTimeoutId = null
    }
    // Safety net: if we're still in loading state after 20 s, show a timeout error
    // (handles cases where API call silently fails or backend hangs)
    if (data.loading) {
      const sym = data.symbol
      const res = data.resolution
      _loadingTimeoutId = setTimeout(() => {
        _loadingTimeoutId = null
        renderWidget({
          error: true,
          errorMessage:
            'Analysis timed out (20 s). The API may not support this resolution, or the backend is not running.',
          symbol: sym,
          resolution: res,
        })
      }, 20000)
    }
    // Create the host element on first call
    if (!widgetHost) {
      widgetHost = document.createElement('div')
      widgetHost.id = 'nepse-analyzer-widget-host'
      shadowRoot = widgetHost.attachShadow({ mode: 'closed' })

      // Load our styles into the shadow DOM
      const styleLink = document.createElement('link')
      styleLink.rel = 'stylesheet'
      if (isContextValid()) {
        styleLink.href = chrome.runtime.getURL('styles.css')
      }
      shadowRoot.appendChild(styleLink)

      document.body.appendChild(widgetHost)
    }

    // Remove old content (keep the stylesheet)
    const oldWidget = shadowRoot.querySelector('.nepse-widget')
    if (oldWidget) oldWidget.remove()

    // Build the widget HTML
    const widget = document.createElement('div')
    widget.className = 'nepse-widget'

    if (data.loading) {
      widget.innerHTML = buildLoadingHTML(data)
    } else if (data.error) {
      widget.innerHTML = buildErrorHTML(data)
    } else {
      widget.innerHTML = buildResultHTML(data)
    }

    // Expand / full-screen toggle
    const expandBtn = widget.querySelector('.widget-expand')
    if (expandBtn) {
      expandBtn.addEventListener('click', (e) => {
        e.stopPropagation()
        widget.classList.toggle('expanded')
        expandBtn.textContent = widget.classList.contains('expanded')
          ? '⊞'
          : '⛶'
        expandBtn.title = widget.classList.contains('expanded')
          ? 'Restore'
          : 'Expand to full screen'
      })
    }

    // Collapse/expand toggle
    const collapseBtn = widget.querySelector('.widget-collapse')
    if (collapseBtn) {
      collapseBtn.addEventListener('click', (e) => {
        e.stopPropagation()
        widget.classList.toggle('collapsed')
        collapseBtn.textContent = widget.classList.contains('collapsed')
          ? '▸'
          : '▾'
      })
    }

    // Close button
    const closeBtn = widget.querySelector('.widget-close')
    if (closeBtn) {
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation()
        widget.style.display = 'none'
      })
    }

    // Refresh button — asks inject.js to re-fetch (same-origin, cookies auto-sent)
    const refreshBtn = widget.querySelector('.widget-refresh')
    if (refreshBtn) {
      refreshBtn.addEventListener('click', (e) => {
        e.stopPropagation()
        _lastAnalysis.clear()
        const sym = _lastCapturedSymbol || _lastResultData?.symbol || 'NEPSE'
        const res =
          _lastCapturedResolution || _lastResultData?.resolution || '1D'
        renderWidget({ loading: true, symbol: sym, resolution: res })
        window.postMessage(
          { type: 'NEPSE_FETCH_REQUEST', symbol: sym, resolution: res },
          '*',
        )
      })
    }

    // Resolution selector — asks inject.js to do a fresh same-origin fetch
    // (no background.js involvement needed; inject.js runs in MAIN world
    //  so the browser sends nepsealpha session cookies automatically)
    const resSelect = widget.querySelector('.resolution-select')
    if (resSelect) {
      resSelect.addEventListener('change', (e) => {
        e.stopPropagation()
        const newRes = e.target.value
        const sym = _lastCapturedSymbol || _lastResultData?.symbol || 'NEPSE'
        _lastCapturedResolution = newRes
        _lastAnalysis.clear()
        renderWidget({ loading: true, symbol: sym, resolution: newRes })
        window.postMessage(
          { type: 'NEPSE_FETCH_REQUEST', symbol: sym, resolution: newRes },
          '*',
        )
      })
    }

    // Tab switching
    const tabs = widget.querySelectorAll('.tab')
    const panels = widget.querySelectorAll('.tab-content')
    tabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        tabs.forEach((t) => t.classList.remove('active'))
        panels.forEach((p) => p.classList.remove('active'))
        tab.classList.add('active')
        const target = widget.querySelector(
          `.tab-content[data-panel="${tab.dataset.tab}"]`,
        )
        if (target) target.classList.add('active')
      })
    })

    // Drag-to-move — attach to the ⠿ drag handle in the header
    const dragHandle = widget.querySelector('.widget-drag')
    if (dragHandle) {
      dragHandle.addEventListener('mousedown', (e) => {
        e.preventDefault()
        e.stopPropagation()
        const rect = widget.getBoundingClientRect()
        // Switch from bottom/right anchoring to top/left so we can freely reposition
        widget.style.bottom = 'auto'
        widget.style.right = 'auto'
        widget.style.top = rect.top + 'px'
        widget.style.left = rect.left + 'px'
        const sx = e.clientX - rect.left
        const sy = e.clientY - rect.top
        function onMove(ev) {
          const l = Math.max(
            0,
            Math.min(ev.clientX - sx, window.innerWidth - widget.offsetWidth),
          )
          const t = Math.max(
            0,
            Math.min(ev.clientY - sy, window.innerHeight - widget.offsetHeight),
          )
          widget.style.left = l + 'px'
          widget.style.top = t + 'px'
        }
        function onUp() {
          document.removeEventListener('mousemove', onMove)
          document.removeEventListener('mouseup', onUp)
          try {
            localStorage.setItem(
              'nepse-widget-pos',
              JSON.stringify({
                top: widget.style.top,
                left: widget.style.left,
              }),
            )
          } catch (_) {}
        }
        document.addEventListener('mousemove', onMove)
        document.addEventListener('mouseup', onUp)
      })
    }

    // Restore saved drag position on every render (survives symbol/resolution switches)
    try {
      const _pos = JSON.parse(
        localStorage.getItem('nepse-widget-pos') || 'null',
      )
      if (_pos && _pos.top && _pos.left) {
        widget.style.top = _pos.top
        widget.style.left = _pos.left
        widget.style.bottom = 'auto'
        widget.style.right = 'auto'
      }
    } catch (_) {}

    shadowRoot.appendChild(widget)
  }

  function buildLoadingHTML(data) {
    return `
      <div class="widget-header">
        <div class="widget-title">
          <span class="widget-icon">📊</span>
          Analyzing: ${escapeHtml(data.symbol)} (${escapeHtml(data.resolution)})
        </div>
        <div class="header-actions">
          <button class="widget-drag" title="Drag to move">⠿</button>
          <button class="widget-expand" title="Expand to full screen">⛶</button>
          <button class="widget-close" title="Close">✕</button>
        </div>
      </div>
      <div class="widget-body">
        <div class="loading-spinner">
          <div class="spinner"></div>
          <span>Running analysis...</span>
        </div>
      </div>
    `
  }

  function buildErrorHTML(data) {
    return `
      <div class="widget-header widget-header-error">
        <div class="widget-title">
          <span class="widget-icon">⚠️</span>
          ${escapeHtml(data.symbol)} (${escapeHtml(data.resolution)})
        </div>
        <div class="header-actions">
          <button class="widget-drag" title="Drag to move">⠿</button>
          <button class="widget-refresh" title="Retry">⟳</button>
          <button class="widget-expand" title="Expand to full screen">⛶</button>
          <button class="widget-close" title="Close">✕</button>
        </div>
      </div>
      <div class="widget-body">
        <div class="error-message">
          <strong>Analysis Failed</strong>
          <p>${escapeHtml(data.errorMessage)}</p>
          <p class="error-hint">Make sure the backend is running:<br>
          <code>cd backend &amp;&amp; uvicorn main:app --reload</code><br>
          Then open a chart on <a href="https://nepsealpha.com/trading/chart" target="_blank" style="color:#60a5fa">nepsealpha.com</a></p>
        </div>
      </div>
    `
  }

  function buildResultHTML(data) {
    const verdictClass = getVerdictClass(data.verdict)
    const operatorClass = data.operator_activity ? 'alert-danger' : 'alert-safe'
    const changeIcon = (data.price_change_pct || 0) >= 0 ? '▲' : '▼'
    const changeClass =
      (data.price_change_pct || 0) >= 0 ? 'change-up' : 'change-down'

    // Patterns
    let patternsHTML = ''
    if (data.patterns && data.patterns.length > 0) {
      patternsHTML = data.patterns
        .slice(0, 6)
        .map((p) => {
          const cls = p.direction === 'Bullish' ? 'tag-bullish' : 'tag-bearish'
          const icon = p.direction === 'Bullish' ? '▲' : '▼'
          return `<span class="pattern-tag ${cls}">${icon} ${escapeHtml(p.name)} <span class="pattern-str">${p.strength > 0 ? '+' : ''}${p.strength}</span></span>`
        })
        .join('')
    } else {
      patternsHTML =
        '<span class="pattern-tag tag-neutral">— No patterns detected</span>'
    }

    // Warnings
    let warningsHTML = ''
    if (data.warnings && data.warnings.length > 0) {
      warningsHTML = `<div class="warnings-section">${data.warnings
        .map((w) => `<div class="warning-item">${escapeHtml(w)}</div>`)
        .join('')}</div>`
    }

    // Oscillator signals table
    let oscTableHTML = ''
    if (data.oscillator_signals && data.oscillator_signals.length > 0) {
      oscTableHTML = data.oscillator_signals
        .map((s) => {
          const dotClass =
            s.signal === 'Buy'
              ? 'dot-buy'
              : s.signal === 'Sell'
                ? 'dot-sell'
                : 'dot-neutral'
          return `<div class="signal-row">
          <span class="sig-name">${escapeHtml(s.name)}</span>
          <span class="sig-value">${s.value != null ? formatNum(s.value) : '—'}</span>
          <span class="sig-dot ${dotClass}">●</span>
          <span class="sig-signal ${dotClass}">${s.signal}</span>
        </div>`
        })
        .join('')
    }

    // MA signals table
    let maTableHTML = ''
    if (data.ma_signals && data.ma_signals.length > 0) {
      maTableHTML = data.ma_signals
        .map((s) => {
          const dotClass = s.signal === 'Buy' ? 'dot-buy' : 'dot-sell'
          return `<div class="signal-row">
          <span class="sig-name">${escapeHtml(s.name)}</span>
          <span class="sig-value">${formatPrice(s.value)}</span>
          <span class="sig-dot ${dotClass}">●</span>
          <span class="sig-signal ${dotClass}">${s.signal}</span>
        </div>`
        })
        .join('')
    }

    // Multi-TF table
    let multiTfHTML = ''
    if (data.multi_tf && data.multi_tf.length > 0) {
      const tfRows = data.multi_tf
        .map((tf) => {
          const trendIcon =
            tf.trend === 'UPTREND' ? '▲' : tf.trend === 'DOWNTREND' ? '▼' : '→'
          const trendCls = getTrendClass(tf.trend)
          const macdIcon =
            tf.macd_signal === 'Bullish'
              ? '▲'
              : tf.macd_signal === 'Bearish'
                ? '▼'
                : '→'
          const macdCls = getMacdClass(tf.macd_signal)
          const vCls = getVerdictClass(tf.verdict)
          return `<div class="tf-row">
          <span class="tf-name">${escapeHtml(tf.timeframe)}</span>
          <span class="tf-rsi ${getRsiClass(tf.rsi_14)}">${tf.rsi_14 != null ? formatNum(tf.rsi_14) : '—'}</span>
          <span class="tf-macd ${macdCls}">${macdIcon}</span>
          <span class="tf-trend ${trendCls}">${trendIcon}</span>
          <span class="tf-verdict verdict-pill-${vCls}">${escapeHtml(tf.verdict)}</span>
        </div>`
        })
        .join('')

      // Alignment check
      const bullish = data.multi_tf.filter(
        (t) => t.verdict === 'BUY' || t.verdict === 'STRONG BUY',
      ).length
      const total = data.multi_tf.length
      let alignText = '⚠️ Diverging'
      if (bullish === total) alignText = '✅ Fully Bullish Aligned'
      else if (bullish === 0) alignText = '🔴 Fully Bearish Aligned'
      else alignText = '⚠️ Partially Aligned'

      multiTfHTML = `
        <div class="tf-header-row">
          <span>TF</span><span>RSI</span><span>MACD</span><span>Trend</span><span>Verdict</span>
        </div>
        <div class="tf-row tf-current">
          <span class="tf-name">Current</span>
          <span class="tf-rsi ${getRsiClass(data.rsi_14)}">${formatNum(data.rsi_14)}</span>
          <span class="tf-macd ${getMacdClass(data.macd_signal)}">${data.macd_signal === 'Bullish' ? '▲' : data.macd_signal === 'Bearish' ? '▼' : '→'}</span>
          <span class="tf-trend ${getTrendClass(data.trend)}">${data.trend === 'UPTREND' ? '▲' : data.trend === 'DOWNTREND' ? '▼' : '→'}</span>
          <span class="tf-verdict verdict-pill-${verdictClass}">${escapeHtml(data.verdict)}</span>
        </div>
        ${tfRows}
        <div class="tf-alignment">${alignText}</div>`
    } else {
      multiTfHTML =
        '<div class="empty-state">📊 Multi-TF available for daily/weekly data with sufficient history</div>'
    }

    // Fibonacci levels
    let fibHTML = ''
    if (data.fibonacci_levels && data.fibonacci_levels.length > 0) {
      fibHTML = data.fibonacci_levels
        .map((f) => {
          const isNear =
            Math.abs(data.current_price - f.price) / data.current_price < 0.02
          return `<div class="fib-row ${isNear ? 'fib-near' : ''}">
          <span class="fib-level">${escapeHtml(f.level)}</span>
          <span class="fib-price">${formatPrice(f.price)}</span>
        </div>`
        })
        .join('')
    }

    // Pivot points
    let pivotHTML = ''
    if (data.pivot_points) {
      const pp = data.pivot_points
      pivotHTML = `
        <div class="pivot-grid">
          <div class="pivot-item pivot-r3"><span class="pv-label">R3</span><span class="pv-val pv-resistance">${formatPrice(pp.r3)}</span></div>
          <div class="pivot-item pivot-r2"><span class="pv-label">R2</span><span class="pv-val pv-resistance">${formatPrice(pp.r2)}</span></div>
          <div class="pivot-item pivot-r1"><span class="pv-label">R1</span><span class="pv-val pv-resistance">${formatPrice(pp.r1)}</span></div>
          <div class="pivot-item pivot-pp"><span class="pv-label">PP</span><span class="pv-val pv-pivot">${formatPrice(pp.pp)}</span></div>
          <div class="pivot-item pivot-s1"><span class="pv-label">S1</span><span class="pv-val pv-support">${formatPrice(pp.s1)}</span></div>
          <div class="pivot-item pivot-s2"><span class="pv-label">S2</span><span class="pv-val pv-support">${formatPrice(pp.s2)}</span></div>
          <div class="pivot-item pivot-s3"><span class="pv-label">S3</span><span class="pv-val pv-support">${formatPrice(pp.s3)}</span></div>
        </div>`
    }

    // 52-week range bar
    let rangeHTML = ''
    if (data.high_52w != null && data.low_52w != null) {
      const range = data.high_52w - data.low_52w
      const pos =
        range > 0 ? ((data.current_price - data.low_52w) / range) * 100 : 50
      rangeHTML = `
        <div class="range-section">
          <div class="range-labels">
            <span class="range-low">${formatPrice(data.low_52w)}</span>
            <span class="range-high">${formatPrice(data.high_52w)}</span>
          </div>
          <div class="range-bar">
            <div class="range-fill"></div>
            <div class="range-marker" style="left:${Math.min(100, Math.max(0, pos))}%"></div>
          </div>
          <div class="range-info">
            Current: ${formatPrice(data.current_price)} · ${data.pct_from_52w_high != null ? data.pct_from_52w_high + '% from high' : ''} · ${data.pct_from_52w_low != null ? '+' + data.pct_from_52w_low + '% from low' : ''}
          </div>
        </div>`
    }

    // Support/Resistance
    let srHTML = ''
    if (
      (data.resistance_levels && data.resistance_levels.length) ||
      (data.support_levels && data.support_levels.length)
    ) {
      let rows = ''
      if (data.resistance_levels) {
        rows += data.resistance_levels
          .slice()
          .reverse()
          .map((r, i) => {
            const distPct = (
              ((r - data.current_price) / data.current_price) *
              100
            ).toFixed(2)
            return `<div class="sr-row sr-resistance">
            <span class="sr-label">R${data.resistance_levels.length - i}</span>
            <span class="sr-price">${formatPrice(r)}</span>
            <span class="sr-dist">+${distPct}%</span>
          </div>`
          })
          .join('')
      }
      rows += `<div class="sr-row sr-current"><span class="sr-label">▶ Price</span><span class="sr-price">${formatPrice(data.current_price)}</span><span class="sr-dist">—</span></div>`
      if (data.support_levels) {
        rows += data.support_levels
          .map((s, i) => {
            const distPct = (
              ((data.current_price - s) / data.current_price) *
              100
            ).toFixed(2)
            return `<div class="sr-row sr-support">
            <span class="sr-label">S${i + 1}</span>
            <span class="sr-price">${formatPrice(s)}</span>
            <span class="sr-dist">-${distPct}%</span>
          </div>`
          })
          .join('')
      }
      srHTML = rows
    }

    // Summary badges
    const oscSumClass = getSummaryClass(data.oscillator_summary)
    const maSumClass = getSummaryClass(data.ma_summary)
    const overallSumClass = getSummaryClass(data.overall_summary)

    // Breakout status class
    const breakoutClass = data.breakout_status
      ? data.breakout_status.includes('Bullish') ||
        data.breakout_status.includes('Upper')
        ? 'status-bullish'
        : data.breakout_status.includes('Bearish') ||
            data.breakout_status.includes('Lower')
          ? 'status-bearish'
          : data.breakout_status.includes('Near')
            ? 'status-warning'
            : 'status-neutral'
      : 'status-neutral'

    // RSI zone label
    const rsiZone =
      data.rsi_14 != null
        ? data.rsi_14 > 80
          ? 'Extreme Overbought'
          : data.rsi_14 > 70
            ? 'Overbought'
            : data.rsi_14 > 60
              ? 'Bullish Zone'
              : data.rsi_14 > 40
                ? 'Neutral Zone'
                : data.rsi_14 > 30
                  ? 'Bearish Zone'
                  : data.rsi_14 > 20
                    ? 'Oversold'
                    : 'Extreme Oversold'
        : 'N/A'

    // ADX strength label
    const adxLabel =
      data.adx_14 != null
        ? data.adx_14 > 50
          ? 'Very Strong'
          : data.adx_14 > 25
            ? 'Strong'
            : data.adx_14 > 20
              ? 'Developing'
              : 'Weak / No Trend'
        : 'N/A'

    return `
      <div class="widget-header widget-header-${verdictClass}">
        <div class="widget-title">
          <span class="widget-icon">💹</span>
          <span class="symbol-name">${escapeHtml(data.symbol)}</span>
          <select class="resolution-select" title="Change Resolution">
            ${RESOLUTIONS.map((r) => `<option value="${r.value}"${normalizeResolution(data.resolution) === r.value ? ' selected' : ''}>${r.label}</option>`).join('')}
          </select>
        </div>
        <div class="header-actions">
          <button class="widget-drag" title="Drag to move">⠿</button>
          <button class="widget-refresh" title="Refresh Analysis">⟳</button>
          <button class="widget-expand" title="Expand to full screen">⛶</button>
          <button class="widget-collapse" title="Collapse">▾</button>
          <button class="widget-close" title="Close">✕</button>
        </div>
      </div>

      <div class="tab-bar">
        <button class="tab active" data-tab="overview">📊 Overview</button>
        <button class="tab" data-tab="momentum">⚡ Momentum</button>
        <button class="tab" data-tab="technical">📈 Technical</button>
        <button class="tab" data-tab="multitf">🔄 Multi-TF</button>
        <button class="tab" data-tab="levels">🎯 Levels</button>
        <button class="tab" data-tab="market">🏛️ Market</button>
      </div>

      <div class="widget-body">
        <!-- ═══ OVERVIEW TAB ═══ -->
        <div class="tab-content active" data-panel="overview">
          <div class="verdict-banner verdict-${verdictClass}">
            <div class="verdict-text">${escapeHtml(data.verdict)}</div>
            <div class="confidence-bar"><div class="confidence-fill" style="width:${data.confidence}%"></div></div>
            <div class="confidence-label">${data.confidence}% confidence</div>
          </div>

          <div class="price-header">
            <span class="current-price">${formatPrice(data.current_price)}</span>
            <span class="price-change ${changeClass}">${changeIcon} ${Math.abs(data.price_change_pct || 0).toFixed(2)}%</span>
          </div>

          <div class="summary-badges">
            <div class="summary-badge ${oscSumClass}">
              <span class="badge-label">Oscillators</span>
              <span class="badge-value">${data.oscillator_summary || 'N/A'}</span>
            </div>
            <div class="summary-badge ${maSumClass}">
              <span class="badge-label">Moving Avg</span>
              <span class="badge-value">${data.ma_summary || 'N/A'}</span>
            </div>
            <div class="summary-badge ${overallSumClass}">
              <span class="badge-label">Overall</span>
              <span class="badge-value">${data.overall_summary || 'N/A'}</span>
            </div>
          </div>

          <!-- Quick Status Cards -->
          <div class="status-cards">
            <div class="status-card ${breakoutClass}">
              <span class="sc-icon">🔓</span>
              <div class="sc-content">
                <span class="sc-label">Breakout</span>
                <span class="sc-value">${escapeHtml(data.breakout_status || 'N/A')}</span>
              </div>
            </div>
            <div class="status-card ${data.trend === 'UPTREND' ? 'status-bullish' : data.trend === 'DOWNTREND' ? 'status-bearish' : 'status-neutral'}">
              <span class="sc-icon">${data.trend === 'UPTREND' ? '📈' : data.trend === 'DOWNTREND' ? '📉' : '➡️'}</span>
              <div class="sc-content">
                <span class="sc-label">Trend</span>
                <span class="sc-value">${escapeHtml(data.trend)}</span>
              </div>
            </div>
            <div class="status-card">
              <span class="sc-icon">🏗️</span>
              <div class="sc-content">
                <span class="sc-label">Structure</span>
                <span class="sc-value">${escapeHtml(data.market_structure || 'N/A')}</span>
              </div>
            </div>
            <div class="status-card">
              <span class="sc-icon">🔄</span>
              <div class="sc-content">
                <span class="sc-label">Phase</span>
                <span class="sc-value">${escapeHtml(data.market_phase || 'N/A')}</span>
              </div>
            </div>
          </div>

          <div class="section">
            <div class="section-label">🔍 Candlestick Patterns</div>
            <div class="patterns-list">${patternsHTML}</div>
          </div>

          <div class="section indicators-grid">
            <div class="indicator">
              <span class="ind-label">RSI (14)</span>
              <div class="ind-gauge"><div class="gauge-fill ${getRsiClass(data.rsi_14)}" style="width:${Math.min(100, data.rsi_14 || 0)}%"></div></div>
              <span class="ind-value ${getRsiClass(data.rsi_14)}">${formatNum(data.rsi_14)} <span class="ind-zone">${rsiZone}</span></span>
            </div>
            <div class="indicator">
              <span class="ind-label">ADX (14)</span>
              <span class="ind-value">${formatNum(data.adx_14 || data.trend_strength)} <span class="ind-zone">${adxLabel}</span></span>
            </div>
            <div class="indicator">
              <span class="ind-label">MACD</span>
              <span class="ind-value ${getMacdClass(data.macd_signal)}">${data.macd_signal === 'Bullish' ? '▲' : data.macd_signal === 'Bearish' ? '▼' : '→'} ${data.macd_signal || 'N/A'}</span>
            </div>
            <div class="indicator">
              <span class="ind-label">Momentum</span>
              <span class="ind-value">${escapeHtml(data.momentum_status || 'N/A')}</span>
            </div>
          </div>

          <div class="section">
            <div class="operator-alert ${operatorClass}">
              <span class="operator-icon">${data.operator_activity ? '🚨' : '✅'}</span>
              <span>${
                data.operator_activity
                  ? `Operator Activity Detected (${data.volume_ratio}x avg vol)`
                  : `Normal Volume (${data.volume_ratio}x avg)`
              }</span>
            </div>
          </div>

          <!-- Nearest S/R Quick View -->
          ${
            data.nearest_support || data.nearest_resistance
              ? `
          <div class="section sr-quick">
            ${
              data.nearest_resistance
                ? `<div class="srq-item srq-resistance">
              <span class="srq-label">Nearest Resistance</span>
              <span class="srq-price">${formatPrice(data.nearest_resistance)}</span>
              <span class="srq-dist">+${data.resistance_distance_pct}%</span>
            </div>`
                : ''
            }
            ${
              data.nearest_support
                ? `<div class="srq-item srq-support">
              <span class="srq-label">Nearest Support</span>
              <span class="srq-price">${formatPrice(data.nearest_support)}</span>
              <span class="srq-dist">-${data.support_distance_pct}%</span>
            </div>`
                : ''
            }
          </div>`
              : ''
          }

          <div class="section price-levels">
            <div class="section-label">🎯 Price Targets</div>
            <div class="price-row price-target">
              <span class="price-label">Target</span>
              <span class="price-value">${formatPrice(data.suggested_target)}</span>
              <span class="price-pct change-up">+${data.suggested_target && data.current_price ? (((data.suggested_target - data.current_price) / data.current_price) * 100).toFixed(2) : '0'}%</span>
            </div>
            <div class="price-row price-sl">
              <span class="price-label">Stop Loss</span>
              <span class="price-value">${formatPrice(data.suggested_sl)}</span>
              <span class="price-pct change-down">${data.suggested_sl && data.current_price ? (((data.suggested_sl - data.current_price) / data.current_price) * 100).toFixed(2) : '0'}%</span>
            </div>
            <div class="price-row">
              <span class="price-label">Risk : Reward</span>
              <span class="price-value rr-value">1 : ${data.risk_reward_ratio}</span>
              <span class="price-pct">${data.risk_reward_ratio >= 2 ? '✅ Good' : data.risk_reward_ratio >= 1.5 ? '⚠️ Fair' : '🔴 Poor'}</span>
            </div>
          </div>

          ${warningsHTML}
        </div>

        <!-- ═══ MOMENTUM TAB ═══ -->
        <div class="tab-content" data-panel="momentum">
          <div class="section">
            <div class="section-label">⚡ Momentum Analysis</div>
            <div class="info-card-grid">
              <div class="info-card">
                <div class="ic-header">Momentum Status</div>
                <div class="ic-value">${escapeHtml(data.momentum_status || 'N/A')}</div>
              </div>
              <div class="info-card">
                <div class="ic-header">Volume Profile</div>
                <div class="ic-value">${escapeHtml(data.volume_profile || 'N/A')}</div>
              </div>
              <div class="info-card">
                <div class="ic-header">BB Position</div>
                <div class="ic-value">${escapeHtml(data.bb_position || 'N/A')}</div>
              </div>
              <div class="info-card">
                <div class="ic-header">RSI Divergence</div>
                <div class="ic-value">${escapeHtml(data.rsi_divergence || 'None Detected')}</div>
              </div>
            </div>
          </div>

          <div class="section">
            <div class="section-label">📊 RSI Analysis</div>
            <div class="rsi-dashboard">
              <div class="rsi-gauge-large">
                <div class="rsi-bar-bg">
                  <div class="rsi-zone rsi-zone-oversold"></div>
                  <div class="rsi-zone rsi-zone-neutral"></div>
                  <div class="rsi-zone rsi-zone-overbought"></div>
                  <div class="rsi-needle" style="left:${Math.min(100, Math.max(0, data.rsi_14 || 50))}%"></div>
                </div>
                <div class="rsi-labels">
                  <span>0</span><span>30</span><span>50</span><span>70</span><span>100</span>
                </div>
                <div class="rsi-reading">${formatNum(data.rsi_14)} — ${rsiZone}</div>
              </div>
            </div>
          </div>

          <div class="section">
            <div class="section-label">📈 Oscillator Details</div>
            <div class="detail-grid">
              <div class="detail-item">
                <span class="det-label">StochRSI K</span>
                <span class="det-value ${data.stochrsi_k != null ? (data.stochrsi_k > 80 ? 'val-red' : data.stochrsi_k < 20 ? 'val-green' : '') : ''}">${formatNum(data.stochrsi_k)}${data.stochrsi_k != null ? (data.stochrsi_k > 80 ? ' OB' : data.stochrsi_k < 20 ? ' OS' : '') : ''}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">StochRSI D</span>
                <span class="det-value">${formatNum(data.stochrsi_d)}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">Williams %R</span>
                <span class="det-value ${data.williams_r != null ? (data.williams_r > -20 ? 'val-red' : data.williams_r < -80 ? 'val-green' : '') : ''}">${formatNum(data.williams_r)}${data.williams_r != null ? (data.williams_r > -20 ? ' OB' : data.williams_r < -80 ? ' OS' : '') : ''}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">CCI (20)</span>
                <span class="det-value ${data.cci_20 != null ? (data.cci_20 > 100 ? 'val-red' : data.cci_20 < -100 ? 'val-green' : '') : ''}">${formatNum(data.cci_20)}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">ROC (14)</span>
                <span class="det-value ${data.roc_14 != null ? (data.roc_14 >= 0 ? 'val-green' : 'val-red') : ''}">${formatNum(data.roc_14)}%</span>
              </div>
              <div class="detail-item">
                <span class="det-label">Volatility</span>
                <span class="det-value">${data.volatility_pct != null ? data.volatility_pct + '%' : 'N/A'}</span>
              </div>
            </div>
          </div>

          <div class="section">
            <div class="section-label">📦 Volume Analysis</div>
            <div class="detail-grid">
              <div class="detail-item">
                <span class="det-label">Volume Ratio</span>
                <span class="det-value ${data.volume_ratio >= 2 ? 'val-red' : ''}">${data.volume_ratio}x avg</span>
              </div>
              <div class="detail-item">
                <span class="det-label">Avg Volume (20)</span>
                <span class="det-value">${data.avg_volume != null ? Number(data.avg_volume).toLocaleString() : 'N/A'}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">OBV Trend</span>
                <span class="det-value ${data.obv_trend === 'Rising' ? 'val-green' : data.obv_trend === 'Falling' ? 'val-red' : ''}">${data.obv_trend || 'N/A'}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">Volume Profile</span>
                <span class="det-value">${escapeHtml(data.volume_profile || 'N/A')}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- ═══ TECHNICAL TAB ═══ -->
        <div class="tab-content" data-panel="technical">
          <div class="section">
            <div class="section-label">📉 Oscillators <span class="sum-badge ${oscSumClass}">${data.oscillator_summary || '—'}</span></div>
            <div class="signal-table">${oscTableHTML || '<div class="empty-state">No oscillator data</div>'}</div>
          </div>

          <div class="section">
            <div class="section-label">📊 Moving Averages <span class="sum-badge ${maSumClass}">${data.ma_summary || '—'}</span></div>
            <div class="signal-table">${maTableHTML || '<div class="empty-state">No MA data</div>'}</div>
          </div>

          <div class="section">
            <div class="section-label">📈 Trend & Bands</div>
            <div class="detail-grid">
              <div class="detail-item">
                <span class="det-label">Trend Direction</span>
                <span class="det-value ${getTrendClass(data.trend)}">${data.trend === 'UPTREND' ? '▲' : data.trend === 'DOWNTREND' ? '▼' : '→'} ${escapeHtml(data.trend)}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">ADX Strength</span>
                <span class="det-value">${formatNum(data.adx_14)} — ${adxLabel}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">DI+</span>
                <span class="det-value val-green">${formatNum(data.di_plus)}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">DI-</span>
                <span class="det-value val-red">${formatNum(data.di_minus)}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">MACD Line</span>
                <span class="det-value">${formatNum(data.macd_line)}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">Signal Line</span>
                <span class="det-value">${formatNum(data.signal_line_val)}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">Histogram</span>
                <span class="det-value ${(data.macd_histogram || 0) >= 0 ? 'val-green' : 'val-red'}">${formatNum(data.macd_histogram)}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">ATR (14)</span>
                <span class="det-value">${formatNum(data.atr_14)}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">BB Upper</span>
                <span class="det-value pv-resistance">${formatPrice(data.bb_upper)}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">BB Middle</span>
                <span class="det-value pv-pivot">${formatPrice(data.bb_middle)}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">BB Lower</span>
                <span class="det-value pv-support">${formatPrice(data.bb_lower)}</span>
              </div>
              <div class="detail-item">
                <span class="det-label">BB %B</span>
                <span class="det-value">${formatNum(data.bb_pct_b)}</span>
              </div>
              ${
                data.ma_crossover
                  ? `<div class="detail-item detail-full">
                <span class="det-label">MA Crossover</span>
                <span class="det-value ${data.ma_crossover.includes('Bullish') || data.ma_crossover.includes('Golden') ? 'val-green' : 'val-red'}">${escapeHtml(data.ma_crossover)}</span>
              </div>`
                  : ''
              }
            </div>
          </div>
        </div>

        <!-- ═══ MULTI-TF TAB ═══ -->
        <div class="tab-content" data-panel="multitf">
          <div class="section">
            <div class="section-label">🔄 Timeframe Comparison</div>
            <div class="tf-table">${multiTfHTML}</div>
          </div>
        </div>

        <!-- ═══ LEVELS TAB ═══ -->
        <div class="tab-content" data-panel="levels">
          ${
            srHTML
              ? `<div class="section">
            <div class="section-label">🛡️ Support & Resistance</div>
            <div class="sr-table">
              <div class="sr-header-row">
                <span>Level</span><span>Price</span><span>Distance</span>
              </div>
              ${srHTML}
            </div>
          </div>`
              : ''
          }

          ${
            data.breakout_status
              ? `<div class="section">
            <div class="breakout-banner ${breakoutClass}">
              <span class="breakout-icon">🔓</span>
              <span class="breakout-text">${escapeHtml(data.breakout_status)}</span>
            </div>
          </div>`
              : ''
          }

          ${
            fibHTML
              ? `<div class="section">
            <div class="section-label">📐 Fibonacci Retracement</div>
            <div class="fib-table">${fibHTML}</div>
          </div>`
              : ''
          }

          ${
            pivotHTML
              ? `<div class="section">
            <div class="section-label">🏛️ Pivot Points (Classic)</div>
            ${pivotHTML}
          </div>`
              : ''
          }

          ${
            rangeHTML
              ? `<div class="section">
            <div class="section-label">📏 52-Week Range</div>
            ${rangeHTML}
          </div>`
              : ''
          }

          <div class="section price-levels">
            <div class="section-label">🎯 Price Targets</div>
            <div class="price-row price-target">
              <span class="price-label">Target</span>
              <span class="price-value">${formatPrice(data.suggested_target)}</span>
            </div>
            <div class="price-row price-sl">
              <span class="price-label">Stop Loss</span>
              <span class="price-value">${formatPrice(data.suggested_sl)}</span>
            </div>
            <div class="price-row">
              <span class="price-label">Risk : Reward</span>
              <span class="price-value rr-value">1 : ${data.risk_reward_ratio}</span>
            </div>
          </div>
        </div>

        <!-- ═══ MARKET TAB ═══ -->
        <div class="tab-content" data-panel="market">
          <div class="section">
            <div class="section-label">🏛️ Market Intelligence</div>
            <div class="info-card-grid">
              <div class="info-card">
                <div class="ic-header">Market Phase</div>
                <div class="ic-value">${escapeHtml(data.market_phase || 'N/A')}</div>
                <div class="ic-hint">Wyckoff-style phase detection</div>
              </div>
              <div class="info-card">
                <div class="ic-header">Market Structure</div>
                <div class="ic-value">${escapeHtml(data.market_structure || 'N/A')}</div>
                <div class="ic-hint">Swing high/low pattern analysis</div>
              </div>
              <div class="info-card">
                <div class="ic-header">Breakout Status</div>
                <div class="ic-value ${breakoutClass}">${escapeHtml(data.breakout_status || 'N/A')}</div>
                <div class="ic-hint">Price vs S/R and Bollinger Bands</div>
              </div>
              <div class="info-card">
                <div class="ic-header">RSI Divergence</div>
                <div class="ic-value">${escapeHtml(data.rsi_divergence || 'None Detected')}</div>
                <div class="ic-hint">Price vs RSI direction mismatch</div>
              </div>
            </div>
          </div>

          <div class="section">
            <div class="section-label">📋 Quick Checklist</div>
            <div class="checklist">
              <div class="check-item ${data.trend === 'UPTREND' ? 'check-pass' : data.trend === 'DOWNTREND' ? 'check-fail' : 'check-neutral'}">
                <span class="check-icon">${data.trend === 'UPTREND' ? '✅' : data.trend === 'DOWNTREND' ? '❌' : '⬜'}</span>
                <span>Trend: ${escapeHtml(data.trend)}</span>
              </div>
              <div class="check-item ${data.rsi_14 != null && data.rsi_14 > 30 && data.rsi_14 < 70 ? 'check-pass' : 'check-fail'}">
                <span class="check-icon">${data.rsi_14 != null && data.rsi_14 > 30 && data.rsi_14 < 70 ? '✅' : '⚠️'}</span>
                <span>RSI in Safe Range (30-70): ${formatNum(data.rsi_14)}</span>
              </div>
              <div class="check-item ${data.macd_signal === 'Bullish' ? 'check-pass' : data.macd_signal === 'Bearish' ? 'check-fail' : 'check-neutral'}">
                <span class="check-icon">${data.macd_signal === 'Bullish' ? '✅' : data.macd_signal === 'Bearish' ? '❌' : '⬜'}</span>
                <span>MACD: ${data.macd_signal || 'N/A'}</span>
              </div>
              <div class="check-item ${data.volume_ratio >= 1.0 ? 'check-pass' : 'check-fail'}">
                <span class="check-icon">${data.volume_ratio >= 1.0 ? '✅' : '⚠️'}</span>
                <span>Volume Confirmation: ${data.volume_ratio}x avg</span>
              </div>
              <div class="check-item ${data.obv_trend === 'Rising' ? 'check-pass' : data.obv_trend === 'Falling' ? 'check-fail' : 'check-neutral'}">
                <span class="check-icon">${data.obv_trend === 'Rising' ? '✅' : data.obv_trend === 'Falling' ? '❌' : '⬜'}</span>
                <span>OBV: ${data.obv_trend || 'N/A'}</span>
              </div>
              <div class="check-item ${data.adx_14 && data.adx_14 > 20 ? 'check-pass' : 'check-fail'}">
                <span class="check-icon">${data.adx_14 && data.adx_14 > 20 ? '✅' : '⚠️'}</span>
                <span>ADX > 20 (Trending): ${formatNum(data.adx_14)}</span>
              </div>
              <div class="check-item ${data.risk_reward_ratio >= 2 ? 'check-pass' : data.risk_reward_ratio >= 1.5 ? 'check-neutral' : 'check-fail'}">
                <span class="check-icon">${data.risk_reward_ratio >= 2 ? '✅' : data.risk_reward_ratio >= 1.5 ? '⬜' : '❌'}</span>
                <span>R:R Ratio ≥ 2: ${data.risk_reward_ratio}</span>
              </div>
            </div>
          </div>

          <div class="section">
            <div class="section-label">📖 Terminology Reference</div>
            <div class="glossary">
              <div class="gloss-item"><span class="gloss-term">Breakout</span><span class="gloss-def">Price breaks above resistance with volume</span></div>
              <div class="gloss-item"><span class="gloss-term">Breakdown</span><span class="gloss-def">Price falls below support with volume</span></div>
              <div class="gloss-item"><span class="gloss-term">Accumulation</span><span class="gloss-def">Smart money buying during a range</span></div>
              <div class="gloss-item"><span class="gloss-term">Distribution</span><span class="gloss-def">Smart money selling at the top</span></div>
              <div class="gloss-item"><span class="gloss-term">HH/HL</span><span class="gloss-def">Higher High/Higher Low — bullish structure</span></div>
              <div class="gloss-item"><span class="gloss-term">LH/LL</span><span class="gloss-def">Lower High/Lower Low — bearish structure</span></div>
              <div class="gloss-item"><span class="gloss-term">Golden Cross</span><span class="gloss-def">SMA50 crosses above SMA200 — long-term bullish</span></div>
              <div class="gloss-item"><span class="gloss-term">Death Cross</span><span class="gloss-def">SMA50 crosses below SMA200 — long-term bearish</span></div>
              <div class="gloss-item"><span class="gloss-term">Divergence</span><span class="gloss-def">Price and indicator move in opposite directions</span></div>
              <div class="gloss-item"><span class="gloss-term">Confluence</span><span class="gloss-def">Multiple indicators agree on direction</span></div>
            </div>
          </div>
        </div>
      </div>

      <div class="widget-footer">
        💹 NEPSE Pro Analyzer v3.0 — Professional Edition
      </div>
    `
  }

  // ── Utility Functions ────────────────────────────────────────────

  function escapeHtml(str) {
    if (str == null) return ''
    const div = document.createElement('div')
    div.textContent = String(str)
    return div.innerHTML
  }

  function formatNum(val) {
    if (val == null || val === undefined) return 'N/A'
    return Number(val).toFixed(2)
  }

  function formatPrice(val) {
    if (val == null) return 'N/A'
    return (
      'Rs. ' + Number(val).toLocaleString('en-IN', { maximumFractionDigits: 2 })
    )
  }

  function getVerdictClass(verdict) {
    const map = {
      'STRONG BUY': 'strong-buy',
      BUY: 'buy',
      HOLD: 'hold',
      SELL: 'sell',
      'STRONG SELL': 'strong-sell',
    }
    return map[verdict] || 'hold'
  }

  function getRsiClass(rsi) {
    if (rsi == null) return ''
    if (rsi < 30) return 'rsi-oversold'
    if (rsi > 70) return 'rsi-overbought'
    return ''
  }

  function getTrendClass(trend) {
    if (trend === 'UPTREND') return 'trend-up'
    if (trend === 'DOWNTREND') return 'trend-down'
    return 'trend-sideways'
  }

  function getMacdClass(signal) {
    if (signal === 'Bullish') return 'macd-bullish'
    if (signal === 'Bearish') return 'macd-bearish'
    return ''
  }

  function getSummaryClass(summary) {
    if (!summary) return ''
    if (summary.includes('Strong Buy')) return 'sum-strong-buy'
    if (summary.includes('Buy')) return 'sum-buy'
    if (summary.includes('Strong Sell')) return 'sum-strong-sell'
    if (summary.includes('Sell')) return 'sum-sell'
    return 'sum-neutral'
  }
})()
