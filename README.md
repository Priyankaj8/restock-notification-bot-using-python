# 🛒 Restock Notification Bot

A full-stack, real-time product monitoring and notification system built using **Python, FastAPI, SQLite, and BeautifulSoup**. This tool tracks product restock availability via web scraping and sends instant email alerts, supporting both CLI and web interfaces.

---

## 🚀 Features

- 🔍 **Web Scraping Engine**: Tracks product availability using CSS selectors and BeautifulSoup.
- 🧠 **Asynchronous Background Monitoring**: FastAPI background tasks with real-time database polling.
- 💌 **Email Notifications**: Sends alerts instantly via SMTP when products are restocked.
- 🖥️ **Dual Interfaces**:
  - **CLI Application** for lightweight monitoring
  - **FastAPI Web Dashboard** for user-friendly control
- 🔐 **User Management**: Add/remove tracked products, configure intervals, and manage user emails.
- 📦 **Product Lifecycle Automation**: Auto-deactivates products post-notification.
- 🧾 **Logging and Error Handling**: Robust error reporting with detailed logs.

---

## 🖼️ Screenshots

> Replace these with actual screenshots

### Web Dashboard
<img width="1899" height="1033" alt="image" src="https://github.com/user-attachments/assets/8a879314-512d-4958-bfc0-5893883b628a" />

### Email Notification
<img width="501" height="323" alt="Screenshot 2025-07-26 203127" src="https://github.com/user-attachments/assets/5a190be5-4de1-47fa-967d-2f8c806062dd" />

### CLI Monitoring
<img width="1909" height="1038" alt="image" src="https://github.com/user-attachments/assets/8e8cd754-bc7a-4fb7-b4a3-d1698ad2e453" />
<img width="1920" height="1032" alt="image" src="https://github.com/user-attachments/assets/8c38f441-b560-4763-adbe-b5f143ef5310" />

---

## ⚙️ Setup Instructions

1. **Clone the repo**
   ```bash
   git clone https://github.com/yourusername/restock-notification-bot.git
   cd restock-notification-bot
