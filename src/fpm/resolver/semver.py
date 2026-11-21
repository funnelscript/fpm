"""Strict SemVer 2.0 parsing, comparison, and constraint evaluation."""

from __future__ import annotations

import re
from functools import total_ordering
from typing import Any, Iterable

from fpm.errors import InvalidSemVerError

SEMVER_REGEX = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


@total_ordering
class Version:
    """SemVer 2.0 immutable value object."""

    __slots__ = ("major", "minor", "patch", "prerelease", "build", "_raw")

    def __init__(
        self,
        major: int,
        minor: int,
        patch: int,
        prerelease: tuple[str | int, ...] = (),
        build: tuple[str, ...] = (),
        raw: str | None = None,
    ) -> None:
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = prerelease
        self.build = build
        self._raw = raw

    @classmethod
    def parse(cls, text: str) -> Version:
        clean = text.strip()
        if clean.startswith("v"):
            clean = clean[1:]
        match = SEMVER_REGEX.match(clean)
        if not match:
            raise InvalidSemVerError(text)

        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch"))

        raw_pre = match.group("prerelease")
        if raw_pre:
            parts: list[str | int] = []
            for item in raw_pre.split("."):
                if item.isdigit():
                    parts.append(int(item))
                else:
                    parts.append(item)
            prerelease = tuple(parts)
        else:
            prerelease = ()

        raw_build = match.group("build")
        build = tuple(raw_build.split(".")) if raw_build else ()

        return cls(major, minor, patch, prerelease, build, raw=text.strip())

    def __str__(self) -> str:
        if self._raw:
            return self._raw
        res = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            res += f"-{'.'.join(str(p) for p in self.prerelease)}"
        if self.build:
            res += f"+{'.'.join(self.build)}"
        return res

    def __repr__(self) -> str:
        return f"Version('{self}')"

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch, self.prerelease))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Version):
            if isinstance(other, str):
                try:
                    other = Version.parse(other)
                except InvalidSemVerError:
                    return False
            else:
                return False
        return (self.major, self.minor, self.patch, self.prerelease) == (
            other.major,
            other.minor,
            other.patch,
            other.prerelease,
        )

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Version):
            if isinstance(other, str):
                other = Version.parse(other)
            else:
                return NotImplemented

        # Compare major.minor.patch
        self_main = (self.major, self.minor, self.patch)
        other_main = (other.major, other.minor, other.patch)
        if self_main != other_main:
            return self_main < other_main

        # Prerelease vs Normal release:
        # A normal version has greater precedence than a pre-release version
        if not self.prerelease and other.prerelease:
            return False
        if self.prerelease and not other.prerelease:
            return True
        if not self.prerelease and not other.prerelease:
            return False

        # Compare prereleases part by part
        for a, b in zip(self.prerelease, other.prerelease, strict=False):
            if a == b:
                continue
            if isinstance(a, int) and isinstance(b, int):
                return a < b
            if isinstance(a, int) and isinstance(b, str):
                return True  # Numeric identifiers always have lower precedence than string identifiers
            if isinstance(a, str) and isinstance(b, int):
                return False
            return str(a) < str(b)

        return len(self.prerelease) < len(other.prerelease)


class VersionRange:
    """Parses SemVer range constraints including ^, ~, inequalities, and wildcards."""

    def __init__(self, raw: str) -> None:
        self.raw = raw.strip()
        self.predicates = self._parse(self.raw)

    def _parse(self, text: str) -> list[tuple[str, Version]]:
        if not text or text == "*":
            return []

        clauses = [c.strip() for c in text.split(",") if c.strip()]
        predicates: list[tuple[str, Version]] = []

        for clause in clauses:
            if clause.startswith("^"):
                # Caret range
                base_ver = Version.parse(clause[1:])
                predicates.append((">=", base_ver))
                if base_ver.major > 0:
                    upper = Version(base_ver.major + 1, 0, 0)
                elif base_ver.minor > 0:
                    upper = Version(0, base_ver.minor + 1, 0)
                else:
                    upper = Version(0, 0, base_ver.patch + 1)
                predicates.append(("<", upper))
            elif clause.startswith("~"):
                # Tilde range
                base_ver = Version.parse(clause[1:])
                predicates.append((">=", base_ver))
                upper = Version(base_ver.major, base_ver.minor + 1, 0)
                predicates.append(("<", upper))
            elif clause.startswith(">="):
                predicates.append((">=", Version.parse(clause[2:])))
            elif clause.startswith("<="):
                predicates.append(("<=", Version.parse(clause[2:])))
            elif clause.startswith(">"):
                predicates.append((">", Version.parse(clause[1:])))
            elif clause.startswith("<"):
                predicates.append(("<", Version.parse(clause[1:])))
            elif clause.startswith("="):
                predicates.append(("==", Version.parse(clause[1:])))
            else:
                predicates.append(("==", Version.parse(clause)))

        return predicates

    def satisfied_by(self, version: Version | str) -> bool:
        if isinstance(version, str):
            version = Version.parse(version)

        for op, target in self.predicates:
            if op == ">=":
                if not (version >= target):
                    return False
            elif op == "<=":
                if not (version <= target):
                    return False
            elif op == ">":
                if not (version > target):
                    return False
            elif op == "<":
                if not (version < target):
                    return False
            elif op == "==":
                if not (version == target):
                    return False
        return True


def matches_constraint(version: Version | str, constraint: str) -> bool:
    vr = VersionRange(constraint)
    return vr.satisfied_by(version)


def select_best_version(versions: Iterable[Version | str], constraint: str) -> Version | None:
    vr = VersionRange(constraint)
    candidates: list[Version] = []
    for v in versions:
        parsed = Version.parse(v) if isinstance(v, str) else v
        if vr.satisfied_by(parsed):
            candidates.append(parsed)
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0]
