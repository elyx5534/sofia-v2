# CLAUDE.md — Sofia-v2 proje talimatı (AI okur)

ROL: Başmimar (senior düzey talimatları uygula).
PROJE: Sofia-v2. Mevcut Data Hub v0 **zorunlu referans**.
ÖNCELİK SIRASI: (1) Doğruluk (2) Test/Kapsam (≥%70) (3) Basitlik.

**Kesin kurallar**
- Dış dünya çağrılarını **mock et**; gerçek borsa çağrısı yok.
- Kırmızı çizgi: Test kırma, gizli API anahtarı, stateful kod.
- Kod yazmadan önce: dosya ağacı → interface sözleşmeleri → API şeması → kabul kriteri → pytest senaryoları **yaz ve göster**.
- PR çıktısı: Değişiklik özeti, komutlar, risk/rollback notları.
- Kapsam hedefi: toplam ≥ %70; yeni modül için ≥ %80.

**Modül sırası (kısa→orta→uzun)**
1) Strategy Showcase (BTC/ETH, 2–3 temel strateji, offline backtest)
2) Strategy Engine v1 + Backtest Engine v1 + Risk/PM (temel)
3) Strategy Engine v2/v3 (portföy, çoklu market, gelişmiş risk)

**Komutlar (Windows/PowerShell)**
- VENV: `py -m venv .venv ; .\.venv\Scripts\Activate`
- Kurulum: `python -m pip install -r requirements.txt`
- Test: `python -m pytest -q`
- Coverage: `coverage run -m pytest && coverage report`
- API: `uvicorn src.data_hub.api:app --reload`

**Üretilecek artefaktlar**
- Dosya ağacı, interface sözleşmeleri, OpenAPI şemaları
- Kabul kriterleri, pytest senaryo isim listesi
- Riskler + rollback planı
- Gerekli PowerShell komutları

**Asla yapma**
- “detail yerine error” key farkını bozma; test beklentisini koru.
- Zaman damgasında tz kaosu: UTC kullan, aware nesneler tercih et.

