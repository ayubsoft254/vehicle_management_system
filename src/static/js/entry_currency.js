/*
 * Entering an amount in a currency other than USD (Japan supplier charges and
 * payments). The ledger stays in USD; the server converts with the rate typed
 * here, expressed as "<currency> per 1 USD".
 *
 *   UsdRates.get()  -> Promise<{rates: {CODE: units per 1 USD}, asOf}>  (live, cached per session)
 *
 * Widget markup (any container with data-entry-currency):
 *   select[data-ec-select]      USD / JPY / ... / OTHER
 *   input[data-ec-other]        3-letter code, shown when OTHER is picked
 *   [data-ec-rate-wrap]         hidden while the currency is USD
 *   input[data-ec-rate]         rate per 1 USD (auto-filled from live rates until edited)
 *   [data-ec-status]            optional rate status text
 * Inside the container's scope (data-ec-scope="<selector>", else its form):
 *   [data-ec-code]              text set to the currency code
 *   [data-ec-symbol]            text set to $ / ¥ / € / £ or the code
 *   input[data-ec-pad]          left padding widened for 3-letter codes
 * Add data-ec-required to make the rate required (only while not USD).
 * Fires "entrycurrencychange" (bubbles) with detail {code, rate, user}; user is
 * false for page-load/draft-restore updates so pages don't overwrite saved values.
 */
