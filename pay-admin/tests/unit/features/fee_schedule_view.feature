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
