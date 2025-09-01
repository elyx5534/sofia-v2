# SOFIA-v2 Yol Haritası (Kısa / Orta / Uzun)

## Kısa (1–2 sprint)
- Strategy Showcase (BTC/USDT, ETH/USDT): SMA-Cross, RSI-Reversal, Breakout
- Backtest v0: OHLCV (Data Hub cache) üzerinden **offline** simülasyon
- Basit raporlar: CAGR, MaxDD, WinRate, Sharpe
- API uçları: /strategies, /backtest/run, /metrics
- UI: tek sayfa chart + metrik kartları
- Test kapsamı ≥ %70

## Orta (1–2 ay)
- Strategy Engine v1: parametreleme, çoklu strateji, risk limitleri
- Backtest v1: portföy, komisyon/kayma, çoklu sembol
- Data Providers: yfinance/ccxt mock; gerçek entegrasyon **yok**
- Raporlama: trade-list, equity-curve, heatmap
- CI sertleştirme, kalite kapıları

## Uzun (>2 ay)
- Strategy v2/v3: rejim tespiti, çoklu zaman-çerçeve, korelasyon, portföy optimizasyon
- Canlı mod (paper/live) için adapter taslağı (sadece mimari)
- Gelişmiş görselleştirme: etkileşimli dashboard, strateji karşılaştırma

## Veri Kaynakları (bütçe ≤ 4000 TL)
- Öncelik: **free yfinance/ccxt + cache**. Ücretliye geçiş: fiyat/performans göre (yalnızca backfill/latency ihtiyacı doğarsa)

## Kabul Kriterleri (örnek)
- /backtest/run: 200 döner, {metrics:{cagr, maxdd,…}, trades:[…]} içerir
- /strategies/list: kayıtlı strateji adlarını ve parametre şemalarını döner
- Coverage raporu ≥ %70; ana akışlar için pytest senaryoları yeşil

## Risk & Rollback
- R1: Tarih bölgesi/UTC sapması → UTC zorunlu, unit test
- R2: Veri delikleri → cache + sentinel test datası
- R3: Aşırı karmaşa → feature flag + modülerleşme
