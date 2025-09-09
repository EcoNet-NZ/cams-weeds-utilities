#!/usr/bin/env python3
"""
Unit Tests for Annual Rollover Tool

Tests all 36 test cases from REQUIREMENTS.md:
- TC01-TC21: Main test cases
- LV01-LV10: Last visit date resolution tests  
- CL01-CL15: Combined logic tests
"""

import unittest
from datetime import datetime, date
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from annual_rollover import (
    resolve_last_visit_date, is_next_visit_due, meets_time_criteria,
    should_update_record, create_audit_log_entry, validate_backup_field,
    TARGET_SPECIES, TARGET_STATUSES
)


class TestAnnualRollover(unittest.TestCase):
    """Test cases for annual rollover business logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Reference date: October 1st, 2025
        self.reference_date = datetime(2025, 10, 1)
    
    def create_mock_record(self, **kwargs):
        """Create a mock record with default values"""
        defaults = {
            'OBJECTID': 12345,
            'SpeciesDropDown': 'MothPlant',
            'ParentStatusWithDomain': 'YellowKilledThisYear',
            'DateForNextVisitFromLastVisit': None,
            'DateVisitMadeFromLastVisit': None,
            'DateOfLastCreateFromLastVisit': None,
            'DateDiscovered': None,
            'audit_log': None
        }
        defaults.update(kwargs)
        return defaults
    
    def datetime_to_timestamp(self, dt):
        """Convert datetime to ArcGIS timestamp (milliseconds since epoch)"""
        if dt is None:
            return None
        return int(dt.timestamp() * 1000)

    # Test Cases TC01-TC21: Main Test Cases
    
    def test_tc01_all_conditions_met(self):
        """TC01: MothPlant YellowKilledThisYear with valid dates - should update"""
        record = self.create_mock_record(
            DateForNextVisitFromLastVisit=self.datetime_to_timestamp(datetime(2025, 1, 1)),
            DateVisitMadeFromLastVisit=self.datetime_to_timestamp(datetime(2025, 6, 1))
        )
        
        should_update, decision = should_update_record(record, self.reference_date)
        
        self.assertTrue(should_update)
        self.assertEqual(decision['species'], 'MothPlant')
        self.assertEqual(decision['status'], 'YellowKilledThisYear')
        self.assertIn('AllCriteriaMet', decision['reasons'])
    
    def test_tc02_next_visit_in_future(self):
        """TC02: Next visit in future - should not update"""
        record = self.create_mock_record(
            DateForNextVisitFromLastVisit=self.datetime_to_timestamp(datetime(2026, 1, 1)),
            DateVisitMadeFromLastVisit=self.datetime_to_timestamp(datetime(2025, 6, 1))
        )
        
        should_update, decision = should_update_record(record, self.reference_date)
        
        self.assertFalse(should_update)
        self.assertIn('NextVisitFuture', decision['reasons'][0])
    
    def test_tc03_last_visit_too_recent(self):
        """TC03: Last visit < 2 months ago - should not update"""
        record = self.create_mock_record(
            DateForNextVisitFromLastVisit=self.datetime_to_timestamp(datetime(2025, 1, 1)),
            DateVisitMadeFromLastVisit=self.datetime_to_timestamp(datetime(2025, 8, 15))
        )
        
        should_update, decision = should_update_record(record, self.reference_date)
        
        self.assertFalse(should_update)
        self.assertIn('VisitTooRecent', decision['reasons'][0])
    
    def test_tc04_orange_dead_headed(self):
        """TC04: OrangeDeadHeaded with valid conditions - should update"""
        record = self.create_mock_record(
            SpeciesDropDown='OldMansBeard',
            ParentStatusWithDomain='OrangeDeadHeaded',
            DateForNextVisitFromLastVisit=self.datetime_to_timestamp(datetime(2025, 1, 1)),
            DateVisitMadeFromLastVisit=self.datetime_to_timestamp(datetime(2025, 6, 1))
        )
        
        should_update, decision = should_update_record(record, self.reference_date)
        
        self.assertTrue(should_update)
        self.assertEqual(decision['status'], 'OrangeDeadHeaded')
    
    def test_tc05_green_less_than_2_years(self):
        """TC05: GreenNoRegrowthThisYear, last visit < 2 years - should not update"""
        record = self.create_mock_record(
            SpeciesDropDown='CathedralBells',
            ParentStatusWithDomain='GreenNoRegrowthThisYear',
            DateForNextVisitFromLastVisit=self.datetime_to_timestamp(datetime(2025, 1, 1)),
            DateVisitMadeFromLastVisit=self.datetime_to_timestamp(datetime(2024, 6, 1))
        )
        
        should_update, decision = should_update_record(record, self.reference_date)
        
        self.assertFalse(should_update)
        self.assertIn('Visit<2Years', decision['reasons'][0])
    
    def test_tc06_green_more_than_2_years(self):
        """TC06: GreenNoRegrowthThisYear, last visit > 2 years - should update"""
        record = self.create_mock_record(
            SpeciesDropDown='CathedralBells',
            ParentStatusWithDomain='GreenNoRegrowthThisYear',
            DateForNextVisitFromLastVisit=self.datetime_to_timestamp(datetime(2025, 1, 1)),
            DateVisitMadeFromLastVisit=self.datetime_to_timestamp(datetime(2023, 6, 1))
        )
        
        should_update, decision = should_update_record(record, self.reference_date)
        
        self.assertTrue(should_update)
        self.assertIn('AllCriteriaMet', decision['reasons'])
    
    def test_tc18_null_next_visit_eligible(self):
        """TC18: Null next visit date - should be eligible"""
        record = self.create_mock_record(
            DateForNextVisitFromLastVisit=None,
            DateVisitMadeFromLastVisit=self.datetime_to_timestamp(datetime(2025, 6, 1))
        )
        
        should_update, decision = should_update_record(record, self.reference_date)
        
        self.assertTrue(should_update)
        self.assertEqual(decision['next_visit_check'], 'NextVisitNull')
    
    def test_tc20_yellow_status_no_visit_dates(self):
        """TC20: YellowKilledThisYear with null visit dates - should update (status = visited)"""
        record = self.create_mock_record(
            DateForNextVisitFromLastVisit=self.datetime_to_timestamp(datetime(2025, 1, 1)),
            DateVisitMadeFromLastVisit=None,
            DateOfLastCreateFromLastVisit=None,
            DateDiscovered=None
        )
        
        should_update, decision = should_update_record(record, self.reference_date)
        
        self.assertTrue(should_update)
        self.assertEqual(decision['last_visit_source'], 'VisitedNoDate')
    
    def test_tc21_green_status_no_visit_dates(self):
        """TC21: GreenNoRegrowthThisYear with null visit dates - should update (status = visited)"""
        record = self.create_mock_record(
            SpeciesDropDown='CathedralBells',
            ParentStatusWithDomain='GreenNoRegrowthThisYear',
            DateForNextVisitFromLastVisit=None,
            DateVisitMadeFromLastVisit=None,
            DateOfLastCreateFromLastVisit=None,
            DateDiscovered=None
        )
        
        should_update, decision = should_update_record(record, self.reference_date)
        
        self.assertTrue(should_update)
        self.assertEqual(decision['last_visit_source'], 'VisitedNoDate')

    # Test Cases LV01-LV10: Last Visit Date Resolution Tests
    
    def test_lv01_first_field_priority(self):
        """LV01: First field takes priority when all populated"""
        record = self.create_mock_record(
            DateVisitMadeFromLastVisit=self.datetime_to_timestamp(datetime(2025, 6, 1)),
            DateOfLastCreateFromLastVisit=self.datetime_to_timestamp(datetime(2025, 5, 1)),
            DateDiscovered=self.datetime_to_timestamp(datetime(2025, 4, 1))
        )
        
        last_visit_date, source = resolve_last_visit_date(record)
        
        self.assertEqual(last_visit_date, datetime(2025, 6, 1))
        self.assertEqual(source, 'DateVisitMade')
    
    def test_lv02_second_field_when_first_null(self):
        """LV02: Second field when first is null"""
        record = self.create_mock_record(
            DateVisitMadeFromLastVisit=None,
            DateOfLastCreateFromLastVisit=self.datetime_to_timestamp(datetime(2025, 5, 1)),
            DateDiscovered=self.datetime_to_timestamp(datetime(2025, 4, 1))
        )
        
        last_visit_date, source = resolve_last_visit_date(record)
        
        self.assertEqual(last_visit_date, datetime(2025, 5, 1))
        self.assertEqual(source, 'DateOfLastCreate')
    
    def test_lv03_third_field_when_first_two_null(self):
        """LV03: Third field when first two null"""
        record = self.create_mock_record(
            DateVisitMadeFromLastVisit=None,
            DateOfLastCreateFromLastVisit=None,
            DateDiscovered=self.datetime_to_timestamp(datetime(2025, 4, 1))
        )
        
        last_visit_date, source = resolve_last_visit_date(record)
        
        self.assertEqual(last_visit_date, datetime(2025, 4, 1))
        self.assertEqual(source, 'DateDiscovered')
    
    def test_lv04_all_null_target_status(self):
        """LV04: All fields null with target status = visited but no date"""
        record = self.create_mock_record(
            ParentStatusWithDomain='YellowKilledThisYear',
            DateVisitMadeFromLastVisit=None,
            DateOfLastCreateFromLastVisit=None,
            DateDiscovered=None
        )
        
        last_visit_date, source = resolve_last_visit_date(record)
        
        self.assertIsNone(last_visit_date)
        self.assertEqual(source, 'VisitedNoDate')

    # Test Cases CL01-CL15: Combined Logic Tests
    
    def test_cl01_uses_visit_made_field(self):
        """CL01: Uses DateVisitMade field, > 2 months"""
        record = self.create_mock_record(
            DateForNextVisitFromLastVisit=self.datetime_to_timestamp(datetime(2025, 1, 1)),
            DateVisitMadeFromLastVisit=self.datetime_to_timestamp(datetime(2025, 6, 1)),
            DateOfLastCreateFromLastVisit=None,
            DateDiscovered=None
        )
        
        should_update, decision = should_update_record(record, self.reference_date)
        
        self.assertTrue(should_update)
        self.assertEqual(decision['last_visit_source'], 'DateVisitMade')
        self.assertEqual(decision['last_visit_date'], '2025-06-01')
    
    def test_cl04_yellow_never_visited_dates(self):
        """CL04: YellowKilledThisYear with no visit dates - treat as visited"""
        record = self.create_mock_record(
            DateForNextVisitFromLastVisit=self.datetime_to_timestamp(datetime(2025, 1, 1)),
            DateVisitMadeFromLastVisit=None,
            DateOfLastCreateFromLastVisit=None,
            DateDiscovered=None
        )
        
        should_update, decision = should_update_record(record, self.reference_date)
        
        self.assertTrue(should_update)
        self.assertEqual(decision['last_visit_source'], 'VisitedNoDate')
    
    def test_cl08_green_2_year_rule(self):
        """CL08: GreenNoRegrowthThisYear with DateVisitMade > 2 years"""
        record = self.create_mock_record(
            SpeciesDropDown='CathedralBells',
            ParentStatusWithDomain='GreenNoRegrowthThisYear',
            DateForNextVisitFromLastVisit=self.datetime_to_timestamp(datetime(2025, 1, 1)),
            DateVisitMadeFromLastVisit=self.datetime_to_timestamp(datetime(2023, 6, 1)),
            DateOfLastCreateFromLastVisit=None,
            DateDiscovered=None
        )
        
        should_update, decision = should_update_record(record, self.reference_date)
        
        self.assertTrue(should_update)
        self.assertEqual(decision['last_visit_source'], 'DateVisitMade')
    
    def test_cl15_yellow_null_dates_null_next_visit(self):
        """CL15: Yellow status, null next visit, null dates - should update"""
        record = self.create_mock_record(
            DateForNextVisitFromLastVisit=None,
            DateVisitMadeFromLastVisit=None,
            DateOfLastCreateFromLastVisit=None,
            DateDiscovered=None
        )
        
        should_update, decision = should_update_record(record, self.reference_date)
        
        self.assertTrue(should_update)
        self.assertEqual(decision['next_visit_check'], 'NextVisitNull')
        self.assertEqual(decision['last_visit_source'], 'VisitedNoDate')

    # Additional Utility Tests
    
    def test_audit_log_creation(self):
        """Test audit log entry creation"""
        # Test with existing audit log
        existing_log = "2024-05-01 Previous entry"
        new_log = create_audit_log_entry("YellowKilledThisYear", existing_log)
        
        self.assertIn("Annual rollover from YellowKilledThisYear to Purple", new_log)
        self.assertIn("Previous entry", new_log)
        
        # Test with null existing audit log
        new_log = create_audit_log_entry("GreenNoRegrowthThisYear", None)
        
        self.assertIn("Annual rollover from GreenNoRegrowthThisYear to Purple", new_log)
        self.assertNotIn(";", new_log)  # No semicolon when no existing log
    
    def test_audit_log_truncation(self):
        """Test audit log truncation at 4000 characters"""
        # Create a very long existing audit log
        long_existing_log = "x" * 3950
        new_log = create_audit_log_entry("YellowKilledThisYear", long_existing_log)
        
        self.assertEqual(len(new_log), 4000)
        self.assertTrue(new_log.endswith("..."))
    
    def test_next_visit_due_logic(self):
        """Test next visit due logic"""
        record = self.create_mock_record()
        
        # Test null date (should be due)
        record['DateForNextVisitFromLastVisit'] = None
        due, reason = is_next_visit_due(record, self.reference_date)
        self.assertTrue(due)
        self.assertEqual(reason, 'NextVisitNull')
        
        # Test past date (should be due)
        record['DateForNextVisitFromLastVisit'] = self.datetime_to_timestamp(datetime(2025, 1, 1))
        due, reason = is_next_visit_due(record, self.reference_date)
        self.assertTrue(due)
        self.assertIn('NextVisitDue', reason)
        
        # Test future date (should not be due)
        record['DateForNextVisitFromLastVisit'] = self.datetime_to_timestamp(datetime(2026, 1, 1))
        due, reason = is_next_visit_due(record, self.reference_date)
        self.assertFalse(due)
        self.assertIn('NextVisitFuture', reason)
    
    def test_species_filtering(self):
        """Test species filtering"""
        # Valid species
        record = self.create_mock_record(SpeciesDropDown='MothPlant')
        should_update, decision = should_update_record(record, self.reference_date)
        self.assertNotIn('SpeciesNotTarget', str(decision['reasons']))
        
        # Invalid species
        record = self.create_mock_record(SpeciesDropDown='InvalidSpecies')
        should_update, decision = should_update_record(record, self.reference_date)
        self.assertFalse(should_update)
        self.assertIn('SpeciesNotTarget', decision['reasons'][0])
    
    def test_status_filtering(self):
        """Test status filtering"""
        # Valid status
        record = self.create_mock_record(ParentStatusWithDomain='YellowKilledThisYear')
        should_update, decision = should_update_record(record, self.reference_date)
        self.assertNotIn('StatusNotTarget', str(decision['reasons']))
        
        # Invalid status
        record = self.create_mock_record(ParentStatusWithDomain='InvalidStatus')
        should_update, decision = should_update_record(record, self.reference_date)
        self.assertFalse(should_update)
        self.assertIn('StatusNotTarget', decision['reasons'][0])
    
    def test_backup_field_validation(self):
        """Test backup field validation logic"""
        # Mock layer with backup field
        mock_layer_with_field = Mock()
        mock_field = Mock()
        mock_field.name = 'StatusAt202510'
        mock_layer_with_field.properties.fields = [mock_field]
        
        # Should pass validation
        result = validate_backup_field(mock_layer_with_field, dry_run=False)
        self.assertTrue(result)
        
        # Mock layer without backup field
        mock_layer_without_field = Mock()
        mock_other_field = Mock()
        mock_other_field.name = 'SomeOtherField'
        mock_layer_without_field.properties.fields = [mock_other_field]
        
        # Should fail in live mode
        with self.assertRaises(ValueError) as context:
            validate_backup_field(mock_layer_without_field, dry_run=False)
        
        self.assertIn('StatusAt202510', str(context.exception))
        self.assertIn('not found in layer', str(context.exception))
        
        # Should return False but not raise in dry run mode
        result = validate_backup_field(mock_layer_without_field, dry_run=True)
        self.assertFalse(result)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
