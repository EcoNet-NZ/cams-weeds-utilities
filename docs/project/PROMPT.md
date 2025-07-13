# CAMS Spatial Query Optimization - Business Requirements

## Business Context
CAMS (Content and Asset Management System) operates as an ArcGIS Online dashboard tracking weed management across regions and districts. The system currently manages 50,000 weed location records with 20,000 new records added annually.

## Performance Problem
Dashboard users experience slow response times when filtering by region or district due to real-time spatial queries executed for each filter operation. With growing data volumes, this performance issue impacts operational efficiency.

## Business Solution
Implement automated daily preprocessing to pre-calculate region and district assignments for all weed locations, eliminating real-time spatial lookups during dashboard interactions.

## Business Requirements

### Functional Requirements
- **Daily Processing**: Automated spatial assignment of region/district codes to weed locations
- **Incremental Updates**: Process only changed records (new weeds, moved locations, updated boundaries)
- **Status Visibility**: Dashboard displays last update timestamp and processing status
- **Version Control**: Verify dashboard and processing utility use identical area layer versions
- **Multi-Environment**: Support separate development and production deployments

### Data Requirements
- **Region Assignment**: 2-character region codes stored in WeedLocations.RegionCode
- **District Assignment**: 5-character district codes stored in WeedLocations.DistrictCode
- **Change Tracking**: Utilize existing EditDate_1 field for detecting modified weed records
- **Layer Monitoring**: Track region/district layer updates via metadata timestamps

### Operational Requirements
- **Schedule**: Process runs nightly at 9:05pm NZT
- **Reliability**: No metadata updates on processing failures
- **Scalability**: Design accommodates future additional area layers
- **Environment Separation**: Distinct dev/prod configurations with appropriate naming

## Technical Specifications

### Layer Identifiers
- **Region Layer**: 7759fbaecd4649dea39c4ac2b07fc4ab (consistent across environments)
- **District Layer**: c8f6ba6b968c4d31beddfb69abfe3df0 (consistent across environments)

### Metadata Table Requirements
- **Production Name**: "Weeds Area Metadata"
- **Development Name**: "XXX Weeds Area Metadata DEV"
- **Content**: Process timestamps, layer IDs, layer versions, status, record counts
- **Access**: Dashboard consumption for status indicators

### Infrastructure Requirements
- **Automation**: GitHub Actions with environment-specific secrets
- **Authentication**: GitHub Repository Secrets with _DEV suffix for development, _PROD/no suffix for production
- **Change Detection**: Monitor layer "Date updated" metadata field
- **Error Handling**: Fail-safe processing with comprehensive status tracking

## Success Criteria
- Eliminated real-time spatial queries during dashboard filtering
- Sub-second response times for region/district filter operations
- Reliable daily processing with status visibility
- Maintained data accuracy with version synchronization
- Scalable foundation for additional area layers

## Future Considerations
System design must accommodate expansion to include additional area layers beyond current region and district requirements.