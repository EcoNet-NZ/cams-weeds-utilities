#!/usr/bin/env python3
"""
Test script for Field Maps Web Map Lister

This script demonstrates that the tool works correctly and provides
examples of usage without requiring actual credentials.
"""

def test_imports():
    """Test that all imports work correctly."""
    print("Testing imports...")
    
    try:
        from field_maps_webmap_lister import FieldMapsWebMapAnalyzer
        print("✅ FieldMapsWebMapAnalyzer import successful")
    except ImportError as e:
        print(f"❌ Failed to import FieldMapsWebMapAnalyzer: {e}")
        return False
    
    try:
        from field_maps_webmap_lister import export_field_maps_spreadsheet_report
        print("✅ Spreadsheet export function import successful")
    except ImportError as e:
        print(f"❌ Failed to import spreadsheet export function: {e}")
        return False
    
    try:
        from arcgis.gis import GIS
        print("✅ ArcGIS Python API import successful")
    except ImportError as e:
        print(f"❌ Failed to import ArcGIS Python API: {e}")
        return False
    
    return True


def test_analyzer_initialization():
    """Test that the analyzer can be initialized."""
    print("\nTesting analyzer initialization...")
    
    try:
        from arcgis.gis import GIS
        from field_maps_webmap_lister import FieldMapsWebMapAnalyzer
        
        # Create a GIS object (without authentication for testing)
        gis = GIS()
        print("✅ GIS object created (anonymous)")
        
        # Initialize analyzer
        analyzer = FieldMapsWebMapAnalyzer(gis)
        print("✅ FieldMapsWebMapAnalyzer initialized successfully")
        
        # Test that the analyzer has expected attributes
        assert hasattr(analyzer, 'gis')
        assert hasattr(analyzer, 'field_maps_webmaps')
        assert hasattr(analyzer, 'analyze_webmap_for_field_maps')
        assert hasattr(analyzer, 'find_field_maps_webmaps')
        print("✅ Analyzer has all expected methods and attributes")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize analyzer: {e}")
        return False


def test_field_maps_detection_logic():
    """Test the Field Maps detection logic with mock data."""
    print("\nTesting Field Maps detection logic...")
    
    try:
        # Mock web map item data structure
        class MockSharingGroupManager:
            def __init__(self):
                pass
            
            def list(self):
                return []
        
        class MockSharingManager:
            def __init__(self):
                self.everyone = False
                self.org = True
                self.groups = MockSharingGroupManager()
        
        class MockWebMapItem:
            def __init__(self, title, tags, has_feature_services=False):
                self.id = "mock_id_123"
                self.title = title
                self.owner = "test_user"
                self.tags = tags
                self.created = "2024-01-01T00:00:00Z"
                self.modified = "2024-01-02T00:00:00Z"
                self._has_feature_services = has_feature_services
                # Mock sharing information using the new SharingManager structure
                self.sharing = MockSharingManager()
            
            def get_data(self):
                operational_layers = []
                if self._has_feature_services:
                    operational_layers.append({
                        'url': 'https://services.arcgis.com/test/arcgis/rest/services/TestLayer/FeatureServer/0',
                        'itemId': 'test_layer_id'
                    })
                return {
                    'operationalLayers': operational_layers
                }
        
        # Test cases
        test_cases = [
            {
                'name': 'Field Maps tagged web map',
                'item': MockWebMapItem("Mobile Survey Map", ["field maps", "mobile"], False),
                'expected': True,
                'reason': 'Has field maps tag'
            },
            {
                'name': 'Web map with feature services',
                'item': MockWebMapItem("Data Collection Map", ["survey"], True),
                'expected': True,
                'reason': 'Has feature service layers'
            },
            {
                'name': 'Basic reference map',
                'item': MockWebMapItem("Reference Map", ["basemap"], False),
                'expected': False,
                'reason': 'No Field Maps indicators'
            },
            {
                'name': 'Mobile tagged map',
                'item': MockWebMapItem("Mobile Map", ["mobile", "offline"], False),
                'expected': True,
                'reason': 'Has mobile/offline tags'
            }
        ]
        
        # Mock analyzer with minimal GIS
        class MockGIS:
            def __init__(self):
                self.content = MockContent()
        
        class MockContent:
            def get(self, item_id):
                # Return None for item lookups since we're testing mock data
                return None
        
        from field_maps_webmap_lister import FieldMapsWebMapAnalyzer
        
        gis = MockGIS()
        analyzer = FieldMapsWebMapAnalyzer(gis)
        
        # Test each case
        passed = 0
        for case in test_cases:
            try:
                # Run the full analysis
                analysis = analyzer.analyze_webmap_for_field_maps(case['item'])
                
                # Check if detection worked as expected based on the full analysis result
                detected_as_field_maps = analysis.get('is_field_maps_enabled', False)
                
                if detected_as_field_maps == case['expected']:
                    print(f"✅ {case['name']}: Correctly detected ({case['reason']})")
                    passed += 1
                else:
                    print(f"❌ {case['name']}: Detection failed")
                    print(f"    Expected: {case['expected']}, Got: {detected_as_field_maps}")
                    print(f"    Indicators: {analysis.get('field_maps_indicators', [])}")
                    
            except Exception as e:
                print(f"❌ {case['name']}: Exception occurred - {str(e)}")
                # Don't count as passed if there's an exception
        
        print(f"\nTag detection tests: {passed}/{len(test_cases)} passed")
        return passed == len(test_cases)
        
    except Exception as e:
        print(f"❌ Failed to test detection logic: {e}")
        return False


def main():
    """Run all tests."""
    print("Field Maps Web Map Lister - Test Suite")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_analyzer_initialization, 
        test_field_maps_detection_logic
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The Field Maps Web Map Lister is working correctly.")
        print("\nTo use the tool:")
        print("1. Set environment variables: ARCGIS_USERNAME, ARCGIS_PASSWORD")
        print("2. Run: python field_maps_webmap_lister.py")
        print("3. The tool will generate JSON and Excel spreadsheet reports of Field Maps-enabled web maps")
    else:
        print("❌ Some tests failed. Please check the implementation.")
    
    return passed == total


if __name__ == "__main__":
    main() 