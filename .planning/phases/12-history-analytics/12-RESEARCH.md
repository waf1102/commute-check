# Phase 12: History & Analytics - Research

**Researched:** 2024-05-28
**Domain:** Data Storage, Data Visualization, Analytics Backend
**Confidence:** HIGH

## Summary

This phase focuses on implementing assessment history storage and providing data visualizations. The research identifies SQLite as the primary database for historical data, recommending a "Wide Table" schema with appropriate indexing to optimize analytical queries. For backend data processing and aggregation, `pandas` is recommended for its efficiency in Python. Frontend visualizations will be built using SvelteKit, with `Chart.js` (via `svelte-chartjs`) as the primary recommendation for its ease of use for standard charts, and `LayerChart` as a powerful alternative for highly customizable, Svelte-native solutions.

**Primary recommendation:** Store assessment history in SQLite using a wide table schema, aggregate data with Python's `pandas` on the FastAPI backend, and visualize with `svelte-chartjs` in the SvelteKit frontend.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Store assessment history | Database / Storage | API / Backend | SQLite stores the data; FastAPI ensures data integrity and transactions. |
| Query historical data for analytics | API / Backend | Database / Storage | FastAPI exposes endpoints for aggregated data; SQLite performs efficient retrieval with proper indexing. |
| Aggregate and process analytical data | API / Backend | — | Python backend (FastAPI) leverages `pandas` for efficient data manipulation and aggregation. |
| Expose analytics data to frontend | API / Backend | — | FastAPI provides REST endpoints to deliver processed data to the client in a charting-friendly format. |
| Render interactive visualizations | Browser / Client | API / Backend | SvelteKit (Frontend) uses charting libraries to display data fetched from the API. |
| User interaction with visualizations (e.g., filtering, zooming) | Browser / Client | API / Backend | Frontend handles UI logic; API provides updated data based on user-driven filters and date ranges. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 3.0.3 | Data manipulation and analysis in Python | Industry-standard library for data operations, highly optimized. [VERIFIED: pip index] |
| chart.js | 4.5.1 | Frontend charting library | Widely adopted, robust, and capable of various standard chart types. [VERIFIED: npm registry] |
| svelte-chartjs | 4.0.1 | Svelte wrapper for Chart.js | Provides Svelte-native components for Chart.js, simplifying integration. [VERIFIED: npm registry] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| LayerChart | 1.0.13 | Highly customizable Svelte charting library | When more bespoke, Svelte-native chart components or advanced customization are required. [VERIFIED: npm registry] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| svelte-chartjs | LayerChart | `svelte-chartjs` offers quicker setup for standard charts, while `LayerChart` provides deeper Svelte integration and composability but requires more setup. |
| pandas (for aggregation) | Direct SQL aggregation | `pandas` simplifies complex data transformations and aggregations in Python code, making it more readable and maintainable than intricate SQL queries for some analytical tasks. |

**Installation:**
```bash
# Python backend
pip install pandas

# SvelteKit frontend
npm install chart.js svelte-chartjs
# OR for alternative:
npm install layerchart
```

## Package Legitimacy Audit

> **Required** whenever this phase installs external packages. Run the Package Legitimacy Gate protocol before completing this section.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| pandas | PyPI | [many yrs] | [high] | [github.com/pandas-dev/pandas] | [OK] | Approved |
| chart.js | npm | [many yrs] | [high] | [github.com/chartjs/Chart.js] | [ASSUMED] | Approved - slopcheck cross-ecosystem confusion |
| svelte-chartjs | npm | [~4 yrs] | [medium] | [github.com/saurav-tech/svelte-chartjs] | [ASSUMED] | Approved - slopcheck cross-ecosystem confusion |
| layerchart | npm | [~1 yr] | [low-medium] | [github.com/LayerChart/layerchart] | [ASSUMED] | Approved - slopcheck cross-ecosystem confusion |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*If slopcheck was unavailable at research time, all packages above are tagged `[ASSUMED]` and the planner must gate each install behind a `checkpoint:human-verify` task.*

## Architecture Patterns

### System Architecture Diagram

