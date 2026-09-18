# eBay Sales Tracker — Handoff

## What this is
A Flask web app that fetches a seller's completed eBay listings over a date range, lets you select which ones to save to a local SQLite database, and tracks payment status + notes per item.

## Stack
- **Backend**: Python + Flask + SQLAlchemy (SQLite)
- **eBay API**: Finding API (`findCompletedItems`) — no OAuth needed, App ID only
- **Frontend**: Single-page HTML/JS served by Flask (no build step)

## Project structure
```
ebay_sales_tracker/
├── app.py              # Flask app + SQLAlchemy models + API routes
├── ebay_client.py      # eBay Finding API client (pagination, filtering, parsing)
├── templates/
│   └── index.html      # Full UI (vanilla JS, CSS tokens, dark/light theme)
├── requirements.txt
├── .env                # Your secrets (not in git)
└── .env.example        # Template for .env
```

## API routes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves the UI |
| POST | `/api/search` | Search eBay for a seller's sold items |
| GET | `/api/items` | Get all saved items |
| POST | `/api/items` | Save selected items to DB |
| PATCH | `/api/items/<id>` | Update payment_received or notes |
| DELETE | `/api/items/<id>` | Delete a saved item |
| GET | `/api/stats` | Totals: revenue, payment pending count/value |

## DB model (SoldItem)
Fields: `id`, `ebay_item_id`, `title`, `sold_price`, `currency`, `sold_date`, `ebay_link`, `seller`, `condition`, `listing_type`, `payment_received` (bool), `notes`, `created_at`

## Setup & run
```cmd
git clone https://github.com/cempron-brandon/ebay_sales_tracker.git
cd ebay_sales_tracker
pip install -r requirements.txt
```

Create `.env`:
```
EBAY_APP_ID=your-app-id-here
EBAY_ENV=production
```

Start:
```cmd
python app.py
```

Open: http://localhost:5000

## Known working state
- Branch `claude/ebay-seller-items-tracker-dzlv8f` was merged into `main` via PR #1
- The app fetches up to 1000 items (10 pages × 100) per search
- Items already saved to DB are greyed out in search results
- Notes auto-save with a 400ms debounce
- Dark/light theme toggle in the nav bar

## Things you might want to add
- Export to CSV
- Shipping cost field
- Multiple seller tracking
- Profit calculator (purchase price vs sold price)
