# Infrastructure scripts

`reset_test_database.py` is the only destructive helper. It refuses any database whose name does not end in `_test`, truncates the complete tenant test-table set (including Stage 13 review, revision, package and operation rows), and is exposed as the explicit `make db-reset-test` command.

There are no cloud or deployment scripts. Normal developer commands remain in the root Makefile.