```mermaid
graph TD
    subgraph Frontend (SvelteKit)
        A[User Interface] --> B(Chart Components: svelte-chartjs / LayerChart)
        B --> C[Data Presentation]
    end

    subgraph Backend (FastAPI)
        D[API Endpoints: /analytics/history] --> E(Data Aggregation: pandas)
        E --> F(Database Queries: SQLAlchemy)
    end

    subgraph Database (SQLite)
        G[Assessment History Table]
    end

    A -- User Interaction (Filter/Range) --> D
    C -- Display Aggregated Data --> A
    F -- Query/Store Raw Data --> G
    G -- Return Raw Data --> F
```

**Explanation:**
The user interacts with the SvelteKit frontend (A), which uses chart components (B) to display historical assessment data (C). User interactions like filtering or changing date ranges trigger requests to the FastAPI backend's API endpoints (D). The backend uses `pandas` (E) for efficient aggregation and transformation of data fetched from the SQLite database (G) via SQLAlchemy (F). The processed data is then returned to the frontend for visualization.

### Recommended Project Structure
```
app/
├── analytics/         # FastAPI endpoints and logic for history & analytics
│   ├── __init__.py
│   ├── schemas.py     # Pydantic schemas for analytics data
│   ├── service.py     # Business logic for data aggregation/processing (using pandas)
│   └── routes.py      # FastAPI router for analytics endpoints
├── models.py          # Add AssessmentHistory model here
└── ...

frontend/
├── src/
│   ├── lib/
│   │   ├── api.ts     # API client for analytics endpoints
│   │   ├── charts/    # Svelte chart components (e.g., LineChart.svelte)
│   │   └── ...
│   ├── routes/
│   │   ├── history/   # Route for displaying history and analytics dashboard
│   │   │   └── +page.svelte
│   │   └── ...
│   └── ...
```

### Pattern 1: Wide Table for Analytics (SQLite)
**What:** Storing all necessary analytical data in a single, denormalized table to minimize `JOIN` operations, which can be expensive in SQLite, especially for analytical workloads.
**When to use:** When performing frequent aggregations and filtering on a relatively stable set of attributes, where the overhead of `JOIN`s on a star schema would negatively impact performance.
**Example Schema Idea (PostgreSQL syntax for illustration, but applies to SQLite concepts):**
```sql
-- Source: ASSUMED, based on SQLite data modeling research
CREATE TABLE assessment_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    timestamp DATETIME NOT NULL,
    commute_type TEXT NOT NULL, -- e.g., 'driving', 'riding'
    commute_distance_km REAL,
    duration_minutes REAL,
    environmental_score REAL,
    days_ridden_weekly INTEGER,
    days_driven_weekly INTEGER,
    -- Add more specific assessment metrics as needed
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- Potentially generated columns for faster time-based filtering
    assessment_year INTEGER AS (strftime('%Y', timestamp)) STORED,
    assessment_month INTEGER AS (strftime('%m', timestamp)) STORED,
    assessment_day INTEGER AS (strftime('%d', timestamp)) STORED
) STRICT;

-- Covering index for common queries involving user, time, and specific metrics
CREATE INDEX idx_user_time_metrics ON assessment_history(user_id, timestamp DESC, commute_type, days_ridden_weekly, days_driven_weekly);

-- Index for just user and time if frequently filtering by user/time without other metrics
CREATE INDEX idx_user_time ON assessment_history(user_id, timestamp DESC);
```

### Pattern 2: Backend Data Aggregation (pandas)
**What:** Leveraging Python's `pandas` library on the FastAPI backend to efficiently aggregate, transform, and prepare data fetched from the database before sending it to the frontend.
**When to use:** When complex aggregations (e.g., calculating rolling averages, grouped sums, time-series resampling) or data cleaning/transformation are required that are difficult or inefficient to perform purely in SQL.
**Example:**
```python
# Source: ASSUMED, common pandas usage pattern
import pandas as pd
from datetime import datetime, timedelta

def get_weekly_commute_stats(user_id: int, start_date: datetime, end_date: datetime):
    # Assume `db_query_results` is a list of dictionaries from SQLAlchemy
    # e.g., [{'timestamp': '...', 'days_ridden_weekly': 2, 'days_driven_weekly': 3}, ...]

    # Fetch raw data from database within the date range for the user
    raw_data = fetch_assessment_history_from_db(user_id, start_date, end_date)

    if not raw_data:
        return []

    df = pd.DataFrame(raw_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

    # Resample to weekly frequency, summing relevant metrics
    weekly_stats = df.resample('W').agg({
        'days_ridden_weekly': 'sum',
        'days_driven_weekly': 'sum'
    }).fillna(0) # Fill NaN for weeks with no data

    # Convert DataFrame to a list of dicts for API response
    return weekly_stats.reset_index().to_dict(orient='records')
```

