/*
 * Multi-currency display.
 *
 * Upgrades <select data-multi-currency="<amount selector>"> into a checkbox
 * dropdown so several currencies can be shown at the same time. Every element
 * matched by the amount selector carries data-kes (its KES amount) and is
 * rendered in the first ticked currency, with the other ticked currencies
 * listed alongside it in smaller text.
 *
 * <select> options (data attributes):
 *   data-currency-decimals     fraction digits (default 2)
 *   data-currency-storage      localStorage key that remembers the ticked currencies
 *   data-currency-rate-inputs  selector for manual "1 X = n KES" inputs, each with
 *                              data-cur-rate="X"; without it, live rates are fetched
 *                              from open.er-api.com
 * Amount element options:
 *   data-prefix                text shown before the primary amount ("Negotiable")
 *   data-currency-layout       "stack" or "inline"; auto-detected when omitted
 *
 * After every render the select fires a bubbling "currencychange" event with
 * detail {currencies, primary, rate(code)}; rate is foreign units per 1 KES.
 * Call MultiCurrency.refresh() after a page changes data-kes values.
 */
(function () {
    'use strict';

    var RATES_URL = 'https://open.er-api.com/v6/latest/KES';
    var RATES_CACHE_KEY = 'vms_live_rates';
    var RATES_TTL_MS = 60 * 60 * 1000;
    var MANUAL_RATE_PREFIX = 'vms_rate_';
    var NAMES = {
        KES: 'Kenyan Shilling', USD: 'US Dollar', EUR: 'Euro',
        TZS: 'Tanzanian Shilling', UGX: 'Ugandan Shilling', JPY: 'Japanese Yen',
    };

    var pickers = [];
    var liveRatesPromise = null;

    // Storage can be blocked (private mode, previews) — never let that break the page.
    function storageGet(kind, key) {
        try { return window[kind].getItem(key); } catch (e) { return null; }
    }
    function storageSet(kind, key, value) {
        try { window[kind].setItem(key, value); } catch (e) { /* ignore */ }
    }

    function loadLiveRates() {
        if (liveRatesPromise) return liveRatesPromise;
        try {
            var cached = JSON.parse(storageGet('sessionStorage', RATES_CACHE_KEY) || 'null');
            if (cached && cached.rates && Date.now() - cached.at < RATES_TTL_MS) {
                liveRatesPromise = Promise.resolve(cached.rates);
                return liveRatesPromise;
            }
        } catch (e) { /* fall through to fetch */ }

        liveRatesPromise = fetch(RATES_URL)
            .then(function (res) {
                if (!res.ok) throw new Error('Exchange rate fetch failed');
                return res.json();
            })
            .then(function (data) {
                if (!data || !data.rates) throw new Error('Invalid exchange rate response');
                storageSet('sessionStorage', RATES_CACHE_KEY, JSON.stringify({ at: Date.now(), rates: data.rates }));
                return data.rates;
            })
            .catch(function (err) {
                liveRatesPromise = null; // allow a retry on the next change
                throw err;
            });
        return liveRatesPromise;
    }

    function formatAmount(amount, code, decimals) {
        return code + ' ' + amount.toLocaleString('en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        });
    }

    // Inline when the amount sits inside running text ("Amount: KES 500 due"),
    // stacked when it stands on its own (KPI cards, table cells, flex rows).
    function detectLayout(node) {
        if (window.getComputedStyle(node).display !== 'inline') return 'stack';
        var parent = node.parentElement;
        if (!parent) return 'stack';
        var parentDisplay = window.getComputedStyle(parent).display;
        if (/flex|grid/.test(parentDisplay)) return 'stack';
        var hasText = Array.prototype.some.call(parent.childNodes, function (child) {
            return child !== node && child.nodeType === 3 && child.textContent.trim();
        });
        return hasText ? 'inline' : 'stack';
    }

    function injectStyles() {
        if (document.getElementById('mc-styles')) return;
        var style = document.createElement('style');
        style.id = 'mc-styles';
        style.textContent = [
            '.mc-picker{position:relative;display:inline-block}',
            ':where(.mc-button){font:inherit;color:inherit;background:transparent;border:0;padding:0}',
            '.mc-button{display:inline-flex;align-items:center;gap:.4em;cursor:pointer;white-space:nowrap}',
            '.mc-button svg{width:.75em;height:.75em;opacity:.6}',
            '.mc-panel{position:absolute;top:calc(100% + 6px);right:0;z-index:60;min-width:14rem;padding:.375rem;',
            'background:#fff;border:1px solid #e5e7eb;border-radius:.5rem;box-shadow:0 10px 25px rgba(0,0,0,.12);',
            'text-align:left;font-size:.875rem;font-weight:400;color:#374151}',
            '.mc-panel[hidden]{display:none}',
            '.mc-panel.mc-panel--left{right:auto;left:0}',
            '.mc-option{display:flex;align-items:center;gap:.6rem;padding:.4rem .5rem;border-radius:.375rem;cursor:pointer}',
            '.mc-option:hover{background:#f3f4f6}',
            '.mc-option input{width:1rem;height:1rem;margin:0;accent-color:#2563eb;cursor:pointer}',
            '.mc-code{font-weight:600;color:#111827;min-width:2.5rem}',
            '.mc-name{color:#6b7280}',
            '.mc-hint{padding:.4rem .5rem .2rem;margin-top:.25rem;border-top:1px solid #f3f4f6;font-size:.75rem;color:#9ca3af}',
            '.mc-hint.mc-hint--error{color:#dc2626}',
            '.mc-extra{opacity:.75;font-weight:500;white-space:nowrap}',
            '.mc-extra--stack{display:block;font-size:.7em;line-height:1.35}',
            '.mc-extra--inline{font-size:.85em;margin-left:.35em}',
            '.mc-extra--inline::before{content:"/ "}',
        ].join('');
        document.head.appendChild(style);
    }

    function Picker(select) {
        this.select = select;
        this.amountSelector = select.dataset.multiCurrency;
        this.decimals = parseInt(select.dataset.currencyDecimals || '2', 10);
        this.storageKey = select.dataset.currencyStorage || '';
        this.rateInputs = select.dataset.currencyRateInputs
            ? Array.prototype.slice.call(document.querySelectorAll(select.dataset.currencyRateInputs))
            : null;
        this.codes = Array.prototype.map.call(select.options, function (o) { return o.value; });
        this.liveRates = null;
        this.hintText = 'The first ticked currency is shown largest.';
        this.selected = this.restore();
        this.build();
        this.bindRateInputs();
        this.update();
    }

    Picker.prototype.restore = function () {
        var codes = this.codes;
        var saved = this.storageKey ? storageGet('localStorage', this.storageKey) : null;
        var list = [];
        if (saved) {
            try {
                list = JSON.parse(saved);
            } catch (e) {
                list = [saved]; // value saved by the old single-currency switcher
            }
            if (!Array.isArray(list)) list = [String(list)];
        }
        list = codes.filter(function (code) { return list.indexOf(code) !== -1; });
        return list.length ? list : [this.select.value || codes[0]];
    };

    Picker.prototype.build = function () {
        var self = this;
        var select = this.select;
        var id = (select.id || 'currency') + '-mc';

        this.wrapper = document.createElement('span');
        this.wrapper.className = 'mc-picker';

        this.button = document.createElement('button');
        this.button.type = 'button';
        this.button.id = id;
        this.button.className = 'mc-button ' + select.className;
        this.button.setAttribute('aria-haspopup', 'true');
        this.button.setAttribute('aria-expanded', 'false');
        this.button.setAttribute('aria-controls', id + '-panel');
        this.buttonLabel = document.createElement('span');
        this.button.appendChild(this.buttonLabel);
        this.button.insertAdjacentHTML('beforeend',
            '<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.17l3.71-3.94a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd"/></svg>');

        this.panel = document.createElement('div');
        this.panel.className = 'mc-panel';
        this.panel.id = id + '-panel';
        this.panel.hidden = true;
        this.panel.setAttribute('role', 'group');
        this.panel.setAttribute('aria-label', 'Currencies to display');

        this.checkboxes = {};
        Array.prototype.forEach.call(select.options, function (option) {
            var code = option.value;
            var label = document.createElement('label');
            label.className = 'mc-option';
            var box = document.createElement('input');
            box.type = 'checkbox';
            box.value = code;
            box.checked = self.selected.indexOf(code) !== -1;
            box.addEventListener('change', function () { self.onToggle(box); });
            var codeEl = document.createElement('span');
            codeEl.className = 'mc-code';
            codeEl.textContent = code;
            var nameEl = document.createElement('span');
            nameEl.className = 'mc-name';
            nameEl.textContent = NAMES[code] || option.textContent.replace(code, '').replace(/^\s*[—-]\s*/, '');
            label.appendChild(box);
            label.appendChild(codeEl);
            label.appendChild(nameEl);
            self.panel.appendChild(label);
            self.checkboxes[code] = box;
        });

        this.hint = document.createElement('p');
        this.hint.className = 'mc-hint';
        this.hint.textContent = this.hintText;
        this.panel.appendChild(this.hint);

        this.wrapper.appendChild(this.button);
        this.wrapper.appendChild(this.panel);
        select.parentNode.insertBefore(this.wrapper, select.nextSibling);
        select.hidden = true;
        select.style.display = 'none'; // a utility class could otherwise override [hidden]

        if (select.id) {
            document.querySelectorAll('label[for="' + select.id + '"]').forEach(function (l) { l.htmlFor = id; });
        }

        this.button.addEventListener('click', function () { self.toggle(self.panel.hidden); });
        document.addEventListener('click', function (e) {
            if (!self.panel.hidden && !self.wrapper.contains(e.target)) self.toggle(false);
        });
        this.wrapper.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !self.panel.hidden) {
                self.toggle(false);
                self.button.focus();
            }
        });
    };

    Picker.prototype.toggle = function (open) {
        this.panel.hidden = !open;
        this.button.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (open) {
            // Open towards whichever side has room so the panel never leaves the screen.
            this.panel.classList.remove('mc-panel--left');
            if (this.panel.getBoundingClientRect().left < 8) this.panel.classList.add('mc-panel--left');
        }
    };

    Picker.prototype.onToggle = function (box) {
        var self = this;
        var ticked = this.codes.filter(function (code) { return self.checkboxes[code].checked; });
        if (!ticked.length) {
            box.checked = true; // at least one currency must stay visible
            this.setHint('Keep at least one currency ticked.', true);
            return;
        }
        this.selected = ticked;
        if (this.storageKey) storageSet('localStorage', this.storageKey, JSON.stringify(ticked));
        this.setHint(this.hintText, false);
        this.update();
    };

    Picker.prototype.setHint = function (text, isError) {
        this.hint.textContent = text;
        this.hint.classList.toggle('mc-hint--error', !!isError);
    };

    Picker.prototype.bindRateInputs = function () {
        var self = this;
        if (!this.rateInputs) return;
        this.rateInputs.forEach(function (input) {
            var stored = storageGet('localStorage', MANUAL_RATE_PREFIX + input.dataset.curRate);
            if (stored) input.value = stored;
            input.addEventListener('change', function () {
                storageSet('localStorage', MANUAL_RATE_PREFIX + input.dataset.curRate, input.value);
                self.render();
            });
        });
    };

    // Foreign units per 1 KES, or null while unknown.
    Picker.prototype.rate = function (code) {
        if (code === 'KES') return 1;
        if (this.rateInputs) {
            var input = this.rateInputs.filter(function (i) { return i.dataset.curRate === code; })[0];
            var kesPerUnit = input ? (parseFloat(input.value) || parseFloat(input.defaultValue)) : null;
            return kesPerUnit ? 1 / kesPerUnit : null;
        }
        return this.liveRates && this.liveRates[code] ? this.liveRates[code] : null;
    };

    Picker.prototype.update = function () {
        var self = this;
        var needsLive = !this.rateInputs && !this.liveRates &&
            this.selected.some(function (code) { return code !== 'KES'; });
        if (!needsLive) {
            this.render();
            return;
        }
        this.render(); // show what we can (KES) while rates load
        loadLiveRates().then(function (rates) {
            self.liveRates = rates;
            self.render();
        }).catch(function () {
            self.setHint('Live exchange rates are unavailable right now — showing KES only.', true);
            self.render();
        });
    };

    Picker.prototype.shownCurrencies = function () {
        var self = this;
        var shown = this.selected.filter(function (code) { return self.rate(code) !== null; });
        return shown.length ? shown : ['KES'];
    };

    Picker.prototype.render = function () {
        var self = this;
        var shown = this.shownCurrencies();
        var primary = shown[0];
        var decimals = this.decimals;

        document.querySelectorAll(this.amountSelector).forEach(function (node) {
            var kes = parseFloat(String(node.dataset.kes || '0').replace(/,/g, '')) || 0;
            var prefix = (node.dataset.prefix || '').trim();
            if (!node.dataset.currencyLayout) node.dataset.currencyLayout = detectLayout(node);
            node.textContent = (prefix ? prefix + ' ' : '') + formatAmount(kes * self.rate(primary), primary, decimals);
            shown.slice(1).forEach(function (code) {
                var extra = document.createElement('span');
                extra.className = 'mc-extra mc-extra--' + node.dataset.currencyLayout;
                extra.textContent = formatAmount(kes * self.rate(code), code, decimals);
                node.appendChild(extra);
            });
        });

        this.buttonLabel.textContent = this.selected.length > 3
            ? this.selected.slice(0, 2).join(', ') + ' +' + (this.selected.length - 2)
            : this.selected.join(', ');
        this.select.value = primary;
        this.select.dispatchEvent(new CustomEvent('currencychange', {
            bubbles: true,
            detail: {
                currencies: shown.slice(),
                primary: primary,
                rate: function (code) { return self.rate(code); },
            },
        }));
    };

    function init() {
        injectStyles();
        document.querySelectorAll('select[data-multi-currency]').forEach(function (select) {
            if (!select._multiCurrency) {
                select._multiCurrency = new Picker(select);
                pickers.push(select._multiCurrency);
            }
        });
    }

    window.MultiCurrency = {
        init: init,
        refresh: function () { pickers.forEach(function (p) { p.render(); }); },
    };

    // This script is included at the end of <body>, so the pickers are already
    // parsed: start now rather than waiting for DOMContentLoaded, which a slow CDN
    // script elsewhere on the page can hold back. The second call is a no-op for
    // pickers already built and catches any that appear later in the document.
    init();
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    }
})();
