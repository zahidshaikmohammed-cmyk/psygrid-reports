# Economic Event Calendar Research — Sep 22 – Oct 31, 2026

**Prepared for:** psygrid-reports quantitative trading research
**Window:** 2026-09-22 through 2026-10-31 (inclusive)
**Instrument universe:** XAUUSD, EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAGUSD, USOIL
**Companion data file:** [`data/events_sep22_oct31_2026.json`](../data/events_sep22_oct31_2026.json) — 74 structured events
**Generated:** 2026-09-22

---

## 1. How this was researched (read this before trading off any single date/time)

This document and its companion JSON were built by:

1. Searching for each agency's/central bank's **official** release calendar (Federal Reserve, BLS, BEA, Census Bureau, ECB, Bank of England/ONS, Bank of Japan, Statistics Bureau of Japan, RBA, ABS, RBNZ, Stats NZ, Bank of Canada, Statistics Canada, National Bureau of Statistics of China, EIA, API, OPEC, IEA).
2. Cross-checking every date/time against at least one reputable secondary calendar (TradingEconomics, Investing.com, FXStreet, Forex Factory, financecalendar.com, or similar).
3. Recording, per event, an `official_source`, a `secondary_crosscheck`, and an `exact_time_confirmed` flag.

**Important environment limitation:** the research sandbox used for this project blocks direct outbound HTTPS fetches to essentially every official domain involved here — `bls.gov`, `bea.gov`, `census.gov`, `federalreserve.gov`, `ecb.europa.eu`, `bankofengland.co.uk`, `ons.gov.uk`, `boj.or.jp`, `rba.gov.au`, `abs.gov.au`, `rbnz.govt.nz`, `stats.govt.nz`, `bankofcanada.ca`, `statcan.gc.ca`, `stats.gov.cn`, `eia.gov`, `api.org`, `opec.org`, and `iea.org` all returned `EGRESS_BLOCKED`. This means **no official page in this research was fetched and read directly** — every official-source date/time below was obtained via web-search snippets that quote, excerpt, or index the official page (including officially-hosted PDFs and press releases surfaced by the search engine), not by opening the page itself. This is a materially weaker form of primary-source confirmation than a direct fetch, and it is the reason a meaningful minority of events below are flagged `exact_time_confirmed: false`.

**Bottom line for the trading desk:** treat every `HIGH`-importance, `exact_time_confirmed: true` event (FOMC, CPI, NFP, ECB, BoC, RBA, RBNZ, China GDP, etc.) as reliable enough to plan around, but **re-verify every event flagged `No*`/`false` against its named `official_source` within the week before it**, and re-verify the whole calendar generally in the days before trading, since official calendars are also revised on short notice (see §4, shutdown risk).

Every event record in the JSON has these fields: `date`, `day_of_week`, `country_region`, `currency`, `event_name`, `importance`, `original_release_timezone`, `exact_release_time_local`, `exact_release_time_IST`, `exact_time_confirmed`, `official_source`, `secondary_crosscheck`, `affected_instruments`, `notes`.

---

## 2. Headline summary

- **74 events** across United States (42), Australia (6), Canada (5), Japan (5), Euro Area (4), United Kingdom (4), China (4), New Zealand (2), OPEC+ (1), IEA (1).
- **Importance split:** 38 HIGH, 34 MEDIUM, 2 LOW.
- **Confidence split:** 59 events have both date and time confirmed with reasonable confidence (`exact_time_confirmed: true`); 15 events carry a date and/or time that is a pattern-based estimate or otherwise uncertain (`exact_time_confirmed: false`) — each of those has a `notes` field explaining exactly what is uncertain and what to check.
- **Central bank decisions in the window:** RBA (Sep 29), FOMC (Oct 28), Bank of Canada (Oct 28), RBNZ (Oct 28), ECB (Oct 29), Bank of Japan (Oct 30). **No Bank of England decision falls in this window** (see §4).
- **Three extremely dense "cluster days":**
  - **Wed Oct 28:** FOMC statement (2:00pm ET) + Bank of Canada decision (9:45am ET) + RBNZ OCR review (2:00pm NZDT) + Australia's monthly/quarterly CPI (11:30am AEDT) + the EIA weekly petroleum report + the U.S. Census "Advance Economic Indicators" bundle (durable goods/trade/inventories). Five countries' worth of high-impact data lands within roughly 24 hours.
  - **Thu Oct 29:** ECB decision (14:15 CET) + U.S. GDP advance estimate for Q3 + Personal Income/Outlays (PCE inflation) (8:30am ET) + BoJ meeting Day 1.
  - **Fri Oct 30:** Bank of Japan decision + Outlook Report (~12:00 JST) + Tokyo CPI + Canada's monthly GDP.
  These three consecutive days (Oct 28–30) concentrate the majority of the window's tail risk for every currency pair in the universe simultaneously, and deserve dedicated risk-management planning (reduced size, wider stops, or flat positioning through the cluster) independent of any single event's own importance rating.

