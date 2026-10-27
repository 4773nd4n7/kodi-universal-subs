"""Test suite for the Universal Subs add-on.

This marker file additionally lets ``python -m unittest discover -s resources/lib/tests -t .``
start inside this directory; discovery requires the start directory to be a package. Running a
module through the package (``python -m resources.lib.tests.test_...``) is also what puts the
repository root on ``sys.path`` and gives the module its package context, so no test module has
to bootstrap ``sys.path`` itself.
"""
