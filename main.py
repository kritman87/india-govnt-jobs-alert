
import asyncio
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="India Govt Jobs Alert API",
    description="Government job notification tracker",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "jobs.db"

KEYWORDS = [
    "recruitment",
    "vacancy",
    "notification",
    "advertisement",
    "apply online",
    "job",
    "apprentice",
    "examination"
]

SOURCES = [
    {
        "name": "UPSC",
        "url": "https://upsc.gov.in/"
    },
    {
        "name": "SSC",
        "url": "https://ssc.gov.in/"
    },
    {
        "name": "Railway",
        "url": "https://indianrailways.gov.in/"
    },
    {
        "name": "National Career Service",
        "url": "https://www.ncs.gov.in/"
    },
    {
        "name": "Employment News",
        "url": "https://employmentnews.gov.in/"
    },
    {
        "name": "UPPSC",
        "url": "https://uppsc.up.nic.in/"
    },
    {
        "name": "UPSSSC",
        "url": "https://upsssc.gov.in/"
    },
    {
        "name": "MPSC",
        "url": "https://mpsc.gov.in/"
    }
]


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def create_database():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            source TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def scan_website(source):
    found = []

    try:
        response = requests.get(
            source["url"],
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for link in soup.find_all("a", href=True):
            title = link.get_text(" ", strip=True)
            url = urljoin(source["url"], link["href"])

            if not title or len(title) < 5:
                continue

            if any(word in title.lower() for word in KEYWORDS):
                found.append({
                    "title": title[:300],
                    "url": url,
                    "source": source["name"]
                })

    except requests.RequestException as error:
        print(f"Scan failed for {source['name']}: {error}")

    return found


def save_notices(notices):
    conn = get_connection()
    saved = 0

    for notice in notices:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO notices
                (title, url, source, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    notice["title"],
                    notice["url"],
                    notice["source"],
                    datetime.now(timezone.utc).isoformat()
                )
            )

            if conn.total_changes > 0:
                saved += 1

        except sqlite3.Error as error:
            print("Database error:", error)

    conn.commit()
    conn.close()

    return saved


def run_scan():
    all_notices = []

    for source in SOURCES:
        notices = scan_website(source)
        all_notices.extend(notices)

    return save_notices(all_notices)


@app.on_event("startup")
async def startup_event():
    create_database()


@app.get("/")
def home():
    return {
        "status": "online",
        "message": "India Govt Jobs Alert API is running"
    }


@app.get("/api/sources")
def get_sources():
    return {
        "total": len(SOURCES),
        "sources": SOURCES
    }


@app.get("/api/notices")
def get_notices(limit: int = 100):
    limit = max(1, min(limit, 500))

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT id, title, url, source, created_at
        FROM notices
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()

    conn.close()

    return {
        "total": len(rows),
        "notices": [dict(row) for row in rows]
    }


@app.post("/api/scan-now")
def scan_now():
    saved = run_scan()

    return {
        "status": "completed",
        "new_notices_saved": saved
    }


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "time": datetime.now(timezone.utc).isoformat()
    }
