"""
MarketMinds - Demo Account Seeder
------------------------------------
Creates a single demo farmer account so you can log in immediately without
registering by hand. Safe to run multiple times -- it skips creation if the
demo account already exists.

Run:  python utils/create_demo_user.py

Demo login:
    Email:    demo@marketminds.test
    Password: demo1234
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

DEMO_EMAIL = "demo@marketminds.test"
DEMO_MOBILE = "9876543210"
DEMO_PASSWORD = "demo1234"


def main():
    # Imported here (not at module level) so this script can be run standalone
    # without triggering app.py's own startup side effects twice.
    from app import app, db, Farmer

    with app.app_context():
        existing = Farmer.query.filter_by(email=DEMO_EMAIL).first()
        if existing:
            print(f"Demo account already exists: {DEMO_EMAIL}")
            return

        farmer = Farmer(
            full_name="Demo Farmer",
            mobile=DEMO_MOBILE,
            email=DEMO_EMAIL,
            state="Uttar Pradesh",
            district="Agra",
            village="Bichpuri",
            language="Hindi",
        )
        farmer.set_password(DEMO_PASSWORD)
        db.session.add(farmer)
        db.session.commit()

        print("Demo account created successfully:")
        print(f"  Email:    {DEMO_EMAIL}")
        print(f"  Mobile:   {DEMO_MOBILE}")
        print(f"  Password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
