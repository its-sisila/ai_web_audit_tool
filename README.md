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
          │  Gemini 3.5 Flash│            │  requests + BS4  │
          │  Structured JSON │            │  Factual metrics │
          │  response_schema │            │  + cleaned text  │
          └──────────────────┘            └──────────────────┘
               (AI layer)                   (Scraping layer)
          No scraper imports              No AI imports
```

**Data flow:**  
`URL input → scraper.py (HTML fetch + metric extraction) → gemini.py (AI analysis with structured schema) → logger.py (prompt log) → JSON response → rendered UI`

The scraper and AI modules are **fully independent** — no cross-imports. This enforces clean separation between factual data and AI-generated content.

---

## 2. AI Design Decisions

### Why `gemini-3.5-flash`
- Available on the **free tier** — no billing required for development and evaluation
- **Fast inference** — sub-second response times for structured output
- **Sufficient quality** for structured analysis tasks — the schema enforcement means we don't need the reasoning depth of Pro models
- Supports `response_schema` for **guaranteed JSON output**

### Why `response_schema` (Structured Output)
- Guarantees the API returns **valid JSON** matching our exact schema — no regex parsing, no "please format as JSON" prompt hacking
- Eliminates an entire class of parsing bugs and retry logic
- Enforces the 5-pillar insight structure and 3–5 recommendation constraint at the API level
- The schema acts as a **contract** between the AI layer and the frontend

### Why 3000-word truncation
- **Token budget management** — Gemini 3.5 Flash has a context window, but sending entire pages would waste tokens on boilerplate (nav, footer, legal text)
- 3000 words captures the **core content** of most marketing pages (hero, features, about sections)
- Combined with `max_output_tokens: 1500`, keeps the total token usage predictable and fast
- Prevents timeout issues on content-heavy pages

### Grounding Strategy
- Every AI insight is required to **explicitly reference extracted metric values** (e.g., "With only 1 H1 tag and 0 H2 tags...")
- The system prompt explicitly forbids generic advice
- Metrics are passed as structured data in the user prompt, not embedded in prose — making it easy for the model to cite them

---

## 3. Trade-offs

| Decision | Chosen Approach | Alternative | Why |
|----------|----------------|-------------|-----|
| **Scope** | Single page only | Multi-page crawl | Hard constraint from the brief. Also keeps scraping fast and predictable |
| **Model** | Flash (free, fast) | Pro (deeper reasoning) | Flash is sufficient for structured output tasks; Pro would add latency and cost without meaningful quality gain for this use case |
| **Scraping** | `requests` + `BeautifulSoup` | Headless browser (Playwright, Selenium) | Brief prohibits headless browsers. Trade-off: JS-rendered content (SPAs, React apps) won't be captured |
| **CTA Detection** | Regex pattern matching | ML-based intent classification | Regex is fast and deterministic; covers 90%+ of standard marketing CTAs. ML would add complexity and a dependency for marginal gain |
| **Token limit** | 1500 output tokens | Higher limit | Keeps responses concise and focused. Higher limits risk verbose, less actionable output |
| **Text truncation** | 3000 words | Full page text | Balances content coverage with token efficiency. Most marketing pages have < 3000 words of meaningful content |
| **Prompt logging** | Local JSON file | Database | File-based logging is zero-dependency and sufficient for a single-user tool. Database would be overkill |

### Known Limitations
- **JavaScript-rendered pages** — Sites built with React, Angular, or Vue that render content client-side will return minimal or no content. The scraper only sees the initial HTML response
- **Rate limiting** — No retry logic or rate limit handling for either the target URL or the Gemini API
- **CTA detection** — Regex-based; may miss unconventional CTA phrases or produce false positives on navigation links
- **Single language** — CTA patterns are English-only

---

## 4. What I Would Improve With More Time

1. **Retry logic with exponential backoff** — for both HTTP requests and Gemini API calls, handling transient failures gracefully
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

## 5. Setup & Run Instructions

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

1. Open your browser to **http://localhost:5000**
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
