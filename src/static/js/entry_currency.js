/*
 * Entering an amount in any currency (Japan supplier charges and payments)
 * with a direct exchange rate: "1 JPY = [rate] [KES]", the second currency
 * being the user's choice. The supplier ledger is kept in USD; the USD leg is
 * worked out here (hidden field) and re-checked by the server.
 *
 *   UsdRates.get()  -> Promise<{rates: {CODE: units per 1 USD}, asOf}>  (live, cached per session)
 *   UsdRates.cross(rates, from, to) -> value of 1 `from` in `to` (0 if unknown)
 *
 * Widget markup (any container with data-entry-currency):
 *   select[data-ec-select]      USD / JPY / ... / OTHER  (currency the amount is entered in)
 *   input[data-ec-other]        3-letter code, shown when OTHER is picked
 *   [data-ec-rate-wrap]         hidden while the amount is in USD
 *   input[data-ec-rate]         rate: 1 <currency> = rate <rate currency>
 *   select[data-ec-quote]       the rate currency (e.g. KES)
 *   input[data-ec-quote-usd]    hidden: value of 1 rate-currency unit in USD
 *   [data-ec-status]            optional rate status text
 * Container attributes:
 *   data-ec-scope="<selector>"  where the [data-ec-code]/[data-ec-symbol]/[data-ec-quote-code] labels live (default: its form)
 *   data-ec-home="KES" data-ec-home-rate="<input selector>"  an on-page "1 USD = x KES" rate to use for the home currency
 *   data-ec-required            the rate is required while it is needed
 * Fires "entrycurrencychange" (bubbles) with detail {code, quote, rate, usdPerUnit, user};
 * user is false for page-load/draft-restore updates so pages don't overwrite saved values.
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

    // Value of 1 `from` in `to`, from USD-based live rates.
    function crossRate(rates, from, to) {
        if (from === to) return 1;
        var f = from === 'USD' ? 1 : rates[from];
        var t = to === 'USD' ? 1 : rates[to];
        return f && t ? t / f : 0;
    }

    function symbolFor(code) { return SYMBOLS[code] || code; }

    function formatRate(rate) {
        // Enough precision for small units (1 JPY = 0.0062687 USD) without float noise.
        return String(parseFloat(rate.toPrecision(8)));
    }

    function Widget(el) {
        this.el = el;
        this.select = el.querySelector('[data-ec-select]');
        this.other = el.querySelector('[data-ec-other]');
        this.rate = el.querySelector('[data-ec-rate]');
        this.quoteSel = el.querySelector('[data-ec-quote]');
        this.quoteUsd = el.querySelector('[data-ec-quote-usd]');
        this.rateWrap = el.querySelector('[data-ec-rate-wrap]');
        this.status = el.querySelector('[data-ec-status]');
        this.home = el.getAttribute('data-ec-home') || '';
        var homeRateSel = el.getAttribute('data-ec-home-rate');
        this.homeRate = homeRateSel ? document.querySelector(homeRateSel) : null;
        var scopeSel = el.getAttribute('data-ec-scope');
        this.scope = (scopeSel && document.querySelector(scopeSel)) || el.closest('form') || document;
        // A rate that came with the page (editing a saved record) counts as typed.
        this.userRate = !!(this.rate && this.rate.value);
        this.live = null;
        this.lastPair = null;

        var self = this;
        function changed() { self.userRate = false; self.apply(true); }
        if (this.select) this.select.addEventListener('change', changed);
        if (this.quoteSel) this.quoteSel.addEventListener('change', changed);
        if (this.other) this.other.addEventListener('input', function () {
            this.value = this.value.toUpperCase().replace(/[^A-Z]/g, '').slice(0, 3);
            changed();
        });
        if (this.rate) this.rate.addEventListener('input', function () {
            self.userRate = true;
            self.setStatus('');
            self.emit(true);
        });
        if (this.homeRate) this.homeRate.addEventListener('input', function () { self.emit(true); });
        this.apply(false);
        // Live rates also give the hidden USD leg for non-home rate currencies.
        getRates().then(function (data) { self.live = data; self.emit(false); }).catch(function () {});
    }

    Widget.prototype.code = function () {
        var code = this.select ? this.select.value : 'USD';
        if (code === 'OTHER') code = this.other ? this.other.value.trim().toUpperCase() : '';
        return code || 'USD';
    };

    Widget.prototype.quote = function () {
        return (this.quoteSel && this.quoteSel.value) || this.home || 'USD';
    };

    // 1 <code> = rateValue() <quote>
    Widget.prototype.rateValue = function () {
        if (this.code() === this.quote()) return 1;
        return parseFloat(this.rate && this.rate.value) || 0;
    };

    // Value of 1 <quote> in USD (0 if not known yet).
    Widget.prototype.usdPerQuote = function () {
        var quote = this.quote();
        if (quote === 'USD') return 1;
        var home = this.homeRate ? parseFloat(this.homeRate.value) : 0;
        if (quote === this.home && home > 0) return 1 / home;
        return this.live ? crossRate(this.live.rates, quote, 'USD') : 0;
    };

    // Value of 1 <code> in USD (0 if not known yet).
    Widget.prototype.usdPerUnit = function () {
        if (this.code() === 'USD') return 1;
        return this.rateValue() * this.usdPerQuote();
    };

    Widget.prototype.setStatus = function (text, isError) {
        if (!this.status) return;
        this.status.textContent = text;
        this.status.classList.toggle('text-red-500', !!isError);
    };

    Widget.prototype.emit = function (user) {
        if (this.quoteUsd) {
            var q = this.usdPerQuote();
            this.quoteUsd.value = q ? String(q) : '';
        }
        this.el.dispatchEvent(new CustomEvent('entrycurrencychange', {
            bubbles: true,
            detail: {
                code: this.code(), quote: this.quote(), rate: this.rateValue(),
                usdPerUnit: this.usdPerUnit(), user: !!user
            }
        }));
    };

    Widget.prototype.setRate = function (rate, statusText, user) {
        if (!this.rate) return;
        this.rate.value = rate ? formatRate(rate) : '';
        this.userRate = false;
        this.setStatus(statusText || '');
        this.emit(user);
    };

    Widget.prototype.fillLive = function (user, force) {
        var self = this;
        var code = this.code();
        var quote = this.quote();
        if (code === 'USD' || code === quote || code.length !== 3 || (this.userRate && !force)) return;
        this.setStatus('Fetching live rate…');
        getRates(force).then(function (data) {
            self.live = data;
            if (self.code() !== code || self.quote() !== quote || (self.userRate && !force)) return;
            var rate = crossRate(data.rates, code, quote);
            if (rate) {
                self.setRate(rate, 'Live rate' + (data.asOf ? ' as of ' + data.asOf : '') + ' — edit to match your invoice.', user);
            } else {
                self.setStatus('No live rate for ' + code + ' to ' + quote + ' — enter it manually.', true);
                self.emit(user);
            }
        }).catch(function () {
            if (self.code() === code) self.setStatus('Live rates unavailable — enter the rate manually.', true);
        });
    };

    Widget.prototype.apply = function (user) {
        var picked = this.select ? this.select.value : 'USD';
        var code = this.code();
        var quote = this.quote();
        var foreign = code !== 'USD';
        var same = code === quote;
        if (this.other) this.other.classList.toggle('hidden', picked !== 'OTHER');
        if (this.rateWrap) this.rateWrap.classList.toggle('hidden', !foreign);
        if (this.rate) {
            this.rate.readOnly = same;
            this.rate.classList.toggle('bg-gray-50', same);
            if (this.el.hasAttribute('data-ec-required')) this.rate.required = foreign && !same;
        }

        this.scope.querySelectorAll('[data-ec-code]').forEach(function (n) { n.textContent = code; });
        this.scope.querySelectorAll('[data-ec-quote-code]').forEach(function (n) { n.textContent = quote; });
        this.scope.querySelectorAll('[data-ec-symbol]').forEach(function (n) { n.textContent = symbolFor(code); });
        var wide = symbolFor(code).length > 1;
        this.scope.querySelectorAll('input[data-ec-pad]').forEach(function (n) { n.style.paddingLeft = wide ? '3.25rem' : ''; });

        var pair = code + '>' + quote;
        if (this.rate) {
            if (same) {
                this.rate.value = '1';
            } else if (this.lastPair !== null && pair !== this.lastPair && !this.userRate) {
                this.rate.value = '';
            }
        }
        this.lastPair = pair;
        if (!foreign || same) this.setStatus('');
        this.emit(user);
        this.fillLive(user, false);
    };

    function init(root) {
        (root || document).querySelectorAll('[data-entry-currency]').forEach(function (el) {
            if (!el._entryCurrency) el._entryCurrency = new Widget(el);
        });
    }

    window.UsdRates = { get: getRates, cross: crossRate, symbol: symbolFor, formatRate: formatRate };
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
            w.lastPair = null;
            w.apply(false);
        });
    });
})();
