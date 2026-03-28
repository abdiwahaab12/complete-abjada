# Tailor Shop Management System

A full-featured tailor shop management system with **HTML frontend** and **Python (Flask) backend**.

## Features

- **Authentication**: Admin / Staff login, JWT, role-based access (Admin, Tailor, Cashier), password reset
- **Customers**: Add, edit, delete, search/filter, measurements, order history
- **Orders**: Create orders, clothing types, fabric, design image upload, delivery date, status workflow
- **Measurements**: Multiple profiles (Men/Women/Kids), history per customer
- **Payments**: Set price, advance/remaining, record payments, **PDF invoice**, daily income report
- **Inventory**: Fabric and accessories, low stock alert, adjust stock
- **Tasks**: Assign order to tailor, progress, completion
- **Dashboard**: Total/pending/completed orders, revenue, monthly chart
- **Reports**: Sales (daily/weekly/monthly), best customers, staff performance
- **Staff**: Admin can add staff (tailor/cashier/admin)

## Setup

### 1. **Install MySQL Database**

Make sure MySQL is installed and running on your system.

### 2. **Create Database**

Connect to MySQL and create the database:

```sql
CREATE DATABASE tailor_db;
```

### 3. **Configure Database Connection**

Edit `config.py` or create a `.env` file with your MySQL credentials:

```env
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/tailor_db
```

Or edit `config.py` directly:
```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/tailor_db'
```

### 4. **Install Dependencies**

```bash
cd tailor
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 5. **Initialize Database**

Run the setup script to create tables and default admin user:

```bash
python database_setup.py
```

Or just run the app (it will auto-create tables):

```bash
python app.py
```

### 6. **Login**

- Open: http://localhost:5000  
- **Email**: `admin@tailor.com`
- **Password**: `admin123`

## Project Structure

```
tailor/
├── app.py              # Flask app, blueprints, init DB
├── config.py           # Configuration
├── extensions.py       # db, bcrypt
├── models.py           # User, Customer, Measurement, Order, Payment, Inventory, Task, Notification
├── requirements.txt
├── routes/
│   ├── auth.py         # Login, JWT, refresh, password reset, staff CRUD
│   ├── customers.py
│   ├── orders.py       # + design image upload
│   ├── measurements.py
│   ├── payments.py     # + PDF invoice
│   ├── inventory.py
│   ├── tasks.py
│   ├── reports.py
│   ├── dashboard.py
│   └── pages.py        # Serve HTML pages
├── utils/
│   └── invoice.py      # PDF invoice (reportlab)
├── templates/          # HTML pages
│   ├── index.html, login.html, dashboard.html
│   ├── customers.html, orders.html, measurements.html
│   ├── payments.html, inventory.html, tasks.html
│   ├── reports.html, staff.html
└── static/
    ├── css/style.css
    ├── js/api.js
    └── uploads/        # Design images
```

## API Overview

| Area        | Endpoints |
|------------|-----------|
| Auth       | `POST /api/auth/login`, `/api/auth/refresh`, `/api/auth/me`, `/api/auth/change-password`, `/api/auth/request-reset`, `/api/auth/reset-password`, `GET/POST /api/auth/staff` |
| Customers  | `GET/POST /api/customers`, `GET/PUT/DELETE /api/customers/:id` |
| Orders     | `GET/POST /api/orders`, `POST /api/orders/upload-design`, `GET/PUT/DELETE /api/orders/:id` |
| Measurements | `GET/POST /api/measurements`, `GET/PUT/DELETE /api/measurements/:id` (query: `customer_id`) |
| Payments   | `GET/POST /api/payments` (query: `order_id`), `GET /api/payments/invoice/:order_id` (PDF) |
| Inventory  | `GET/POST /api/inventory`, `GET/PUT /api/inventory/:id`, `POST /api/inventory/:id/adjust` |
| Tasks      | `GET/POST /api/tasks`, `GET/PUT /api/tasks/:id` (JWT) |
| Reports    | `GET /api/reports/sales?period=`, `GET /api/reports/income?date=`, `GET /api/reports/best-customers`, `GET /api/reports/staff-performance` |
| Dashboard  | `GET /api/dashboard` |

## Optional: Notifications (SMS)

The `Notification` model is in place. To send SMS (order ready, delivery/payment reminders), integrate a provider (e.g. Twilio) in a background task or webhook and create `Notification` records and call the provider API.

## Database

- **MySQL** is the default database (configured in `config.py`)
- Database name: `tailor_db`
- Tables are automatically created on first run
- Default admin user is created automatically:
  - Email: `admin@tailor.com`
  - Password: `admin123`

## Environment Variables

- `SECRET_KEY`, `JWT_SECRET_KEY` – change in production
- `DATABASE_URL` – DB connection string
- `MAIL_*` – for password reset emails (optional)
