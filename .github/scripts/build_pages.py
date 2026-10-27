"""Build and assemble a GitHub Pages site from every remote branch."""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


STATIC_DOC_FILES = (".nojekyll", "logo.png", "README.md", "index.html")


def run(command, cwd):
    subprocess.run(command, cwd=cwd, check=True)


def get_remote_branches(repository):
    run(
        ["git", "fetch", "--prune", "origin", "+refs/heads/*:refs/remotes/origin/*"],
        repository,
    )
    result = subprocess.run(
        [
            "git",
            "for-each-ref",
            "--format=%(refname:strip=3)",
            "refs/remotes/origin/",
        ],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(branch for branch in result.stdout.splitlines() if branch != "HEAD")


def reset_docs_directory(repository):
    docs_directory = repository / "docs"
    preserved_files = {
        name: docs_directory / name
        for name in STATIC_DOC_FILES
        if (docs_directory / name).is_file()
    }
    temporary_files = {}
    for name, path in preserved_files.items():
        temporary_path = repository / f".{name}.pages-static"
        shutil.copy2(path, temporary_path)
        temporary_files[name] = temporary_path

    if docs_directory.exists():
        shutil.rmtree(docs_directory)
    docs_directory.mkdir(parents=True)

    for name, temporary_path in temporary_files.items():
        shutil.move(temporary_path, docs_directory / name)


def branch_site_path(branch):
    parts = branch.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"Unsafe branch name for a Pages path: {branch!r}")
    return Path(*parts)


def build_pages(repository, default_branch, output_directory):
    branches = get_remote_branches(repository)
    if default_branch not in branches:
        raise ValueError(f"Default branch {default_branch!r} was not fetched from origin")

    if output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True)

    with tempfile.TemporaryDirectory(prefix="oofs-pages-worktrees-") as temporary_directory:
        worktree_root = Path(temporary_directory)
        for index, branch in enumerate(branches):
            worktree = worktree_root / f"branch-{index}"
            branch_ref = f"refs/remotes/origin/{branch}"
            run(["git", "worktree", "add", "--detach", str(worktree), branch_ref], repository)
            try:
                reset_docs_directory(worktree)
                run([sys.executable, "generate_stats_page.py"], worktree)

                generated_docs = worktree / "docs"
                if not (generated_docs / "index.html").is_file():
                    raise FileNotFoundError(f"The {branch!r} build did not generate docs/index.html")

                if branch == default_branch:
                    destination = output_directory
                else:
                    destination = output_directory / branch_site_path(branch)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(generated_docs, destination, dirs_exist_ok=True)
            finally:
                run(["git", "worktree", "remove", "--force", str(worktree)], repository)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--default-branch", required=True)
    parser.add_argument("--output", type=Path, default=Path("_site"))
    arguments = parser.parse_args()

    repository = Path(__file__).resolve().parents[2]
    output_directory = arguments.output.resolve()
    build_pages(repository, arguments.default_branch, output_directory)


if __name__ == "__main__":
    main()