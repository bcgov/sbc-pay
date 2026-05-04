# pay-admin tests

BDD tests using [pytest-bdd](https://pytest-bdd.readthedocs.io/) with Gherkin `.feature` files.

## How it works

Each test area has two files:

```
tests/unit/
├── features/
│   └── keycloak.feature          <- plain-English scenarios (Given / When / Then)
└── test_keycloak_steps.py        <- Python functions that implement each step
```

`@scenarios("features/foo.feature")` in the step file tells pytest to generate one test per Gherkin scenario. Each `@given` / `@when` / `@then` function is matched to the scenario line with the same text.

Steps share state through the `context` dict fixture (defined in `conftest.py`):

```python
@given("something")
def setup(context):
    context["value"] = 42        # store

@then("it should be correct")
def check(context):
    assert context["value"] == 42  # read
```

## Shared fixtures and steps (`conftest.py`)

| Fixture / step | What it does |
|----------------|-------------|
| `app` | Session-scoped Flask app + app context |
| `client` | Session-scoped test client |
| `context` | Fresh `{}` dict per test for step communication |
| `a user is logged in` | Sets `FakeOidc.user_loggedin = True` |
| `a user is not logged in` | Sets `FakeOidc.user_loggedin = False` |
| `a user is logged in as "{username}"` | Overrides `user_getfield` to return the username |
| `a user is logged in with role "{role}"` | Stores role in `context["user_roles"]` |
| `the current time is "{timestamp}"` | Stores timestamp for `freeze_time` in `@when` steps |

## Running tests

```bash
cd pay-admin
make test
# or
pytest tests/
```
