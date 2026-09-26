"""Isolated, mocked browser acceptance fixture; never uses the development database."""
from pathlib import Path
from tempfile import TemporaryDirectory
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import create_app
from app.database import get_db
from tests.test_reports import completed

with TemporaryDirectory(prefix='interview-ui-') as folder:
    engine = create_engine(f"sqlite:///{Path(folder) / 'browser.db'}", connect_args={'check_same_thread': False})
    sessions = sessionmaker(bind=engine)
    app = create_app(engine)
    def database():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        client.test_sessions = sessions
        completed(client, 'recruiter', 'CHANGE_CONSTRAINT')
        completed(client, 'practice', 'TEACH_NEW_CHALLENGE')
    uvicorn.run(app, host='127.0.0.1', port=8002)
