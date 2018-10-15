import bugzilla
import pathlib
import sys
from click import progressbar
import logging

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.DEBUG)
fh = logging.FileHandler('bugzilla.log')
fh.setLevel(logging.DEBUG)
LOGGER.addHandler(fh)

TESTING = True

if TESTING:
    F29FTBFS = 1626028
    URL = 'partner-bugzilla.redhat.com'
else:
    F29FTBFS = 1602938
    URL = 'bugzilla.redhat.com'

TEMPLATE = """Dear Maintainer,

your package has not been built successfully in F29. Action is required from you.

If you can fix your package to build, perform a build in koji, and either create
an update in bodhi, or close this bug without creating an update, if updating is
not appropriate [1]. If you are working on a fix, set the status to ASSIGNED to
acknowledge this. Following the latest policy for such packages [2], your package
will be orphaned if this bug remains in NEW state more than 8 weeks.

[1] https://fedoraproject.org/wiki/Updates_Policy
[2] https://fedoraproject.org/wiki/Fails_to_build_from_source#Package_Removal_for_Long-standing_FTBFS_bugs
"""  # noqa

ALREADY_FILLED = pathlib.Path(__file__).parent / 'ALREADY_FILLED'

bzapi = bugzilla.Bugzilla(URL)
if not bzapi.logged_in:
    bzapi.interactive_login()

failed = []
updated = []


def new_ftbfs_bugz(tracker=F29FTBFS, version='29'):
    query = bzapi.build_query(product='Fedora', status='NEW', version=version)
    query['blocks'] = tracker
    return bzapi.query(query)


def needinfo(requestee):
    return {
        'name': 'needinfo',
        'requestee': requestee,
        'status': '?',
    }


def send_reminder(bug, comment=TEMPLATE):
    flags = [needinfo(bug.assigned_to)]
    update = bzapi.build_update(comment=comment, flags=flags)
    try:
        bzapi.update_bugs([bug.id], update)
    except Exception:
        LOGGER.exception(bug.weburl)
        failed.append(bug)
    else:
        updated.append(bug)
        with open(ALREADY_FILLED, 'a') as f:
            print(bug.id, file=f)


if ALREADY_FILLED.exists():
    print(f'Loading bug IDs from {ALREADY_FILLED}. Will not fill those. '
          f'Remove {ALREADY_FILLED} to stop this from happening.')
    ignore = [
        int(line.rstrip()) for line in ALREADY_FILLED.read_text().splitlines()
    ]
else:
    ignore = []


print('Gathering bugz, this can take a while...')

bugz = new_ftbfs_bugz()

print(f'There are {len(bugz)} NEW bugz, will send a reminder')
if ignore:
    print(f'Will ignore {len(ignore)} bugz from {ALREADY_FILLED}')
    print(f'Will update {len(set(b.id for b in bugz) - set(ignore))} bugz')


def _item_show_func(bug):
    if bug is None:
        return 'Finished!'
    return bug.weburl


with progressbar(bugz, item_show_func=_item_show_func) as bugbar:
    for bug in bugbar:
        if bug.id not in ignore:
            send_reminder(bug)

print(f'Updated {len(updated)} bugz')

if failed:
    print(f'Failed to update {len(failed)} bugz', file=sys.stderr)
    for bug in failed:
        print(bug.weburl, file=sys.stderr)
