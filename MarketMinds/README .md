# MarketMinds 🌾

**Smarter Markets. Better Decisions for Farmers.**

MarketMinds is an AI-powered agricultural market intelligence and decision-support platform built as a prototype for helping farmers make better selling decisions.

Instead of recommending a market only because it offers the highest crop price, MarketMinds considers **expected revenue, transportation cost, storage cost, other charges, market trends, buyer requirements, and farmer preferences** to identify the most practical and profitable option.

> **Tagline:** Detect. Assess. Decide.  
> **Project:** MarketMinds – AI-Powered Agricultural Market Intelligence Platform

---

## 📌 Problem Statement

Farmers often sell their produce based on the nearest mandi or the highest quoted price. However, the highest price does not always result in the highest profit.

For example, a market offering a higher price may also have:

- Higher transportation costs
- Higher storage costs
- Longer waiting periods
- Additional charges
- Less suitable buyers
- Greater price uncertainty

MarketMinds addresses this problem by calculating **expected net profit** and combining market intelligence with buyer matching and price forecasting.

---

## 💡 Core Idea

The platform follows:

```text
Expected Net Profit
= Expected Revenue
  − Transport Cost
  − Storage Cost
  − Other Charges
```

The goal is to help answer five practical questions:

1. **Where should I sell my crop?**
2. **Which market can give me the highest expected net profit?**
3. **Should I sell now or wait?**
4. **Which buyer is the best match for my crop?**
5. **Can I combine my produce with other farmers through an FPO?**

---

## ✨ Key Features

### 👨‍🌾 Farmer Account Management
- Farmer registration and login
- Password hashing using Werkzeug
- Farmer profile management
- State, district, village and preferred language
- Session-based authentication

### 📊 Market Intelligence
- Crop and quantity based market search
- Mandi price history
- Minimum, maximum and modal prices
- Market comparison
- Price trend visualization
- Distance-aware market analysis

### 🤖 AI Price Forecasting
- Random Forest Regression model
- Historical price-based features
- Previous-day price feature
- Time-based train/test split
- Model saved using Joblib
- Historical-trend fallback if the ML model is unavailable

### 💰 Profit-Based Recommendation
Market ranking considers:

- Expected crop revenue
- Transportation cost
- Storage cost
- Other charges
- Waiting period
- Expected net profit

The recommendation is therefore based on **profit rather than price alone**.

### ⏳ Sell Now vs Wait
The system compares:

```text
Profit If Sold Now
vs.
Expected Profit If Waiting
```

It considers predicted price and storage/perishability effects before producing a recommendation.

### 🤝 Buyer Matching
Buyers are ranked using an explainable scoring system based on:

| Factor | Score |
|---|---:|
| Crop Match | 25 |
| Quality Match | 15 |
| Quantity Compatibility | 15 |
| Price Score | 20 |
| Distance Score | 10 |

### 🌾 FPO Aggregation
Farmers can be grouped conceptually through an FPO-style aggregation workflow to help fulfill larger buyer requirements.

### 💳 Transaction Tracking
The prototype includes a transaction record with:

- Buyer
- Crop
- Quantity
- Price
- Market
- Transaction status
- Payment status

**Important:** This is only a prototype tracking system. No real payment is processed.

### 📚 Search History
Each farmer's searches are stored separately so previous recommendations can be reviewed later.

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Backend | Python, Flask |
| Database | SQLite |
| ORM | Flask-SQLAlchemy |
| Data Processing | Pandas, NumPy |
| Machine Learning | Scikit-learn |
| Model Serialization | Joblib |
| Authentication | Flask Sessions + Werkzeug |
| Charts | Chart.js |
| Configuration | python-dotenv |

---

## 📁 Project Structure