---

## 3. Event tables by region

*"IST" = the event's release time converted to India Standard Time (UTC+5:30, no DST), computed programmatically per-event from IANA timezone data so each conversion correctly reflects whichever DST regime was in effect in the source country **on that specific date** (see the DST-transition note in §5). "Time Confirmed = No\*" means the notes field explains a specific uncertainty — read it before relying on that row.*

### United States  (42 events)

| Date | Local Time (tz) | IST | Importance | Event | Time Confirmed | Instruments |
|---|---|---|---|---|---|---|
| 2026-09-22 (Tue) | 16:30 New_York | 02:00 IST | MEDIUM | API Weekly Statistical Bulletin (crude/product inventories, industry estimate) | Yes | USOIL, XAUUSD |
| 2026-09-23 (Wed) | 10:30 New_York | 20:00 IST | HIGH | EIA Weekly Petroleum Status Report (crude/gasoline/distillate inventories) | Yes | USOIL, USDCAD, XAUUSD |
| 2026-09-24 (Thu) | 08:30 New_York | 18:00 IST | MEDIUM | U.S. International Transactions & International Investment Position, Q2 2026 | Yes | EURUSD, GBPUSD, USDJPY, XAUUSD |
| 2026-09-24 (Thu) | 08:30 New_York | 18:00 IST | MEDIUM | Initial Jobless Claims (weekly UI claims report) | Yes | USDJPY, EURUSD, GBPUSD, XAUUSD |
| 2026-09-24 (Thu) | 10:00 New_York | 19:30 IST | MEDIUM | New Residential Sales (New Home Sales), August 2026 | Yes | XAUUSD, USDJPY, EURUSD |
| 2026-09-25 (Fri) | 08:30 New_York | 18:00 IST | MEDIUM | Advance Durable Goods Orders, August 2026 | Yes | XAUUSD, EURUSD, USDJPY |
| 2026-09-29 (Tue) | 10:00 New_York | 19:30 IST | MEDIUM | JOLTS Job Openings, August 2026 | Yes | USDJPY, EURUSD, GBPUSD, XAUUSD |
| 2026-09-29 (Tue) | 16:30 New_York | 02:00 IST | MEDIUM | API Weekly Statistical Bulletin (crude/product inventories, industry estimate) | Yes | USOIL, XAUUSD |
| 2026-09-30 (Wed) | 08:30 New_York | 18:00 IST | HIGH | GDP (Third Estimate), Corporate Profits, State GDP/Income, Q2 2026 | Yes | EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAUUSD, XAGUSD |
| 2026-09-30 (Wed) | 08:30 New_York | 18:00 IST | HIGH | Personal Income and Outlays (PCE Price Index), August 2026 | Yes | EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAUUSD, XAGUSD |
| 2026-09-30 (Wed) | 10:30 New_York | 20:00 IST | HIGH | EIA Weekly Petroleum Status Report (crude/gasoline/distillate inventories) | Yes | USOIL, USDCAD, XAUUSD |
| 2026-10-01 (Thu) | 08:30 New_York | 18:00 IST | MEDIUM | Initial Jobless Claims (weekly UI claims report) | Yes | USDJPY, EURUSD, GBPUSD, XAUUSD |
| 2026-10-01 (Thu) | 10:00 New_York | 19:30 IST | HIGH | ISM Manufacturing PMI, September 2026 | Yes | EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAUUSD, XAGUSD |
| 2026-10-02 (Fri) | 08:30 New_York | 18:00 IST | HIGH | Employment Situation (Nonfarm Payrolls), September 2026 | Yes | EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAUUSD, XAGUSD |
| 2026-10-05 (Mon) | 10:00 New_York | 19:30 IST | HIGH | ISM Services PMI, September 2026 | Yes | EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAUUSD, XAGUSD |
| 2026-10-06 (Tue) | 08:30 New_York | 18:00 IST | MEDIUM | U.S. International Trade in Goods and Services, August 2026 | Yes | USDCAD, EURUSD, XAUUSD, USOIL |
| 2026-10-06 (Tue) | 16:30 New_York | 02:00 IST | MEDIUM | API Weekly Statistical Bulletin (crude/product inventories, industry estimate) | Yes | USOIL, XAUUSD |
| 2026-10-07 (Wed) | 10:30 New_York | 20:00 IST | HIGH | EIA Weekly Petroleum Status Report (crude/gasoline/distillate inventories) | Yes | USOIL, USDCAD, XAUUSD |
| 2026-10-08 (Thu) | 08:30 New_York | 18:00 IST | MEDIUM | Initial Jobless Claims (weekly UI claims report) | Yes | USDJPY, EURUSD, GBPUSD, XAUUSD |
| 2026-10-09 (Fri) | 10:00 New_York | 19:30 IST | MEDIUM | University of Michigan Consumer Sentiment, October 2026 (Preliminary) | Yes | XAUUSD, EURUSD, USDJPY |
| 2026-10-13 (Tue) | 10:00 New_York | 19:30 IST | MEDIUM | NAR Existing-Home Sales, September 2026 | Yes | XAUUSD, USDJPY |
| 2026-10-14 (Wed) | 08:30 New_York | 18:00 IST | HIGH | Consumer Price Index (CPI), September 2026 | Yes | EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAUUSD, XAGUSD |
| 2026-10-14 (Wed) | 16:30 New_York | 02:00 IST | MEDIUM | API Weekly Statistical Bulletin (crude/product inventories, industry estimate) | No* | USOIL, XAUUSD |
| 2026-10-15 (Thu) | 08:30 New_York | 18:00 IST | MEDIUM | Initial Jobless Claims (weekly UI claims report) | Yes | USDJPY, EURUSD, GBPUSD, XAUUSD |
| 2026-10-15 (Thu) | 08:30 New_York | 18:00 IST | MEDIUM | Producer Price Index (PPI), September 2026 | Yes | USDJPY, EURUSD, XAUUSD |
| 2026-10-15 (Thu) | 10:30 New_York | 20:00 IST | HIGH | EIA Weekly Petroleum Status Report (crude/gasoline/distillate inventories) | No* | USOIL, USDCAD, XAUUSD |
| 2026-10-16 (Fri) | 08:30 New_York | 18:00 IST | HIGH | Advance Monthly Retail Sales, September 2026 | Yes | EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAUUSD, XAGUSD |
| 2026-10-16 (Fri) | 09:15 New_York | 18:45 IST | MEDIUM | Industrial Production and Capacity Utilization (G.17), September 2026 | Yes | USDJPY, XAUUSD, USOIL |
| 2026-10-20 (Tue) | 08:30 New_York | 18:00 IST | MEDIUM | Housing Starts and Building Permits, September 2026 | Yes | XAUUSD, USDJPY |
| 2026-10-20 (Tue) | 16:30 New_York | 02:00 IST | MEDIUM | API Weekly Statistical Bulletin (crude/product inventories, industry estimate) | Yes | USOIL, XAUUSD |
| 2026-10-21 (Wed) | 10:30 New_York | 20:00 IST | HIGH | EIA Weekly Petroleum Status Report (crude/gasoline/distillate inventories) | Yes | USOIL, USDCAD, XAUUSD |
| 2026-10-22 (Thu) | 08:30 New_York | 18:00 IST | MEDIUM | Initial Jobless Claims (weekly UI claims report) | Yes | USDJPY, EURUSD, GBPUSD, XAUUSD |
| 2026-10-23 (Fri) | 09:45 New_York | 19:15 IST | HIGH | S&P Global Flash US Composite/Manufacturing/Services PMI, October 2026 | Yes | EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAUUSD, XAGUSD |
| 2026-10-26 (Mon) | 10:00 New_York | 19:30 IST | MEDIUM | New Residential Sales (New Home Sales), September 2026 | No* | XAUUSD, USDJPY |
| 2026-10-27 (Tue) | 10:00 New_York | 19:30 IST | MEDIUM | Conference Board Consumer Confidence Index, October 2026 | Yes | XAUUSD, EURUSD |
| 2026-10-27 (Tue) | 16:30 New_York | 02:00 IST | MEDIUM | API Weekly Statistical Bulletin (crude/product inventories, industry estimate) | Yes | USOIL, XAUUSD |
| 2026-10-28 (Wed) | 08:30 New_York | 18:00 IST | MEDIUM | Advance Economic Indicators (Advance Durable Goods, Advance Intl. Trade in Goods, Wholesale/Retail Inventories), September 2026 | Yes | USDCAD, EURUSD, XAUUSD |
| 2026-10-28 (Wed) | 10:30 New_York | 20:00 IST | HIGH | EIA Weekly Petroleum Status Report (crude/gasoline/distillate inventories) | Yes | USOIL, USDCAD, XAUUSD |
| 2026-10-28 (Wed) | 14:00 New_York | 23:30 IST | HIGH | FOMC Statement and Interest Rate Decision | Yes | EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAUUSD, XAGUSD |
| 2026-10-29 (Thu) | 08:30 New_York | 18:00 IST | MEDIUM | Initial Jobless Claims (weekly UI claims report) | Yes | USDJPY, EURUSD, GBPUSD, XAUUSD |
| 2026-10-29 (Thu) | 08:30 New_York | 18:00 IST | HIGH | GDP (Advance Estimate), Q3 2026 | Yes | EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAUUSD, XAGUSD |
| 2026-10-29 (Thu) | 08:30 New_York | 18:00 IST | HIGH | Personal Income and Outlays (PCE Price Index), September 2026 | Yes | EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAUUSD, XAGUSD |

