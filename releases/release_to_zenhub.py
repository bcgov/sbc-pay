import sys

from dotenv import load_dotenv
from util import add_issues_to_release, create_release, get_issue_id, get_issues_from_repo, get_workspace_release_for_report

load_dotenv()

# Optional: pass a tag (e.g. V1.25.0) to target that release explicitly instead of
# whatever the release list endpoint happens to return first.
tag = sys.argv[1] if len(sys.argv) > 1 else None

auth_issue_ids, _, _ = get_issues_from_repo('sbc-auth')
pay_issue_ids, release_names, release_dates = get_issues_from_repo(
    'sbc-pay', latest_release_only=tag is None, tag=tag)
pay_release_issue_ids = list(set([item for item in pay_issue_ids if item not in auth_issue_ids]))
target_release_name = f'Pay Release - {release_names[0]}'
release_id = get_workspace_release_for_report(target_release_name)
if release_id is None:
    release_id = create_release(target_release_name, release_dates[0])
    print(f'Zenhub release created id: {release_id} - {target_release_name}')
else:
    print(f'Zenhub release found id: {release_id} - {target_release_name}')
added, skipped = 0, []
for issue in pay_release_issue_ids:
    issue_id = get_issue_id(issue)
    if issue_id is None:
        skipped.append(issue)
        print(f'Skipping issue {issue} - not found in Zenhub repository')
        continue
    add_issues_to_release(issue_id, release_id)
    added += 1
    print(f'Adding issue {issue} - {issue_id} to Zenhub release {release_id}')
print(f'\nDone. Added {added} issue(s) to {target_release_name}.')
if skipped:
    print(f'Skipped {len(skipped)}: {", ".join(skipped)}')