```text
MarketMinds/
│
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── .env.example
│
├── data/
│   ├── mandi_prices.csv
│   ├── buyers.csv
│   └── farmers.csv
│
├── models/
│   └── price_model.pkl
│
├── utils/
│   ├── __init__.py
│   ├── generate_data.py
│   ├── train_model.py
│   ├── create_demo_user.py
│   ├── data_processor.py
│   ├── recommendation_engine.py
│   ├── sell_decision.py
│   └── buyer_matching.py
│
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── about.html
│   ├── register.html
│   ├── login.html
│   ├── profile.html
│   ├── dashboard.html
│   ├── market.html
│   ├── recommendation.html
│   ├── buyers.html
│   ├── fpo.html
│   ├── payment.html
│   └── history.html
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── script.js
│
└── instance/
    └── marketminds.db
```

---

## ⚙️ Installation

### 1. Clone or open the project

Open the `MarketMinds` folder in VS Code.

### 2. Create a virtual environment

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

For macOS/Linux:

```bash
cp .env.example .env
```

Set a secure secret key in `.env`:

```env
MARKETMINDS_SECRET_KEY=your-secret-key
```

---

## ▶️ Running the Application

From the project root:

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

The application automatically:

- Creates the SQLite database if required
- Creates database tables
- Generates demo datasets if they are missing
- Trains the price model if it is missing
- Uses the historical-trend fallback if model training/loading fails

No separate database setup is required for the prototype.

---

## 👤 Demo Account

To create a ready-made demo farmer account:

```bash
python utils/create_demo_user.py
```

Demo credentials:

```text
Email:    demo@marketminds.test
Mobile:   9876543210
Password: demo1234
```

You can also create your own account through the registration page.

---

## 📂 Dataset

The prototype currently uses **synthetically generated demo data**.

### `mandi_prices.csv`

Contains sample mandi price history with fields such as:

```text
Arrival_Date
State
District
Market
Commodity
Variety
Min_Price
Max_Price
Modal_Price
Distance_KM
```

### `buyers.csv`

Contains demo buyer information:

```text
Buyer_ID
Buyer_Name
Crop
Quantity_Required
Quality
Price_Offered
Location
Distance_KM
Payment_Score
Dispute_Score
Verified
Contact_Phone
Contact_Email
```

### `farmers.csv`

Contains demo farmer/FPO data:

```text
Farmer_ID
Farmer_Name
Crop
Quantity
Quality
Location
```

> ⚠️ These datasets are synthetic and are intended only for demonstration and prototype testing.

---

## 🤖 Machine Learning Model

MarketMinds uses a **RandomForestRegressor** for price forecasting.

### Input features

The model uses:

- Month
- Day
- Day of week
- Previous day's price
- Market
- Commodity

The data is sorted chronologically by crop and market before calculating the previous-day price.

### Train/Test Strategy

A time-based split is used:

```text
Earlier 80% → Training
Recent 20%  → Testing
```

This is preferable to a random split for time-series-like price data because it better represents predicting future prices from past information.

### Model File

The trained model is stored as:

```text
models/price_model.pkl
```

Joblib is used to serialize the model and its associated encoders.

### Fallback System

If the trained model is unavailable, corrupted, or cannot handle a requested crop/market combination, MarketMinds uses a transparent historical-trend prediction instead.

This allows the application to continue functioning even when the ML model is unavailable.

---

## 💰 Recommendation Logic

For each relevant market, MarketMinds calculates:

```text
Expected Revenue
= Predicted Price × Quantity
```

```text
Transport Cost
= Distance × Transport Cost Per KM Per Quintal × Quantity
```

```text
Storage Cost
= Quantity × Storage Cost Per Quintal Per Day × Waiting Days
```

```text
Other Charges
= Flat Charges + Per-Quintal Charges × Quantity
```

Finally:

```text
Expected Net Profit
= Expected Revenue
  − Transport Cost
  − Storage Cost
  − Other Charges
```

Markets are then ranked according to expected net profit.

---

## ⏳ Sell Now vs Wait

The system compares:

```text
Profit If Sold Now
=
Current Price × Quantity
```

with:

```text
Expected Profit If Waiting
=
Predicted Future Price × Quantity
− Storage Cost
```

Crop perishability is also considered.

Example:

```text
Tomato → higher perishability
Wheat  → lower perishability
```

The system then provides:

```text
SELL NOW
```

or

```text
WAIT
```