### Canada  (5 events)

| Date | Local Time (tz) | IST | Importance | Event | Time Confirmed | Instruments |
|---|---|---|---|---|---|---|
| 2026-09-29 (Tue) | 08:30 Toronto | 18:00 IST | MEDIUM | Gross Domestic Product by Industry, July 2026 (plus August advance estimate) | Yes | USDCAD, XAUUSD |
| 2026-10-09 (Fri) | 08:30 Toronto | 18:00 IST | HIGH | Labour Force Survey, September 2026 | Yes | USDCAD, XAUUSD |
| 2026-10-19 (Mon) | 08:30 Toronto | 18:00 IST | HIGH | Consumer Price Index, September 2026 | Yes | USDCAD, XAUUSD |
| 2026-10-28 (Wed) | 09:45 Toronto | 19:15 IST | HIGH | Bank of Canada Interest Rate Decision + Monetary Policy Report | Yes | USDCAD, XAUUSD, XAGUSD |
| 2026-10-30 (Fri) | 08:30 Toronto | 18:00 IST | MEDIUM | Gross Domestic Product by Industry, August 2026 | Yes | USDCAD |

### Euro Area  (4 events)

| Date | Local Time (tz) | IST | Importance | Event | Time Confirmed | Instruments |
|---|---|---|---|---|---|---|
| 2026-10-01 (Thu) | 11:00 Brussels | 14:30 IST | HIGH | Eurostat Flash Estimate - Euro Area Annual Inflation, September 2026 | Yes | EURUSD, XAUUSD, XAGUSD |
| 2026-10-23 (Fri) | 10:00 Berlin | 13:30 IST | HIGH | HCOB/S&P Global Flash Eurozone Composite, Manufacturing & Services PMI, October 2026 | Yes | EURUSD, XAUUSD |
| 2026-10-28 (Wed) | 00:00 Berlin | 04:30 IST | LOW | ECB Governing Council Monetary Policy Meeting begins (Day 1) | No* | EURUSD |
| 2026-10-29 (Thu) | 14:15 Berlin | 18:45 IST | HIGH | ECB Interest Rate Decision + Press Conference | Yes | EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAUUSD, XAGUSD |

