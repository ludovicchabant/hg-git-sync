
# Hg-Git Sync

This is a small Python script that tries to fix the most common problems with
[Hg-Git][1]. It's not meant to be awesome, it's just meant to get me out of
trouble.

If your `.hg/git-mapfile` is out of sync (pointing to bad commit hashes):

    cd path/to/your/repo
    python hggit_sync.py

This will rebuild the map file by looking at the commit history of both the
Mercurial and Git repos, and figure out (quite stupidly so far) how the hashes
correspond to each other.

If you're in deeper trouble, however, like you get error messages about your
local Git mirror having hashes that the server doesn't know about:

    cd path/to/your/repo
    python hggit_sync.py --rebuild git@github.com/whatever/something.git

This will wipe your local Git mirror, re-fetch it from the given remote URL, and
rebuild the map file.

Of course, this script is offered without any guarantees, may format your
hard-drive, yada yada. You know the drill when it comes to running random code
you found on the web! (I hope)


[1]: https://bitbucket.org/durin42/hg-git/src