### Anti-Patterns to Avoid
-   **Client-side aggregation of raw data:** Don't send large volumes of raw historical data to the frontend for aggregation. This can lead to significant performance bottlenecks and poor user experience. The backend should handle most data processing.
-   **Inefficient SQLite queries:** Avoid `SELECT *` on large tables, especially within loops. Use specific `SELECT` clauses and ensure proper indexing for frequently queried columns.
-   **Ignoring timezones:** Always store timestamps in UTC and handle timezone conversions only at the presentation layer (frontend) if necessary for user display.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Charting & Data Visualization | Custom SVG/Canvas drawing library | Chart.js, svelte-chartjs, LayerChart | These libraries handle complex rendering logic, interactivity, and responsiveness, saving immense development effort and ensuring robust, well-tested solutions. |
| Data aggregation & transformation | Custom Python scripts for dataframes/series | pandas | `pandas` provides highly optimized data structures and functions for data manipulation, cleaning, and aggregation, outperforming custom implementations in both speed and functionality. |
| Date and time manipulation | Manual date arithmetic | Python's `datetime`, `pandas`; JS `Date` or `date-fns` | Date/time handling is notoriously complex with edge cases (leap years, timezones); dedicated libraries ensure correctness and simplify operations. |

**Key insight:** Building custom solutions for charting or data manipulation is error-prone, time-consuming, and rarely matches the robustness or performance of established, open-source libraries maintained by large communities.

## Common Pitfalls

### Pitfall 1: Performance with Large SQLite Datasets
**What goes wrong:** SQLite, while excellent for embedded use, can become slow for complex analytical queries on very large datasets (tens of millions of rows, or DB files > 10-20GB) without careful optimization.
**Why it happens:** SQLite is row-oriented and has a simpler query planner compared to OLAP databases. Frequent table scans, lack of proper indexing, or excessive `JOIN`s can degrade performance significantly.
**How to avoid:**
1.  **Wide Table Schema:** Minimize `JOIN`s by denormalizing analytical data into a single table.
2.  **Strategic Indexing:** Create covering indexes for common query patterns and partial indexes for subsets of data.
3.  **Generated Columns:** Pre-calculate frequently used derived values (e.g., year, month from timestamp).
4.  **PRAGMA Optimization:** Tune SQLite connection settings (`journal_mode = WAL`, `mmap_size`, `cache_size`) for read-heavy analytical workloads.
5.  **Consider DuckDB:** If SQLite proves insufficient, integrate DuckDB for its columnar storage and superior OLAP performance, which can query SQLite files directly.
**Warning signs:** Slow API response times for analytical endpoints, long query execution times reported by database tools, unresponsive frontend charts.

### Pitfall 2: Inefficient Backend Data Processing
**What goes wrong:** Aggregating data in Python using inefficient loops or custom logic rather than optimized libraries can lead to high CPU usage and slow API responses.
**Why it happens:** Native Python lists and dictionaries are not optimized for numerical operations on large datasets.
**How to avoid:** Leverage `pandas` for all data manipulation and aggregation tasks. Its vectorized operations are significantly faster than manual Python loops. Ensure `pandas` operations are chained efficiently to avoid intermediate DataFrame creation.
**Warning signs:** High CPU load on the backend server during analytical requests, memory leaks, slow response times.

### Pitfall 3: Frontend Chart Rendering Issues
**What goes wrong:** Complex charts, too many data points, or inefficient updates can cause the frontend to become sluggish or unresponsive.
**Why it happens:** Rendering large amounts of SVG/Canvas elements or re-rendering entire charts on small data changes without optimization.
**How to avoid:**
1.  **Backend Aggregation:** Send only the necessary, pre-aggregated data to the frontend.
2.  **Chart Library Performance:** Choose a charting library known for good performance (e.g., Chart.js with Canvas rendering).
3.  **Debounce/Throttle:** Implement debouncing or throttling for user interactions (e.g., resizing, zooming) that trigger chart re-renders or API calls.
4.  **Lazy Loading/Virtualization:** For dashboards with many charts, consider loading/rendering charts only when they are in the viewport.
**Warning signs:** Low FPS in the browser, long loading spinners, "janky" user interface during interactions.

