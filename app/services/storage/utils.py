from contextlib import contextmanager


@contextmanager
def session_scope(sessionmaker):
    """Provide a transactional scope around a series of operations."""
    session = sessionmaker()
    try:
        yield session
        session.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
        session.rollback()
        raise
    finally:
        session.close()
