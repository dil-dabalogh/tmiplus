import nox


@nox.session
def lint(session: nox.Session) -> None:
    session.install("ruff", "black")
    session.run("ruff", "check", ".")
    session.run("black", "--check", ".")


@nox.session
def typecheck(session: nox.Session) -> None:
    session.install(".[dev]")
    session.run("mypy", ".")


@nox.session
def tests(session: nox.Session) -> None:
    session.install(".[dev]")
    session.run("pytest", "--maxfail=1", "--disable-warnings", "-q")


@nox.session
def all(session: nox.Session) -> None:
    session.install(".[dev]")
    session.run("ruff", "check", ".")
    session.run("black", "--check", ".")
    session.run("mypy", ".")
    session.run("pytest", "--maxfail=1", "--disable-warnings", "-q")
