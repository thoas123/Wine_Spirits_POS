# Trevor and Jed Wines & Spirits POS

A centralized web-based Point of Sale and Business Management System for a wine and spirits business operating multiple shops.

## Current Stage

**Step 1: Project Foundation** — Django project initialized with custom user model, base templates, and environment-aware configuration. No business modules implemented yet.

## Technology Stack

- **Backend:** Python, Django 6.1
- **Frontend:** Django Templates, HTML, CSS, JavaScript
- **Database:** SQLite (development), PostgreSQL (production)

## Setup

### 1. Create and activate virtual environment

```bash
# Create
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment (optional for development)

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your settings (SQLite works out of the box)
```

### 4. Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Create a superuser

```bash
python manage.py createsuperuser
```

### 6. Start the development server

```bash
python manage.py runserver
```

Visit [http://127.0.0.1:8000](http://127.0.0.1:8000) to access the application.

## Project Structure

```
Wine_Spirits_POS/
├── manage.py              # Django management script
├── config/                # Project configuration
│   ├── settings.py        # Environment-aware settings
│   ├── urls.py            # Root URL configuration
│   ├── wsgi.py            # WSGI entry point
│   └── asgi.py            # ASGI entry point
├── accounts/              # Custom user model & authentication
├── core/                  # Shared functionality & home view
├── templates/             # Project-level templates
│   ├── base.html          # Base template
│   ├── home.html          # Home page placeholder
│   └── registration/      # Auth templates
│       └── login.html     # Login page
├── static/                # Static files (CSS, JS, images)
│   └── css/
│       └── style.css      # Base stylesheet
├── .env.example           # Environment variable template
├── .gitignore             # Git ignore rules
├── requirements.txt       # Python dependencies
└── README.md              # This file
```