(function () {
    'use strict';

    var RATES_URL = 'https://open.er-api.com/v6/latest/USD';
    var CACHE_KEY = 'vms_usd_rates';
    var TTL_MS = 6 * 60 * 60 * 1000;
    var SYMBOLS = { USD: '$', JPY: '¥', EUR: '€', GBP: '£' };
    var ratesPromise = null;

    function getRates(force) {
        if (ratesPromise && !force) return ratesPromise;
        if (!force) {
            try {
                var cached = JSON.parse(window.sessionStorage.getItem(CACHE_KEY) || 'null');
                if (cached && cached.rates && Date.now() - cached.at < TTL_MS) {
                    ratesPromise = Promise.resolve(cached);
                    return ratesPromise;
                }
            } catch (e) { /* fetch below */ }
        }
        ratesPromise = fetch(RATES_URL)
            .then(function (res) {
                if (!res.ok) throw new Error('Exchange rate fetch failed');
                return res.json();
            })
            .then(function (data) {
                if (!data || !data.rates) throw new Error('Invalid exchange rate response');
                var result = { at: Date.now(), rates: data.rates, asOf: data.time_last_update_utc || '' };
                try { window.sessionStorage.setItem(CACHE_KEY, JSON.stringify(result)); } catch (e) { /* ignore */ }
                return result;
            });
        ratesPromise.catch(function () { ratesPromise = null; });
        return ratesPromise;
    }

    function symbolFor(code) { return SYMBOLS[code] || code; }

    function formatRate(rate) {
        // Enough precision for small units (e.g. 0.0067 USD-quoted) without noise.
        return String(parseFloat(rate.toPrecision(8)));
    }

    function Widget(el) {
        this.el = el;
        this.select = el.querySelector('[data-ec-select]');
        this.other = el.querySelector('[data-ec-other]');
        this.rate = el.querySelector('[data-ec-rate]');
        this.rateWrap = el.querySelector('[data-ec-rate-wrap]');
        this.status = el.querySelector('[data-ec-status]');
        var scopeSel = el.getAttribute('data-ec-scope');
        this.scope = (scopeSel && document.querySelector(scopeSel)) || el.closest('form') || document;
        // A rate that came with the page (editing a saved record) counts as typed.
        this.userRate = !!(this.rate && this.rate.value);
        this.lastCode = null;

        var self = this;
        if (this.select) this.select.addEventListener('change', function () { self.userRate = false; self.apply(true); });
        if (this.other) this.other.addEventListener('input', function () {
            this.value = this.value.toUpperCase().replace(/[^A-Z]/g, '').slice(0, 3);
            self.userRate = false;
            self.apply(true);
        });
        if (this.rate) this.rate.addEventListener('input', function () {
            self.userRate = true;
            self.setStatus('');
            self.emit(true);
        });
        this.apply(false);
    }

    Widget.prototype.code = function () {
        var code = this.select ? this.select.value : 'USD';
        if (code === 'OTHER') code = this.other ? this.other.value.trim().toUpperCase() : '';
        return code || 'USD';
    };

    Widget.prototype.rateValue = function () {
        if (this.code() === 'USD') return 1;
        return parseFloat(this.rate && this.rate.value) || 0;
    };

    Widget.prototype.setStatus = function (text, isError) {
        if (!this.status) return;
        this.status.textContent = text;
        this.status.classList.toggle('text-red-500', !!isError);
    };

    Widget.prototype.emit = function (user) {
        this.el.dispatchEvent(new CustomEvent('entrycurrencychange', {
            bubbles: true,
            detail: { code: this.code(), rate: this.rateValue(), user: !!user }
        }));
    };

    Widget.prototype.setRate = function (rate, statusText, user) {
        if (!this.rate) return;
        this.rate.value = rate ? formatRate(rate) : '';
        this.userRate = false;
        this.setStatus(statusText || '');
        this.emit(user);
    };

    Widget.prototype.fillLive = function (user) {
        var self = this;
        var code = this.code();
        if (code === 'USD' || code.length !== 3 || this.userRate) return;
        this.setStatus('Fetching live rate…');
        getRates().then(function (data) {
            if (self.code() !== code || self.userRate) return;
            var rate = data.rates[code];
            if (rate) {
                self.setRate(rate, 'Live rate' + (data.asOf ? ' as of ' + data.asOf : '') + ' — edit to match your invoice.', user);
            } else {
                self.setStatus('No live rate for ' + code + ' — enter it manually.', true);
            }
        }).catch(function () {
            if (self.code() === code) self.setStatus('Live rates unavailable — enter the rate manually.', true);
        });
    };

    Widget.prototype.apply = function (user) {
        var picked = this.select ? this.select.value : 'USD';
        var code = this.code();
        var foreign = code !== 'USD';
        if (this.other) this.other.classList.toggle('hidden', picked !== 'OTHER');
        if (this.rateWrap) this.rateWrap.classList.toggle('hidden', !foreign);
        if (this.rate && this.el.hasAttribute('data-ec-required')) this.rate.required = foreign;

        this.scope.querySelectorAll('[data-ec-code]').forEach(function (n) { n.textContent = code; });
        this.scope.querySelectorAll('[data-ec-symbol]').forEach(function (n) { n.textContent = symbolFor(code); });
        var wide = symbolFor(code).length > 1;
        this.scope.querySelectorAll('input[data-ec-pad]').forEach(function (n) { n.style.paddingLeft = wide ? '3.25rem' : ''; });

        if (code !== this.lastCode && this.lastCode !== null && !this.userRate && this.rate) this.rate.value = '';
        this.lastCode = code;
        if (!foreign) this.setStatus('');
        this.emit(user);
        this.fillLive(user);
    };

    function init(root) {
        (root || document).querySelectorAll('[data-entry-currency]').forEach(function (el) {
            if (!el._entryCurrency) el._entryCurrency = new Widget(el);
        });
    }

    window.UsdRates = { get: getRates, symbol: symbolFor, formatRate: formatRate };
    window.EntryCurrency = {
        init: init,
        of: function (el) { return el && el._entryCurrency; }
    };

    document.addEventListener('DOMContentLoaded', function () { init(); });
    // The site-wide draft autosave restores field values after load.
    document.addEventListener('draft-restored', function () {
        document.querySelectorAll('[data-entry-currency]').forEach(function (el) {
            var w = el._entryCurrency;
            if (!w) return;
            w.userRate = !!(w.rate && w.rate.value);
            w.lastCode = null;
            w.apply(false);
        });
    });
})();