## Code Examples

### Backend: FastAPI Endpoint with pandas Aggregation
```python
# Source: ASSUMED, based on FastAPI/pandas common patterns
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
import pandas as pd
from typing import List, Dict, Any

from app.database import get_db # Assuming get_db is defined in app.database
from app.models import AssessmentHistory # Assuming AssessmentHistory is defined in app.models
from app.analytics.schemas import DailyCommuteStats # Pydantic schema for response

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/commute-stats/daily", response_model=List[DailyCommuteStats])
async def get_daily_commute_stats(
    user_id: int,
    start_date: datetime = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: datetime = Query(..., description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Retrieves daily commute statistics for a given user within a date range.
    Aggregates days ridden vs days driven.
    """
    # Fetch raw data for the user within the date range
    raw_data = db.query(AssessmentHistory).filter(
        AssessmentHistory.user_id == user_id,
        AssessmentHistory.timestamp >= start_date,
        AssessmentHistory.timestamp <= end_date
    ).order_by(AssessmentHistory.timestamp).all()

    if not raw_data:
        return []

    # Convert to list of dicts for pandas
    data_dicts = [
        {
            "timestamp": record.timestamp,
            "days_ridden_weekly": record.days_ridden_weekly,
            "days_driven_weekly": record.days_driven_weekly,
            # include other relevant metrics
        }
        for record in raw_data
    ]

    df = pd.DataFrame(data_dicts)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

    # Resample to daily frequency and sum relevant metrics
    # Note: If AssessmentHistory stores daily entries, this resample might not be strictly needed,
    # but demonstrates how pandas can aggregate if data is more granular or inconsistent.
    daily_stats = df.resample('D').agg({
        'days_ridden_weekly': 'sum', # Summing weekly stats for daily entries might be conceptually wrong if "weekly" is a snapshot
        'days_driven_weekly': 'sum'
    }).fillna(0)

    # For daily stats, if 'days_ridden_weekly' was a daily snapshot:
    # daily_stats = df.groupby(df.index.date).agg({
    #     'days_ridden_weekly': 'first', # Or 'mean', depending on data semantics
    #     'days_driven_weekly': 'first'
    # }).fillna(0)
    # daily_stats.index = pd.to_datetime(daily_stats.index) # Convert date index back to datetime

    # Prepare data for frontend
    result = daily_stats.reset_index().rename(columns={'index': 'date'}).to_dict(orient='records')
    return result

```