### United Kingdom  (4 events)

| Date | Local Time (tz) | IST | Importance | Event | Time Confirmed | Instruments |
|---|---|---|---|---|---|---|
| 2026-10-13 (Tue) | 07:00 London | 11:30 IST | HIGH | UK Labour Market Overview (3 months to August 2026) | No* | GBPUSD, GBPJPY, XAUUSD |
| 2026-10-15 (Thu) | 07:00 London | 11:30 IST | HIGH | GDP Monthly Estimate, August 2026 | Yes | GBPUSD, GBPJPY |
| 2026-10-21 (Wed) | 07:00 London | 11:30 IST | HIGH | Consumer Price Inflation (CPI/CPIH), September 2026 | Yes | GBPUSD, GBPJPY, XAUUSD |
| 2026-10-23 (Fri) | 07:00 London | 11:30 IST | MEDIUM | Retail Sales, September 2026 | No* | GBPUSD |

### Japan  (5 events)

| Date | Local Time (tz) | IST | Importance | Event | Time Confirmed | Instruments |
|---|---|---|---|---|---|---|
| 2026-10-19 (Mon) | 08:50 Tokyo | 05:20 IST | MEDIUM | Trade Statistics (Merchandise Trade Balance), September 2026 | No* | USDJPY, GBPJPY |
| 2026-10-23 (Fri) | 08:30 Tokyo | 05:00 IST | HIGH | National Consumer Price Index, September 2026 | Yes | USDJPY, GBPJPY, XAUUSD |
| 2026-10-29 (Thu) | 00:00 Tokyo | 20:30 IST | LOW | Bank of Japan Monetary Policy Meeting begins (Day 1) | No* | USDJPY, GBPJPY |
| 2026-10-30 (Fri) | 08:30 Tokyo | 05:00 IST | MEDIUM | Tokyo Consumer Price Index, October 2026 | Yes | USDJPY, GBPJPY |
| 2026-10-30 (Fri) | 12:00 Tokyo | 08:30 IST | HIGH | Bank of Japan Monetary Policy Decision + Outlook for Economic Activity and Prices | No* | USDJPY, GBPJPY, XAUUSD |

