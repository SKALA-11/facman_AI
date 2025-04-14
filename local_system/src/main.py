from core import FacmanApplication
# db_migration.py 모듈 가져오기
from db_migration import main as db_main


def main():
    app = FacmanApplication()
    app.start()


if __name__ == "__main__":
    main()
    db_main()
    