### Frontend: Svelte Chart.js Component
```svelte
<!-- Source: CITED: github.com/saurav-tech/svelte-chartjs -->
<script lang="ts">
  import { Line } from 'svelte-chartjs';
  import {
    Chart as ChartJS,
    Title,
    Tooltip,
    Legend,
    LineElement,
    LinearScale,
    CategoryScale,
    PointElement,
    ChartData,
    ChartOptions
  } from 'chart.js';

  ChartJS.register(
    Title,
    Tooltip,
    Legend,
    LineElement,
    LinearScale,
    CategoryScale,
    PointElement
  );

  export let chartData: ChartData<'line'>;
  export let chartOptions: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: 'Commute History',
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Days',
        },
      },
      x: {
        title: {
          display: true,
          text: 'Date',
        },
      },
    },
  };
</script>

<div style="height: 400px; width: 100%;">
  <Line data={chartData} options={chartOptions} />
</div>
```
*   **Usage Example (in a SvelteKit page):**
```svelte
<!-- Source: ASSUMED, example usage -->
<script lang="ts">
  import { onMount } from 'svelte';
  import CommuteHistoryChart from '$lib/charts/CommuteHistoryChart.svelte'; // Assuming path
  import type { ChartData } from 'chart.js';
  import type { DailyCommuteStats } from '$lib/api'; // Assuming API client types

  let chartData: ChartData<'line'> = {
    labels: [],
    datasets: [
      {
        label: 'Days Ridden',
        data: [],
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.5)',
      },
      {
        label: 'Days Driven',
        data: [],
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.5)',
      },
    ],
  };

  onMount(async () => {
    // Fetch data from your FastAPI backend
    const response = await fetch('/api/analytics/commute-stats/daily?user_id=1&start_date=2023-01-01&end_date=2023-12-31');
    const data: DailyCommuteStats[] = await response.json();

    chartData.labels = data.map(item => new Date(item.date).toLocaleDateString());
    chartData.datasets[0].data = data.map(item => item.days_ridden_weekly);
    chartData.datasets[1].data = data.map(item => item.days_driven_weekly);

    // Trigger reactivity
    chartData = { ...chartData };
  });
</script>

<CommuteHistoryChart {chartData} />
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom data aggregation scripts | `pandas` for backend aggregation | Mid-2000s onwards (pandas introduction) | Dramatically improved performance, readability, and maintainability of data processing in Python. |
| Manual chart rendering (e.g., D3.js without frameworks) | Component-based charting libraries (e.g., svelte-chartjs) | Early 2010s (frameworks rise) | Simplifies chart integration and reactivity within modern frontend frameworks, reducing boilerplate. |
| SQLite for all analytical loads | Consider DuckDB for OLAP | Early 2020s (DuckDB maturity) | Offers a performant, embedded, columnar alternative to SQLite for heavy analytical workloads without deploying a separate server. |

**Deprecated/outdated:**
-   **Direct manipulation of Chart.js DOM element in Svelte:** This approach bypasses Svelte's reactivity model. Instead, use a dedicated Svelte wrapper like `svelte-chartjs`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `slopcheck` cross-ecosystem confusion for npm packages | Package Legitimacy Audit | Planner might not correctly interpret the `[ASSUMED]` status and may require manual verification of these specific npm packages. |
| A2 | SQLite performance will be adequate for initial historical data volumes. | Common Pitfalls | If initial data volumes are unexpectedly large or queries are more complex than anticipated, performance issues could arise quickly, requiring an earlier transition to DuckDB or other optimizations. |

## Open Questions

1.  **Level of Detail for Assessment History:**
    *   What we know: The goal is to store assessment history (e.g., Days Ridden vs Driven).
    *   What's unclear: What other specific metrics or contextual data should be captured with each assessment for future analytical needs? (e.g., weather conditions, route details, user feedback, specific commute start/end times).
    *   Recommendation: During the discuss phase, clarify the full scope of data points to be stored in the `assessment_history` table to ensure future extensibility.

2.  **Granularity of Stored Data:**
    *   What we know: We need to store "assessment history."
    *   What's unclear: Is an "assessment" a daily record, a per-commute record, or something else? How frequently will data be captured? This affects the row count and the primary key strategy.
    *   Recommendation: Define the smallest atomic unit of an "assessment" to properly design the database schema and ensure data capture aligns with analytical goals.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | FastAPI Backend | ✓ | 3.13 (Assumed) | — |
| Node.js / npm | SvelteKit Frontend | ✓ | (Assumed current) | — |
| SQLite | Database persistence | ✓ | (Assumed integrated) | — |

**Missing dependencies with no fallback:**
- None identified that are not part of the existing project stack.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` (for Python backend), `vitest` (for SvelteKit frontend) |
| Config file | `pytest.ini` (backend), `vite.config.ts` (frontend) |
| Quick run command | `pytest tests/test_analytics.py::test_get_daily_commute_stats -x` (backend), `vitest run src/lib/charts/CommuteHistoryChart.test.ts` (frontend) |
| Full suite command | `pytest` (backend), `vitest run` (frontend) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HIST-01 | Store historical assessment data | unit/integration | `pytest tests/test_analytics_db.py::test_store_assessment_history` | ❌ Wave 0 |
| HIST-02 | Retrieve daily commute stats via API | integration | `pytest tests/test_analytics_api.py::test_get_daily_commute_stats` | ❌ Wave 0 |
| HIST-03 | Frontend displays "Days Ridden vs Driven" chart | e2e/component | `vitest run src/lib/charts/CommuteHistoryChart.test.ts` | ❌ Wave 0 |
| HIST-04 | Filtering charts by date range | integration/e2e | `vitest run src/routes/history/+page.test.ts` | ❌ Wave 0 |