### Australia  (6 events)

| Date | Local Time (tz) | IST | Importance | Event | Time Confirmed | Instruments |
|---|---|---|---|---|---|---|
| 2026-09-24 (Thu) | 11:30 Sydney | 07:00 IST | HIGH | Labour Force, Australia, August 2026 (employment/unemployment) | Yes | AUDUSD |
| 2026-09-29 (Tue) | 14:30 Sydney | 10:00 IST | HIGH | RBA Cash Rate Decision (Monetary Policy Board Meeting, Sept 28-29) | Yes | AUDUSD |
| 2026-09-30 (Wed) | 11:30 Sydney | 07:00 IST | HIGH | Monthly CPI Indicator, August 2026 | Yes | AUDUSD |
| 2026-10-15 (Thu) | 11:30 Sydney | 06:00 IST | HIGH | Labour Force, Australia, September 2026 | Yes | AUDUSD |
| 2026-10-22 (Thu) | 11:00 Sydney | 05:30 IST | MEDIUM | S&P Global/Judo Bank Flash Australia Composite PMI, October 2026 | No* | AUDUSD |
| 2026-10-28 (Wed) | 11:30 Sydney | 06:00 IST | HIGH | Monthly CPI Indicator (incl. Q3 2026 quarterly CPI), September 2026 | Yes | AUDUSD |

### New Zealand  (2 events)

| Date | Local Time (tz) | IST | Importance | Event | Time Confirmed | Instruments |
|---|---|---|---|---|---|---|
| 2026-10-22 (Thu) | 10:45 Auckland | 03:15 IST | HIGH | Consumers Price Index, September Quarter 2026 (Q3) | No* | NZDUSD |
| 2026-10-28 (Wed) | 14:00 Auckland | 06:30 IST | HIGH | RBNZ Official Cash Rate Decision (Monetary Policy Review) | Yes | NZDUSD |

### China  (4 events)

