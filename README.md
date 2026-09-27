# 💳 Smart Billing Validator

A full-featured **Billing Validation & Decision Support System** built with **Python (Flask)**, **SQLite**, and modern **Vanilla HTML/CSS/JS**. It automates bill audit trails, detects anomalies, calculates tax discrepancies, flags duplicate line items, and generates intelligent recommendations.

---

## 🚀 Features

- **📊 Interactive Dashboard**: High-level metrics, validation rates, anomaly breakdown, and real-time activity feed.
- **🔍 Multi-Rule Validation Engine**:
  - **Duplicate Item Detection**: Identifies repetitive product lines in the same invoice.
  - **Price Drift & Discrepancy**: Validates billed unit prices against catalog reference prices.
  - **Tax & Calculation Integrity**: Verifies line item math, subtotal additions, and tax applications.
  - **Suspicious Total / Anomaly Alerts**: Flags statistical outliers and excessive single transactions.
- **💡 Decision Support Recommendations**: Actionable insights and suggested corrections for flagged invoices.
- **➕ Bill Builder**: Interactive interface to construct and simulate bills with multi-product line items.
- **📦 Product Catalog Management**: CRUD management for inventory items, standard base prices, and tax rates.
- **📈 Reporting & Exports**: Comprehensive audit logs and analytical summaries.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.8+, Flask, SQLite3
- **Architecture**: Object-Oriented Design (OOP), Abstract Base Classes (ABC), Polymorphic Validation Rules, Decorator patterns
- **Frontend**: Responsive Vanilla CSS, Modern Glassmorphism aesthetic, Vanilla JavaScript (Fetch API)
- **Database**: SQLite3 (`billing_validator.db`)

---

## 📁 Project Structure

```
Smart Billing Validator/
├── app.py                 # Flask server, database layer, OOP models, validation engine
├── billing_validator.db   # SQLite database (auto-created on startup)
├── requirements.txt       # Python dependencies
├── static/
│   ├── style.css          # Design system, layout, and component styling
│   └── script.js          # Client-side routing, API integration, and DOM updates
├── templates/
│   └── index.html         # Main single-page application template
├── exports/               # Export reports & generated audit files
└── .gitignore             # Ignored files (database, caches, envs)
```

---

## ⚡ Getting Started

### 1. Prerequisites
- Python 3.8 or higher installed on your system.
- Git.

### 2. Clone the Repository
```bash
git clone <your-repository-url>
cd "Smart Billing Validator"
```

### 3. Set Up Virtual Environment (Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Run the Application
```bash
python app.py
```

Open your browser and navigate to:
```
http://localhost:5000
```

---

## 📜 License
This project is licensed under the MIT License.
