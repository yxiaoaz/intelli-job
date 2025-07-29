from contextlib import contextmanager

@contextmanager
def session_scope(sessionmaker):
    """Provide a transactional scope around a series of operations."""
    session = sessionmaker()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
