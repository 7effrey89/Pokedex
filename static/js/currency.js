/**
 * Currency conversion utility for TCG card prices.
 * All source prices are in USD (TCGPlayer) or EUR (Cardmarket).
 * Rates are approximate — updated periodically.
 */
const CurrencyConverter = (() => {
    const STORAGE_KEY = 'pokedex_currency';
    const LOCALE_KEY = 'pokedex_number_locale';
    const BUCKETS_KEY = 'pokedex_price_buckets';

    // Rates: 1 USD → target currency (approximate, April 2026)
    const USD_RATES = {
        USD: 1.0,
        EUR: 0.92,
        GBP: 0.79,
        DKK: 6.87,
        SEK: 10.45,
        NOK: 10.65,
        CHF: 0.88,
        JPY: 151.5,
        CAD: 1.37,
        AUD: 1.53,
        PLN: 4.02,
        CZK: 23.2,
        BRL: 5.05,
        MXN: 17.1,
        KRW: 1340,
        CNY: 7.25,
        INR: 83.5,
        TRY: 32.5,
        NZD: 1.67,
        SGD: 1.34,
        HKD: 7.82,
        TWD: 31.8,
    };

    // EUR → USD rate (for converting Cardmarket EUR prices to user currency)
    const EUR_TO_USD = 1.0 / USD_RATES.EUR;

    const CURRENCY_INFO = {
        USD: { symbol: '$',  name: 'US Dollar',         flag: '🇺🇸' },
        EUR: { symbol: '€',  name: 'Euro',              flag: '🇪🇺' },
        GBP: { symbol: '£',  name: 'British Pound',     flag: '🇬🇧' },
        DKK: { symbol: 'kr', name: 'Danish Krone',      flag: '🇩🇰' },
        SEK: { symbol: 'kr', name: 'Swedish Krona',     flag: '🇸🇪' },
        NOK: { symbol: 'kr', name: 'Norwegian Krone',   flag: '🇳🇴' },
        CHF: { symbol: 'Fr', name: 'Swiss Franc',       flag: '🇨🇭' },
        JPY: { symbol: '¥',  name: 'Japanese Yen',      flag: '🇯🇵' },
        CAD: { symbol: 'C$', name: 'Canadian Dollar',   flag: '🇨🇦' },
        AUD: { symbol: 'A$', name: 'Australian Dollar', flag: '🇦🇺' },
        PLN: { symbol: 'zł', name: 'Polish Zloty',      flag: '🇵🇱' },
        CZK: { symbol: 'Kč', name: 'Czech Koruna',      flag: '🇨🇿' },
        BRL: { symbol: 'R$', name: 'Brazilian Real',    flag: '🇧🇷' },
        MXN: { symbol: 'Mex$', name: 'Mexican Peso',   flag: '🇲🇽' },
        KRW: { symbol: '₩',  name: 'South Korean Won',  flag: '🇰🇷' },
        CNY: { symbol: '¥',  name: 'Chinese Yuan',      flag: '🇨🇳' },
        INR: { symbol: '₹',  name: 'Indian Rupee',      flag: '🇮🇳' },
        TRY: { symbol: '₺',  name: 'Turkish Lira',      flag: '🇹🇷' },
        NZD: { symbol: 'NZ$', name: 'New Zealand Dollar', flag: '🇳🇿' },
        SGD: { symbol: 'S$', name: 'Singapore Dollar',  flag: '🇸🇬' },
        HKD: { symbol: 'HK$', name: 'Hong Kong Dollar', flag: '🇭🇰' },
        TWD: { symbol: 'NT$', name: 'Taiwan Dollar',    flag: '🇹🇼' },
    };

    // Number locale presets
    const LOCALE_PRESETS = {
        'en': { thousand: ',', decimal: '.', label: '1,000.00', name: 'English (1,000.00)' },
        'eu': { thousand: '.', decimal: ',', label: '1.000,00', name: 'European (1.000,00)' },
        'ch': { thousand: "'", decimal: '.', label: "1'000.00", name: "Swiss (1'000.00)" },
        'sp': { thousand: ' ', decimal: ',', label: '1 000,00', name: 'Space (1 000,00)' },
    };

    // Default price color buckets (thresholds in USD)
    const DEFAULT_BUCKETS = [
        { max: 5,      color: '#28a745', label: 'Cheap' },
        { max: 10,     color: '#ffc107', label: 'Moderate' },
        { max: 100,    color: '#fd7e14', label: 'Expensive' },
        { max: Infinity, color: '#dc3545', label: 'Premium' },
    ];

    let _current = null;
    let _locale = null;
    let _buckets = null;

    // ── Currency ──────────────────────────────────────────────────────

    function getCurrency() {
        if (_current) return _current;
        try {
            _current = localStorage.getItem(STORAGE_KEY) || 'USD';
        } catch {
            _current = 'USD';
        }
        if (!USD_RATES[_current]) _current = 'USD';
        return _current;
    }

    function setCurrency(code) {
        code = (code || 'USD').toUpperCase();
        if (!USD_RATES[code]) code = 'USD';
        _current = code;
        try {
            localStorage.setItem(STORAGE_KEY, code);
        } catch { /* ignore */ }
    }

    /** Convert a USD amount to the current currency */
    function fromUSD(amount) {
        if (typeof amount !== 'number' || isNaN(amount)) return 0;
        const cur = getCurrency();
        return amount * (USD_RATES[cur] || 1);
    }

    /** Convert a EUR amount to the current currency */
    function fromEUR(amount) {
        if (typeof amount !== 'number' || isNaN(amount)) return 0;
        const usd = amount * EUR_TO_USD;
        return fromUSD(usd);
    }

    // ── Locale / Number Formatting ───────────────────────────────────

    function getLocale() {
        if (_locale) return _locale;
        try {
            _locale = localStorage.getItem(LOCALE_KEY) || 'en';
        } catch {
            _locale = 'en';
        }
        if (!LOCALE_PRESETS[_locale]) _locale = 'en';
        return _locale;
    }

    function setLocale(loc) {
        loc = loc || 'en';
        if (!LOCALE_PRESETS[loc]) loc = 'en';
        _locale = loc;
        try {
            localStorage.setItem(LOCALE_KEY, loc);
        } catch { /* ignore */ }
    }

    function getLocalePresets() {
        return Object.entries(LOCALE_PRESETS).map(([key, v]) => ({
            key, label: v.label, name: v.name,
        }));
    }

    /** Format a number with thousand separators per the selected locale */
    function _formatNumber(value, decimals) {
        const loc = LOCALE_PRESETS[getLocale()] || LOCALE_PRESETS.en;
        const fixed = value.toFixed(decimals);
        const [intPart, decPart] = fixed.split('.');
        // Insert thousand separators
        const withSep = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, loc.thousand);
        return decPart !== undefined ? withSep + loc.decimal + decPart : withSep;
    }

    /** Format a price in the current currency with symbol + locale formatting */
    function formatUSD(amount, decimals) {
        const converted = fromUSD(amount);
        return formatValue(converted, decimals);
    }

    /** Format a EUR price in the current currency with symbol */
    function formatEUR(amount, decimals) {
        const converted = fromEUR(amount);
        return formatValue(converted, decimals);
    }

    /** Format a pre-converted value with the current currency symbol */
    function formatValue(value, decimals) {
        const cur = getCurrency();
        const info = CURRENCY_INFO[cur] || CURRENCY_INFO.USD;
        const dec = decimals !== undefined ? decimals : (cur === 'JPY' || cur === 'KRW' ? 0 : 2);
        return `${info.symbol}${_formatNumber(value, dec)}`;
    }

    // ── Price Color Buckets ──────────────────────────────────────────

    function getBuckets() {
        if (_buckets) return _buckets;
        try {
            const raw = localStorage.getItem(BUCKETS_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed) && parsed.length >= 2) {
                    // Ensure last bucket always has Infinity max
                    parsed[parsed.length - 1].max = Infinity;
                    _buckets = parsed;
                    return _buckets;
                }
            }
        } catch { /* ignore */ }
        _buckets = DEFAULT_BUCKETS.map(b => ({ ...b }));
        return _buckets;
    }

    function setBuckets(buckets) {
        if (!Array.isArray(buckets) || buckets.length < 2) return;
        // Ensure sorted by max, last is Infinity
        buckets.sort((a, b) => (a.max === Infinity ? 1e18 : a.max) - (b.max === Infinity ? 1e18 : b.max));
        buckets[buckets.length - 1].max = Infinity;
        _buckets = buckets;
        try {
            localStorage.setItem(BUCKETS_KEY, JSON.stringify(buckets));
        } catch { /* ignore */ }
    }

    function resetBuckets() {
        _buckets = DEFAULT_BUCKETS.map(b => ({ ...b }));
        try {
            localStorage.setItem(BUCKETS_KEY, JSON.stringify(_buckets));
        } catch { /* ignore */ }
        return _buckets;
    }

    /**
     * Get color for a USD price based on bucket thresholds.
     * Thresholds are defined in the display currency.
     */
    function getPriceColor(usdAmount) {
        const converted = fromUSD(usdAmount);
        const buckets = getBuckets();
        for (const bucket of buckets) {
            if (converted <= bucket.max || bucket.max === Infinity) {
                return bucket.color;
            }
        }
        return buckets[buckets.length - 1].color;
    }

    /** Get list of available currencies for building a selector UI */
    function getAvailableCurrencies() {
        return Object.entries(CURRENCY_INFO).map(([code, info]) => ({
            code,
            symbol: info.symbol,
            name: info.name,
            flag: info.flag,
        }));
    }

    function getInfo(code) {
        return CURRENCY_INFO[code || getCurrency()] || CURRENCY_INFO.USD;
    }

    return {
        getCurrency,
        setCurrency,
        fromUSD,
        fromEUR,
        formatUSD,
        formatEUR,
        formatValue,
        getAvailableCurrencies,
        getInfo,
        getLocale,
        setLocale,
        getLocalePresets,
        getBuckets,
        setBuckets,
        resetBuckets,
        getPriceColor,
    };
})();
