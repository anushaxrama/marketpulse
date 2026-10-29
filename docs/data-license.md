# Source and derived-data terms

The default data is downloaded from Binance Vision's public historical spot archive. The source describes one-minute OHLCV bars, including executed base-asset volume. The adapter uses January 6, 2025, BTCUSDT, ETHUSDT, and SOLUSDT.

- Archive documentation: https://github.com/binance/binance-public-data
- Dataset terms: https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md
- Download service: https://data.binance.vision/

The published dataset terms were checked on October 29, 2026. They specify non-commercial use with CC BY-NC-SA 4.0 attribution/share-alike obligations and additional source terms. Commercial financial products and trading execution are outside this project's use. The source can revise or withdraw datasets; availability is not guaranteed.

Raw archives and normalized event files are downloaded locally and excluded from Git. Source URLs, byte sizes, checksums, and aggregate verification counts are retained. Screenshots and reports derived from these market observations retain Binance Vision attribution and the applicable CC BY-NC-SA 4.0 terms. The software's own license does not replace the source-data terms.

MarketPulse is independent and is not endorsed by Binance. Exchange names identify provenance. USDT is the archive's quote asset; the application does not convert it to USD or promise a stable exchange rate.

The UI font is DM Sans. Its OFL license is retained beside the font under `apps/dashboard/public/fonts/`.
