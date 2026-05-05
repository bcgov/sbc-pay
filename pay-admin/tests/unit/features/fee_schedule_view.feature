Feature: FeeSchedule admin view

  Scenario: List view shows corp type, filing type and fee columns
    Given the FeeSchedule admin view is loaded
    Then the list columns should include "corp_type_code"
    And the list columns should include "filing_type_code"
    And the list columns should include "fee"

  Scenario: All list columns are in the declared column_list
    Given the FeeSchedule admin view is loaded
    Then all list columns should be within the configured column_list

  Scenario: Default sort is by corp type code
    Given the FeeSchedule admin view is loaded
    Then the default sort column should be "corp_type_code"

  Scenario: Audit fields are stripped from the create form
    Given the FeeSchedule admin view is loaded
    When the FeeSchedule create form is generated
    Then the audit fields should not be present in the create form

  Scenario: Audit fields are readonly in the edit form
    Given the FeeSchedule admin view is loaded
    When the FeeSchedule edit form is generated
    Then the audit fields should be readonly

  Scenario: Audit fields are populated when a fee schedule is created
    Given the FeeSchedule admin view is loaded
    And a user is logged in as "Joe"
    And the current time is "2024-01-15 10:00:00"
    When a new FeeSchedule record is saved
    Then the created audit fields should be "Joe" and "2024-01-15 10:00:00"

  Scenario: Audit fields are updated when a fee schedule is edited
    Given the FeeSchedule admin view is loaded
    And a user is logged in as "Joe"
    And the current time is "2024-01-15 10:00:00"
    When an existing FeeSchedule record is saved
    Then the updated audit fields should be "Joe" and "2024-01-15 10:00:00"
