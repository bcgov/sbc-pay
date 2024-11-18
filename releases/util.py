import os
import re
import requests
from github import Github


def get_issues_from_repo(target, latest_release_only=False):
    """Get issue ids from repos on github."""
    issue_ids = []
    release_names = []
    g = Github(os.getenv("GITHUB_ACCESS_TOKEN"))
    repository_owner = 'bcgov'
    repo = g.get_repo(f"{repository_owner}/{target}")
    for release in repo.get_releases():
        release_names.append(release.title)
        for l in release.body.splitlines():
            if re.search(r'\d+ -', l):
                issue_ids.append(re.search(r'\d+ -', l).group(0).replace(' -',''))
            if re.search(r'\d+-', l):
                issue_ids.append(re.search(r'\d+-', l).group(0).replace('-',''))
        if latest_release_only:
            break
    return issue_ids, release_names

def add_issues_to_release(issue_id: int, zenhub_release_hash: str):
    """Add issues to Zenhub release."""
    response = requests.post('https://api.zenhub.com/public/graphql',
    headers={
        'Authorization': f'Bearer {os.getenv("ZENHUB_GRAPHQL_TOKEN")}'
    },
    json={
        "operationName": "addIssuesToReleases",
        "query": "mutation addIssuesToReleases($AddIssuesToReleasesInput: AddIssuesToReleasesInput!) {  addIssuesToReleases(input: $AddIssuesToReleasesInput) {    releases {      id      title      state      startOn      endOn      closedAt      __typename    }    __typename  }}}",
        "variables": {"AddIssuesToReleasesInput":{"issueIds":[issue_id],"releaseIds":[zenhub_release_hash]}},
    }, timeout=60000)
    assert response.status_code == 200
  
def get_issue_id(issue_number):
    """Get issue from Zenhub."""
    query = "query getGHIssueFull($repositoryId: ID!, $issueNumber: Int!, $workspaceId: ID!) {  issueByInfo(repositoryId: $repositoryId, issueNumber: $issueNumber) {    id    title    body    state    type    number    viewerPermission    created_at: createdAt    updated_at: updatedAt    html_url: htmlUrl    user {      id      avatar_url: avatarUrl      login      __typename    }    labels {      nodes {        id        color        name        __typename      }      __typename    }    assignees {      totalCount      nodes {        id        login        avatar_url: avatarUrl        name        __typename      }      __typename    }    repository {      id      name      estimateSet {        values        __typename      }      __typename    }    epic {      id      __typename    }    estimate {      value      __typename    }    parentEpics {      nodes {        id        issue {          title          __typename        }        __typename      }      __typename    }    parentZenhubEpics {      nodes {        id        __typename      }      __typename    }    milestone {      ...activeMilestone      __typename    }    releases {      nodes {        id        title        __typename      }      __typename    }    pipelineIssues {      nodes {        id        workspace {          _id: id          name          displayName          isEditable          pipelinesConnection {            nodes {              _id: id              name              __typename            }            __typename          }          prioritiesConnection {            nodes {              _id: id              name              color              __typename            }            __typename          }          __typename        }        pipeline {          _id: id          __typename        }        priority {          id          __typename        }        __typename      }      __typename    }    sprints(workspaceId: $workspaceId) {      nodes {        id        __typename      }      __typename    }    ...issueDependencies    __typename  }}fragment activeMilestone on Milestone {  ...milestoneData  __typename}fragment milestoneData on Milestone {  __typename}fragment issueDependencies on Issue {  id  type  viewerPermission  blockedItems {    totalCount    nodes {      ... on Issue {        id        title        issueState: state        number        type        htmlUrl        repository {          id          name          owner {            id            login            __typename          }          __typename        }        pipelineIssue(workspaceId: $workspaceId) {          id          pipeline {            id            name            __typename          }          priority {            id            name            __typename          }          __typename        }        __typename      }      ... on ZenhubEpic {        id        title        state        __typename      }      __typename    }    __typename  }  blockingItems {    totalCount    nodes {      ... on Issue {        id        title        issueState: state        number        type        htmlUrl        repository {          id          name          owner {            id            login            __typename          }          __typename        }        pipelineIssue(workspaceId: $workspaceId) {          id          pipeline {            id            name            __typename          }          priority {            id            name            __typename          }          __typename        }        __typename      }      ... on ZenhubEpic {        id        title        state        __typename      }      __typename    }    __typename  }  __typename}"
    response = requests.post('https://api.zenhub.com/public/graphql',
        headers={
            'Authorization': f'Bearer {os.getenv("ZENHUB_GRAPHQL_TOKEN")}'
        },
        json={
            "operationName": "getGHIssueFull",
            "query": query,
            "variables": {
                "repositoryId": os.getenv("ZENHUB_REPOSITORY_ID"),
                "issueNumber": int(issue_number),
                "workspaceId": os.getenv("TARGET_ZENHUB_WORKSPACE_ID")
            }
        }, timeout=60000)
    assert response.status_code == 200
    data = response.json()
    return data.get('data').get('issueByInfo').get('id')

def get_workspace_release_for_report(release_name):
    """Get workspace release for report."""
    response = requests.post('https://api.zenhub.com/public/graphql',
        headers={
            'Authorization': f'Bearer {os.getenv("ZENHUB_GRAPHQL_TOKEN")}'
        },
        json={
            "operationName": "getWorkspaceReleasesForReport",
            "variables": {
              "workspaceId": os.getenv("TARGET_ZENHUB_WORKSPACE_ID"),
              "pageSize": 30,
              "state": {
                  "eq": "OPEN"
              },
              "query": f'{release_name}'
          },
          "query": "query getWorkspaceReleasesForReport($workspaceId: ID!, $pageSize: Int, $after: String, $query: String, $state: ReleaseStateInput, $repositoryIds: [ID!], $ids: [ID!]) {  workspace(id: $workspaceId) {    id    releases(      first: $pageSize      query: $query      after: $after      state: $state      repositoryIds: $repositoryIds      ids: $ids     ) {      totalCount      pageInfo {        hasNextPage        hasPreviousPage        endCursor        __typename      }      nodes {        ...ReleaseForReport        __typename      }      __typename    }    __typename  }}fragment ReleaseForReport on Release {  id  title  state  endOn  closedAt  startOn  description  issuesCount  __typename}"
        }, timeout=60000)
    assert response.status_code == 200
    data = response.json()
    nodes = data.get('data').get('workspace').get('releases').get('nodes')
    if nodes:
        return nodes[0].get('id')
    return None

def create_release(release_name):
    """Create release in Zenhub."""
    response = requests.post('https://api.zenhub.com/public/graphql',
    headers={
        'Authorization': f'Bearer {os.getenv("ZENHUB_GRAPHQL_TOKEN")}'
    },
    json={
        "operationName": "createRelease",
        "variables": {
            "input": {
                "release": {
                    "title": release_name,
                    "description": release_name,
                    "startOn": "2024-01-01T00:00:00.000Z",
                    "endOn": "2024-01-02T00:00:00.000Z",
                    "repositoryGhIds": [int(os.getenv('ENTITY_GITHUB_REPO_ID'))]
                }
            }
        },
        "query": "mutation createRelease($input: CreateReleaseInput!) {  createRelease(input: $input) {    release {      id      title      startOn      endOn      __typename    }    __typename  }}"
    }, timeout=60000)
    assert response.status_code == 200
    data = response.json()
    return data.get('data').get('createRelease').get('release').get('id')
