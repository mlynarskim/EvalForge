from app.database import SessionLocal, create_schema
from app.services.demo_service import seed_demo


def main() -> None:
    create_schema()
    with SessionLocal() as db:
        seed_demo(db)


if __name__ == "__main__":
    main()