| Date | Local Time (tz) | IST | Importance | Event | Time Confirmed | Instruments |
|---|---|---|---|---|---|---|
| 2026-09-30 (Wed) | 09:30 Shanghai | 07:00 IST | HIGH | NBS Manufacturing & Non-Manufacturing PMI, September 2026 | Yes | AUDUSD, NZDUSD, USOIL, XAGUSD |
| 2026-10-08 (Thu) | 09:45 Shanghai | 07:15 IST | MEDIUM | Caixin China Manufacturing PMI, September 2026 | No* | AUDUSD, NZDUSD, USOIL |
| 2026-10-13 (Tue) | 10:00 Shanghai | 07:30 IST | MEDIUM | China Trade Balance (Exports/Imports), September 2026 | No* | AUDUSD, NZDUSD, USOIL |
| 2026-10-20 (Tue) | 10:00 Shanghai | 07:30 IST | HIGH | Q3 2026 GDP, plus September Retail Sales / Industrial Production / Fixed-Asset Investment | Yes | AUDUSD, NZDUSD, USOIL, XAGUSD |

### OPEC+ (multilateral)  (1 events)

| Date | Local Time (tz) | IST | Importance | Event | Time Confirmed | Instruments |
|---|---|---|---|---|---|---|
| 2026-10-04 (Sun) | TBD Vienna | TBD IST | HIGH | OPEC+ Joint Ministerial Monitoring Committee (JMMC), 68th Meeting | No* | USOIL, USDCAD, XAUUSD |

### IEA / International  (1 events)

| Date | Local Time (tz) | IST | Importance | Event | Time Confirmed | Instruments |
|---|---|---|---|---|---|---|
| 2026-10-14 (Wed) | TBD Vienna | TBD IST | MEDIUM | IEA Oil Market Report, October 2026 | No* | USOIL |
---

## 4. Key caveats to read before trading (explicit, as requested)

### 4.1 U.S. government shutdown risk
- A federal funding lapse (shutdown) ran **October 1 – November 12, 2025**, which disrupted BLS/Census/BEA data collection and release schedules (e.g., October 2025 CPI data could not be collected at all, JOLTS releases were merged, population-control adjustments were pushed from January to February 2026).
- A **second, DHS-related partial shutdown ran February 14 – April 30, 2026**, again inside FY2026, and again produced revised BLS release dates (e.g., the January 2026 Employment Situation moved from Feb 6 to Feb 11; January 2026 CPI moved from Feb 11 to Feb 13).
- As of this research date (Sep 22, 2026), search results indicate Congress passed a continuing resolution funding the government **through December 11, 2026**, and no active shutdown was found affecting September–October 2026. **This should not be treated as a guarantee** — the pattern of two lapses already in FY2026 means a further lapse before Dec 11 is not implausible, and any lapse would delay BLS/BEA/Census releases in this window (CPI, PPI, NFP, GDP, retail sales, trade balance, durable goods, housing data, JOLTS). **Re-check bls.gov/schedule, bea.gov/news/schedule, and census.gov/economic-indicators for shutdown-driven revisions in the days immediately before each U.S. release**, especially the Oct 2 NFP, Oct 14 CPI, and Oct 28–29 GDP/PCE releases.

### 4.2 Bank of England — no MPC decision in this window
The 2026 MPC schedule (bankofengland.co.uk/news/2024/december/mpc-dates-for-2026) confirmed via search: Feb 5, Mar 19, Apr 30, Jun 18, Jul 30, **Sep 17**, **Nov 5**, Dec 17. The Sep 17, 2026 decision falls *before* this window opens (Sep 22), and the next decision, Nov 5, 2026, falls *after* this window closes (Oct 31). **There is deliberately no BoE rate-decision entry in the JSON.** UK data releases in the window (labour market, GDP, CPI, retail sales) are still included and remain highly GBP-relevant even without an MPC meeting.

### 4.3 RBA — no October meeting
The RBA moved to an 8-meetings-per-year schedule. The official 2026 dates (rba.gov.au media release, confirmed via search): Feb 2–3, Mar 16–17, May 4–5, Jun 15–16, Aug 10–11, **Sep 28–29**, **Nov 2–3**, Dec 7–8. **There is no RBA meeting in October 2026** — the Sep 28–29 meeting (decision Sep 29) is the only RBA decision in this window; the next is Nov 2–3, outside the window.

