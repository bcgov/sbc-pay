Feature: SecuredView behaviour

  Scenario: Deletion is never allowed
    Given the SecuredView is loaded
    Then deletion should not be allowed

  Scenario: Inaccessible view redirects to login on first attempt
    Given the SecuredView is loaded
    When the inaccessible view is requested
    Then the response should be a redirect to login

  Scenario: Inaccessible view returns not authorised on repeated attempt
    Given the SecuredView is loaded
    And the view has already redirected once
    When the inaccessible view is requested
    Then the response should be "not authorized"
