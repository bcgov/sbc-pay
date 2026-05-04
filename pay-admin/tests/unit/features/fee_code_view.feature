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
