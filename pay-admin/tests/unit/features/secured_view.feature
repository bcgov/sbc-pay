Feature: SecuredView behaviour

  Scenario: Deletion is never allowed
    Given the SecuredView is loaded
    Then deletion should not be allowed

  Scenario: User with view role only cannot create or edit records
    Given the SecuredView is loaded
    And a user is logged in with role "admin_view"
    When we check create and edit permissions
    Then create should not be allowed
    And edit should not be allowed

  Scenario: User with edit role can create and edit records
    Given the SecuredView is loaded
    And a user is logged in with roles "admin_view" and "admin_edit"
    When we check create and edit permissions
    Then create should be allowed
    And edit should be allowed

  Scenario: Inaccessible view redirects to login on first attempt
    Given the SecuredView is loaded
    When the inaccessible view is requested
    Then the response should be a redirect to login

  Scenario: Inaccessible view returns not authorised on repeated attempt
    Given the SecuredView is loaded
    And the view has already redirected once
    When the inaccessible view is requested
    Then the response should be "not authorized"
