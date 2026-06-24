# AI-Powered Website Audit Tool

> A lightweight, AI-driven website audit tool built for the EIGHT25MEDIA engineering assessment.  
> Analyzes a single webpage for SEO structure, content quality, CTA usage, and UX concerns using factual scraping + Gemini AI insights.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (User)                          │
│                                                                │
│   URL Input  ──►  POST /audit  ──►  JSON Response  ──►  UI    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Flask (app.py)                            │
│                                                                │
│   1. Validate URL                                              │
│   2. Call scraper.scrape(url) ─────────────────────┐           │
│   3. Call gemini.analyze(url, metrics, text) ──┐   │           │
│   4. Call logger.log(...) ──────────────────┐  │   │           │
│   5. Return { metrics, insights, recs }    │  │   │           │
└────────────────────────────────────────────┼──┼───┼───────────┘
                                             │  │   │
                    ┌────────────────────────┘  │   │
                    ▼                           │   │
          ┌──────────────────┐                  │   │
          │   logger.py      │                  │   │
          │                  │                  │   │
          │  Appends full    │                  │   │
          │  prompt log to   │                  │   │
          │  prompt_log.json │                  │   │
          └──────────────────┘                  │   │
                                                │   │
                    ┌───────────────────────────┘   │
                    ▼                               │
          ┌──────────────────┐            ┌────────┴─────────┐
          │   gemini.py      │            │   scraper.py     │
          │                  │            │                  │
          │  Model Fallbacks │            │  requests + BS4  │
          │  Structured JSON │            │  Factual metrics │
          │  response_schema │            │  + cleaned text  │
          └─────────┬────────┘            └──────────────────┘
                    │
          ┌─────────▼────────┐
          │ grounding.py     │
          │                  │
          │ Post-processing  │
          │ validation       │
          └──────────────────┘
               (AI layer)                   (Scraping layer)
          No scraper imports              No AI imports
```

**Data flow:**  
`URL input → scraper.py (HTML fetch + metric extraction) → gemini.py (AI analysis with structured schema) → logger.py (prompt log) → JSON response → rendered UI`

The scraper and AI modules are **fully independent** — no cross-imports. This enforces clean separation between factual data and AI-generated content.

---

## 2. AI Design Decisions

### Model Selection & Fallback Chain

- **Primary Model:** `gemini-3.5-flash` is used as specified in the brief for fast, free-tier structured output.
- **Robust Fallback Strategy:** To handle frequent `503 UNAVAILABLE` errors due to high demand, the app implements an automatic fallback chain (`gemini-3.5-flash` → `gemini-2.5-flash` → `gemini-2.5-flash-lite` → `gemini-3.1-flash-lite`). This ensures the app remains reliable without exhausting quotas on failed requests.
- Supports `response_schema` for **guaranteed JSON output** across the Flash model family.

### Why `response_schema` (Structured Output)

- Guarantees the API returns **valid JSON** matching our exact schema — no regex parsing, no "please format as JSON" prompt hacking
- Eliminates an entire class of parsing bugs and retry logic
- Enforces the 5-pillar insight structure and 3–5 recommendation constraint at the API level
- The schema acts as a **contract** between the AI layer and the frontend

### Why 3000-word truncation

- **Token budget management** — Gemini 3.5 Flash has a context window, but sending entire pages would waste tokens on boilerplate (nav, footer, legal text)
- 3000 words captures the **core content** of most marketing pages (hero, features, about sections)
- Combined with `max_output_tokens: 8192`, keeps the total token usage predictable while allowing enough budget for newer "thinking" models (like `gemini-2.5-flash`) to process internal reasoning without truncating the final JSON.
- Prevents timeout issues on content-heavy pages

### Benchmark-Informed Prompting

- The AI is provided with **industry benchmarks** in the system prompt (e.g., "marketing pages should have 800-2000 words").
- This transforms insights from generic observations ("You have 500 words") into actionable, contextual analysis ("Your 500 words is 37% below the minimum benchmark").

### Grounding Strategy & Verification

- Every AI insight is required to **explicitly reference extracted metric values** (e.g., "With only 1 H1 tag and 0 H2 tags...").
- The system prompt explicitly forbids generic advice.
- **Post-Processing Validation:** The app includes a standalone `grounding.py` module that acts as a strict verification layer. It scans the AI's output using deterministic string matching to prove that specific metric values were actually cited.
- Insights that pass get a ✅ in the UI; insights that fail get a ⚠️.
- This demonstrates true AI-native thinking: **trust, but verify**. We don't just ask the AI to ground its output; we programmatically prove that it did.

---

## 3. Trade-offs

| Decision | Chosen Approach | Alternative | Why |
|----------|----------------|-------------|-----|
| **Scope** | Single page only | Multi-page crawl | Hard constraint from the brief. Also keeps scraping fast and predictable |
| **Model** | Multi-model Fallback Chain | Single Pro model | A fallback chain of Flash/Lite models ensures high availability during traffic spikes, whereas a single Pro model would be a single point of failure and cost more. |
| **Scraping** | `requests` + `BeautifulSoup` | Headless browser (Playwright, Selenium) | Brief prohibits headless browsers. Trade-off: JS-rendered content (SPAs, React apps) won't be captured |
| **CTA Detection** | Regex pattern matching | ML-based intent classification | Regex is fast and deterministic; covers 90%+ of standard marketing CTAs. ML would add complexity and a dependency for marginal gain |
| **Token limit** | 8192 output tokens | 1500 limit | Increased to 8192 to prevent JSON truncation issues when fallback models (like `gemini-2.5-flash`) use internal reasoning tokens that count against the output limit. |
| **Text truncation** | 3000 words | Full page text | Balances content coverage with token efficiency. Most marketing pages have < 3000 words of meaningful content |
| **Prompt logging** | Local JSON file | Database | File-based logging is zero-dependency and sufficient for a single-user tool. Database would be overkill |

### Known Limitations

- **JavaScript-rendered pages** — Sites built with React, Angular, or Vue that render content client-side will return minimal or no content. The scraper only sees the initial HTML response
- **Rate limiting** — No retry logic or rate limit handling for either the target URL or the Gemini API
- **CTA detection** — Regex-based; may miss unconventional CTA phrases or produce false positives on navigation links
- **Single language** — CTA patterns are English-only
- **Total model exhaustion** — If all four models in the fallback chain return `503 UNAVAILABLE` simultaneously (e.g., during a region-wide Gemini outage), the app returns a clear error listing every model tried; the user must retry later

---

## 4. Example Output

**URL audited:** `https://vercel.com`

