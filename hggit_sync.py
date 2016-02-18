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
    commit_map = dict(map(lambda c: (c.timestamp, (c, None)), commits1))
    for c in commits2:
        entry = commit_map.get(c.timestamp, (None, None))
        entry = (entry[0], c)
        commit_map[c.timestamp] = entry
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
            help="The path to the mapfile to generate.")
    res = parser.parse_args()

    hg_repo = os.getcwd()
    if not os.path.exists(os.path.join(hg_repo, '.hg')):
        print("You must run this in the root of a Mercurial repository.")
        return 1

    git_repo = os.path.join(hg_repo, '.hg', 'git')
    if res.rebuild:
        print("Removing existing Git repo...")
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
    for key, val in commit_map.iteritems():
        if val[0] is None:
            print("Mercurial commit '%s' (%s) has no Git mirror yet: %s" %
                  (val[1].nodeid, val[1].timestamp, val[1].description))
        if val[1] is None:
            print("Git commit '%s' (%s) is new: %s" %
                  (val[0].nodeid, val[0].timestamp, val[0].description))

    map_file = res.mapfile or os.path.join(hg_repo, '.hg', 'git-mapfile')
    print("Saving map file: %s" % map_file)
    with codecs.open(map_file, 'w', encoding='utf8') as fp:
        for key, val in commit_map.iteritems():
            if val[0] is None or val[1] is None:
                continue
            fp.write(val[0].nodeid)
            fp.write(' ')
            fp.write(val[1].nodeid)
            fp.write('\n')


if __name__ == '__main__':
    res = main()
    sys.exit(res)

