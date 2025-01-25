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


def get_link(root: str = GH_REPO_URL, check_404: bool = True) -> str:
    """Return the link to the current version of the repository."""
    href = root
    # try to build a link to this specific version
    treeish = get_treeish()
    href = f"{root}/tree/{treeish}"

    if check_404:
        # check if the link is 404 and fallback to the main url
        try:
            urllib.request.urlopen(href)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                href = root

    return href
