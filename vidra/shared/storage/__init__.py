"""Where a document goes.

`files` writes one document to one path, atomically. `database` is the base
every backend implements, and `folder` is a backend. Components only write
files; a pipeline copies them to a database.
"""
