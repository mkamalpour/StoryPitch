# db/seed_data.py
from db.db import init_db, create_user, create_session

def seed():
    init_db()
    u = create_user("tester")
    s = create_session(u.id, title="Seed: Mysterious School", world_state={"theme":"mysterious school","traits":["brave","curious"]})
    print("Seeded user", u.id, "session", s.id)

if __name__ == "__main__":
    seed()