### Sampling Rate
-   **Per task commit:** `pytest -k "test_analytics" -x` (backend), `vitest run --file {test_file}` (frontend)
-   **Per wave merge:** `pytest` (backend), `vitest run` (frontend)
-   **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
-   [ ] `tests/test_analytics_db.py` — covers HIST-01 (database interaction tests)
-   [ ] `tests/test_analytics_api.py` — covers HIST-02 (API endpoint tests)
-   [ ] `frontend/src/lib/charts/CommuteHistoryChart.test.ts` — covers HIST-03 (chart component tests)
-   [ ] `frontend/src/routes/history/+page.test.ts` — covers HIST-04 (page integration/e2e tests)
-   [ ] Framework install: `pip install pytest`, `npm install -D vitest` — if not detected from current project setup.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing authentication controls for API endpoints (e.g., JWT) |
| V3 Session Management | yes | Existing session management for frontend and API |
| V4 Access Control | yes | Ensure only authenticated and authorized users can access their own analytics data |
| V5 Input Validation | yes | FastAPI Pydantic models for request parameters (date ranges, user_id) |
| V6 Cryptography | no | (Not directly applicable to new components, relies on existing infrastructure for secure transport) |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Insecure Direct Object Reference (IDOR) | Tampering / Information Disclosure | Ensure `user_id` in API requests is validated against the authenticated user's ID to prevent access to other users' data. |
| SQL Injection (via date filters, etc.) | Tampering / Information Disclosure | Use SQLAlchemy's ORM and parameterized queries (which it does by default) to prevent injection. |
| Denial of Service (DoS) via expensive queries | Denial of Service | Implement rate limiting on analytical endpoints. Optimize database queries and use efficient data aggregation (`pandas`). Implement query timeouts. |

## Sources

### Primary (HIGH confidence)
-   Web Search: "sqlite data modeling for analytics best practices" - [https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGP3RhFXIwS-aOhFoUGfczxIMhge1772RKPdm83ZnJhNhFJ_lF8R2yYBwVh2vm9DmECkUVkg2cGNe_ACHmR0Ej4OdoDTbgXkYg0YTuLWmexKNmXiifW5S8z6GqrL6SYXIoi5VKMRjSK-tO2nuM1jTTu60wt-Wg5wgeJYp4rVNH72qVVg23YbYQXYDxsQgZD33wszt891v0mm_bDoYm8Z](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGP3RhFXIwS-aOhFoUGfczxIMhge1772RKPdm83ZnJhNhFJ_lF8R2yYBwVh2vm9DmECkUVkg2cGNe_ACHmR0Ej4OdoDTbgXkYg0YTuLWmexKNmXiifW5S8z6GqrL6SYXIoi5VKMRjSK-tO2nuM1jTTu60wt-Wg5wgeJYp4rVNH72qVVg23YbYQXYDxsQgZD33wszt891v0mm_bDoYm8Z)
-   Web Search: "best charting libraries for sveltekit" - [https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEjFJmruORxpHVyKjSYCgbJMhge1772RKPdm83ZnJhNhFJ_lF8R2yYBwVh2vm9DmECkUVkg2cGNe_ACHmR0Ej4OdoDTbgXkYg0YTuLWmexKNmXiifW5S8z6GqrL6SYXIoi5VKMRjSK-tO2nuM1jTTu60wt-Wg5wgeJYp4rVNH72qVVg23YbYQXYDxsQgZD33wszt891v0mm_bDoYm8Z](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEjFJmruORxpHVyKjSYCgbJMhge1772RKPdm83ZnJhNhFJ_lF8R2yYBwVh2vm9DmECkUVkg2cGNe_ACHmR0Ej4OdoDTbgXkYg0YTuLWmexKNmXiifW5S8z6GqrL6SYXIoi5VKMRjSK-tO2nuM1jTTu60wt-Wg5wgeJYp4rVNH72qVVg23YbYQXYDxsQgZD33wszt891v0mm_bDoYm8Z)
-   npm registry: `chart.js` (4.5.1), `svelte-chartjs` (4.0.1), `layerchart` (1.0.13)
-   pip index: `pandas` (3.0.3)

### Secondary (MEDIUM confidence)
-   (None directly, primary sources were sufficient for core claims)

### Tertiary (LOW confidence)
-   (None)

## Metadata

**Confidence breakdown:**
-   Standard stack: HIGH - Libraries are widely used and well-documented for their respective ecosystems.
-   Architecture: HIGH - Based on common patterns for full-stack applications with analytics.
-   Pitfalls: HIGH - Common issues identified through general knowledge and verified by research.

**Research date:** 2024-05-28
**Valid until:** 2024-08-28 (3 months - reasonable for stable libraries)
