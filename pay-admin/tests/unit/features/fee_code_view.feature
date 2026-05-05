Feature: FeeCode admin view

  Scenario: List view shows the code and amount columns
    Given the FeeCode admin view is loaded
    Then the list columns should include "code"
    And the list columns should include "amount"

  Scenario: All list columns are in the declared column_list
    Given the FeeCode admin view is loaded
    Then all list columns should be within the configured column_list

  Scenario: Default sort is by code
    Given the FeeCode admin view is loaded
    Then the default sort column should be "code"

  Scenario: Code field is readonly when editing an existing fee code
    Given the FeeCode admin view is loaded
    When the edit form is prefilled for an existing record
    Then the code field should be readonly

  Scenario: Audit fields are stripped from the create form
    Given the FeeCode admin view is loaded
    When the FeeCode create form is generated
    Then the audit fields should not be present in the create form

  Scenario: Audit fields are readonly in the edit form
    Given the FeeCode admin view is loaded
    When the FeeCode edit form is generated
    Then the audit fields should be readonly

  Scenario: Audit fields are populated when a fee code is created
    Given the FeeCode admin view is loaded
    And a user is logged in as "Joe"
    And the current time is "2024-01-15 10:00:00"
    When a new FeeCode record is saved
    Then the created audit fields should be "Joe" and "2024-01-15 10:00:00"

  Scenario: Audit fields are updated when a fee code is edited
    Given the FeeCode admin view is loaded
    And a user is logged in as "Joe"
    And the current time is "2024-01-15 10:00:00"
    When an existing FeeCode record is saved
    Then the updated audit fields should be "Joe" and "2024-01-15 10:00:00"