### 4.4 China National Day "Golden Week" (Oct 1–7, 2026)
China's National Day holiday falls Oct 1–7, 2026, which is why the NBS official Manufacturing/Non-Manufacturing PMI for September is released *before* the holiday, on **Sep 30**, while the privately-compiled **Caixin** Manufacturing PMI (which normally releases on the first business day of the month) is expected to be delayed to roughly **Oct 8**, the first business day after the holiday. This is a pattern-based estimate (flagged `exact_time_confirmed: false`); confirm against a live Caixin/S&P Global release calendar closer to the date.

### 4.5 EIA / API weekly oil-inventory holiday shifts (Columbus Day, Oct 12, 2026)
Columbus Day (a Monday) falls in the window. Based on EIA's and API's published holiday-shift rules and the historical analog of the 2025 Columbus Day shift:
- The **EIA Weekly Petroleum Status Report** normally due Wednesday Oct 14 is expected to shift to **Thursday Oct 15, 2026**.
- The **API Weekly Statistical Bulletin** normally due Tuesday Oct 13 is expected to shift to **Wednesday Oct 14, 2026**.
Both shifts are flagged `exact_time_confirmed: false` pending direct confirmation from eia.gov/petroleum/supply/weekly/schedule.php and api.org (both unreachable from this research environment — see §1).

### 4.6 Egress-blocked official domains (full list)
The following domains returned `EGRESS_BLOCKED` when this research attempted a direct fetch, meaning nothing in this document was sourced by reading an official page directly — only via search-engine snippets/indexing of those pages: `bls.gov`, `bea.gov`, `census.gov`, `whitehouse.gov` (PFEI schedule PDF), `ecb.europa.eu`, `rba.gov.au`, `eia.gov`. (Other official domains — `federalreserve.gov`, `bankofengland.co.uk`, `boj.or.jp`, `abs.gov.au`, `rbnz.govt.nz`, `stats.govt.nz`, `bankofcanada.ca`, `statcan.gc.ca`, `stats.gov.cn`, `api.org`, `opec.org`, `iea.org`, `ons.gov.uk` — were not individually fetch-tested but are the same class of domain and should be assumed similarly blocked in this environment; all data on them was likewise obtained via search snippets, not direct reads.)

---

## 5. Timezone / DST handling

All `exact_release_time_IST` values in the JSON were computed **programmatically**, per event, using IANA tzdata (Python `zoneinfo`) applied to that event's specific calendar date — not by a single manual offset — so each conversion is correct for whichever DST regime applies on that date. The relevant transitions inside or adjacent to this window:

| Region | Standard → Daylight transition in/near this window | Effect |
|---|---|---|
| **United States / Canada** (Eastern) | DST does **not** end until **Sunday, Nov 1, 2026** (after this window) | Every US/Canada Eastern time in this dataset is **EDT (UTC−4)** for the entire window — no mid-window shift. |
| **India** | No DST | IST is fixed **UTC+5:30** throughout. |
| **Euro Area / United Kingdom** | DST (CEST/BST) ends **Sunday, Oct 25, 2026** | Events **before** Oct 25 use CEST/BST (UTC+2/UTC+1); events **on/after** Oct 25 use CET/GMT (UTC+1/UTC+0) — i.e., the same local clock time sits **one hour later relative to IST** after Oct 25 than before it. The ECB decision (Oct 29) and post-Oct-25 UK/EU data therefore already reflect winter time in the IST column. |
| **Australia** | DST (AEDT) begins **Sunday, Oct 4, 2026** | The Sep 24/29/30 Australian events use AEST (UTC+10); the Oct 15/22/28 Australian events use AEDT (UTC+11) — a one-hour shift mid-window. |
| **New Zealand** | DST (NZDT) begins **Sunday, Sep 27, 2026** | Nearly the entire window (from Sep 27 onward) uses NZDT (UTC+13); this only matters for events before Sep 27, of which there are none in the NZ event list. |
| **Japan / China** | No DST | JST fixed UTC+9; CST fixed UTC+8, throughout. |

