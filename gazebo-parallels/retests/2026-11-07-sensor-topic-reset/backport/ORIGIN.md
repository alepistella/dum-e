# Patch origin

The corrective logic comes from Federico Celauro's
[gazebosim/gz-sim PR #4082](https://github.com/gazebosim/gz-sim/pull/4082),
head commit `fd3794882aa647b79f2769f56b46bc8cc7ee37c7` at the time of testing.
This package documents an independent test of an additional metadata symptom.
It does not claim authorship of the upstream fix.

The backport starts from tag `gz-sim8_8.15.0`. Sensors hunks apply directly.
The exact added RenderUtil filtering block is inserted before the existing
creation loop: the main-only model presort in the original hunk context is
absent in 8.15.0 and is not added here. No new public API is introduced.

Only RenderUtil and Sensors changes are applied by the build script. The
PR's C++ regression tests were not run in this component-only build.
Upstream Gazebo code retains its Apache-2.0 license; see the repository's
root LICENSE. Original source files are downloaded from the immutable tag
and checked against the hashes recorded here.
