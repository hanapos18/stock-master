# StockMaster - Inventory Management System

## Quick Start

### Requirements
- Python 3.10+
- MariaDB 10.6+ (or MySQL 8.0+)

### Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure database:**
- Copy `.env.example` to `.env` and edit database credentials
- Run the schema: `mysql -u root -p stock_master < database/schema.sql`

3. **Run the app:**
```bash
python run.py
```
Open http://localhost:5556

4. **Login:**
- Default: `admin` / `admin123`

---

## Features

### Common
- Multi-business, multi-store support
- Product & category management
- Supplier management
- Inventory tracking (by location)
- Stock in/out/adjust/discard/move
- Purchase management with inventory integration
- Stock count (physical inventory) reports
- Reports with Excel export

### Restaurant Mode
- Recipe management (menu = N ingredients)
- POS sales integration (auto-deduct by recipe)
- Daily stock count reports
- Cost rate analysis

### Mart / Retail Mode
- Bulk repackaging management
- Wholesale client management (per-client discount pricing)
- Wholesale order with A4 delivery list printing
- Wholesale revenue tracking

### Non-POS Users
- Built-in sales recording
- Sales-based inventory deduction
- A4 delivery list printing

---

## Build Windows EXE

```bash
pyinstaller stock_master.spec --noconfirm
```

Output: `dist/StockMaster/StockMaster.exe`

---

## Cloud Deployment

### Nginx + Gunicorn (Linux)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5556 "app:create_app()"
```

### Nginx config:
```nginx
server {
    listen 80;
    server_name stockmaster.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5556;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static {
        alias /path/to/stock-master/app/static;
    }
}
```

### SSL with Certbot:
```bash
sudo certbot --nginx -d stockmaster.yourdomain.com
```

---

## Project Structure

```
stock-master/
  run.py                 # Entry point
  config.py              # Configuration
  .env                   # Environment variables
  database/schema.sql    # MariaDB schema (21 tables)
  app/
    __init__.py          # Flask factory
    db.py                # Database helper
    controllers/         # Business logic (12 modules)
    routes/              # Flask routes (13 blueprints)
    services/            # Shared services
    templates/           # Jinja2 HTML (40+ templates)
    static/              # CSS, JS
```

## Tech Stack
- **Backend**: Flask (Python)
- **Database**: MariaDB (PyMySQL)
- **Frontend**: Bootstrap 5 + Jinja2
- **Excel**: openpyxl
- **Build**: PyInstaller
