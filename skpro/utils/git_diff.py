"""Git related utilities to identify changed modules."""

__author__ = ["fkiraly"]
__all__ = []

import importlib.util
import inspect
import subprocess
from functools import lru_cache


@lru_cache
def get_module_from_class(cls):
    """Get full parent module string from class.

    Parameters
    ----------
    cls : class
        class to get module string from, e.g., NaiveForecaster

    Returns
    -------
    str : module string, e.g., sktime.forecasting.naive
    """
    module = inspect.getmodule(cls)
    return module.__name__ if module else None


@lru_cache
def get_path_from_module(module_str):
    r"""Get local path string from module string.

    Parameters
    ----------
    module_str : str
        module string, e.g., sktime.forecasting.naive

    Returns
    -------
    str : local path string, e.g., sktime\forecasting\naive.py
    """
    try:
        module_spec = importlib.util.find_spec(module_str)
        if module_spec is None:
            raise ImportError(
                f"Error in get_path_from_module, module '{module_str}' not found."
            )
        module_path = module_spec.origin
        if module_path.endswith("__init__.py"):
            return module_path[:-11]
        return module_path
    except Exception as e:
        raise ImportError(f"Error finding module '{module_str}'") from e


@lru_cache
def get_merge_base_ref():
    """Return the preferred git reference to diff against, if available.

    Returns
    -------
    str or None
        First available base reference among common local and remote main branches.
        Returns None when no suitable reference is available.
    """
    candidate_refs = (
        "remotes/origin/main",
        "remotes/origin/master",
        "main",
        "master",
    )

    for ref in candidate_refs:
        try:
            subprocess.check_output(
                ["git", "rev-parse", "--verify", ref],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            continue
        else:
            return ref

    return None


def _run_git_diff(file_path):
    """Return git diff output for a file against the configured merge base."""
    merge_base_ref = get_merge_base_ref()
    if merge_base_ref is None:
        return None

    return subprocess.check_output(
        ["git", "diff", merge_base_ref, "--", file_path],
        text=True,
        encoding="utf-8",
    )


@lru_cache
def is_module_changed(module_str):
    """Check if a module has changed compared to the main branch.

    If a child module has changed, the parent module is considered changed as well.

    Parameters
    ----------
    module_str : str
        module string, e.g., sktime.forecasting.naive
    """
    module_file_path = get_path_from_module(module_str)
    try:
        output = _run_git_diff(module_file_path)
        return output is None or bool(output)
    except subprocess.CalledProcessError:
        return True


@lru_cache
def is_class_changed(cls):
    """Check if a class' parent module has changed compared to the main branch.

    Parameters
    ----------
    cls : class
        class to get module string from, e.g., NaiveForecaster

    Returns
    -------
    bool : True if changed, False otherwise
    """
    module_str = get_module_from_class(cls)
    return is_module_changed(module_str)


def get_changed_lines(file_path, only_indented=True):
    """Get changed or added lines from a file.

    Compares the current branch to the origin-main branch.

    Parameters
    ----------
    file_path : str
        path to file to get changed lines from
    only_indented : bool, default=True
        if True, only indented lines are returned, otherwise all lines are returned;
        more precisely, only changed/added lines starting with a space are returned

    Returns
    -------
    list of str : changed or added lines on current branch
    """
    try:
        result = _run_git_diff(file_path)
        if result is None:
            return []

        start_chars = "+"
        if only_indented:
            start_chars += " "

        changed_lines = [
            line.strip() for line in result.split("\n") if line.startswith(start_chars)
        ]
        changed_lines = [line[1:] for line in changed_lines]

        return changed_lines

    except subprocess.CalledProcessError:
        return []


def get_packages_with_changed_specs():
    """Get packages with changed or added specs.

    Returns
    -------
    list of str : names of packages with changed or added specs
    """
    return list(_get_packages_with_changed_specs())


@lru_cache
def _get_packages_with_changed_specs():
    """Get packages with changed or added specs.

    Private version of get_packages_with_changed_specs,
    to avoid side effects on the list return.

    Returns
    -------
    tuple of str : names of packages with changed or added specs
    """
    from packaging.requirements import InvalidRequirement, Requirement

    changed_lines = get_changed_lines("pyproject.toml")

    packages = []
    for line in changed_lines:
        if line.find("'") > line.find('"') and line.find('"') != -1:
            sep = '"'
        elif line.find("'") == -1:
            sep = '"'
        else:
            sep = "'"

        splits = line.split(sep)
        if len(splits) < 2:
            continue

        req = line.split(sep)[1]

        # deal with ; python_version >= "3.7" in requirements
        if ";" in req:
            req = req.split(";")[0]

        try:  # deal with lines that are not package requirement strings
            pkg = Requirement(req).name
        except InvalidRequirement:
            continue
        else:
            packages.append(pkg)

    packages = tuple(set(packages))

    return packages
