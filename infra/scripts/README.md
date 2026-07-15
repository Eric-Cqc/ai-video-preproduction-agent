# Infrastructure scripts

`reset_test_database.py` is the only destructive helper. It refuses any database whose name does not end in `_test`, truncates only the five tenant foundation tables, and is exposed as the explicit `make db-reset-test` command.

There are no cloud or deployment scripts. Normal developer commands remain in the root Makefile.
