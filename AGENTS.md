# AGENTS.md

## Project Overview

Vinted-Scraper is a Python tool to download images and scrape data from Vinted & Depop, storing it in a SQLite database.

## Language & Dependencies

- **Language**: Python
- **Main entry**: `scraper.py`
- **Dependencies**: `cloudscraper==1.2.71`, `requests==2.32.5`, `black==26.1.0`
- **Install**: `pip install -r requirements.txt`

## Code Style

- **Formatter**: Black
- **Line length**: 88
- **Target version**: Python 3.14

## Running the Scraper

```bash
python scraper.py [options]
```

### Arguments

| Flag | Platform | Description |
|------|----------|-------------|
| `-p` | Vinted | Scrape images from private messages (requires `-s` and `-u`) |
| `-s "session"` | Vinted | Login with Vinted session ID |
| `-u` | Vinted | Set user ID |
| `-i N` | Vinted | Max images to download per product (min 1) |
| `-d` | Depop | Enable Depop mode |
| `-n` | Depop | Disable file download (scrape only) |
| `-g` | Depop | Also download sold items |
| `-b "item"` | Depop | Start from specific item |

## Database

- **File**: `data.sqlite`
- **Tables**: Vinted Users, Vinted Products, Depop Users, Depop Products

## Database Changes

When modifying SQL statements (CREATE TABLE, INSERT, ALTER):
- Ensure existing users with existing databases are not affected
- If changes would break existing users, ask the user for one of:
  1. Introduce migrations (add logic to alter tables on startup if needed)
  2. Revert the changes
  3. Continue with the changes (user accepts breaking change)

## Notes

- User IDs are stored in `users.txt`
- Downloaded images are stored in `downloads/`
