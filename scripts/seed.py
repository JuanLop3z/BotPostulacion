"""Load synthetic jobs into the personal workspace; no real application is sent."""
import argparse

from app.database.session import SessionLocal
from app.models import SearchRun
from app.services.workspace import get_local_user
from app.services.search_pipeline import process_search


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar vacantes de prueba en el espacio personal local")
    parser.parse_args()
    with SessionLocal() as db:
        user = get_local_user(db)
        run = SearchRun(user_id=user.id, source="demo", query="")
        db.add(run)
        db.commit()
        run_id = run.id
    print(process_search(run_id))


if __name__ == "__main__":
    main()
