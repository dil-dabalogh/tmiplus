import nox


@nox.session
def lint(session):
    session.install("ruff", "black")
    session.run("ruff", "check", ".")
    session.run("black", "--check", ".")


@nox.session
def typecheck(session):
    session.install("mypy")
    session.run("mypy", "tmiplus")


@nox.session
def tests(session):
    session.install(".[dev]")
    session.run("pytest", "--maxfail=1", "--disable-warnings", "-q")


@nox.session
def all(session):
    session.install(".[dev]")
    session.run("ruff", "check", ".")
    session.run("black", "--check", ".")
    session.run("mypy", "tmiplus")
    session.run("pytest", "--maxfail=1", "--disable-warnings", "-q")