along with the financial reasoning behind the decision.

---

## 🤝 Buyer Matching Algorithm

Buyer matching uses a deterministic weighted score.

```text
Total Score = 100 points
```

| Matching Factor | Maximum Points |
|---|---:|
| Crop Match | 25 |
| Quality Match | 15 |
| Quantity Compatibility | 15 |
| Price Score | 20 |
| Distance Score | 10 |

The resulting ranking is explainable rather than being a random recommendation.

---

## 🌾 FPO Workflow

The FPO module demonstrates how individual farmer produce can be aggregated.

Example:

```text
Farmer A → 5 Quintals
Farmer B → 7 Quintals
Farmer C → 4 Quintals
             ↓
        FPO Aggregation
             ↓
        16 Quintals
             ↓
      Large Buyer Demand
```

This can help demonstrate how collective selling may make larger buyer opportunities possible.

---

## 🔐 Security

The prototype includes:

- Password hashing
- Session-based authentication
- Login-protected routes
- Farmer-specific search history
- SQLAlchemy ORM instead of raw SQL
- Environment-based secret-key configuration

For production deployment, additional security hardening would be required.

---

## 📈 Application Flow

```text
                    ┌───────────────┐
                    │     Farmer    │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │ Register/Login│
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │ Farmer Profile│
                    └───────┬───────┘
                            ↓
                  ┌────────────────────┐
                  │ Enter Crop Details │
                  └──────────┬─────────┘
                             ↓
                  ┌────────────────────┐
                  │ Market Intelligence│
                  └──────────┬─────────┘
                             ↓
              ┌─────────────────────────────┐
              │ AI Price Forecast + Ranking │
              └──────────────┬──────────────┘
                             ↓
               ┌──────────────────────────┐
               │ Best Market Recommendation│
               └────────────┬─────────────┘
                            ↓
                 ┌─────────────────────┐
                 │ Sell Now vs Wait    │
                 └──────────┬──────────┘
                            ↓
                  ┌───────────────────┐
                  │ Buyer Matching    │
                  └─────────┬─────────┘
                            ↓
                  ┌───────────────────┐
                  │ FPO Aggregation   │
                  └─────────┬─────────┘
                            ↓
                  ┌───────────────────┐
                  │ Transaction Record│
                  └───────────────────┘
```

---

## 🔄 Future Scope

MarketMinds is currently a prototype. Possible production improvements include:

### Live Agricultural Data
Integrate authorized government/agricultural data sources such as:

- AGMARKNET
- data.gov.in
- State agricultural market APIs

### Real-Time Distance & Logistics
Integrate mapping APIs for:

- Accurate route distance
- Transport cost estimation
- Travel time
- Logistics recommendations

### Advanced ML
Future models could include:

- XGBoost
- Gradient Boosting
- Time-series forecasting
- Crop-specific models
- Weather-aware forecasting
- Seasonal trend modelling

### Real Buyer Accounts
Replace the static buyer dataset with:

- Buyer registration
- Buyer verification
- Buyer dashboard
- Live offers
- Demand posting
- Offer negotiation

### Notifications
Add:

- SMS alerts
- WhatsApp notifications
- Email notifications
- Price alerts
- Buyer demand alerts

### Payments
Integrate a real payment/settlement system in a production environment.

### Multilingual Interface
The current system stores the farmer's preferred language. A future version can provide complete multilingual UI and localized recommendations.

---

## ⚠️ Prototype Disclaimer

MarketMinds is a **student/prototype project**.

The current version uses synthetic/demo market, buyer, and farmer data. Price predictions and profit recommendations are for demonstration purposes only.

**The platform should not be used as a source for real agricultural trading, investment, or financial decisions.**

---

## 👨‍💻 Project

**MarketMinds**

**AI-Powered Agricultural Market Intelligence Platform**

Built using:

```text
HTML + CSS + JavaScript
        +
Python + Flask
        +
SQLite + SQLAlchemy
        +
Pandas + NumPy
        +
Scikit-learn + Joblib
        +
Chart.js
```

**Smarter Markets. Better Decisions for Farmers. 🌾**
