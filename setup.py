from setuptools import find_packages, setup

setup(
    name="mail-organizer",
    version="0.1.0",
    description="Intelligente E-Mail-Verwaltung mit lokaler Ollama-LLM-Integration",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.11",
    install_requires=[
        "PyQt6>=6.6.0",
        "imapclient>=3.0.0",
        "requests>=2.31.0",
        "SQLAlchemy>=2.0.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "cryptography>=42.0.0",
        "alembic>=1.13.0",
    ],
    entry_points={
        "console_scripts": [
            "mailorganizer=mailorganizer.main:main",
        ],
    },
)
