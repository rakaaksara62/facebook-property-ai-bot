# Real Estate Intelligence Bot: Facebook Scraper + Gemini AI + Telegram Alerts

An automated, end-to-end Property Monitoring Engine built with Python, Playwright, Google Gemini AI, and Telegram Bot API. 

The system continuously scans target Facebook Groups, bypasses dynamic login walls, uses Gemini AI to evaluate and score property listings in real-time, and pushes structured alerts with photo attachments directly to Telegram.

---

## Key Features

- Automated Web Scraping: Uses Playwright with session state persistence (storage_state) to maintain Facebook login context without triggering re-authentication.
- AI-Powered Evaluation: Integrates Google Gemini 3.5 Flash to parse unstructured post text, detect listing viability, extract metrics (Price, Location, Property Type), and calculate a Potential Score (1-10).
- Real-Time Telegram Alerts: Delivers formatted Markdown alerts containing key parameters, AI summary, original listing URLs, and direct photo previews via Telegram Bot.
- Anti-Duplication Engine: Implements a localized JSON hashing history to ensure same posts are never alert-triggered twice.
- Robust Scheduling: Equipped with a loop scheduler running periodic background checks.

---

## Tech Stack

- Language: Python 3.x
- Automation: Playwright (Python Sync API)
- Artificial Intelligence: Google GenAI SDK (gemini-3.5-flash)
- Notification Engine: Telegram Bot API (requests)
- Environment Management: python-dotenv

---

## Installation & Setup

### 1. Clone the Repository
```bash
git clone [https://github.com/rakaaksara62/facebook-property-ai-bot.git](https://github.com/rakaaksara62/facebook-property-ai-bot.git)
cd facebook-property-ai-bot
```
### 2. Create Virtual Environment & Install Dependencies
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```
### 3. Configure Environment Variables
Copy .env.example to .env and fill in your credentials:

```bash
cp .env.example .env
```
### 4. Save Facebook Login Session
Run the session saver script to log in to Facebook manually and save your authentication cookies into fb_state.json:

```bash
python save_session.py
```
A browser window will open. Log in to your Facebook account, wait for the homepage to load completely, and then close the browser to save the state.

### 5. Run the Main Application
Start the background scraper engine:

```bash
python main_bot.py
```