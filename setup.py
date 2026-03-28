from setuptools import find_packages, setup  # type: ignore

setup(
    name="hanson",
    version="0.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "authlib>=1.3",
        "click",
        "flask>=3.0",
        "httpx",
        "jinja2",
        "psycopg2",
        "requests",
        "waitress",
    ],
    scripts=[
        "app.py",
        "cli.py",
    ],
)
