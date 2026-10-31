"""Build the GitHub Pages site from the checked-out trusted branch."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def build_pages(repository, output_directory):
    if output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True)

    subprocess.run([sys.executable, "generate_stats_page.py"], cwd=repository, check=True)
    generated_docs = repository / "docs"
    if not (generated_docs / "index.html").is_file():
        raise FileNotFoundError("The build did not generate docs/index.html")
    shutil.copytree(generated_docs, output_directory, dirs_exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("_site"))
    arguments = parser.parse_args()

    repository = Path(__file__).resolve().parents[2]
    output_directory = arguments.output.resolve()
    build_pages(repository, output_directory)


if __name__ == "__main__":
    main()