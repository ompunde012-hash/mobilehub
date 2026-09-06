MobileHub Professional
======================

Cleaned from the latest MobileHub v3 section of the supplied source.
Duplicate older app versions were removed.

Features in this version include authentication, product search/filter/sort,
product details, stock-aware cart, wishlist, checkout, orders/order details,
reviews, profile, admin product/order management, CSRF protection, and
optional Razorpay integration.

Windows setup
-------------
1. Open this folder in VS Code.
2. Create virtual environment:
   py -m venv venv
3. Activate:
   venv\Scripts\activate
4. Install:
   pip install -r requirements.txt
5. Optional: copy .env.example to .env and set your Razorpay credentials.
6. Run:
   py app.py
7. Open:
   http://127.0.0.1:5000

Default admin shown by the supplied source:
Email: admin@gmail.com
Password: admin123

IMPORTANT:
- Change the admin password before real deployment.
- Set SECRET_KEY to a strong random value in production.
- Razorpay stays in demo mode unless both Razorpay environment variables are set.
- The app uses SQLite (shop.db) and creates/migrates its tables at startup.
