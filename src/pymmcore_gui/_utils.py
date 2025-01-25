import urllib.error
import urllib.request

GH_REPO_URL = "http://github.com/pymmcore-plus/pymmcore-gui"


def get_treeish() -> str:
    """Return the git treeish of the current version.

    https://setuptools-scm.readthedocs.io/en/latest/usage/#default-versioning-scheme
    setuptools_scm versioning will look like one of these
    {tag}
    {next_version}.dev{distance}+{scm letter}{revision_hash}
    {tag}+dYYYYMMDD
    {next_version}.dev{distance}+{scm letter}{revision_hash}.dYYYYMMDD

    ... and we want to return the revision_hash when present, and the `tag` otherwise.

    """
    from . import __version__

    tag = __version__
    if "+" in __version__:
        right_part = __version__.split("+")[1].split(".")[0]
        tag = right_part[1:]  # remove the scm letter, e.g. 'g' from 'g1234567'
    return tag


def gh_link(
    file: str | None = None,
    line_no: int | tuple[int, int] | None = None,
    root: str = GH_REPO_URL,
    treeish: str | None = None,
    check_404: bool = True,
) -> str:
    """Return a link to the root, file, or line number on the github repository.

    Parameters
    ----------
    file : str | None
        The file to link to. If None, the link will point to the root of the repository.
    line_no : int | tuple[int, int] | None
        The line number or range of (start, end) numbers to link to. If None, the link
        will point to the file.
    root : str
        The root url of the repository. Default is the pymmcore-plus/pymmcore-gui
        repository.
    treeish : str | None
        The git treeish of the version to link to (such as "main", "v0.1.0", or a
        commit hash). If None, the treeish is determined from the current version.
    check_404 : bool
        If True, check if the link is 404 and fallback to the main url. Default is True.
    """
    href = root
    href = f"{root}/tree/{treeish or get_treeish()}"
    if file is not None:
        href += f"/{file}"
        if line_no is not None:
            if isinstance(line_no, tuple):
                href += f"#L{line_no[0]}-L{line_no[1]}"
            else:
                href += f"#L{line_no}"

    if check_404:
        # check if the link is 404 and fallback to the main url
        try:
            urllib.request.urlopen(href)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                href = root

    return href