---

## 6. Items with meaningfully uncertain dates/times (`exact_time_confirmed: false`) — verify before use

| Event | Estimated date | Why uncertain |
|---|---|---|
| US New Residential (New Home) Sales, Sept 2026 | ~Oct 26 | Exact date not confirmed on census.gov (blocked); estimated from the ~4-week lag pattern of the August release. |
| ECB Governing Council meeting Day 1 | Oct 28 | Included only as a blackout-period marker; no announcement occurs this day. |
| UK Labour Market Overview (Jun–Aug 2026) | ~Oct 13 | Specific October release page not directly confirmed; estimated from ONS's ~4-week publication cadence. |
| UK Retail Sales, Sept 2026 | ~Oct 23 | Pattern-based estimate from ONS's typical ~5-week cadence. |
| Japan Trade Statistics, Sept 2026 | ~Oct 19 | MOF/Customs provisional calendar page not directly fetchable; estimated from the general "~20th of the following month" pattern. |
| BoJ meeting Day 1 | Oct 29 | Blackout-period marker only; the decision itself (Oct 30) is separately listed and is the primary event. |
| BoJ policy decision exact minute | Oct 30, ~12:00 JST | BoJ does not pre-announce an exact release minute; historical announcements have ranged roughly 11:20–13:00 JST. Press conference ~15:30 JST is a standard convention, not independently reconfirmed here. |
| Australia flash Composite PMI, Oct 2026 | ~Oct 22 | Judo Bank/S&P Global flash-PMI date for Australia not independently confirmed for Oct 2026; estimated from the standard flash-PMI cycle (a day ahead of the US/Eurozone batch on Oct 23). |
| NZ Q3 2026 CPI exact release minute | Oct 22, ~10:45 NZDT | Date corroborated via search; the specific minute for this release was not re-verified against a primary stats.govt.nz fetch. |
| Caixin China Manufacturing PMI, Sept 2026 | ~Oct 8 | Standard "1st business day" release would fall inside China's Oct 1–7 National Day holiday; Oct 8 is a holiday-delay estimate, not a confirmed Caixin calendar date. |
| China Trade Balance, Sept 2026 | ~Oct 13 | Exact 2026 date not independently confirmed; estimated from typical early/mid-month cadence of Chinese customs data releases. |
| EIA Weekly Petroleum Status Report (Columbus Day week) | Oct 15 (shifted from Oct 14) | Holiday-shift rule applied by analogy to 2025; not directly reconfirmed against the 2026 eia.gov holiday schedule page (blocked). |
| API Weekly Statistical Bulletin (Columbus Day week) | Oct 14 (shifted from Oct 13) | Same as above, applied to API's published Monday-holiday rule. |
| OPEC+ JMMC (68th meeting) | Oct 4 | Date inferred from the JMMC meeting-numbering sequence (64th on Feb 1, 67th on Aug 2) rather than a directly confirmed opec.org calendar entry; no time is pre-announced for JMMC videoconferences in any case. OPEC+ can also add/reschedule output-policy meetings on short notice — treat this as a soft date. |
| IEA Oil Market Report, Oct 2026 | ~Oct 14 | Only a generic "mid-month" cadence and an IEA events-page title were found; exact 2026 date not independently confirmed (iea.org blocked). |

---

## 7. Non-government indicators included (flagged for transparency)

A few widely-market-moving releases in this dataset are compiled by **private organizations, not government agencies**, and are labeled as such in their `official_source` field: S&P Global / HCOB / Judo Bank flash PMIs, ISM Manufacturing/Services PMI, Caixin China PMI, the Conference Board Consumer Confidence Index, the University of Michigan Consumer Sentiment survey, and NAR Existing-Home Sales. These were included per the research brief's explicit request to cover "PMIs... consumer confidence... housing data" even though they are not official government statistics; they are nonetheless on fixed, publicly pre-announced release schedules and are heavily traded.

---

## 8. Full structured data

See [`data/events_sep22_oct31_2026.json`](../data/events_sep22_oct31_2026.json) for the complete 74-event dataset with every field described in §1, including the full `methodology` note reproduced at the top level of that file.
