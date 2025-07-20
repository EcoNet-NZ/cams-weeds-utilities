#!/usr/bin/env python3
"""
Field Maps Web Map Lister

This script identifies and lists ArcGIS Online Web Maps that are configured 
for use with ArcGIS Field Maps. It checks for Field Maps-specific settings,
offline capabilities, and appropriate layer configurations.

Requirements:
- ArcGIS Python API
- Valid ArcGIS Online credentials

Author: CAMS Utilities
Date: 2024
"""

import json
import os
import warnings
from typing import List, Dict, Any
from arcgis.gis import GIS
import pandas as pd




class FieldMapsWebMapAnalyzer:
    """Analyzes web maps to identify those configured for Field Maps use."""
    
    def __init__(self, gis: GIS):
        """
        Initialize the analyzer with a GIS connection.
        
        Args:
            gis: Authenticated GIS object
        """
        self.gis = gis
        self.field_maps_webmaps = []
        
    def analyze_webmap_for_field_maps(self, webmap_item) -> Dict[str, Any]:
        """
        Analyze a web map item to determine Field Maps compatibility.
        
        Args:
            webmap_item: Web map item to analyze
            
        Returns:
            Dictionary with analysis results
        """
        # Get sharing information
        sharing_info = self._get_sharing_info(webmap_item)
        
        # Initialize analysis results
        analysis = {
            'is_field_maps_enabled': False,
            'field_maps_indicators': [],
            'total_layers': 0,
            'editable_layers': 0,
            'sync_enabled_layers': 0,
            'layer_details': [],
            'title': webmap_item.title,
            'id': webmap_item.id,
            'owner': webmap_item.owner,
            'sharing': sharing_info,
            'created': webmap_item.created,
            'modified': webmap_item.modified
        }
        
        try:
            # Get web map definition to analyze layers
            webmap_data = webmap_item.get_data()
            operational_layers = webmap_data.get('operationalLayers', [])
            
            # Count total layers
            analysis['total_layers'] = len(operational_layers)
            
            # Check each layer for editability and Field Maps compatibility
            editable_count = 0
            has_feature_services = False
            
            for layer in operational_layers:
                try:
                    layer_url = layer.get('url', '')
                    
                    # Check if it's a feature service (potential for editing/sync)
                    if 'FeatureServer' in layer_url:
                        has_feature_services = True
                        
                        # Try to get the actual layer to check capabilities
                        try:
                            layer_item = self.gis.content.get(layer.get('itemId', ''))
                            if layer_item:
                                # Check if the layer supports editing
                                layer_obj = layer_item.layers[0] if layer_item.layers else None
                                if layer_obj and hasattr(layer_obj, 'properties'):
                                    capabilities = getattr(layer_obj.properties, 'capabilities', '')
                                    if any(cap in str(capabilities) for cap in ['Create', 'Update', 'Delete', 'Edit']):
                                        editable_count += 1
                        except Exception:
                            # If we can't access the layer details, assume potential editability for FeatureServer
                            editable_count += 1
                        
                except Exception as e:
                    print(f"Warning: Could not analyze layer in {webmap_item.title}: {str(e)}")
                    
            analysis['editable_layers'] = editable_count
            
            if has_feature_services:
                analysis['field_maps_indicators'].append('Has feature service layers')
                analysis['is_field_maps_enabled'] = True
            
            # Check tags for Field Maps indicators
            field_maps_tags = ['field maps', 'fieldmaps', 'mobile', 'offline', 'data collection']
            webmap_tags_lower = [tag.lower() for tag in webmap_item.tags]
            
            for tag in field_maps_tags:
                if tag in webmap_tags_lower:
                    analysis['field_maps_indicators'].append(f'Has relevant tag: {tag}')
                    analysis['is_field_maps_enabled'] = True
                    
            # Check web map properties for Field Maps configuration
            try:
                # Look for offline properties in web map definition
                if 'offline' in str(webmap_data).lower():
                    analysis['field_maps_indicators'].append('Contains offline configuration')
                    analysis['is_field_maps_enabled'] = True
                    
                # Check for sync capabilities in operational layers
                for op_layer in operational_layers:
                    if 'sync' in str(op_layer).lower() or 'offline' in str(op_layer).lower():
                        analysis['field_maps_indicators'].append('Has operational layers with sync capabilities')
                        analysis['is_field_maps_enabled'] = True
                        break
                        
            except Exception as e:
                print(f"Warning: Could not analyze web map definition for {webmap_item.title}: {str(e)}")
            
            # Determine overall Field Maps enablement
            if analysis['is_field_maps_enabled'] or analysis['editable_layers'] > 0:
                analysis['is_field_maps_enabled'] = True
                
        except Exception as e:
            print(f"Error analyzing web map {webmap_item.title}: {str(e)}")
            analysis['error'] = str(e)
            
        return analysis
    
    def _get_sharing_info(self, webmap_item) -> str:
        """
        Get sharing information for a web map item.
        
        Args:
            webmap_item: Web map item to analyze
            
        Returns:
            String describing how the item is shared
        """
        try:
            # Get sharing details using the new Item.sharing property
            sharing = webmap_item.sharing
            
            # Check if shared with everyone (public)
            if hasattr(sharing, 'everyone') and sharing.everyone:
                return "Public"
            
            # Check if shared with organization
            elif hasattr(sharing, 'org') and sharing.org:
                return "Organisation"
            
            # Check if shared with specific groups
            elif hasattr(sharing, 'groups') and sharing.groups:
                groups = sharing.groups.list() if hasattr(sharing.groups, 'list') else []
                if len(groups) == 1:
                    # Groups are Group objects, access title attribute
                    return getattr(groups[0], 'title', str(groups[0]))
                elif len(groups) <= 3:
                    return ", ".join([getattr(group, 'title', str(group)) for group in groups])
                else:
                    group_titles = [getattr(group, 'title', str(group)) for group in groups[:2]]
                    return f"{group_titles[0]}, {group_titles[1]}, +{len(groups)-2} more"
            
            # Not shared or private
            else:
                return "Private"
                
        except Exception as e:
            print(f"Warning: Could not determine sharing for {webmap_item.title}: {str(e)}")
            return "Unknown"
    
    def find_field_maps_webmaps(self, search_query: str = "*", max_items: int = 10000) -> List[Dict[str, Any]]:
        """
        Search for and analyze web maps for Field Maps compatibility.
        
        Args:
            search_query: Search query for web maps (default: all web maps)
            max_items: Maximum number of items to analyze
            
        Returns:
            List of analysis results for Field Maps-enabled web maps
        """
        print(f"Searching for web maps with query: '{search_query}' (max: {max_items})")
        
        # Search for web maps
        webmap_items = self.gis.content.search(
            query=search_query,
            item_type="Web Map",
            max_items=max_items,
            sort_field="modified",
            sort_order="desc"
        )
        
        print(f"Found {len(webmap_items)} web maps to analyze")
        
        field_maps_webmaps = []
        
        for i, webmap_item in enumerate(webmap_items, 1):
            print(f"Analyzing {i}/{len(webmap_items)}: {webmap_item.title}")
            
            analysis = self.analyze_webmap_for_field_maps(webmap_item)
            
            # Only include if it shows Field Maps indicators
            if analysis['is_field_maps_enabled']:
                field_maps_webmaps.append(analysis)
                print(f"  ✓ Field Maps enabled: {', '.join(analysis['field_maps_indicators'])}")
            else:
                print(f"  ✗ No Field Maps indicators found")
                
        return field_maps_webmaps
    
    def export_results(self, results: List[Dict[str, Any]], output_file: str = "field_maps_webmaps.json"):
        """
        Export analysis results to JSON file.
        
        Args:
            results: Analysis results to export
            output_file: Output file path
        """
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results exported to {output_file}")
    
    def export_to_spreadsheet(self, results: List[Dict[str, Any]], output_file: str = "field_maps_webmaps.xlsx"):
        """
        Export analysis results to Excel spreadsheet.
        
        Args:
            results: Analysis results to export
            output_file: Output Excel file path
        """
        # Sort results by title (layer name)
        sorted_results = sorted(results, key=lambda x: x['title'].lower())
        
        # Prepare data for DataFrame
        spreadsheet_data = []
        for result in sorted_results:
            # Format indicators as comma-separated string
            indicators = '; '.join(result.get('field_maps_indicators', []))
            if not indicators:
                indicators = 'No specific indicators found'
            
            # Format created and modified dates
            try:
                from datetime import datetime
                created = datetime.fromisoformat(str(result['created']).replace('Z', '+00:00')).strftime('%Y-%m-%d')
                modified = datetime.fromisoformat(str(result['modified']).replace('Z', '+00:00')).strftime('%Y-%m-%d')
            except:
                created = str(result['created'])[:10] if result['created'] else 'Unknown'
                modified = str(result['modified'])[:10] if result['modified'] else 'Unknown'
            
            # Create row data
            row = {
                'Web Map Name': result['title'],
                'Item ID': result['id'],
                'Owner': result['owner'],
                'Sharing': result.get('sharing', 'Unknown'),
                'Total Layers': result.get('total_layers', 0),
                'Editable Layers': result.get('editable_layers', 0),
                'Sync Enabled Layers': result.get('sync_enabled_layers', 0),
                'Field Maps Indicators': indicators,
                'Created': created,
                'Modified': modified,
                'Settings URL': f"https://www.arcgis.com/home/item.html?id={result['id']}#settings"
            }
            spreadsheet_data.append(row)
        
        # Create DataFrame and export
        df = pd.DataFrame(spreadsheet_data)
        
        # Export to Excel with formatting
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Field Maps Web Maps', index=False)
            
            # Get the workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Field Maps Web Maps']
            
            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        print(f"Spreadsheet exported to {output_file}")
        print(f"Open in Excel: {os.path.abspath(output_file)}")
        
        # Also export as CSV for broader compatibility
        csv_file = output_file.replace('.xlsx', '.csv')
        df.to_csv(csv_file, index=False)
        print(f"CSV version exported to {csv_file}")
    
    def export_html_table(self, results: List[Dict[str, Any]], output_file: str = "field_maps_webmaps.html", portal_url: str = None):
        """
        Export analysis results to HTML table with links to map settings pages.
        
        Args:
            results: Analysis results to export
            output_file: Output HTML file path
            portal_url: Portal URL (e.g., https://econethub.maps.arcgis.com)
        """
        # Sort results by title (layer name)
        sorted_results = sorted(results, key=lambda x: x['title'].lower())
        
        # Determine portal URL
        if portal_url is None:
            # Try to get portal URL from GIS connection
            try:
                portal_url = self.gis.properties.portalHostname
                if not portal_url.startswith('http'):
                    portal_url = f"https://{portal_url}"
            except:
                portal_url = "https://www.arcgis.com"
        
        # Ensure portal URL doesn't end with slash
        portal_url = portal_url.rstrip('/')
        
        # Generate HTML content
        html_content = self._generate_html_table(sorted_results, portal_url)
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"HTML table exported to {output_file}")
        print(f"Open in browser: file://{os.path.abspath(output_file)}")
    
    def _generate_html_table(self, results: List[Dict[str, Any]], portal_url: str) -> str:
        """
        Generate HTML content for the Field Maps web maps table.
        
        Args:
            results: Analysis results
            portal_url: Portal URL for creating links
            
        Returns:
            HTML content as string
        """
        html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Field Maps Web Maps Inventory</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #0079c1 0%, #00a8cc 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 2.2em;
            font-weight: 300;
        }}
        
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 1.1em;
        }}
        
        .summary {{
            background-color: #f8f9fa;
            padding: 20px 30px;
            border-bottom: 1px solid #e9ecef;
        }}
        
        .summary-stats {{
            display: flex;
            justify-content: space-around;
            text-align: center;
        }}
        
        .stat-item {{
            flex: 1;
        }}
        
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #0079c1;
            display: block;
        }}
        
        .stat-label {{
            font-size: 0.9em;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .table-container {{
            padding: 20px 30px 30px;
            overflow-x: auto;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        
        th {{
            background-color: #0079c1;
            color: white;
            padding: 15px 12px;
            text-align: left;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.85em;
            letter-spacing: 0.5px;
        }}
        
        td {{
            padding: 12px;
            border-bottom: 1px solid #e9ecef;
            vertical-align: top;
        }}
        
        tr:hover {{
            background-color: #f8f9fa;
        }}
        
        .web-map-title {{
            font-weight: 600;
            color: #0079c1;
        }}
        
        .web-map-link {{
            color: #0079c1;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }}
        
        .web-map-link:hover {{
            color: #005a87;
            text-decoration: underline;
        }}
        
        .external-link-icon {{
            width: 12px;
            height: 12px;
            opacity: 0.7;
        }}
        
        .item-id {{
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            color: #6c757d;
            background-color: #f8f9fa;
            padding: 2px 6px;
            border-radius: 3px;
            display: inline-block;
            margin-top: 5px;
        }}
        
        .owner {{
            color: #495057;
            font-weight: 500;
        }}
        
        .indicators {{
            font-size: 0.85em;
            color: #6c757d;
        }}
        
        .indicator-tag {{
            background-color: #e7f3ff;
            color: #0079c1;
            padding: 2px 8px;
            border-radius: 12px;
            display: inline-block;
            margin: 2px 4px 2px 0;
            font-size: 0.8em;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
            text-align: center;
            font-size: 0.85em;
        }}
        
        .stats-item {{
            background-color: white;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #e9ecef;
        }}
        
        .stats-value {{
            font-size: 1.4em;
            font-weight: bold;
            color: #0079c1;
            display: block;
        }}
        
        .stats-label {{
            color: #6c757d;
            margin-top: 5px;
        }}
        
        .footer {{
            background-color: #f8f9fa;
            padding: 20px 30px;
            border-top: 1px solid #e9ecef;
            text-align: center;
            color: #6c757d;
            font-size: 0.9em;
        }}
        
        @media (max-width: 768px) {{
            .summary-stats {{
                flex-direction: column;
                gap: 20px;
            }}
            
            .table-container {{
                padding: 10px;
            }}
            
            th, td {{
                padding: 8px;
                font-size: 0.9em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🗺️ Field Maps Web Maps Inventory</h1>
            <p>ArcGIS Field Maps-Enabled Web Maps Analysis Report</p>
        </div>
        
        <div class="summary">
            <div class="summary-stats">
                <div class="stat-item">
                    <span class="stat-number">{total_count}</span>
                    <span class="stat-label">Total Field Maps Web Maps</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number">{offline_count}</span>
                    <span class="stat-label">With Offline Areas</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number">{editable_count}</span>
                    <span class="stat-label">With Editable Layers</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number">{unique_owners}</span>
                    <span class="stat-label">Unique Owners</span>
                </div>
            </div>
        </div>
        
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Web Map Name</th>
                        <th>Owner</th>
                        <th>Field Maps Indicators</th>
                        <th>Statistics</th>
                        <th>Last Modified</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>Generated by CAMS Field Maps Web Map Lister • {timestamp}</p>
            <p>Total of {total_count} Field Maps-enabled web maps found across your organization</p>
        </div>
    </div>
</body>
</html>"""

        # Calculate summary statistics
        total_count = len(results)
        offline_count = sum(1 for r in results if r.get('is_field_maps_enabled', False))
        editable_count = sum(1 for r in results if r.get('editable_layers', 0) > 0)
        unique_owners = len(set(r['owner'] for r in results))
        
        # Generate table rows
        table_rows = []
        for result in results:
            # Create settings page URL
            settings_url = f"{portal_url}/home/item.html?id={result['id']}#settings"
            
            # Format indicators as tags
            indicators_html = ""
            for indicator in result.get('field_maps_indicators', []):
                indicators_html += f'<span class="indicator-tag">{indicator}</span>'
            
            # Format statistics
            stats_html = f"""
                <div class="stats-grid">
                    <div class="stats-item">
                        <span class="stats-value">{result.get('total_layers', 0)}</span>
                        <span class="stats-label">Total Layers</span>
                    </div>
                    <div class="stats-item">
                        <span class="stats-value">{result.get('editable_layers', 0)}</span>
                        <span class="stats-label">Editable</span>
                    </div>
                    <div class="stats-item">
                        <span class="stats-value">{result.get('sync_enabled_layers', 0)}</span>
                        <span class="stats-label">Sync Enabled</span>
                    </div>
                </div>
            """
            
            # Format modified date
            try:
                from datetime import datetime
                modified_date = datetime.fromisoformat(str(result['modified']).replace('Z', '+00:00'))
                formatted_date = modified_date.strftime('%Y-%m-%d')
            except:
                formatted_date = str(result['modified'])[:10] if result['modified'] else 'Unknown'
            
            row_html = f"""
                <tr>
                    <td>
                        <div class="web-map-title">
                            <a href="{settings_url}" target="_blank" class="web-map-link">
                                {result['title']}
                                <svg class="external-link-icon" fill="currentColor" viewBox="0 0 20 20">
                                    <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z"></path>
                                    <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-1a1 1 0 10-2 0v1H5V7h1a1 1 0 000-2H5z"></path>
                                </svg>
                            </a>
                        </div>
                        <div class="item-id">{result['id']}</div>
                    </td>
                    <td>
                        <span class="owner">{result['owner']}</span>
                    </td>
                    <td>
                        <div class="indicators">
                            {indicators_html}
                        </div>
                    </td>
                    <td>
                        {stats_html}
                    </td>
                    <td>{formatted_date}</td>
                </tr>
            """
            table_rows.append(row_html)
        
        # Get current timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Format the complete HTML
        formatted_html = html_template.format(
            total_count=total_count,
            offline_count=offline_count,
            editable_count=editable_count,
            unique_owners=unique_owners,
            table_rows=''.join(table_rows),
            timestamp=timestamp
        )
        
        return formatted_html
    
    def print_summary(self, results: List[Dict[str, Any]]):
        """
        Print a summary of Field Maps-enabled web maps.
        
        Args:
            results: Analysis results to summarize
        """
        print(f"\n{'='*60}")
        print(f"FIELD MAPS WEB MAPS SUMMARY")
        print(f"{'='*60}")
        print(f"Total Field Maps-enabled web maps found: {len(results)}")
        
        if not results:
            print("No Field Maps-enabled web maps found.")
            return
            
        print(f"\n{'Title':<40} {'Owner':<15} {'Total Layers':<12} {'Editable Layers'}")
        print(f"{'-'*40} {'-'*15} {'-'*12} {'-'*15}")
        
        for result in results:
            title = result['title'][:37] + "..." if len(result['title']) > 40 else result['title']
            owner = result['owner'][:12] + "..." if len(result['owner']) > 15 else result['owner']
            total_layers = result.get('total_layers', 0)
            editable_layers = result.get('editable_layers', 0)
            
            print(f"{title:<40} {owner:<15} {total_layers:<12} {editable_layers}")
            
        print(f"\n{'DETAILED ANALYSIS'}")
        print(f"{'-'*60}")
        
        for result in results:
            print(f"\n🗺️  {result['title']}")
            print(f"   ID: {result['id']}")
            print(f"   Owner: {result['owner']}")
            print(f"   Created: {result['created']}")
            print(f"   Modified: {result['modified']}")
            print(f"   Total Layers: {result.get('total_layers', 0)}")
            print(f"   Editable Layers: {result.get('editable_layers', 0)}")
            print(f"   Sync Enabled Layers: {result.get('sync_enabled_layers', 0)}")
            print(f"   Field Maps Indicators:")
            for indicator in result.get('field_maps_indicators', []):
                print(f"     • {indicator}")
            if not result.get('field_maps_indicators', []):
                print(f"     • No specific indicators found")


def export_field_maps_spreadsheet_report(gis, search_query="*", max_items=10000):
    """
    Generate a spreadsheet report of Field Maps web maps with sharing information.
    
    Args:
        gis: Authenticated GIS object
        search_query: Search query for web maps
        max_items: Maximum number of web maps to analyze
    """
    print(f"=== Generating Field Maps Spreadsheet Report ===")
    
    try:
        # Initialize analyzer
        analyzer = FieldMapsWebMapAnalyzer(gis)
        
        # Find Field Maps web maps
        results = analyzer.find_field_maps_webmaps(search_query=search_query, max_items=max_items)
        
        if not results:
            print("No Field Maps-enabled web maps found.")
            return
        
        # Export to spreadsheet
        output_file = "field_maps_report.xlsx"
        analyzer.export_to_spreadsheet(results, output_file=output_file)
        
        print(f"\n✅ Spreadsheet report generated successfully!")
        print(f"📁 Report saved as: {output_file}")
        print(f"📊 Open in Excel to view the detailed analysis")
        
        # Print quick summary
        print(f"\n📊 Report Summary:")
        print(f"  • Total Field Maps web maps: {len(results)}")
        print(f"  • With editable layers: {sum(1 for r in results if r.get('editable_layers', 0) > 0)}")
        print(f"  • Unique owners: {len(set(r['owner'] for r in results))}")
        print(f"  • Sharing breakdown:")
        sharing_counts = {}
        for r in results:
            sharing = r.get('sharing', 'Unknown')
            sharing_counts[sharing] = sharing_counts.get(sharing, 0) + 1
        for sharing_type, count in sharing_counts.items():
            print(f"    - {sharing_type}: {count}")
        
    except Exception as e:
        print(f"Error generating spreadsheet report: {str(e)}")


def main():
    """
    Main execution function.
    
    Environment variables:
    - ARCGIS_USERNAME: ArcGIS username (required)
    - ARCGIS_PASSWORD: ArcGIS password (required)  
    - ARCGIS_PORTAL_URL: Portal URL (default: https://www.arcgis.com)
         - MAX_WEBMAPS: Maximum number of web maps to analyze (default: 10000)
    """
    # Load credentials from environment or config
    username = os.getenv('ARCGIS_USERNAME')
    password = os.getenv('ARCGIS_PASSWORD')
    portal_url = os.getenv('ARCGIS_PORTAL_URL', 'https://www.arcgis.com')
    
    if not username or not password:
        print("Error: Please set ARCGIS_USERNAME and ARCGIS_PASSWORD environment variables")
        print("Optional: Set MAX_WEBMAPS to limit the number of web maps analyzed (default: 10000)")
        return
    
    try:
        # Connect to ArcGIS Online
        print(f"Connecting to {portal_url}...")
        gis = GIS(portal_url, username, password)
        print(f"Connected as: {gis.properties.user.username}")
        
        # Initialize analyzer
        analyzer = FieldMapsWebMapAnalyzer(gis)
        
        # Search for Field Maps web maps
        # You can modify the search query to be more specific:
        # - "tags:field maps" - search for web maps tagged with "field maps"
        # - "owner:your_username" - search your own web maps
        # - "title:mobile" - search for web maps with "mobile" in title
        search_query = "*"  # Search all web maps
        
        # Get max_items from environment variable or use default
        max_items = int(os.getenv('MAX_WEBMAPS', '10000'))
        print(f"Will analyze up to {max_items} web maps (set MAX_WEBMAPS env var to change)")
        
        results = analyzer.find_field_maps_webmaps(search_query=search_query, max_items=max_items)
        
        # Display results
        analyzer.print_summary(results)
        
        # Export to JSON
        analyzer.export_results(results)
        
        # Export to spreadsheet
        analyzer.export_to_spreadsheet(results)
        
        print(f"\n✅ Analysis complete! Found {len(results)} Field Maps-enabled web maps.")
        print(f"📁 Outputs generated:")
        print(f"  • JSON: field_maps_webmaps.json")
        print(f"  • Excel: field_maps_webmaps.xlsx")
        print(f"  • CSV: field_maps_webmaps.csv")
        
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main() 