"""Hypothesis property-based tests verifying SemVer transitivity and lockfile idempotency."""

from hypothesis import given
from hypothesis import strategies as st

from fpm.models.lockfile import LockedPackage, Lockfile
from fpm.resolver.semver import Version

# Strategy for generating valid SemVer components
version_numbers = st.integers(min_value=0, max_value=1000)
prerelease_identifiers = st.lists(
    st.one_of(
        st.integers(min_value=0, max_value=100),
        st.from_regex(r"[a-z0-9-]{1,10}", fullmatch=True),
    ),
    min_size=0,
    max_size=3,
)


@st.composite
def semver_strategy(draw):
    major = draw(version_numbers)
    minor = draw(version_numbers)
    patch = draw(version_numbers)
    pre = tuple(draw(prerelease_identifiers))
    return Version(major, minor, patch, prerelease=pre)


@given(semver_strategy(), semver_strategy(), semver_strategy())
def test_semver_ordering_transitivity(v1: Version, v2: Version, v3: Version):
    """If v1 < v2 and v2 < v3, then v1 must be strictly < v3."""
    if v1 < v2 and v2 < v3:
        assert v1 < v3


@given(semver_strategy(), semver_strategy())
def test_semver_trichotomy(v1: Version, v2: Version):
    """Exactly one of v1 < v2, v1 == v2, or v1 > v2 must hold."""
    is_lt = v1 < v2
    is_eq = v1 == v2
    is_gt = v1 > v2

    assert sum([is_lt, is_eq, is_gt]) == 1


@given(st.text(min_size=1, max_size=50), st.integers(min_value=1, max_value=5))
def test_lockfile_roundtrip_idempotency(manifest_hash: str, num_pkgs: int):
    """Lockfile serialization must be 100% idempotent and stable."""
    pkgs = {}
    for i in range(num_pkgs):
        name = f"pkg/dep_{i}"
        ver = f"1.{i}.0"
        pkgs[f"{name}@{ver}"] = LockedPackage(
            name=name,
            version=ver,
            resolved=f"https://registry.funnelscript.org/{name}-{ver}.tar.gz",
            integrity=f"sha256-{i * 11111111}",
            entry="index.fnls",
            dependencies={},
        )

    lockfile = Lockfile(
        lockfile_version=1,
        manifest_hash=f"sha256-{manifest_hash}",
        packages=pkgs,
    )

    first_json = lockfile.to_canonical_json()
    reloaded = Lockfile.model_validate_json(first_json)
    second_json = reloaded.to_canonical_json()

    assert first_json == second_json
