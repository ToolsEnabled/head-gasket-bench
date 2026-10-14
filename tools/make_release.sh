#!/bin/sh
# Build the release files for one version from the committed main branch.
#
#   tools/make_release.sh [VERSION]      (default 0.1.0)
#
# Writes dist/head-gasket-bench-VERSION.tar.gz (git archive of main),
# dist/paper.pdf and dist/SHA256SUMS. Builds only; it does not tag, push or
# publish anything.
set -eu
VERSION="${1:-0.1.0}"
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "make_release: the working tree has uncommitted changes; commit them first" >&2
    exit 1
fi
mkdir -p dist
NAME="head-gasket-bench-$VERSION"
# git archive stamps files with the commit time and gzip -n omits its own timestamp,
# so the same commit gives the same bytes.
git archive --format=tar --prefix="$NAME/" main | gzip -n -9 > "dist/$NAME.tar.gz"
git show main:paper/paper.pdf > dist/paper.pdf
cd dist
sha256sum "$NAME.tar.gz" paper.pdf > SHA256SUMS
cat SHA256SUMS
echo "commit $(git rev-parse main)"
