Feature: Keycloak authentication

  Scenario: Logged in user is recognised as logged in
    Given a user is logged in
    When we check if the user is logged in
    Then the result should be true

  Scenario: Logged out user is not recognised as logged in
    Given a user is not logged in
    When we check if the user is logged in
    Then the result should be false

  Scenario: User with correct role can access the application
    Given a user is logged in with role "admin_view"
    When we check if the user has access to "admin_view"
    Then the result should be true

  Scenario: User with wrong role cannot access the application
    Given a user is logged in with role "other_role"
    When we check if the user has access to "admin_view"
    Then the result should be false

  Scenario: User without access token cannot access the application
    Given a user is logged in but has no access token
    When we check if the user has access to "admin_view"
    Then the result should be false

  Scenario: Username is returned from the OIDC profile
    Given a user is logged in as "Joe"
    When we get the username
    Then the username should be "Joe"