**AI-Powered Score:** 62 / 100
*The page relies on a high-density, product-centric navigation structure common in SaaS, but significantly underperforms on SEO-driven content volume and accessibility standards compared to industry leaders.*

**Metrics extracted:**
- Word Count: 501
- H1: 1, H2: 17, H3: 6
- CTAs: 12 | Internal Links: 141 | External Links: 17
- Images: 18 | Missing Alt Text: 16.7%
- Meta Title: "Agentic Infrastructure"
- Meta Description: "The autonomous stack for every app and agent."

**Sample AI Insight (SEO Structure) ✅:**
> "With 17 H2 tags and 6 H3 tags for only 501 words, the page exceeds the
> recommended header limit, creating a fragmented hierarchy that confuses
> search crawlers regarding primary topics."

**Sample Recommendation (High Priority):**
> "Expand the textual content under each of the 16 H2 headings to
> provide more detailed explanations and value. A low word count of
> 555 across 16 H2 tags suggests shallow content for many distinct
> topics."

---

## 5. What I Would Improve With More Time

1. **Retry logic with exponential backoff** — for HTTP scraping requests and API rate limits (we currently handle `503` availability errors via the model fallback chain, but `429` rate limits could use backoff)
2. **Caching layer** — store scrape results and AI analysis by URL + timestamp to avoid redundant API calls
3. **Comparison mode** — audit two URLs side-by-side to compare metrics and insights (useful for competitive analysis)
4. **Historical tracking** — store audit results over time and show trend graphs for repeat audits of the same URL
5. **PDF/CSV export** — generate downloadable audit reports for client presentations
6. **Enhanced CTA detection** — use NLP or a small classifier to identify CTAs by intent rather than regex patterns
7. **Accessibility audit** — extend beyond alt text to check ARIA labels, color contrast ratios, keyboard navigation
8. **Screenshot capture** — integrate a headless browser (optional mode) to capture above-the-fold screenshots for visual context
9. **Multi-language CTA support** — extend regex patterns or use translation for non-English sites
10. **Test suite** — unit tests for the scraper (mock HTML fixtures), integration tests for the API routes, and contract tests for the Gemini schema

---

## 6. Setup & Run Instructions

### Prerequisites

- **Python 3.10+** installed
- A **Google Gemini API key** ([Get one free here](https://aistudio.google.com/apikey))

### Step-by-step Setup

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd eigth25

# 2. Create a virtual environment
py -m venv venv

# 3. Activate the virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
.\venv\Scripts\activate.bat
# macOS/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure your API key
cp .env.example .env
# Then edit .env and replace 'your_key_here' with your actual Gemini API key

# 6. Run the application
py app.py
```

### Usage

1. Open your browser to **<http://localhost:5000>**
2. Enter a URL (e.g., `https://example.com`)
3. Click **"Run Audit"**
4. View:
   - **Factual Metrics** — scraped data (word count, headings, CTAs, links, images, meta tags)
   - **AI Insights** — Gemini analysis across 5 pillars
   - **Recommendations** — 3–5 prioritized action items
   - **Prompt Log** — click "View Prompt Log" to see the full AI prompt exchange

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serve the web UI |
| `POST` | `/audit` | Run audit. Body: `{ "url": "https://..." }` |
| `GET` | `/last-log` | Return the last prompt log entry |

### Troubleshooting

- **`GEMINI_API_KEY not found`** — Make sure your `.env` file exists in the project root with `GEMINI_API_KEY=your_key`
- **Empty scrape results** — The target site may be JavaScript-rendered (SPA). Try a static HTML site instead
- **Gemini API errors** — Check your API key is valid and has quota remaining
