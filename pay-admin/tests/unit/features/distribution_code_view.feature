Feature: DistributionCode admin view — column configuration and form behaviour
  (Service-fee field disabling when referenced by another record requires a real
  DB and is out of scope for unit tests.)

  Scenario: List view shows the key GL code fields
    Given the DistributionCode admin view is loaded
    Then the list columns should include "name"
    And the list columns should include "client"
    And the list columns should include "responsibility_centre"
    And the list columns should include "service_line"
    And the list columns should include "stob"
    And the list columns should include "project_code"

  Scenario: All list columns are in the declared column_list
    Given the DistributionCode admin view is loaded
    Then all list columns should be within the configured column_list

  Scenario: Default sort is by name
    Given the DistributionCode admin view is loaded
    Then the default sort column should be "name"

  Scenario: Audit fields are stripped from the create form
    Given the DistributionCode admin view is loaded
    When the DistributionCode create form is generated
    Then the audit fields should not be present in the create form

  Scenario: Account field is always disabled in the edit form
    Given the DistributionCode admin view is loaded
    When the DistributionCode edit form is generated
    Then the account field should be disabled

  Scenario: Audit fields are readonly in the edit form
    Given the DistributionCode admin view is loaded
    When the DistributionCode edit form is generated
    Then the audit fields should be readonly

  Scenario: Audit fields are populated when a distribution code is created
    Given the DistributionCode admin view is loaded
    And a user is logged in as "Joe"
    And the current time is "2024-01-15 10:00:00"
    When a new distribution code record is saved
    Then the distribution code created_by should be "Joe"
    And the distribution code created_on should be "2024-01-15 10:00:00"
    And the distribution code updated fields should not be set

  Scenario: Audit fields are updated when a distribution code is edited
    Given the DistributionCode admin view is loaded
    And a user is logged in as "Joe"
    And the current time is "2024-01-15 10:00:00"
    When an existing distribution code record is saved
    Then the distribution code updated_by should be "Joe"
    And the distribution code updated_on should be "2024-01-15 10:00:00"
