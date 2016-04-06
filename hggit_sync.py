import os
import os.path
import sys
import codecs
import shutil
import argparse
import subprocess


class CommitInfo(object):
    def __init__(self):
        self.nodeid = None
        self.timestamp = None
        self.description = None


def parse_commits(text):
    commits = []
    cur_commit = None
    for line in text.split('\n'):
        if line == '':
            if cur_commit:
                commits.append(cur_commit)
                cur_commit = None
            continue
        if cur_commit is None:
            cur_commit = CommitInfo()
        if cur_commit.nodeid is None:
            id_and_date = line.split(' ', 1)
            cur_commit.nodeid = id_and_date[0]
            cur_commit.timestamp = int(id_and_date[1].split('.')[0])
        else:
            cur_commit.description = line
    return commits


def build_commit_map(commits1, commits2):
    commits1 = sorted(commits1, key=lambda c: c.timestamp)
    commits2 = sorted(commits2, key=lambda c: c.timestamp)

    # Build the commit map with the "left" commits' info.
    commit_map = {}
    for c1 in commits1:
        if c1.timestamp not in commit_map:
            commit_map[c1.timestamp] = [(c1, None)]
        else:
            # Each entry in the map is a list in case we have commits at the
            # same timestamp. It's rare, but it happens, especially with
            # people who have some fucked-up Git-fu.
            print("Conflicting timestamps between %s and %s" %
                    (c1.nodeid, commit_map[c1.timestamp][0][0].nodeid))
            commit_map[c1.timestamp].append((c1, None))

    # Now put the "easy" matches from the "right" commits.
    orphan_commits2 = []
    print("Building commit map...")
    for c in commits2:
        entry = commit_map.get(c.timestamp)
        if entry is None:
            # No "left" commit had this timestamp... we'll have an orphan.
            entry = [(None, None)]
            commit_map[c.timestamp] = entry

        # Add the commit info.
        idx = 0
        if len(entry) > 1:
            for i, e in enumerate(entry):
                if e[0] and e[0].description.strip() == c.description.strip():
                    idx = i
                    break
        if entry[idx][1] is None:
            entry[idx] = (entry[idx][0], c)
        else:
            print("Attempting to match 2 commits (%s and %s) to the same base "
                    "commit %s... creating orphan instead." %
                    (entry[idx][1].nodeid, c.nodeid, entry[idx][0].nodeid))
            entry.append((None, c))
            idx = len(entry) - 1
        if entry[idx][0] is None:
            orphan_commits2.append(c)

    orphan_commits1 = []
    for entry in commit_map.values():
        for e in entry:
            if e[1] is None:
                orphan_commits1.append(e[0])

    if orphan_commits1 or orphan_commits2:
        print("Fixing orphaned commits...")
        did_fix = True
        while did_fix:
            did_fix = False
            for c2 in orphan_commits2:
                for c1 in orphan_commits1:
                    if c1.description.strip() == c2.description.strip():
                        print("Mapping '%s' to '%s'" % (c1.nodeid, c2.nodeid))
                        print("  Same description: %s" % c1.description)
                        print("  Timestamp difference: %d" % (c2.timestamp - c1.timestamp))
                        entry = commit_map[c1.timestamp]
                        for i, e in enumerate(entry):
                            if e[0] and e[0].nodeid == c1.nodeid:
                                entry[i] = (c1, c2)
                                break
                        entry = commit_map[c2.timestamp]
                        for i, e in enumerate(entry):
                            if e[1] and e[1].nodeid == c2.nodeid:
                                assert e[0] is None
                                del entry[i]
                        if len(entry) == 0:
                            del commit_map[c2.timestamp]
                        orphan_commits1.remove(c1)
                        orphan_commits2.remove(c2)
                        did_fix = True
                        break
                if did_fix:
                    break

        if orphan_commits1 or orphan_commits2:
            print("Still have %d and %d orphaned commits." %
                    (len(orphan_commits1), len(orphan_commits2)))

    return commit_map


def main():
    parser = argparse.ArgumentParser(
            description="Helps you fix problems with hg-git. Maybe.",
            epilog="Don't trust scripts you found on the web! Backup your stuff!")
    parser.add_argument(
            '--rebuild',
            nargs=1,
            metavar='REMOTE',
            help="Rebuild the Git repo from the given remote URL.")
    parser.add_argument(
            'mapfile',
            metavar='MAPFILE',
            nargs='?',
            help="The path to the mapfile to generate.")
    res = parser.parse_args()

    hg_repo = os.getcwd()
    if not os.path.exists(os.path.join(hg_repo, '.hg')):
        print("You must run this in the root of a Mercurial repository.")
        return 1

    git_repo = os.path.join(hg_repo, '.hg', 'git')
    if res.rebuild:
        print("Removing existing Git repo...")
        if os.path.isdir(git_repo):
            shutil.rmtree(git_repo)
        print("Syncing it again into: %s" % git_repo)
        git_output = subprocess.check_output([
            'git', 'clone', '--bare', res.rebuild, git_repo])

    if not os.path.exists(git_repo):
        print("This Mercurial repository doesn't seem to have any Git mirror "
              "to sync with.")
        return 1

    hg_output = subprocess.check_output([
        'hg', 'log',
        '--template', "{node} {date}\n{firstline(desc)}\n\n"])
    hg_commits = parse_commits(hg_output)

    os.chdir(git_repo)
    git_output = subprocess.check_output([
        'git', 'log', '--format=%H %ct%n%s%n%n'])
    git_commits = parse_commits(git_output)
    os.chdir(hg_repo)

    commit_map = build_commit_map(git_commits, hg_commits)
    for key, vals in commit_map.iteritems():
        for val in vals:
            if val[0] is None:
                print("Mercurial commit '%s' (%s) has no Git mirror yet: %s" %
                      (val[1].nodeid, val[1].timestamp, val[1].description))
            if val[1] is None:
                print("Git commit '%s' (%s) is new: %s" %
                      (val[0].nodeid, val[0].timestamp, val[0].description))

    map_file = res.mapfile or os.path.join(hg_repo, '.hg', 'git-mapfile')
    print("Saving map file: %s" % map_file)
    with codecs.open(map_file, 'w', encoding='utf8') as fp:
        for key, vals in commit_map.iteritems():
            for val in vals:
                if val[0] is None or val[1] is None:
                    continue
                fp.write(val[0].nodeid)
                fp.write(' ')
                fp.write(val[1].nodeid)
                fp.write('\n')


if __name__ == '__main__':
    res = main()
    sys.exit(res)

